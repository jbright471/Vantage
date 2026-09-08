import { useEffect, useState } from "react";

import {
  createRoutingRule,
  deleteRoutingRule,
  fetchRoutingHistory,
  patchRoutingRule,
  simulateRoutingRule,
  updateRoutingRule,
  type RoutingHistoryRecord,
  type RoutingRuleRecord,
  type RoutingSimulationRecord,
} from "../../api/client";

type RoutingPageProps = {
  rules: RoutingRuleRecord[];
  availableNodes: string[];
  nodeSummaries?: NodeRouteSummary[];
};

type NodeRouteSummary = {
  node_id: string;
  display_name: string;
  observed_status: string;
  freshness: string;
  model_count: number;
};

type PendingRouteChange = {
  ruleId: string;
  nodeId: string;
  currentOrder: string[];
  nextOrder: string[];
};

type RouteSimulationState = {
  phase: "idle" | "loading" | "ready" | "error";
  result?: RoutingSimulationRecord;
  message?: string;
};

type RuleFormState = {
  rule_id: string;
  priority_class: string;
  model_name: string;
  preferred_nodes: string;
  minimum_eval_pass_rate: string;
  allow_degraded: boolean;
  allow_stale: boolean;
  allow_unreachable: boolean;
};

type HistoryState = {
  ruleId: string | null;
  phase: "idle" | "loading" | "ready" | "error";
  items: RoutingHistoryRecord[];
  message?: string;
};

function formatModelScope(modelName: string | null | undefined): string {
  if (!modelName) {
    return "Default rule";
  }

  return modelName;
}

function stateIcon(value: string): string {
  if (value === "healthy" || value === "live") {
    return "✓";
  }

  if (value === "unreachable" || value === "failed") {
    return "!";
  }

  return "△";
}

function formatSignalAge(value: number | null): string {
  if (value === null) {
    return "no signal";
  }

  if (value < 1) {
    return `${Math.round(value * 1000)}ms`;
  }

  return `${value.toFixed(1)}s`;
}

function formatRoutingReason(reason: string): string {
  return reason.replaceAll("_", " ").replace(":", ": ");
}

function defaultRuleForm(availableNodes: string[]): RuleFormState {
  return {
    rule_id: "",
    priority_class: "interactive",
    model_name: "",
    preferred_nodes: availableNodes.join(", "),
    minimum_eval_pass_rate: "",
    allow_degraded: false,
    allow_stale: false,
    allow_unreachable: false,
  };
}

function parsePreferredNodes(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatPassRate(value: number | null): string {
  if (value === null) {
    return "no eval data";
  }
  return `${Math.round(value * 100)}% pass`;
}

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.valueOf())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(timestamp);
}

