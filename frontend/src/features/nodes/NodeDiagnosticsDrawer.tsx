import type { NodeRecord, OllamaErrorRecord } from "../../api/client";

type DiagnosticNode = Pick<
  NodeRecord,
  | "node_id"
  | "display_name"
  | "base_url"
  | "observed_status"
  | "freshness"
  | "last_seen_at"
  | "ollama_status"
  | "ollama_errors"
  | "model_count"
> &
  Partial<Pick<NodeRecord, "role">>;

type NodeDiagnosticsDrawerProps = {
  node: DiagnosticNode;
  onClose: () => void;
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "No observation recorded";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }

  return parsed.toLocaleString();
}

function summarizePrimaryIssue(node: DiagnosticNode): string {
  if (node.freshness === "unreachable") {
    return "Vantage has no current signal from this node. Treat all telemetry as last-known state.";
  }

  if (node.freshness === "stale") {
    return "The latest observation is stale. Check network reachability and the collector/agent process.";
  }

  if (node.ollama_status === "error") {
    return "The node is live, but one or more Ollama endpoints failed during collection.";
  }

  if (node.observed_status !== "healthy") {
    return "The node is reporting degraded health. Review subsystem details before routing work here.";
  }

  return "No active degradation is visible in the current node record.";
}

function remediationForError(error: OllamaErrorRecord): string[] {
  const endpoint = error.base_url ?? error.source ?? "the failing endpoint";
  const message = error.error.toLowerCase();

  if (message.includes("connection refused") || message.includes("actively refused")) {
    return [
      `Confirm the service expected at ${endpoint} is running.`,
      "If the endpoint is no longer intentional, remove it from `local_ollama_base_urls` and restart Vantage.",
      "Use Refresh node after the service or config is corrected.",
    ];
  }

  if (message.includes("network is unreachable") || message.includes("name or service not known")) {
    return [
      `Confirm the backend container can route to ${endpoint}.`,
      "For Docker Desktop, prefer `host.docker.internal` when the service runs on the host.",
      "Check firewall, Docker Desktop networking, and whether the target port is bound on the host.",
    ];
  }

  if (message.includes("timed out")) {
    return [
      `Check whether ${endpoint} is overloaded or slow to respond.`,
      "Review loaded models and host resource pressure before routing more work to this node.",
      "Use Refresh node after load drops or the service recovers.",
    ];
  }

  return [
    `Inspect ${endpoint} directly from the host and from the Vantage backend container.`,
    "Compare the failing endpoint against the configured node and Ollama base URLs.",
    "Use Refresh node after applying the fix.",
  ];
}

export function NodeDiagnosticsDrawer({ node, onClose }: NodeDiagnosticsDrawerProps) {
  const hasOllamaErrors = node.ollama_errors.length > 0;
  const suggestedSteps = hasOllamaErrors
    ? node.ollama_errors.flatMap(remediationForError)
    : [
        "Run Refresh node to request a fresh observation.",
        "Check the node's agent or local collector process if the status does not recover.",
        "Review recent Runs for failed actions targeting this node.",
      ];
  const uniqueSteps = Array.from(new Set(suggestedSteps));

  return (
    <div className="run-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="run-drawer diagnostics-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="node-diagnostics-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <div>
            <p className="section-kicker">Node diagnostics</p>
            <h3 id="node-diagnostics-title">{node.display_name}</h3>
            <p className="drawer-run-id">{node.node_id}</p>
          </div>
          <button type="button" className="drawer-close-button" aria-label="Close node diagnostics" onClick={onClose}>
            X
          </button>
        </header>

        <div className="drawer-content">
          <section className="drawer-section">
            <h4>Primary issue</h4>
            <p>{summarizePrimaryIssue(node)}</p>
          </section>

          <dl className="run-stats-grid">
            <div>
              <dt>Health</dt>
              <dd>
                <span className={`status-chip is-${node.observed_status}`}>{node.observed_status}</span>
              </dd>
            </div>
            <div>
              <dt>Freshness</dt>
              <dd>
                <span className={`status-chip is-${node.freshness}`}>{node.freshness}</span>
              </dd>
            </div>
            <div>
              <dt>Ollama</dt>
              <dd>{node.ollama_status ?? "unknown"}</dd>
            </div>
            <div>
              <dt>Last Seen</dt>
              <dd>{formatTimestamp(node.last_seen_at)}</dd>
            </div>
          </dl>

          {hasOllamaErrors ? (
            <section className="drawer-section">
              <h4>Observed endpoint errors</h4>
              <div className="diagnostic-error-list">
                {node.ollama_errors.map((error, index) => (
                  <article key={`${error.base_url ?? error.source ?? "error"}-${index}`} className="diagnostic-error">
                    <strong>{error.base_url ?? error.source ?? "unknown source"}</strong>
                    <p>{error.error}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <section className="drawer-section">
            <h4>Suggested remediation</h4>
            <ol className="diagnostic-steps">
              {uniqueSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </section>

          <section className="drawer-section">
            <h4>Safety boundary</h4>
            <p>
              Vantage is diagnosing from observed state only. Host-level fixes such as restarting services should be
              routed through a future allowlisted node agent action, not silently executed from the dashboard.
            </p>
          </section>
        </div>
      </aside>
    </div>
  );
}
