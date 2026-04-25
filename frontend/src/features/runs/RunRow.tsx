import type { KeyboardEvent } from "react";

import type { RunRecord } from "../../api/client";

type RunRowProps = {
  run: RunRecord;
  onSelect: (run: RunRecord) => void;
};

function formatStartedAt(startedAt: string | null | undefined): string {
  if (!startedAt) {
    return "Waiting for timestamp";
  }

  const parsed = new Date(startedAt);
  if (Number.isNaN(parsed.valueOf())) {
    return startedAt;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function truncateRunId(runId: string): string {
  return runId.length > 8 ? `${runId.slice(0, 8)}...` : runId;
}

async function copyRunId(runId: string) {
  if (!navigator.clipboard) {
    return;
  }

  await navigator.clipboard.writeText(runId);
}

export function RunRow({ run, onSelect }: RunRowProps) {
  const shortRunId = truncateRunId(run.run_id);

  function handleKeyDown(event: KeyboardEvent<HTMLTableRowElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(run);
    }
  }

  return (
    <tr className="clickable-row" tabIndex={0} onClick={() => onSelect(run)} onKeyDown={handleKeyDown}>
      <td>
        <div className="run-summary">
          <strong>{run.summary}</strong>
          <span className="run-meta run-id-preview">
            Run ID: <code>{shortRunId}</code>
            <button
              type="button"
              className="copy-id-button"
              aria-label={`Copy full run ID ${run.run_id}`}
              title="Copy full run ID"
              onClick={(event) => {
                event.stopPropagation();
                void copyRunId(run.run_id);
              }}
            >
              <svg aria-hidden="true" viewBox="0 0 16 16" focusable="false">
                <path d="M5 2h8v9h-2V4H5V2Zm-2 3h8v9H3V5Zm2 2v5h4V7H5Z" />
              </svg>
            </button>
          </span>
        </div>
      </td>
      <td>
        <span className={`status-chip is-${run.status}`}>{run.status}</span>
      </td>
      <td>{run.node_id ?? "unknown"}</td>
      <td>{formatStartedAt(run.started_at)}</td>
    </tr>
  );
}
