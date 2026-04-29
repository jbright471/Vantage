import { useEffect, useState } from "react";

import { fetchEvalSuites, type EvalSuiteRecord } from "../../api/client";

export function EvalsPage() {
  const [suites, setSuites] = useState<EvalSuiteRecord[]>([]);
  const [requestState, setRequestState] = useState<"loading" | "idle" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
          <strong>Planned</strong>
        </article>
      </div>

      {errorMessage ? <p className="inline-warning">{errorMessage}</p> : null}

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
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {suites.map((suite) => (
                <tr key={suite.suite_id}>
                  <td>{suite.name}</td>
                  <td>{suite.description || "No description"}</td>
                  <td>{suite.case_count}</td>
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
