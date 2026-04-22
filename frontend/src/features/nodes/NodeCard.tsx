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
        </div>
        <span className={`status-chip is-${node.observed_status}`}>{node.observed_status}</span>
      </div>

      <div className="chip-row">
        <span className={`status-chip is-${node.freshness}`}>{node.freshness}</span>
        <span className="meta-chip">{role}</span>
        <span className="meta-chip">{createdFrom}</span>
        {!isEnabled ? <span className="meta-chip">disabled</span> : null}
      </div>

      <dl className="node-details">
        <div>
          <dt>Last seen</dt>
          <dd>{formatLastSeen(node.last_seen_at)}</dd>
        </div>
        <div>
          <dt>State model</dt>
          <dd>Observed, not inferred</dd>
        </div>
      </dl>
    </article>
  );
}
