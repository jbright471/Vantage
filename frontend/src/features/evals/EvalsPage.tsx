import { useEffect, useState, type FormEvent } from "react";

import {
  createEvalCase,
  createEvalSuite,
  executeEvalRun,
  fetchEvalSuites,
  queueEvalAttempt,
  type EvalAttemptRecord,
  type EvalSuiteRecord,
  type ModelRecord,
  type RunRecord,
} from "../../api/client";

type EvalsPageProps = {
  models?: ModelRecord[];
  runs?: RunRecord[];
};

type PlacementOption = {
  key: string;
  model_name: string;
  node_id: string;
};

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Pending timestamp";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.valueOf())) {
    return value;
  }

  return timestamp.toLocaleString();
}

function dedupeRuns(runs: RunRecord[]): RunRecord[] {
  const seen = new Set<string>();
  return runs.filter((run) => {
    if (seen.has(run.run_id)) {
      return false;
    }
    seen.add(run.run_id);
    return true;
  });
}

export function EvalsPage({ models = [], runs = [] }: EvalsPageProps) {
  const [suites, setSuites] = useState<EvalSuiteRecord[]>([]);
  const [requestState, setRequestState] = useState<"loading" | "idle" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [suiteForm, setSuiteForm] = useState({ name: "", description: "" });
  const [caseForm, setCaseForm] = useState({ suite_id: "", name: "", prompt: "", expected_json: "{}" });
  const [attemptForm, setAttemptForm] = useState({ suite_id: "", placement_key: "" });
  const [attemptResult, setAttemptResult] = useState<EvalAttemptRecord | null>(null);
  const [queuedEvalRuns, setQueuedEvalRuns] = useState<RunRecord[]>([]);
  const [executionStateByRun, setExecutionStateByRun] = useState<Record<string, "idle" | "running" | "error">>({});
  const [mutationState, setMutationState] = useState<"idle" | "saving" | "error">("idle");

  useEffect(() => {
    let isCurrent = true;
    setRequestState("loading");
    setErrorMessage(null);

    fetchEvalSuites()
      .then((payload) => {
        if (!isCurrent) {
          return;
        }
        setSuites(payload);
        setRequestState("idle");
      })
      .catch((error) => {
        if (!isCurrent) {
          return;
        }
        setRequestState("error");
        setErrorMessage(error instanceof Error ? error.message : "Eval suites request failed.");
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  const totalCases = suites.reduce((total, suite) => total + suite.case_count, 0);
  const placementOptions: PlacementOption[] = models
    .flatMap((model) =>
      model.placement_details
        .filter((placement) => placement.available)
        .map((placement) => ({
          key: `${model.model_name}::${placement.node_id}`,
          model_name: model.model_name,
          node_id: placement.node_id,
        })),
    )
    .sort((left, right) => `${left.model_name}:${left.node_id}`.localeCompare(`${right.model_name}:${right.node_id}`));
  const recentEvalRuns = dedupeRuns([
    ...queuedEvalRuns,
    ...runs.filter((run) => run.detail_type === "eval_attempt"),
  ])
    .sort((left, right) => {
      const leftTime = left.started_at ? new Date(left.started_at).valueOf() : 0;
      const rightTime = right.started_at ? new Date(right.started_at).valueOf() : 0;
      return rightTime - leftTime;
    })
    .slice(0, 5);

  function upsertSuite(updatedSuite: EvalSuiteRecord) {
    setSuites((current) => {
      const withoutSuite = current.filter((suite) => suite.suite_id !== updatedSuite.suite_id);
      return [...withoutSuite, updatedSuite].sort((left, right) => left.name.localeCompare(right.name));
    });
  }

  function upsertEvalRun(updatedRun: RunRecord) {
    setQueuedEvalRuns((current) => dedupeRuns([updatedRun, ...current.filter((run) => run.run_id !== updatedRun.run_id)]));
  }

  async function handleCreateSuite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const suite = await createEvalSuite(suiteForm);
      upsertSuite(suite);
      setSuiteForm({ name: "", description: "" });
      setCaseForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setAttemptForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval suite creation failed.");
    }
  }

  async function handleQueueEvalAttempt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    const placement = placementOptions.find((option) => option.key === attemptForm.placement_key);
    if (!placement) {
      setMutationState("error");
      setErrorMessage("Select an available model placement before queueing an eval attempt.");
      return;
    }

    try {
      const result = await queueEvalAttempt(attemptForm.suite_id, {
        model_name: placement.model_name,
        node_id: placement.node_id,
      });
      setAttemptResult(result);
      setQueuedEvalRuns((current) => dedupeRuns([...result.runs, ...current]));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval attempt queueing failed.");
    }
  }

  async function handleExecuteEvalRun(runId: string) {
    setExecutionStateByRun((current) => ({ ...current, [runId]: "running" }));
    setErrorMessage(null);

    try {
      const run = await executeEvalRun(runId);
      upsertEvalRun(run);
      setExecutionStateByRun((current) => ({ ...current, [runId]: "idle" }));
    } catch (error) {
      setExecutionStateByRun((current) => ({ ...current, [runId]: "error" }));
      setErrorMessage(error instanceof Error ? error.message : "Eval run execution failed.");
    }
  }

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    let expectedJson: Record<string, unknown>;
    try {
      expectedJson = JSON.parse(caseForm.expected_json) as Record<string, unknown>;
    } catch {
      setMutationState("error");
      setErrorMessage("Expected JSON must be valid JSON.");
      return;
    }

    try {
      const suite = await createEvalCase(caseForm.suite_id, {
        name: caseForm.name,
        prompt: caseForm.prompt,
        expected_json: expectedJson,
      });
      upsertSuite(suite);
      setCaseForm((current) => ({ ...current, name: "", prompt: "", expected_json: "{}" }));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval case creation failed.");
    }
  }

  return (
    <section className="panel-section" aria-labelledby="evals-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Evals</p>
          <h2 id="evals-title">Eval Lab foundation</h2>
        </div>
        <p className="section-copy">
          Phase 2 starts with prompt-suite inventory and run-ready structure. Execution and score history come after the
          run system is mature enough to stay truthful.
        </p>
      </header>

      <div className="metric-strip">
        <article className="metric-card">
          <p className="info-kicker">Suites</p>
          <strong>{suites.length}</strong>
        </article>
        <article className="metric-card">
          <p className="info-kicker">Cases</p>
          <strong>{totalCases}</strong>
        </article>
        <article className="metric-card">
          <p className="info-kicker">Execution</p>
          <strong>{recentEvalRuns.length} queued</strong>
        </article>
      </div>

      {errorMessage ? <p className="inline-warning">{errorMessage}</p> : null}

      <div className="eval-form-grid">
        <form className="eval-form" onSubmit={handleCreateSuite}>
          <div>
            <p className="info-kicker">Prompt suite</p>
            <h3>Create suite</h3>
          </div>
          <label>
            <span>Name</span>
            <input
              required
              value={suiteForm.name}
              onChange={(event) => setSuiteForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Reasoning smoke test"
            />
          </label>
          <label>
            <span>Description</span>
            <textarea
              value={suiteForm.description}
              onChange={(event) => setSuiteForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="Short operator note about what this suite measures."
            />
          </label>
          <button type="submit" className="action-button" disabled={mutationState === "saving"}>
            {mutationState === "saving" ? "Saving..." : "Create suite"}
          </button>
        </form>

        <form className="eval-form" onSubmit={handleCreateCase}>
          <div>
            <p className="info-kicker">Prompt case</p>
            <h3>Add case</h3>
          </div>
          <label>
            <span>Suite</span>
            <select
              required
              value={caseForm.suite_id}
              onChange={(event) => setCaseForm((current) => ({ ...current, suite_id: event.target.value }))}
              disabled={suites.length === 0}
            >
              <option value="">Select suite</option>
              {suites.map((suite) => (
                <option key={suite.suite_id} value={suite.suite_id}>
                  {suite.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Case name</span>
            <input
              required
              value={caseForm.name}
              onChange={(event) => setCaseForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="JSON format check"
              disabled={suites.length === 0}
            />
          </label>
          <label>
            <span>Prompt</span>
            <textarea
              required
              value={caseForm.prompt}
              onChange={(event) => setCaseForm((current) => ({ ...current, prompt: event.target.value }))}
              placeholder="Ask the model to produce a concise answer."
              disabled={suites.length === 0}
            />
          </label>
          <label>
            <span>Expected JSON</span>
            <textarea
              value={caseForm.expected_json}
              onChange={(event) => setCaseForm((current) => ({ ...current, expected_json: event.target.value }))}
              disabled={suites.length === 0}
            />
          </label>
          <button type="submit" className="action-button" disabled={mutationState === "saving" || suites.length === 0}>
            {mutationState === "saving" ? "Saving..." : "Add case"}
          </button>
        </form>

        <form className="eval-form" onSubmit={handleQueueEvalAttempt}>
          <div>
            <p className="info-kicker">Eval attempt</p>
            <h3>Queue attempt</h3>
          </div>
          <label>
            <span>Suite</span>
            <select
              required
              value={attemptForm.suite_id}
              onChange={(event) => setAttemptForm((current) => ({ ...current, suite_id: event.target.value }))}
              disabled={suites.length === 0}
            >
              <option value="">Select suite</option>
              {suites.map((suite) => (
                <option key={suite.suite_id} value={suite.suite_id}>
                  {suite.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Model placement</span>
            <select
              required
              value={attemptForm.placement_key}
              onChange={(event) => setAttemptForm((current) => ({ ...current, placement_key: event.target.value }))}
              disabled={placementOptions.length === 0}
            >
              <option value="">Select model on node</option>
              {placementOptions.map((placement) => (
                <option key={placement.key} value={placement.key}>
                  {placement.model_name} on {placement.node_id}
                </option>
              ))}
            </select>
          </label>
          <p className="action-copy">
            Queueing creates durable Run records only. Model execution, scoring, and comparisons stay in the next eval
            slice.
          </p>
          <button
            type="submit"
            className="action-button"
            disabled={mutationState === "saving" || suites.length === 0 || placementOptions.length === 0}
          >
            {mutationState === "saving" ? "Queueing..." : "Queue eval attempt"}
          </button>
          {attemptResult ? (
            <div className="inline-result">
              <span className="status-chip is-queued">queued</span>
              <span className="action-copy">
                {attemptResult.run_count} run{attemptResult.run_count === 1 ? "" : "s"} queued for{" "}
                {attemptResult.model_name} on {attemptResult.node_id}.
              </span>
            </div>
          ) : null}
        </form>
      </div>

      {recentEvalRuns.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Eval runs</p>
              <h3>Recent queued attempts</h3>
            </div>
            <p className="section-copy">These are stored in the same durable Runs ledger as actions and checks.</p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Status</th>
                  <th scope="col">Target</th>
                  <th scope="col">Started</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {recentEvalRuns.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.summary}</td>
                    <td>
                      <span className={`status-chip is-${run.status}`}>{run.status}</span>
                    </td>
                    <td>
                      {run.model_name ?? "Unknown model"} / {run.node_id ?? "unknown node"}
                    </td>
                    <td>{formatTimestamp(run.started_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="action-button"
                        disabled={executionStateByRun[run.run_id] === "running" || run.status === "running"}
                        onClick={() => void handleExecuteEvalRun(run.run_id)}
                      >
                        {executionStateByRun[run.run_id] === "running" || run.status === "running"
                          ? "Executing..."
                          : run.status === "queued"
                            ? "Execute"
                            : "Re-run"}
                      </button>
                      {executionStateByRun[run.run_id] === "error" ? (
                        <p className="action-copy is-error">Execution failed. Check the run details.</p>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {suites.length === 0 ? (
        <div className="empty-state">
          {requestState === "loading"
            ? "Loading eval suites..."
            : "No eval suites have been defined yet. Add prompt suites in Phase 2 before running comparisons."}
        </div>
      ) : (
        <div className="table-shell">
          <table className="inventory-table">
            <thead>
              <tr>
                <th scope="col">Suite</th>
                <th scope="col">Description</th>
                <th scope="col">Cases</th>
                <th scope="col">Case Preview</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {suites.map((suite) => (
                <tr key={suite.suite_id}>
                  <td>{suite.name}</td>
                  <td>{suite.description || "No description"}</td>
                  <td>{suite.case_count}</td>
                  <td>
                    {suite.cases.length > 0 ? (
                      <div className="placement-stack">
                        {suite.cases.slice(0, 3).map((evalCase) => (
                          <span key={evalCase.case_id} className="meta-chip placement-chip">
                            {evalCase.name}
                          </span>
                        ))}
                      </div>
                    ) : (
                      "No cases"
                    )}
                  </td>
                  <td>{suite.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
