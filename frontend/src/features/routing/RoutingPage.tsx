import { useEffect, useState } from "react";

import { updateRoutingRule, type RoutingRuleRecord } from "../../api/client";

type RoutingPageProps = {
  rules: Array<Pick<RoutingRuleRecord, "rule_id" | "priority_class" | "preferred_nodes"> & Partial<Pick<RoutingRuleRecord, "model_name">>>;
  availableNodes: string[];
};

type PendingRouteChange = {
  ruleId: string;
  nodeId: string;
  currentOrder: string[];
  nextOrder: string[];
};

function formatModelScope(modelName: string | null | undefined): string {
  if (!modelName) {
    return "Default rule";
  }

  return modelName;
}

export function RoutingPage({ rules, availableNodes }: RoutingPageProps) {
  const [preferredNodesByRule, setPreferredNodesByRule] = useState<Record<string, string[]>>({});
  const [saveStateByRule, setSaveStateByRule] = useState<
    Record<string, { phase: "idle" | "saving" | "saved" | "error"; message?: string }>
  >({});
  const [pendingRouteChange, setPendingRouteChange] = useState<PendingRouteChange | null>(null);
  const orderedRules = [...rules].sort((left, right) => left.priority_class.localeCompare(right.priority_class));
  const effectiveRules = orderedRules.map((rule) => ({
    ...rule,
    preferred_nodes: preferredNodesByRule[rule.rule_id] ?? rule.preferred_nodes,
  }));
  const uniqueTargetNodes = new Set(effectiveRules.flatMap((rule) => rule.preferred_nodes));
  const priorityClasses = new Set(orderedRules.map((rule) => rule.priority_class));

  useEffect(() => {
    setPreferredNodesByRule((current) => {
      const next = { ...current };
      for (const rule of rules) {
        next[rule.rule_id] = rule.preferred_nodes;
      }
      return next;
    });
  }, [rules]);

  function buildPreferredOrder(ruleId: string, nodeId: string): PendingRouteChange {
    const currentOrder = preferredNodesByRule[ruleId] ?? rules.find((rule) => rule.rule_id === ruleId)?.preferred_nodes ?? [];
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

  function openRouteConfirmation(ruleId: string, nodeId: string) {
    setPendingRouteChange(buildPreferredOrder(ruleId, nodeId));
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
        message: `Saving ${nodeId} as the preferred node...`,
      },
    }));

    try {
      const updated = await updateRoutingRule(ruleId, nextOrder);
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
      setPendingRouteChange(null);
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
                    <td>{rule.preferred_nodes.length > 0 ? "ACTIVE" : "IDLE"}</td>
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
                        </div>
                        {saveStateByRule[rule.rule_id]?.message ? (
                          <p
                            className={
                              saveStateByRule[rule.rule_id]?.phase === "error" ? "action-copy is-error" : "action-copy"
                            }
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
            <div className="modal-actions">
              <button type="button" className="action-button" onClick={() => setPendingRouteChange(null)}>
                Cancel
              </button>
              <button type="button" className="action-button is-danger" onClick={confirmRouteChange}>
                Confirm routing change
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
