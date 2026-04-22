import type { RunRecord } from "../../api/client";

type RunRowProps = {
  run: Pick<RunRecord, "run_id" | "summary" | "status" | "node_id"> & Partial<Pick<RunRecord, "started_at">>;
};

function describeStatus(status: string): string {
  switch (status) {
    case "submitted_unverified":
      return "Request sent; Vantage has not verified completion yet.";
    case "running":
      return "Run is active.";
    case "success":
      return "Run completed successfully.";
    case "failed":
      return "Run failed and needs attention.";
    case "timed_out":
      return "Run exceeded its expected response window.";
    case "abandoned":
      return "Run started but never produced a terminal event.";
    case "partial":
      return "Run completed with incomplete or degraded results.";
    default:
      return "Status reported by the control plane.";
  }
}

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

export function RunRow({ run }: RunRowProps) {
  return (
    <tr>
      <td>
        <div className="run-summary">
          <strong>{run.summary}</strong>
          <span className="run-meta">Run ID: {run.run_id}</span>
        </div>
      </td>
      <td>
        <span className={`status-chip is-${run.status}`}>{run.status}</span>
        <p className="run-status-copy">{describeStatus(run.status)}</p>
      </td>
      <td>{run.node_id ?? "unknown"}</td>
      <td>{formatStartedAt(run.started_at)}</td>
    </tr>
  );
}
