import type { NodeRecord } from "../../api/client";

type NodeCardProps = {
  node: Pick<NodeRecord, "node_id" | "display_name" | "observed_status" | "freshness" | "last_seen_at"> &
    Partial<Pick<NodeRecord, "role" | "enabled" | "created_from">>;
};

function formatLastSeen(value: string | null): string {
  if (!value) {
    return "Never seen";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function describeFreshness(value: string): string {
  if (value === "live") {
    return "Current sample";
  }

  if (value === "stale") {
    return "Observation delayed";
  }

  return "Awaiting sync";
}

export function NodeCard({ node }: NodeCardProps) {
  const role = node.role ?? "unassigned";
  const createdFrom = node.created_from ?? "runtime";
  const isEnabled = node.enabled ?? true;

  return (
    <article className="node-card">
      <div className="node-card-header">
        <div>
          <p className="node-eyebrow">{node.node_id}</p>
          <h3>{node.display_name}</h3>
          <p className="node-subtitle">{role}</p>
        </div>
        <span className={`status-chip is-${node.observed_status}`}>{node.observed_status}</span>
      </div>

      <div className="node-chip-row">
        <span className={`status-chip is-${node.freshness}`}>{node.freshness}</span>
        <span className="meta-chip">{isEnabled ? "enabled" : "disabled"}</span>
      </div>

      <dl className="node-metrics">
        <div className="node-metric">
          <dt>Origin</dt>
          <dd>{createdFrom}</dd>
        </div>
        <div className="node-metric">
          <dt>Last seen</dt>
          <dd>{formatLastSeen(node.last_seen_at)}</dd>
        </div>
        <div className="node-metric">
          <dt>Freshness</dt>
          <dd>{describeFreshness(node.freshness)}</dd>
        </div>
        <div className="node-metric">
          <dt>Observation model</dt>
          <dd>Observed</dd>
        </div>
      </dl>
    </article>
  );
}
