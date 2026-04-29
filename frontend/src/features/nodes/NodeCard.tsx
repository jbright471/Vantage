import type { CSSProperties } from "react";

import type { NodeRecord } from "../../api/client";

type NodeCardNode = Pick<
    NodeRecord,
    | "node_id"
    | "display_name"
    | "observed_status"
    | "freshness"
    | "last_seen_at"
    | "model_count"
    | "ollama_status"
    | "ollama_errors"
  > &
    Partial<Pick<NodeRecord, "role" | "enabled" | "created_from">>;

type NodeCardProps = {
  node: NodeCardNode;
  onRefresh: (nodeId: string) => void;
  onDiagnose: () => void;
  refreshState?: {
    phase: "idle" | "submitting" | "submitted" | "error";
    status?: string;
    message?: string;
  };
};

function formatLastSeen(value: string | null): string {
  if (!value) {
    return "Never seen";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function describeFreshness(value: string): string {
  if (value === "live") {
    return "Current observation";
  }

  if (value === "stale") {
    return "Observation delayed";
  }

  if (value === "unreachable") {
    return "Last-known only";
  }

  return "Awaiting sync";
}

function formatSignalAge(value: string | null): string {
  if (!value) {
    return "No signal yet";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return "Timestamp unknown";
  }

  const elapsedMs = Math.max(0, Date.now() - parsed.getTime());

  if (elapsedMs < 10_000) {
    return `${elapsedMs}ms`;
  }

  const elapsedSeconds = Math.floor(elapsedMs / 1000);

  if (elapsedSeconds < 60) {
    return `${(elapsedMs / 1000).toFixed(1)}s`;
  }

  const elapsedMinutes = Math.floor(elapsedSeconds / 60);

  if (elapsedMinutes < 60) {
    return `${elapsedMinutes}m ago`;
  }

  const elapsedHours = Math.floor(elapsedMinutes / 60);

  if (elapsedHours < 48) {
    return `${elapsedHours}h ago`;
  }

  return `${Math.floor(elapsedHours / 24)}d ago`;
}

function freshnessLevel(value: string): number {
  if (value === "live") {
    return 92;
  }

  if (value === "stale") {
    return 52;
  }

  return 18;
}

function freshnessOpacity(value: string): number {
  if (value === "live") {
    return 1;
  }

  if (value === "stale") {
    return 0.58;
  }

  return 0.32;
}

export function NodeCard({ node, onRefresh, onDiagnose, refreshState }: NodeCardProps) {
  const role = node.role ?? "unassigned";
  const createdFrom = node.created_from ?? "runtime";
  const isEnabled = node.enabled ?? true;
  const refreshPhase = refreshState?.phase ?? "idle";
  const refreshStatus = refreshState?.status ?? null;
  const refreshMessage = refreshState?.message ?? null;
  const needsDiagnosis = node.observed_status !== "healthy" || node.freshness !== "live" || node.ollama_errors.length > 0;

  const freshnessStyle = {
    "--freshness-level": `${freshnessLevel(node.freshness)}%`,
    "--freshness-opacity": String(freshnessOpacity(node.freshness)),
  } as CSSProperties & Record<"--freshness-level" | "--freshness-opacity", string>;

  return (
    <article className={`node-card freshness-${node.freshness}`}>
      <div className="node-card-header">
        <div>
          <p className="node-eyebrow">{node.node_id}</p>
          <h3>{node.display_name}</h3>
          <p className="node-subtitle">{role}</p>
        </div>
        <span className={`status-chip is-${node.observed_status}`}>{node.observed_status}</span>
      </div>

      <div className="node-chip-row">
        <span className={`status-chip is-${node.freshness}`}>{node.freshness}</span>
        <span className="meta-chip">{isEnabled ? "enabled" : "disabled"}</span>
      </div>

      <div className="freshness-strip" aria-label={`${node.display_name} heartbeat freshness`}>
        <div className="freshness-strip-header">
          <span>Heartbeat</span>
          <strong className="telemetry-value">{formatSignalAge(node.last_seen_at)}</strong>
        </div>
        <div className="freshness-meter" style={freshnessStyle}>
          <span />
        </div>
      </div>

      <dl className="node-metrics">
        <div className="node-metric">
          <dt>Origin</dt>
          <dd>{createdFrom}</dd>
        </div>
        <div className="node-metric">
          <dt>Last seen</dt>
          <dd>{formatLastSeen(node.last_seen_at)}</dd>
        </div>
        <div className="node-metric">
          <dt>Freshness</dt>
          <dd>{describeFreshness(node.freshness)}</dd>
        </div>
        <div className="node-metric">
          <dt>Signal age</dt>
          <dd className="telemetry-value">{formatSignalAge(node.last_seen_at)}</dd>
        </div>
        <div className="node-metric">
          <dt>Observation model</dt>
          <dd>{node.ollama_status ?? "Unknown"}</dd>
        </div>
        <div className="node-metric">
          <dt>Models</dt>
          <dd>{node.model_count}</dd>
        </div>
      </dl>

      <div className="node-action-row">
        <button
          type="button"
          className="action-button"
          disabled={refreshPhase === "submitting"}
          onClick={() => onRefresh(node.node_id)}
        >
          {refreshPhase === "submitting" ? "Submitting refresh..." : "Refresh node"}
        </button>

        {refreshStatus ? <span className={`status-chip is-${refreshStatus}`}>{refreshStatus}</span> : null}
        {needsDiagnosis ? (
          <button type="button" className="action-button is-secondary" onClick={onDiagnose}>
            Diagnose
          </button>
        ) : null}
      </div>

      {refreshMessage ? (
        <p className={`action-copy${refreshPhase === "error" ? " is-error" : ""}`} role="status">
          {refreshMessage}
        </p>
      ) : null}
    </article>
  );
}
