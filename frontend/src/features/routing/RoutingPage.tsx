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
        <div className="info-grid">
          {orderedRules.map((rule) => (
            <article className="info-card" key={rule.rule_id}>
              <p className="info-kicker">{formatModelScope(rule.model_name)}</p>
              <h3>{rule.priority_class}</h3>
              <p className="info-copy">{rule.preferred_nodes.join(" → ")}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
