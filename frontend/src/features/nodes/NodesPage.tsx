import { useState } from "react";

import {
  setLocalOllamaEndpointDisabled,
  setNodeEnabled,
  submitRefreshNode,
  type NodeRecord,
  type RunRecord,
} from "../../api/client";
import { NodeCard } from "./NodeCard";
import { NodeDiagnosticsDrawer } from "./NodeDiagnosticsDrawer";
import { RemoteFocusPanel } from "./RemoteFocusPanel";

type NodesPageProps = {
  nodes: Array<
    Pick<
      NodeRecord,
      | "node_id"
      | "display_name"
      | "base_url"
      | "observed_status"
      | "freshness"
      | "last_seen_at"
      | "gpu_stats"
      | "cpu_usage_percent"
      | "memory_used_mb"
      | "ollama_status"
      | "ollama_errors"
      | "model_count"
    > &
      Partial<Pick<NodeRecord, "role" | "enabled" | "created_from">>
  >;
  runs: Array<Pick<RunRecord, "run_id" | "summary" | "status" | "node_id"> & Partial<Pick<RunRecord, "started_at">>>;
};

export function NodesPage({ nodes, runs }: NodesPageProps) {
  const [selectedDiagnosticNode, setSelectedDiagnosticNode] = useState<NodesPageProps["nodes"][number] | null>(null);
  const [pendingEnabledChange, setPendingEnabledChange] = useState<{
    node: NodesPageProps["nodes"][number];
    enabled: boolean;
  } | null>(null);
  const [pendingEndpointChange, setPendingEndpointChange] = useState<{
    nodeId: string;
    endpointUrl: string;
    disabled: boolean;
  } | null>(null);
  const [enabledOverrideByNode, setEnabledOverrideByNode] = useState<Record<string, boolean>>({});
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
  const [enabledActionStateByNode, setEnabledActionStateByNode] = useState<
    Record<
      string,
      {
        phase: "idle" | "submitting" | "submitted" | "error";
        status?: string;
        message?: string;
      }
    >
  >({});
  const [endpointActionStateByUrl, setEndpointActionStateByUrl] = useState<
    Record<
      string,
      {
        phase: "idle" | "submitting" | "submitted" | "error";
        status?: string;
        message?: string;
      }
    >
  >({});
  const orderedNodes = [...nodes]
    .map((node) => ({
      ...node,
      enabled: enabledOverrideByNode[node.node_id] ?? node.enabled,
    }))
    .sort((left, right) => left.display_name.localeCompare(right.display_name));

  async function handleRefresh(nodeId: string) {
    setRefreshStateByNode((current) => ({
      ...current,
      [nodeId]: {
        phase: "submitting",
        message: "Submitting refresh request to the control plane…",
      },
    }));

    try {
      const run = await submitRefreshNode(nodeId);
      const message =
        run.status === "submitted_unverified"
          ? "Refresh request submitted. Completion has not been verified yet."
          : run.status === "success"
            ? "Refresh verified. Vantage collected a fresh observation for this node."
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

  function openEnabledConfirmation(nodeId: string, enabled: boolean) {
    const node = orderedNodes.find((candidate) => candidate.node_id === nodeId);
    if (!node) {
      return;
    }
    setPendingEnabledChange({ node, enabled });
  }

  async function confirmEnabledChange() {
    if (!pendingEnabledChange) {
      return;
    }

    const { node, enabled } = pendingEnabledChange;
    const nodeId = node.node_id;
    setEnabledActionStateByNode((current) => ({
      ...current,
      [nodeId]: {
        phase: "submitting",
        message: `${enabled ? "Re-enabling" : "Quarantining"} ${node.display_name}…`,
      },
    }));

    try {
      const run = await setNodeEnabled(nodeId, enabled);
      setEnabledOverrideByNode((current) => ({
        ...current,
        [nodeId]: enabled,
      }));
      setEnabledActionStateByNode((current) => ({
        ...current,
        [nodeId]: {
          phase: "submitted",
          status: run.status,
          message: enabled
            ? `${node.display_name} re-enabled. Add it back to routing only after it is healthy.`
            : `${node.display_name} quarantined. Vantage will skip polling and removed it from routing preference lists.`,
        },
      }));
    } catch (error) {
      setEnabledActionStateByNode((current) => ({
        ...current,
        [nodeId]: {
          phase: "error",
          message: error instanceof Error ? error.message : "Node state action failed.",
        },
      }));
    } finally {
      setPendingEnabledChange(null);
    }
  }

  function openEndpointConfirmation(nodeId: string, endpointUrl: string) {
    setPendingEndpointChange({ nodeId, endpointUrl, disabled: true });
  }

  async function confirmEndpointChange() {
    if (!pendingEndpointChange) {
      return;
    }

    const { nodeId, endpointUrl, disabled } = pendingEndpointChange;
    setEndpointActionStateByUrl((current) => ({
      ...current,
      [endpointUrl]: {
        phase: "submitting",
        message: `${disabled ? "Disabling" : "Re-enabling"} ${endpointUrl}…`,
      },
    }));

    try {
      const run = await setLocalOllamaEndpointDisabled(nodeId, endpointUrl, disabled);
      setEndpointActionStateByUrl((current) => ({
        ...current,
        [endpointUrl]: {
          phase: "submitted",
          status: run.status,
          message: disabled
            ? "Endpoint disabled. Refresh the node to verify health without this URL."
            : "Endpoint re-enabled. Refresh the node to verify the endpoint.",
        },
      }));
    } catch (error) {
      setEndpointActionStateByUrl((current) => ({
        ...current,
        [endpointUrl]: {
          phase: "error",
          message: error instanceof Error ? error.message : "Endpoint action failed.",
        },
      }));
    } finally {
      setPendingEndpointChange(null);
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
              onDiagnose={() => setSelectedDiagnosticNode(node)}
              onSetEnabled={openEnabledConfirmation}
              refreshState={refreshStateByNode[node.node_id]}
              enabledActionState={enabledActionStateByNode[node.node_id]}
            />
          ))}
        </div>
      )}

      <RemoteFocusPanel nodes={orderedNodes as NodeRecord[]} runs={runs as RunRecord[]} />
      {selectedDiagnosticNode ? (
        <NodeDiagnosticsDrawer
          node={selectedDiagnosticNode}
          onClose={() => setSelectedDiagnosticNode(null)}
          onDisableEndpoint={openEndpointConfirmation}
          endpointActionState={endpointActionStateByUrl}
        />
      ) : null}
      {pendingEnabledChange ? (
        <div className="modal-backdrop" role="presentation">
          <section
            className="confirmation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="node-enabled-confirm-title"
          >
            <p className="section-kicker">Node action</p>
            <h3 id="node-enabled-confirm-title">
              {pendingEnabledChange.enabled ? "Confirm node re-enable" : "Confirm node quarantine"}
            </h3>
            <p className="info-copy">
              {pendingEnabledChange.enabled
                ? "This returns the node to Vantage's enabled registry. Routing preferences are not restored automatically."
                : "This disables the node in Vantage, stops normal polling for it, and removes it from routing preference lists. Host services are not stopped."}
            </p>
            <dl className="modal-meta">
              <div>
                <dt>Node</dt>
                <dd>{pendingEnabledChange.node.display_name}</dd>
              </div>
              <div>
                <dt>Current state</dt>
                <dd>{pendingEnabledChange.node.enabled ? "enabled" : "disabled"}</dd>
              </div>
              <div>
                <dt>Requested state</dt>
                <dd>{pendingEnabledChange.enabled ? "enabled" : "disabled"}</dd>
              </div>
            </dl>
            {!pendingEnabledChange.enabled ? (
              <p className="inline-warning">
                Quarantine is a configured-state change. Confirm only when this node should stop receiving new work.
              </p>
            ) : null}
            <div className="modal-actions">
              <button type="button" className="action-button" onClick={() => setPendingEnabledChange(null)}>
                Cancel
              </button>
              <button
                type="button"
                className={pendingEnabledChange.enabled ? "action-button" : "action-button is-override"}
                onClick={confirmEnabledChange}
              >
                {pendingEnabledChange.enabled ? "Confirm re-enable" : "Confirm quarantine"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
      {pendingEndpointChange ? (
        <div className="modal-backdrop" role="presentation">
          <section
            className="confirmation-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="endpoint-confirm-title"
          >
            <p className="section-kicker">Endpoint action</p>
            <h3 id="endpoint-confirm-title">Confirm endpoint disable</h3>
            <p className="info-copy">
              This writes a runtime override for a local Ollama base URL. Vantage will stop polling this endpoint and
              local capability checks will skip it. The Ollama service itself is not stopped.
            </p>
            <dl className="modal-meta">
              <div>
                <dt>Node</dt>
                <dd>{pendingEndpointChange.nodeId}</dd>
              </div>
              <div>
                <dt>Endpoint</dt>
                <dd>{pendingEndpointChange.endpointUrl}</dd>
              </div>
              <div>
                <dt>Requested state</dt>
                <dd>disabled</dd>
              </div>
            </dl>
            <p className="inline-warning">
              Disable only endpoints that are known bad or intentionally retired. This changes configured collection
              behavior until the endpoint is re-enabled or the override is removed.
            </p>
            <div className="modal-actions">
              <button type="button" className="action-button" onClick={() => setPendingEndpointChange(null)}>
                Cancel
              </button>
              <button type="button" className="action-button is-override" onClick={confirmEndpointChange}>
                Confirm disable endpoint
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
