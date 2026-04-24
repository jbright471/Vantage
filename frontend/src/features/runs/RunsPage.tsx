import { useEffect, useState } from "react";

import { buildRunExportUrl, fetchRuns, type RunsQuery, type RunRecord } from "../../api/client";
import { RunRow } from "./RunRow";

type RunsPageProps = {
  runs: Array<Pick<RunRecord, "run_id" | "summary" | "status" | "node_id"> & Partial<Pick<RunRecord, "started_at">>>;
};

const RUN_FILTERS = [
  { label: "All", status: null },
  { label: "Failed", status: "failed" },
  { label: "Submitted", status: "submitted_unverified" },
  { label: "Running", status: "running" },
  { label: "Stale", status: "abandoned" },
];

export function RunsPage({ runs }: RunsPageProps) {
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [pageState, setPageState] = useState({
    items: runs as RunRecord[],
    total: runs.length,
    limit: 10,
    offset: 0,
  });
  const [requestState, setRequestState] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const query: RunsQuery = {
      status: statusFilter,
      limit: pageState.limit,
      offset: pageState.offset,
    };
    let isCurrent = true;

    setRequestState("loading");
    setErrorMessage(null);

    fetchRuns(query)
      .then((payload) => {
        if (!isCurrent) {
          return;
        }
        setPageState((current) => ({
          ...current,
          items: payload.items,
          total: payload.total,
          limit: payload.limit,
          offset: payload.offset,
        }));
        setRequestState("idle");
      })
      .catch((error) => {
        if (!isCurrent) {
          return;
        }
        setRequestState("error");
        setErrorMessage(error instanceof Error ? error.message : "Runs request failed.");
      });

    return () => {
      isCurrent = false;
    };
  }, [statusFilter, pageState.limit, pageState.offset]);

  const orderedRuns = [...pageState.items].sort((left, right) => {
    const leftValue = left.started_at ? Date.parse(left.started_at) : 0;
    const rightValue = right.started_at ? Date.parse(right.started_at) : 0;
    return rightValue - leftValue;
  });
  const latestRun = orderedRuns[0] ?? null;
  const hasPreviousPage = pageState.offset > 0;
  const hasNextPage = pageState.offset + pageState.limit < pageState.total;
  const exportQuery = { status: statusFilter };

  function updateStatusFilter(status: string | null) {
    setStatusFilter(status);
    setPageState((current) => ({ ...current, offset: 0 }));
  }

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

      <div className="runs-toolbar" aria-label="Run filters and exports">
        <div className="segmented-control" aria-label="Run status filter">
          {RUN_FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              className={statusFilter === filter.status ? "is-selected" : ""}
              onClick={() => updateStatusFilter(filter.status)}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="button-row">
          <a className="action-button" href={buildRunExportUrl("csv", exportQuery)}>
            Export CSV
          </a>
          <a className="action-button" href={buildRunExportUrl("json", exportQuery)}>
            Export JSON
          </a>
        </div>
      </div>

      {errorMessage ? <p className="inline-warning">{errorMessage}</p> : null}

      {orderedRuns.length === 0 ? (
        <div className="empty-state">
          {requestState === "loading" ? "Loading run history..." : "No run history matches the current filter."}
        </div>
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

      <footer className="pagination-row" aria-label="Run pagination">
        <button
          type="button"
          className="action-button"
          disabled={!hasPreviousPage || requestState === "loading"}
          onClick={() =>
            setPageState((current) => ({
              ...current,
              offset: Math.max(0, current.offset - current.limit),
            }))
          }
        >
          Previous
        </button>
        <span className="run-meta">
          {pageState.total === 0
            ? "0 runs"
            : `${pageState.offset + 1}-${Math.min(pageState.offset + pageState.limit, pageState.total)} of ${
                pageState.total
              }`}
        </span>
        <button
          type="button"
          className="action-button"
          disabled={!hasNextPage || requestState === "loading"}
          onClick={() =>
            setPageState((current) => ({
              ...current,
              offset: current.offset + current.limit,
            }))
          }
        >
          Next
        </button>
      </footer>
    </section>
  );
}
