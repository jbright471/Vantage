import type { NodeRecord } from "../../api/client";
import { NodeCard } from "./NodeCard";

type NodesPageProps = {
  nodes: Array<
    Pick<NodeRecord, "node_id" | "display_name" | "observed_status" | "freshness" | "last_seen_at"> &
      Partial<Pick<NodeRecord, "role" | "enabled" | "created_from">>
  >;
};

export function NodesPage({ nodes }: NodesPageProps) {
  const orderedNodes = [...nodes].sort((left, right) => left.display_name.localeCompare(right.display_name));

  return (
    <section className="panel-section" aria-labelledby="nodes-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Nodes</p>
          <h2 id="nodes-title">Machine health across your local fleet</h2>
        </div>
        <p className="section-copy">
          Freshness is rendered separately from health so older snapshots cannot pass as current state.
        </p>
      </header>

      {orderedNodes.length === 0 ? (
        <div className="empty-state">Awaiting the first full-state snapshot from the control plane.</div>
      ) : (
        <div className="node-grid">
          {orderedNodes.map((node) => (
            <NodeCard key={node.node_id} node={node} />
          ))}
        </div>
      )}
    </section>
  );
}
