import { ModelsPage } from "./features/models/ModelsPage";
import { NodesPage } from "./features/nodes/NodesPage";
import { RoutingPage } from "./features/routing/RoutingPage";
import { RunsPage } from "./features/runs/RunsPage";
import { useEventSource } from "./hooks/useEventSource";

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

export default function App() {
  const { state, streamStatus, lastSyncAt, errorMessage } = useEventSource("/api/stream");

  const liveNodes = state.nodes.filter((node) => node.freshness === "live").length;
  const staleNodes = state.nodes.filter((node) => node.freshness !== "live").length;
  const degradedNodes = state.nodes.filter((node) => node.observed_status !== "healthy").length;

  return (
    <main className="app-shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Vantage</p>
          <h1>Visibility-first control for your local AI nodes.</h1>
          <p className="lede">
            Built to keep configured state, observed state, and last-known freshness separate so the operator view
            stays honest when a node drifts, stalls, or disappears.
          </p>
        </div>

        <div className="hero-meta">
          <span className={`status-pill is-${streamStatus}`}>{labelStreamStatus(streamStatus)}</span>
          <span className="hero-stat">{state.nodes.length} nodes tracked</span>
          <span className="hero-stat">{state.warnings.length} active warnings</span>
          <span className="hero-stat">{formatRelativeSync(lastSyncAt)}</span>
        </div>
      </header>

      <section className="signal-bar" aria-label="Fleet summary">
        <article className="signal-card">
          <span className="signal-label">Live</span>
          <strong>{liveNodes}</strong>
        </article>
        <article className="signal-card">
          <span className="signal-label">Stale</span>
          <strong>{staleNodes}</strong>
        </article>
        <article className="signal-card">
          <span className="signal-label">Need attention</span>
          <strong>{degradedNodes}</strong>
        </article>
      </section>

      {errorMessage ? <p className="inline-warning">{errorMessage}</p> : null}

      <NodesPage nodes={state.nodes} />
      <RunsPage runs={state.runs} />
      <ModelsPage models={state.models} />
      <RoutingPage rules={state.routing} />
    </main>
  );
}
