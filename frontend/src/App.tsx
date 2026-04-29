import { lazy, Suspense, useState } from "react";
import { ModelsPage } from "./features/models/ModelsPage";
import { NodesPage } from "./features/nodes/NodesPage";
import { RoutingPage } from "./features/routing/RoutingPage";
import { RunsPage } from "./features/runs/RunsPage";
import { EvalsPage } from "./features/evals/EvalsPage";
import { useEventSource } from "./hooks/useEventSource";
import { acknowledgeWarning } from "./api/client";

const OperatorGuideDrawer = lazy(() =>
  import("./features/docs/OperatorGuideDrawer").then((module) => ({ default: module.OperatorGuideDrawer })),
);

function formatRelativeSync(lastSyncAt: string | null): string {
  if (!lastSyncAt) {
    return "Awaiting first snapshot";
  }

  const lastSync = new Date(lastSyncAt);
  if (Number.isNaN(lastSync.valueOf())) {
    return `Last sync ${lastSyncAt}`;
  }

  return `Last sync ${new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(lastSync)}`;
}

function labelStreamStatus(streamStatus: string): string {
  switch (streamStatus) {
    case "live":
      return "Live";
    case "reconnecting":
      return "Reconnecting";
    case "error":
      return "Sync issue";
    default:
      return "Connecting";
  }
}

function labelPrimaryNode(nodes: Array<{ node_id: string; role: string; observed_status: string }>): string {
  const primaryNode = nodes.find((node) => node.role === "primary") ?? nodes[0];

  if (!primaryNode) {
    return "NO_NODES";
  }

  const status = primaryNode.observed_status === "healthy" ? "ONLINE" : primaryNode.observed_status.toUpperCase();
  return `${primaryNode.node_id.toUpperCase()}: ${status}`;
}

function summarizeAttention(
  nodes: Array<{ observed_status: string; freshness: string }>,
  pendingRuns: number,
  warningCount: number,
): string {
  const staleNodes = nodes.filter((node) => node.freshness !== "live").length;
  const degradedNodes = nodes.filter((node) => node.observed_status !== "healthy").length;
  const issueCount = staleNodes + degradedNodes + pendingRuns + warningCount;

  if (issueCount === 0) {
    return "All lanes nominal";
  }

  return `${issueCount} signals need attention`;
}

