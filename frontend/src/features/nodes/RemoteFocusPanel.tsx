import type { NodeRecord, RunRecord } from "../../api/client";

type RemoteFocusPanelProps = {
  nodes: NodeRecord[];
  runs: RunRecord[];
};

function formatMegabytes(value: number | null): string {
  if (value === null) {
    return "Unknown";
  }

  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} GB`;
  }

  return `${value} MB`;
}

function labelRunStatus(status: string): string {
  return status.replaceAll("_", " ");
}

export function RemoteFocusPanel({ nodes, runs }: RemoteFocusPanelProps) {
  const remoteNodes = nodes.filter((node) => node.role === "remote");

  if (remoteNodes.length === 0) {
    return null;
  }

  return (
    <section className="focus-section" aria-labelledby="remote-focus-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Remote Focus</p>
          <h2 id="remote-focus-title">Remote node telemetry and recent operations</h2>
        </div>
        <p className="section-copy">
          Bastet-style remote workers should surface transport health, GPU telemetry, and the most recent remote runs
          without forcing you to leave the shell.
        </p>
      </header>

      <div className="focus-stack">
        {remoteNodes.map((node) => {
          const remoteRuns = runs.filter((run) => run.node_id === node.node_id).slice(0, 3);

          return (
            <article key={node.node_id} className="focus-card">
              <div className="focus-card-header">
                <div>
                  <p className="node-eyebrow">{node.node_id}</p>
                  <h3>{node.display_name}</h3>
                  <p className="node-subtitle">Remote agent telemetry</p>
                </div>
                <div className="node-chip-row">
                  <span className={`status-chip is-${node.observed_status}`}>{node.observed_status}</span>
                  <span className="meta-chip">{node.model_count} models</span>
                </div>
              </div>

              <div className="info-grid focus-summary-grid">
                <article className="info-card">
                  <p className="info-kicker">Agent endpoint</p>
                  <h3>{node.base_url}</h3>
                  <p className="info-copy">Current node freshness: {node.freshness}</p>
                </article>
                <article className="info-card">
                  <p className="info-kicker">Ollama status</p>
                  <h3>{node.ollama_status ?? "unknown"}</h3>
                  <p className="info-copy">Observed models: {node.model_count}</p>
                </article>
                <article className="info-card">
                  <p className="info-kicker">Host memory</p>
                  <h3>{formatMegabytes(node.memory_used_mb)}</h3>
                  <p className="info-copy">
                    CPU usage: {node.cpu_usage_percent === null ? "Unknown" : `${node.cpu_usage_percent}%`}
                  </p>
                </article>
              </div>

              <div className="focus-layout">
                <section className="focus-panel">
                  <p className="info-kicker">GPU telemetry</p>
                  {node.gpu_stats.length === 0 ? (
                    <div className="empty-state">No GPU telemetry has been observed for this node yet.</div>
                  ) : (
                    <div className="focus-gpu-grid">
                      {node.gpu_stats.map((gpu) => (
                        <article key={`${node.node_id}-${gpu.name}`} className="info-card">
                          <p className="info-kicker">GPU</p>
                          <h3>{gpu.name}</h3>
                          <p className="info-copy">Memory: {formatMegabytes(gpu.memory_total_mb)}</p>
                          <p className="info-copy">Temp: {gpu.temperature_c} C</p>
                        </article>
                      ))}
                    </div>
                  )}
                </section>

                <aside className="summary-panel">
                  <p className="info-kicker">Recent remote runs</p>
                  <h3>Latest Bastet-side activity</h3>
                  {remoteRuns.length === 0 ? (
                    <p className="info-copy">No remote runs have been recorded for this node yet.</p>
                  ) : (
                    <div className="focus-run-list">
                      {remoteRuns.map((run) => (
                        <article key={run.run_id} className="focus-run-item">
                          <div className="run-summary">
                            <strong>{run.summary}</strong>
                            <span className="run-meta">{run.started_at ?? "Awaiting timestamp"}</span>
                          </div>
                          <span className={`status-chip is-${run.status}`}>{labelRunStatus(run.status)}</span>
                        </article>
                      ))}
                    </div>
                  )}

                  {node.ollama_errors.length > 0 ? (
                    <div className="focus-warning-list" role="list" aria-label={`${node.display_name} agent warnings`}>
                      {node.ollama_errors.map((error, index) => (
                        <p key={`${node.node_id}-error-${index}`} className="inline-warning" role="listitem">
                          {error.source ? `${error.source}: ` : ""}
                          {error.base_url ? `${error.base_url} ` : ""}
                          {error.error}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </aside>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
