import type { RoutingRuleRecord } from "../../api/client";

type RoutingPageProps = {
  rules: Array<Pick<RoutingRuleRecord, "rule_id" | "priority_class" | "preferred_nodes"> & Partial<Pick<RoutingRuleRecord, "model_name">>>;
};

function formatModelScope(modelName: string | null | undefined): string {
  if (!modelName) {
    return "Default rule";
  }

  return modelName;
}

export function RoutingPage({ rules }: RoutingPageProps) {
  const orderedRules = [...rules].sort((left, right) => left.priority_class.localeCompare(right.priority_class));
  const uniqueTargetNodes = new Set(orderedRules.flatMap((rule) => rule.preferred_nodes));
  const priorityClasses = new Set(orderedRules.map((rule) => rule.priority_class));

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
                </tr>
              </thead>
              <tbody>
                {orderedRules.map((rule) => (
                  <tr key={rule.rule_id}>
                    <td>{rule.rule_id}</td>
                    <td>{rule.priority_class}</td>
                    <td>{formatModelScope(rule.model_name)}</td>
                    <td>{rule.preferred_nodes.join(" → ")}</td>
                    <td>{rule.preferred_nodes.length > 0 ? "ACTIVE" : "IDLE"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
