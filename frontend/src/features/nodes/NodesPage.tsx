import { useState } from "react";

import { submitRefreshNode, type NodeRecord } from "../../api/client";
import { NodeCard } from "./NodeCard";

type NodesPageProps = {
  nodes: Array<
    Pick<NodeRecord, "node_id" | "display_name" | "observed_status" | "freshness" | "last_seen_at"> &
      Partial<Pick<NodeRecord, "role" | "enabled" | "created_from">>
  >;
};

export function NodesPage({ nodes }: NodesPageProps) {
  const [refreshStateByNode, setRefreshStateByNode] = useState<
    Record<
      string,
      {
        phase: "idle" | "submitting" | "submitted" | "error";
        status?: string;
        message?: string;
      }
    >
  >({});
  const orderedNodes = [...nodes].sort((left, right) => left.display_name.localeCompare(right.display_name));

  async function handleRefresh(nodeId: string) {
    setRefreshStateByNode((current) => ({
      ...current,
      [nodeId]: {
        phase: "submitting",
        message: "Submitting refresh request to the control plane...",
      },
    }));

    try {
      const run = await submitRefreshNode(nodeId);
      const message =
        run.status === "submitted_unverified"
          ? "Refresh request submitted. Completion has not been verified yet."
          : run.summary;

      setRefreshStateByNode((current) => ({
        ...current,
        [nodeId]: {
          phase: "submitted",
          status: run.status,
          message,
        },
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Refresh request failed.";

      setRefreshStateByNode((current) => ({
        ...current,
        [nodeId]: {
          phase: "error",
          message,
        },
      }));
    }
  }

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
            <NodeCard
              key={node.node_id}
              node={node}
              onRefresh={handleRefresh}
              refreshState={refreshStateByNode[node.node_id]}
            />
          ))}
        </div>
      )}
    </section>
  );
}
