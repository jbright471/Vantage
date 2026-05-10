import { useEffect, useState } from "react";

import { buildRunExportUrl, fetchRuns, type RunsQuery, type RunRecord } from "../../api/client";
import { RunRow } from "./RunRow";

type RunsPageProps = {
  runs: RunRecord[];
};

const DEFAULT_RUN_PREVIEW_LIMIT = 5;
const EXPANDED_RUN_LIMIT = 500;
type RunsViewMode = "preview" | "all";

const RUN_FILTERS = [
  { label: "All", status: null },
  { label: "Failed", status: "failed" },
  { label: "Submitted", status: "submitted_unverified" },
  { label: "Running", status: "running" },
  { label: "Stale", status: "abandoned" },
];

function sortRunsByStartedAt(runs: RunRecord[]): RunRecord[] {
  return [...runs].sort((left, right) => {
    const leftValue = left.started_at ? Date.parse(left.started_at) : 0;
    const rightValue = right.started_at ? Date.parse(right.started_at) : 0;
    return rightValue - leftValue;
  });
}

function formatExactTimestamp(timestamp: string | null | undefined): string {
  return timestamp ?? "Not recorded";
}

async function copyText(value: string) {
  if (!navigator.clipboard) {
    return;
  }

  await navigator.clipboard.writeText(value);
}

function RunDetailsDrawer({ run, onClose }: { run: RunRecord; onClose: () => void }) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const metadataPayload = run.metadata_json ?? {};
  const metadataJson = Object.keys(metadataPayload).length
    ? JSON.stringify(metadataPayload, null, 2)
    : "{\n  // No extended metadata available for this run\n}";
  const fullRunJson = JSON.stringify(run, null, 2);

  return (
    <div className="run-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="run-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-drawer-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <div>
            <p className="section-kicker">Run details</p>
            <h3 id="run-drawer-title">Run Details</h3>
            <p className="drawer-run-id">{run.run_id}</p>
          </div>
          <button type="button" className="drawer-close-button" aria-label="Close run details" onClick={onClose}>
            X
          </button>
        </header>

        <div className="drawer-content">
          <dl className="run-stats-grid">
            <div>
              <dt>Status</dt>
              <dd>
                <span className={`status-chip is-${run.status}`}>{run.status}</span>
              </dd>
            </div>
            <div>
              <dt>Target Node</dt>
              <dd>{run.node_id ?? "unknown"}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatExactTimestamp(run.started_at)}</dd>
            </div>
            <div>
              <dt>Ended</dt>
              <dd>{formatExactTimestamp(run.ended_at)}</dd>
            </div>
          </dl>

          <section className="drawer-section">
            <h4>Event Summary</h4>
            <p>{run.summary}</p>
          </section>

          <section className="json-panel" aria-label="Observed metadata JSON">
            <div className="json-panel-header">
              <p className="info-kicker">Observed metadata (JSON)</p>
              <button type="button" className="text-action-button" onClick={() => void copyText(metadataJson)}>
                Copy Payload
              </button>
            </div>
            <pre>
              <code>{metadataJson}</code>
            </pre>
          </section>

          <section className="json-panel" aria-label="Full run JSON">
            <div className="json-panel-header">
              <p className="info-kicker">Full run record (JSON)</p>
              <button type="button" className="text-action-button" onClick={() => void copyText(fullRunJson)}>
                Copy Run JSON
              </button>
            </div>
            <pre>
              <code>{fullRunJson}</code>
            </pre>
          </section>
        </div>
      </aside>
    </div>
  );
}

export function RunsPage({ runs }: RunsPageProps) {
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<RunsViewMode>("preview");
  const runLimit = viewMode === "all" ? EXPANDED_RUN_LIMIT : DEFAULT_RUN_PREVIEW_LIMIT;
  const [pageState, setPageState] = useState({
    items: sortRunsByStartedAt(runs).slice(0, DEFAULT_RUN_PREVIEW_LIMIT),
    total: runs.length,
    limit: DEFAULT_RUN_PREVIEW_LIMIT,
    offset: 0,
  });
  const [requestState, setRequestState] = useState<"idle" | "loading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunRecord | null>(null);

  useEffect(() => {
    const query: RunsQuery = {
      status: statusFilter,
      limit: runLimit,
      offset: 0,
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
  }, [statusFilter, runLimit]);

  const orderedRuns = sortRunsByStartedAt(pageState.items).slice(0, runLimit);
  const visibleRunCount = Math.min(orderedRuns.length, pageState.total);
  const exportQuery = { status: statusFilter };

  function updateStatusFilter(status: string | null) {
    setStatusFilter(status);
    setPageState((current) => ({ ...current, offset: 0 }));
  }

  function toggleRunsView() {
    setViewMode((current) => (current === "preview" ? "all" : "preview"));
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
          <a className="action-button" href={buildRunExportUrl("bundle.json", exportQuery)}>
            Export Signed Bundle
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
                  <RunRow key={run.run_id} run={run} onSelect={setSelectedRun} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <footer className="pagination-row" aria-label="Run pagination hook">
        <span className="run-meta">
          {pageState.total === 0
            ? "0 runs"
            : `Showing ${visibleRunCount} of ${pageState.total} ${viewMode === "all" ? "runs" : "recent runs"}`}
        </span>
        <button type="button" className="action-button" disabled={requestState === "loading"} onClick={toggleRunsView}>
          {viewMode === "all" ? "Show Recent Runs" : "View All Runs"}
        </button>
      </footer>

      {selectedRun ? <RunDetailsDrawer run={selectedRun} onClose={() => setSelectedRun(null)} /> : null}
    </section>
  );
}
