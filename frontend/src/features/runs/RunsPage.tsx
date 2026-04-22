import type { RunRecord } from "../../api/client";
import { RunRow } from "./RunRow";

type RunsPageProps = {
  runs: Array<Pick<RunRecord, "run_id" | "summary" | "status" | "node_id"> & Partial<Pick<RunRecord, "started_at">>>;
};

export function RunsPage({ runs }: RunsPageProps) {
  const orderedRuns = [...runs].sort((left, right) => {
    const leftValue = left.started_at ? Date.parse(left.started_at) : 0;
    const rightValue = right.started_at ? Date.parse(right.started_at) : 0;
    return rightValue - leftValue;
  });
  const latestRun = orderedRuns[0] ?? null;

  return (
    <section className="panel-section" aria-labelledby="runs-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Runs</p>
          <h2 id="runs-title">Recent actions, inferences, and scheduled work</h2>
        </div>
        <p className="section-copy">
          Runs stay explicit about uncertainty, especially when a request has been submitted but not yet verified.
        </p>
      </header>

      {orderedRuns.length === 0 ? (
        <div className="empty-state">No run history yet. The first task or action will appear here.</div>
      ) : (
        <div className="runs-layout">
          <div className="table-shell">
            <table className="runs-table">
              <thead>
                <tr>
                  <th scope="col">Summary</th>
                  <th scope="col">Status</th>
                  <th scope="col">Node</th>
                  <th scope="col">Started</th>
                </tr>
              </thead>
              <tbody>
                {orderedRuns.map((run) => (
                  <RunRow key={run.run_id} run={run} />
                ))}
              </tbody>
            </table>
          </div>

          {latestRun ? (
            <aside className="summary-panel" aria-label="Latest run summary">
              <p className="info-kicker">Run Summary</p>
              <h3>Latest observed run</h3>
              <p className="info-copy">Action: {latestRun.summary}</p>
              <div className="summary-meta">
                <div>
                  <dt>Status</dt>
                  <dd>
                    <span className={`status-chip is-${latestRun.status}`}>{latestRun.status.replaceAll("_", " ")}</span>
                  </dd>
                </div>
                <div>
                  <dt>Run ID</dt>
                  <dd>{latestRun.run_id}</dd>
                </div>
                <div>
                  <dt>Node</dt>
                  <dd>{latestRun.node_id ?? "unknown"}</dd>
                </div>
                <div>
                  <dt>Started</dt>
                  <dd>{latestRun.started_at ?? "Waiting for timestamp"}</dd>
                </div>
              </div>
            </aside>
          ) : null}
        </div>
      )}
    </section>
  );
}