export function RoutingPage({ rules, availableNodes, nodeSummaries = [] }: RoutingPageProps) {
  const [localRules, setLocalRules] = useState<RoutingRuleRecord[]>(rules);
  const [preferredNodesByRule, setPreferredNodesByRule] = useState<Record<string, string[]>>({});
  const [saveStateByRule, setSaveStateByRule] = useState<
    Record<string, { phase: "idle" | "saving" | "saved" | "error"; message?: string }>
  >({});
  const [pendingRouteChange, setPendingRouteChange] = useState<PendingRouteChange | null>(null);
  const [routeSimulation, setRouteSimulation] = useState<RouteSimulationState>({ phase: "idle" });
  const [ruleForm, setRuleForm] = useState<RuleFormState>(() => defaultRuleForm(availableNodes));
  const [formState, setFormState] = useState<{ phase: "idle" | "saving" | "error" | "saved"; message?: string }>({
    phase: "idle",
  });
  const [historyState, setHistoryState] = useState<HistoryState>({ ruleId: null, phase: "idle", items: [] });
  const orderedRules = [...localRules].sort((left, right) => left.priority_class.localeCompare(right.priority_class));
  const effectiveRules = orderedRules.map((rule) => ({
    ...rule,
    preferred_nodes: preferredNodesByRule[rule.rule_id] ?? rule.preferred_nodes,
  }));
  const uniqueTargetNodes = new Set(effectiveRules.flatMap((rule) => rule.preferred_nodes));
  const priorityClasses = new Set(orderedRules.map((rule) => rule.priority_class));
  const nodeSummaryById = new Map(nodeSummaries.map((node) => [node.node_id, node]));
  const pendingTargetNode = pendingRouteChange ? nodeSummaryById.get(pendingRouteChange.nodeId) : undefined;
  const pendingTargetRequiresOverride = pendingTargetNode
    ? pendingTargetNode.observed_status !== "healthy" || pendingTargetNode.freshness !== "live"
    : false;

  useEffect(() => {
    setLocalRules(rules);
    setPreferredNodesByRule((current) => {
      const next = { ...current };
      for (const rule of rules) {
        next[rule.rule_id] = rule.preferred_nodes;
      }
      return next;
    });
  }, [rules]);

  useEffect(() => {
    setRuleForm((current) => ({
      ...current,
      preferred_nodes: current.preferred_nodes || availableNodes.join(", "),
    }));
  }, [availableNodes]);

  function buildPreferredOrder(ruleId: string, nodeId: string): PendingRouteChange {
    const currentOrder = preferredNodesByRule[ruleId] ?? localRules.find((rule) => rule.rule_id === ruleId)?.preferred_nodes ?? [];
    const nextOrder = [
      nodeId,
      ...currentOrder.filter((candidate) => candidate !== nodeId),
      ...availableNodes.filter((candidate) => candidate !== nodeId && !currentOrder.includes(candidate)),
    ];

    return {
      ruleId,
      nodeId,
      currentOrder,
      nextOrder,
    };
  }

  function closeRouteConfirmation() {
    setPendingRouteChange(null);
    setRouteSimulation({ phase: "idle" });
  }

  function openRouteConfirmation(ruleId: string, nodeId: string) {
    const routeChange = buildPreferredOrder(ruleId, nodeId);
    setPendingRouteChange(routeChange);
    setRouteSimulation({
      phase: "loading",
      message: "Simulating route order against current node state…",
    });

    simulateRoutingRule(ruleId, routeChange.nextOrder)
      .then((result) => {
        setRouteSimulation({ phase: "ready", result });
      })
      .catch((error) => {
        setRouteSimulation({
          phase: "error",
          message: error instanceof Error ? error.message : "Routing dry-run failed.",
        });
      });
  }

  async function confirmRouteChange() {
    if (!pendingRouteChange) {
      return;
    }

    const { ruleId, nodeId, nextOrder } = pendingRouteChange;

    setPreferredNodesByRule((current) => ({
      ...current,
      [ruleId]: nextOrder,
    }));
    setSaveStateByRule((current) => ({
      ...current,
      [ruleId]: {
        phase: "saving",
        message: `Saving ${nodeId} as the preferred node…`,
      },
    }));

    try {
      const updated = await updateRoutingRule(ruleId, nextOrder);
      setLocalRules((current) => current.map((rule) => (rule.rule_id === ruleId ? updated : rule)));
      setPreferredNodesByRule((current) => ({
        ...current,
        [ruleId]: updated.preferred_nodes,
      }));
      setSaveStateByRule((current) => ({
        ...current,
        [ruleId]: {
          phase: "saved",
          message: `Preferred node updated: ${updated.preferred_nodes.join(" → ")}`,
        },
      }));
    } catch (error) {
      setPreferredNodesByRule((current) => ({
        ...current,
        [ruleId]: pendingRouteChange.currentOrder,
      }));
      setSaveStateByRule((current) => ({
        ...current,
        [ruleId]: {
          phase: "error",
          message: error instanceof Error ? error.message : "Routing update failed.",
        },
      }));
    } finally {
      closeRouteConfirmation();
    }
  }

  async function handleCreateRule() {
    const preferredNodes = parsePreferredNodes(ruleForm.preferred_nodes);
    if (!ruleForm.rule_id.trim() || preferredNodes.length === 0) {
      setFormState({ phase: "error", message: "Rule ID and at least one preferred node are required." });
      return;
    }

    const minimumEvalPassRate = ruleForm.minimum_eval_pass_rate.trim()
      ? Number(ruleForm.minimum_eval_pass_rate)
      : null;
    if (minimumEvalPassRate !== null && (Number.isNaN(minimumEvalPassRate) || minimumEvalPassRate < 0 || minimumEvalPassRate > 1)) {
      setFormState({ phase: "error", message: "Minimum eval pass rate must be between 0 and 1." });
      return;
    }

    setFormState({ phase: "saving", message: "Creating routing rule…" });
    try {
      const created = await createRoutingRule({
        rule_id: ruleForm.rule_id.trim(),
        priority_class: ruleForm.priority_class.trim() || "interactive",
        model_name: ruleForm.model_name.trim() || null,
        preferred_nodes: preferredNodes,
        minimum_eval_pass_rate: minimumEvalPassRate,
        allow_degraded: ruleForm.allow_degraded,
        allow_stale: ruleForm.allow_stale,
        allow_unreachable: ruleForm.allow_unreachable,
      });
      setLocalRules((current) => [...current.filter((rule) => rule.rule_id !== created.rule_id), created]);
      setPreferredNodesByRule((current) => ({ ...current, [created.rule_id]: created.preferred_nodes }));
      setRuleForm(defaultRuleForm(availableNodes));
      setFormState({ phase: "saved", message: `Created routing rule ${created.rule_id}.` });
    } catch (error) {
      setFormState({
        phase: "error",
        message: error instanceof Error ? error.message : "Routing rule creation failed.",
      });
    }
  }

  async function handlePatchRule(rule: RoutingRuleRecord, patch: Partial<RoutingRuleRecord>) {
    setSaveStateByRule((current) => ({
      ...current,
      [rule.rule_id]: { phase: "saving", message: "Updating routing policy…" },
    }));

    try {
      const updated = await patchRoutingRule(rule.rule_id, patch);
      setLocalRules((current) => current.map((item) => (item.rule_id === updated.rule_id ? updated : item)));
      setPreferredNodesByRule((current) => ({ ...current, [updated.rule_id]: updated.preferred_nodes }));
      setSaveStateByRule((current) => ({
        ...current,
        [rule.rule_id]: { phase: "saved", message: `Policy updated for ${updated.rule_id}.` },
      }));
    } catch (error) {
      setSaveStateByRule((current) => ({
        ...current,
        [rule.rule_id]: {
          phase: "error",
          message: error instanceof Error ? error.message : "Routing policy update failed.",
        },
      }));
    }
  }

  async function handleDeleteRule(ruleId: string) {
    setSaveStateByRule((current) => ({
      ...current,
      [ruleId]: { phase: "saving", message: "Deleting routing rule…" },
    }));
    try {
      await deleteRoutingRule(ruleId);
      setLocalRules((current) => current.filter((rule) => rule.rule_id !== ruleId));
      setPreferredNodesByRule((current) => {
        const next = { ...current };
        delete next[ruleId];
        return next;
      });
    } catch (error) {
      setSaveStateByRule((current) => ({
        ...current,
        [ruleId]: {
          phase: "error",
          message: error instanceof Error ? error.message : "Routing rule deletion failed.",
        },
      }));
    }
  }

  async function handleShowHistory(ruleId: string) {
    setHistoryState({ ruleId, phase: "loading", items: [], message: "Loading route history…" });
    try {
      const items = await fetchRoutingHistory(ruleId);
      setHistoryState({ ruleId, phase: "ready", items });
    } catch (error) {
      setHistoryState({
        ruleId,
        phase: "error",
        items: [],
        message: error instanceof Error ? error.message : "Routing history request failed.",
      });
    }
  }

  return (
    <section className="panel-section" aria-labelledby="routing-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Routing</p>
          <h2 id="routing-title">Preferred node order for each policy lane</h2>
        </div>
        <p className="section-copy">
          This is the current routing visibility layer, not a hidden decision engine. The view shows which nodes are
          preferred, in order, for each class of work.
        </p>
      </header>

      <div className="routing-editor-panel" aria-label="Create routing rule">
        <div>
          <p className="info-kicker">Policy editor</p>
          <h3>Create model-specific lane</h3>
          <p className="info-copy">
            Add a strict policy lane for a model, then let dry-run explain whether current health, placement, and eval
            signals would actually use the preferred node.
          </p>
        </div>
        <div className="routing-editor-grid">
          <label>
            Rule ID
            <input
              name="routing-rule-id"
              autoComplete="off"
              spellCheck={false}
              value={ruleForm.rule_id}
              placeholder="e.g., llama-batch…"
              onChange={(event) => setRuleForm((current) => ({ ...current, rule_id: event.target.value }))}
            />
          </label>
          <label>
            Priority
            <select
              name="routing-priority"
              autoComplete="off"
              value={ruleForm.priority_class}
              onChange={(event) => setRuleForm((current) => ({ ...current, priority_class: event.target.value }))}
            >
              <option value="interactive">interactive</option>
              <option value="batch">batch</option>
              <option value="scheduled">scheduled</option>
            </select>
          </label>
          <label>
            Model
            <input
              name="routing-model-name"
              autoComplete="off"
              spellCheck={false}
              value={ruleForm.model_name}
              placeholder="e.g., qwen3.5:27b…"
              onChange={(event) => setRuleForm((current) => ({ ...current, model_name: event.target.value }))}
            />
          </label>
          <label>
            Preferred nodes
            <input
              name="routing-preferred-nodes"
              autoComplete="off"
              spellCheck={false}
              value={ruleForm.preferred_nodes}
              placeholder="e.g., remote-worker, control-plane…"
              onChange={(event) => setRuleForm((current) => ({ ...current, preferred_nodes: event.target.value }))}
            />
          </label>
          <label>
            Min eval pass rate
            <input
              name="routing-minimum-eval-pass-rate"
              autoComplete="off"
              value={ruleForm.minimum_eval_pass_rate}
              placeholder="e.g., 0.75…"
              inputMode="decimal"
              onChange={(event) =>
                setRuleForm((current) => ({ ...current, minimum_eval_pass_rate: event.target.value }))
              }
            />
          </label>
        </div>
        <div className="routing-policy-switches">
          <label>
            <input
              name="routing-allow-degraded"
              type="checkbox"
              checked={ruleForm.allow_degraded}
              onChange={(event) => setRuleForm((current) => ({ ...current, allow_degraded: event.target.checked }))}
            />
            Allow degraded
          </label>
          <label>
            <input
              name="routing-allow-stale"
              type="checkbox"
              checked={ruleForm.allow_stale}
              onChange={(event) => setRuleForm((current) => ({ ...current, allow_stale: event.target.checked }))}
            />
            Allow stale
          </label>
          <label>
            <input
              name="routing-allow-unreachable"
              type="checkbox"
              checked={ruleForm.allow_unreachable}
              onChange={(event) =>
                setRuleForm((current) => ({ ...current, allow_unreachable: event.target.checked }))
              }
            />
            Allow unreachable
          </label>
          <button
            type="button"
            className="action-button"
            onClick={handleCreateRule}
            disabled={formState.phase === "saving"}
          >
            Create rule
          </button>
        </div>
        {formState.message ? (
          <p
            className={formState.phase === "error" ? "action-copy is-error" : "action-copy"}
            role={formState.phase === "error" ? "alert" : "status"}
          >
            {formState.message}
          </p>
        ) : null}
      </div>

      {orderedRules.length === 0 ? (
        <div className="empty-state">No routing rules have been configured yet.</div>
      ) : (
        <>
          <div className="route-flow">
            <article className="info-card">
              <p className="info-kicker">Gateway</p>
              <h3>Ingress</h3>
              <p className="info-copy">Control plane requests enter through the routing layer.</p>
            </article>
            <div className="flow-arrow">→</div>
            <article className="info-card">
              <p className="info-kicker">Priority classes</p>
              <h3>{priorityClasses.size}</h3>
              <p className="info-copy">{Array.from(priorityClasses).map((value) => value.toUpperCase()).join(" / ")}</p>
            </article>
            <div className="flow-arrow">→</div>
            <article className="info-card">
              <p className="info-kicker">Target nodes</p>
              <h3>{uniqueTargetNodes.size}</h3>
              <p className="info-copy">{Array.from(uniqueTargetNodes).join(", ")}</p>
            </article>
          </div>

          <div className="table-shell">
            <table className="routing-table">
              <thead>
                <tr>
                  <th scope="col">Rule ID</th>
                  <th scope="col">Priority Class</th>
                  <th scope="col">Model</th>
                  <th scope="col">Route Order</th>
                  <th scope="col">Status</th>
                  <th scope="col">Policy</th>
                  <th scope="col">Operator</th>
                </tr>
              </thead>
              <tbody>
                {effectiveRules.map((rule) => (
                  <tr key={rule.rule_id}>
                    <td>{rule.rule_id}</td>
                    <td>{rule.priority_class}</td>
                    <td>{formatModelScope(rule.model_name)}</td>
                    <td>{rule.preferred_nodes.join(" → ")}</td>
                    <td>{rule.enabled ? (rule.preferred_nodes.length > 0 ? "ACTIVE" : "IDLE") : "DISABLED"}</td>
                    <td>
                      <div className="policy-chip-row">
                        {rule.minimum_eval_pass_rate !== null ? (
                          <span className="meta-chip">eval ≥ {Math.round(rule.minimum_eval_pass_rate * 100)}%</span>
                        ) : null}
                        {rule.allow_degraded ? <span className="meta-chip">degraded ok</span> : null}
                        {rule.allow_stale ? <span className="meta-chip">stale ok</span> : null}
                        {rule.allow_unreachable ? <span className="meta-chip">unreachable ok</span> : null}
                        {!rule.minimum_eval_pass_rate &&
                        !rule.allow_degraded &&
                        !rule.allow_stale &&
                        !rule.allow_unreachable ? (
                          <span className="meta-chip">strict failover</span>
                        ) : null}
                      </div>
                    </td>
                    <td className="table-action-cell">
                      <div className="action-stack">
                        <div className="button-row">
                          {availableNodes.map((nodeId) => (
                            <button
                              key={`${rule.rule_id}-${nodeId}`}
                              type="button"
                              className="action-button"
                              onClick={() => openRouteConfirmation(rule.rule_id, nodeId)}
                              disabled={saveStateByRule[rule.rule_id]?.phase === "saving"}
                            >
                              Prefer {nodeId}
                            </button>
                          ))}
                          <button
                            type="button"
                            className="action-button is-secondary"
                            onClick={() => handlePatchRule(rule, { enabled: !rule.enabled })}
                            disabled={saveStateByRule[rule.rule_id]?.phase === "saving"}
                          >
                            {rule.enabled ? "Disable" : "Enable"}
                          </button>
                          <button
                            type="button"
                            className="action-button is-secondary"
                            onClick={() => handlePatchRule(rule, { allow_degraded: !rule.allow_degraded })}
                            disabled={saveStateByRule[rule.rule_id]?.phase === "saving"}
                          >
                            {rule.allow_degraded ? "Block degraded" : "Allow degraded"}
                          </button>
                          <button
                            type="button"
                            className="action-button is-secondary"
                            onClick={() => handlePatchRule(rule, { allow_stale: !rule.allow_stale })}
                            disabled={saveStateByRule[rule.rule_id]?.phase === "saving"}
                          >
                            {rule.allow_stale ? "Block stale" : "Allow stale"}
                          </button>
                          <button
                            type="button"
                            className="action-button is-secondary"
                            onClick={() => handleShowHistory(rule.rule_id)}
                          >
                            History
                          </button>
                          <button
                            type="button"
                            className="action-button is-danger"
                            onClick={() => handleDeleteRule(rule.rule_id)}
                            disabled={saveStateByRule[rule.rule_id]?.phase === "saving"}
                          >
                            Delete
                          </button>
                        </div>
                        {saveStateByRule[rule.rule_id]?.message ? (
                          <p
                            className={
                              saveStateByRule[rule.rule_id]?.phase === "error" ? "action-copy is-error" : "action-copy"
                            }
                            role="status"
                          >
                            {saveStateByRule[rule.rule_id]?.message}
                          </p>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {historyState.ruleId ? (
            <section className="routing-history-panel" aria-label={`Route history for ${historyState.ruleId}`}>
              <div className="panel-heading-row">
                <div>
                  <p className="info-kicker">Route history</p>
                  <h3>{historyState.ruleId}</h3>
                </div>
                <button
                  type="button"
                  className="text-action-button"
                  onClick={() => setHistoryState({ ruleId: null, phase: "idle", items: [] })}
                >
                  Close
                </button>
              </div>
              {historyState.phase === "loading" ? <p className="info-copy" role="status">{historyState.message}</p> : null}
              {historyState.phase === "error" ? <p className="inline-warning" role="alert">{historyState.message}</p> : null}
              {historyState.phase === "ready" && historyState.items.length === 0 ? (
                <p className="info-copy">No route history has been recorded for this rule yet.</p>
              ) : null}
              {historyState.phase === "ready" && historyState.items.length > 0 ? (
                <div className="history-timeline">
                  {historyState.items.map((item) => (
                    <article key={item.history_id} className="history-event">
                      <div>
                        <strong>{item.action_type}</strong>
                        <span>{formatTimestamp(item.changed_at)}</span>
                      </div>
                      <p>{item.summary}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </>
      )}

      {pendingRouteChange ? (
        <div className="modal-backdrop" role="presentation">
          <section
            className="confirmation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="routing-confirm-title"
          >
            <p className="section-kicker">Routing change</p>
            <h3 id="routing-confirm-title">Confirm preferred node change</h3>
            <p className="info-copy">
              This changes configured routing order for the selected lane. Vantage requires explicit confirmation before
              altering where future work is preferred.
            </p>
            <dl className="modal-meta">
              <div>
                <dt>Rule</dt>
                <dd>{pendingRouteChange.ruleId}</dd>
              </div>
              <div>
                <dt>Promote</dt>
                <dd>{pendingRouteChange.nodeId}</dd>
              </div>
              <div>
                <dt>New order</dt>
                <dd>{pendingRouteChange.nextOrder.join(" → ")}</dd>
              </div>
            </dl>
            {pendingTargetNode ? (
              <div className="routing-safety-panel">
                <p className="info-kicker">Target node state</p>
                <div className="state-token-row">
                  <span className={`state-token is-${pendingTargetNode.observed_status}`}>
                    <span className="state-icon" aria-hidden="true">
                      {stateIcon(pendingTargetNode.observed_status)}
                    </span>
                    {pendingTargetNode.observed_status}
                  </span>
                  <span className={`state-token is-${pendingTargetNode.freshness}`}>
                    <span className="state-icon" aria-hidden="true">
                      {stateIcon(pendingTargetNode.freshness)}
                    </span>
                    {pendingTargetNode.freshness}
                  </span>
                  <span className="meta-chip">{pendingTargetNode.model_count} models</span>
                </div>
                {pendingTargetRequiresOverride ? (
                  <p className="inline-warning">
                    This node is not currently healthy and live. Confirm only if you are intentionally testing or
                    redirecting work with that risk.
                  </p>
                ) : (
                  <p className="info-copy">The target node is currently healthy and live.</p>
                )}
              </div>
            ) : null}
            <div className="routing-safety-panel route-simulation-panel">
              <p className="info-kicker">Route simulation</p>
              {routeSimulation.phase === "loading" ? (
                <p className="info-copy" role="status">{routeSimulation.message}</p>
              ) : null}
              {routeSimulation.phase === "error" ? (
                <p className="inline-warning" role="alert">{routeSimulation.message}</p>
              ) : null}
              {routeSimulation.phase === "ready" && routeSimulation.result ? (
                <>
                  <div className="state-token-row">
                    <span className="meta-chip">
                      Selected: {routeSimulation.result.selected_node ?? "none"}
                    </span>
                    <span className="meta-chip">
                      Order: {routeSimulation.result.candidate_order.join(" → ")}
                    </span>
                    {routeSimulation.result.policy?.minimum_eval_pass_rate !== null &&
                    routeSimulation.result.policy?.minimum_eval_pass_rate !== undefined ? (
                      <span className="meta-chip">
                        Eval ≥ {Math.round(routeSimulation.result.policy.minimum_eval_pass_rate * 100)}%
                      </span>
                    ) : null}
                  </div>
                  {routeSimulation.result.warnings.length > 0 ? (
                    <div className="inline-warning">
                      {routeSimulation.result.warnings.map((warning) => (
                        <p key={warning}>{warning}</p>
                      ))}
                    </div>
                  ) : (
                    <p className="info-copy">Dry-run found an eligible route using the proposed order.</p>
                  )}
                  <div className="simulation-decision-list">
                    {routeSimulation.result.decisions.map((decision) => (
                      <div key={decision.node_id} className={`simulation-decision is-${decision.decision}`}>
                        <div>
                          <strong>{decision.display_name}</strong>
                          <span>{decision.node_id}</span>
                        </div>
                        <div className="simulation-decision-meta">
                          <span>{decision.decision}</span>
                          <span>{decision.observed_status}</span>
                          <span>{decision.freshness}</span>
                          <span>{formatSignalAge(decision.signal_age_seconds)}</span>
                          <span>{formatPassRate(decision.eval_pass_rate)}</span>
                        </div>
                        <p>{decision.reasons.map(formatRoutingReason).join(" / ")}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
            <div className="modal-actions">
              <button type="button" className="action-button" onClick={closeRouteConfirmation}>
                Cancel
              </button>
              <button
                type="button"
                className={pendingTargetRequiresOverride ? "action-button is-override" : "action-button"}
                onClick={confirmRouteChange}
              >
                {pendingTargetRequiresOverride ? "Confirm override" : "Confirm routing change"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