export default function App() {
  const { state, streamStatus, lastSyncAt, errorMessage } = useEventSource("/api/stream");
  const [isDocsOpen, setIsDocsOpen] = useState(false);
  const [showAllWarnings, setShowAllWarnings] = useState(false);
  const [acknowledgedWarningIds, setAcknowledgedWarningIds] = useState<Set<string>>(() => new Set());
  const [warningActionState, setWarningActionState] = useState<Record<string, "idle" | "saving" | "error">>({});

  const activeWarnings = state.warnings.filter((warning) => !acknowledgedWarningIds.has(warning.warning_id));
  const liveNodes = state.nodes.filter((node) => node.freshness === "live").length;
  const staleNodes = state.nodes.filter((node) => node.freshness !== "live").length;
  const degradedNodes = state.nodes.filter((node) => node.observed_status !== "healthy").length;
  const pendingRuns = state.runs.filter((run) => ["submitted_unverified", "running"].includes(run.status)).length;
  const mirroredModels = state.models.filter((model) => model.placements.length > 1).length;
  const activePolicyCount = state.routing.filter((rule) => rule.preferred_nodes.length > 0).length;
  const primaryNodeLabel = labelPrimaryNode(state.nodes);
  const attentionSummary = summarizeAttention(state.nodes, pendingRuns, activeWarnings.length);
  const needsAttention = degradedNodes > 0 || staleNodes > 0 || pendingRuns > 0 || activeWarnings.length > 0;
  const visibleWarningLimit = showAllWarnings ? activeWarnings.length : 2;
  const visibleWarnings = activeWarnings.slice(0, visibleWarningLimit);
  const hiddenWarningCount = Math.max(0, activeWarnings.length - visibleWarnings.length);

  async function handleAcknowledgeWarning(warningId: string) {
    setWarningActionState((current) => ({ ...current, [warningId]: "saving" }));
    try {
      await acknowledgeWarning(warningId);
      setAcknowledgedWarningIds((current) => new Set(current).add(warningId));
      setWarningActionState((current) => ({ ...current, [warningId]: "idle" }));
    } catch {
      setWarningActionState((current) => ({ ...current, [warningId]: "error" }));
    }
  }

  return (
    <main className="command-shell">
      <aside className="side-rail">
        <div className="brand-block">
          <p className="rail-label">terminal</p>
          <h1 className="brand-title">Vantage</h1>
          <p className="brand-subtitle">CONTROL_PLANE</p>
        </div>

        <nav className="rail-nav" aria-label="Primary">
          <a href="#nodes-title">
            <span>hub Nodes</span>
            <strong>{state.nodes.length}</strong>
          </a>
          <a href="#runs-title">
            <span>analytics Runs</span>
            <strong>{state.runs.length}</strong>
          </a>
          <a href="#models-title">
            <span>memory Models</span>
            <strong>{state.models.length}</strong>
          </a>
          <a href="#routing-title">
            <span>route Routing</span>
            <strong>{activePolicyCount}</strong>
          </a>
          <a href="#evals-title">
            <span>science Evals</span>
            <strong>2</strong>
          </a>
        </nav>

        <section className="rail-panel">
          <p className="rail-label">{primaryNodeLabel}</p>
          <strong className={`rail-sync is-${streamStatus}`}>{labelStreamStatus(streamStatus)}</strong>
          <p className="rail-copy">{formatRelativeSync(lastSyncAt)}</p>
        </section>

        <section className="rail-panel">
          <p className="rail-label">Freshness</p>
          <dl className="rail-metrics">
            <div>
              <dt>Live</dt>
              <dd>{liveNodes}</dd>
            </div>
            <div>
              <dt>Stale</dt>
              <dd>{staleNodes}</dd>
            </div>
            <div>
              <dt>Warnings</dt>
              <dd>{activeWarnings.length}</dd>
            </div>
            <div>
              <dt>Pending</dt>
              <dd>{pendingRuns}</dd>
            </div>
          </dl>
        </section>
      </aside>

      <section className="main-column">
        <header className="command-header">
          <div>
            <p className="section-kicker">CONTROL_PLANE</p>
            <h2 className="command-title">Local AI Command Center</h2>
            <p className="command-copy">
              Vantage keeps observed state, configured state, and last-known freshness visibly separate so operators
              can trust what they are seeing under load.
            </p>
          </div>

          <div className="header-meta">
            <p className="command-breadcrumb">US_EAST_1 / CLUSTER_ALPHA / VANTAGE</p>
            <div className="header-status-row">
              <span className={`status-chip is-${streamStatus}`}>{labelStreamStatus(streamStatus)}</span>
              <span className="meta-chip">{primaryNodeLabel}</span>
            </div>
            <div className="attention-ribbon" aria-label="Operator attention summary">
              <span className={needsAttention ? "attention-dot is-active" : "attention-dot"} />
              <strong>{attentionSummary}</strong>
              <small>
                {degradedNodes} degraded / {staleNodes} stale / {activeWarnings.length} warnings / {pendingRuns} pending
              </small>
            </div>
            <button type="button" className="docs-trigger-button" onClick={() => setIsDocsOpen(true)}>
              <span aria-hidden="true">?</span>
              Docs
            </button>
          </div>
        </header>

        <section className="telemetry-strip" aria-label="Fleet summary">
          <article className="telemetry-tile">
            <span className="signal-label">Tracked nodes</span>
            <strong>{state.nodes.length}</strong>
            <p>{liveNodes} live / {staleNodes} stale</p>
          </article>
          <article className="telemetry-tile">
            <span className="signal-label">Run queue</span>
            <strong>{pendingRuns}</strong>
            <p>{state.runs.length} total observed runs</p>
          </article>
          <article className="telemetry-tile">
            <span className="signal-label">Model registry</span>
            <strong>{state.models.length}</strong>
            <p>{mirroredModels} mirrored across nodes</p>
          </article>
          <article className="telemetry-tile">
            <span className="signal-label">Routing</span>
            <strong>{activePolicyCount}</strong>
            <p>{state.routing.length} policies visible</p>
          </article>
        </section>

        {errorMessage ? <p className="inline-warning">{errorMessage}</p> : null}

        {activeWarnings.length > 0 ? (
          <section className="warning-strip" aria-label="Active warnings">
            <div>
              <p className="section-kicker">Warnings</p>
              <h2>Configuration drift and operator notices</h2>
            </div>
            <div className="warning-list">
              {visibleWarnings.map((warning) => (
                <article key={warning.warning_id} className="warning-item">
                  <span className={`status-chip is-${warning.severity}`}>{warning.severity}</span>
                  <div>
                    <strong>{warning.summary}</strong>
                    <p>{warning.node_id ? `${warning.warning_type} / ${warning.node_id}` : warning.warning_type}</p>
                    {warningActionState[warning.warning_id] === "error" ? (
                      <p className="warning-action-error">Acknowledge failed. Try again.</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="warning-ack-button"
                    disabled={warningActionState[warning.warning_id] === "saving"}
                    onClick={() => void handleAcknowledgeWarning(warning.warning_id)}
                  >
                    {warningActionState[warning.warning_id] === "saving" ? "Acknowledging..." : "Acknowledge"}
                  </button>
                </article>
              ))}
              {activeWarnings.length > 2 ? (
                <button
                  type="button"
                  className="warning-expand-button"
                  onClick={() => setShowAllWarnings((current) => !current)}
                >
                  {showAllWarnings ? "Show fewer warnings" : `+${hiddenWarningCount} more`}
                </button>
              ) : null}
            </div>
          </section>
        ) : null}

        <NodesPage nodes={state.nodes} runs={state.runs} />
        <RunsPage runs={state.runs} />
        <ModelsPage models={state.models} />
        <RoutingPage
          rules={state.routing}
          availableNodes={state.nodes.map((node) => node.node_id)}
          nodeSummaries={state.nodes.map((node) => ({
            node_id: node.node_id,
            display_name: node.display_name,
            observed_status: node.observed_status,
            freshness: node.freshness,
            model_count: node.model_count,
          }))}
        />
        <EvalsPage />
      </section>

      {isDocsOpen ? (
        <Suspense fallback={null}>
          <OperatorGuideDrawer isOpen={isDocsOpen} onClose={() => setIsDocsOpen(false)} />
        </Suspense>
      ) : null}
    </main>
  );
}
