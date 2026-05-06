export type GpuStat = {
  name: string;
  memory_total_mb: number;
  temperature_c: number;
};

export type OllamaErrorRecord = {
  source?: string;
  base_url?: string;
  error: string;
};

export type NodeRecord = {
  node_id: string;
  display_name: string;
  base_url: string;
  role: string;
  enabled: boolean;
  created_from: string;
  observed_status: string;
  freshness: string;
  last_seen_at: string | null;
  gpu_stats: GpuStat[];
  cpu_usage_percent: number | null;
  memory_used_mb: number | null;
  ollama_status: string | null;
  ollama_errors: OllamaErrorRecord[];
  model_count: number;
};

export type RunRecord = {
  run_id: string;
  summary: string;
  status: string;
  source_type?: string;
  detail_type?: string;
  node_id: string | null;
  started_at: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  model_name?: string | null;
  action_type?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type RunsQuery = {
  status?: string | null;
  node_id?: string | null;
  detail_type?: string | null;
  limit?: number;
  offset?: number;
};

export type RunsQueryResult = {
  items: RunRecord[];
  total: number;
  limit: number;
  offset: number;
  filters: {
    status: string | null;
    node_id: string | null;
    detail_type: string | null;
  };
};

export type ActionRunRecord = RunRecord & {
  idempotency_key: string | null;
};

export type ModelPlacementRecord = {
  node_id: string;
  model_digest: string | null;
  available: boolean;
};

export type ModelRecord = {
  model_name: string;
  placements: string[];
  placement_details: ModelPlacementRecord[];
};

export type RoutingRuleRecord = {
  rule_id: string;
  priority_class: string;
  model_name: string | null;
  preferred_nodes: string[];
};

export type EvalCaseRecord = {
  case_id: string;
  name: string;
  prompt: string;
  expected_json: Record<string, unknown>;
  sort_order: number;
};

export type EvalSuiteRecord = {
  suite_id: string;
  name: string;
  description: string;
  created_at: string;
  metadata_json: Record<string, unknown>;
  case_count: number;
  cases: EvalCaseRecord[];
};

export type EvalAttemptRecord = {
  attempt_id: string;
  suite_id: string;
  suite_name: string;
  model_name: string;
  node_id: string;
  run_count: number;
  runs: RunRecord[];
};

export type EvalScheduleQueueRecord = EvalAttemptRecord & {
  schedule: EvalScheduleRecord | null;
};

export type EvalScheduleRecord = {
  schedule_id: string;
  suite_id: string;
  suite_name: string | null;
  model_name: string;
  node_id: string;
  interval_minutes: number;
  enabled: boolean;
  auto_execute: boolean;
  created_at: string;
  updated_at: string;
  next_run_at: string;
  last_queued_at: string | null;
  metadata_json: Record<string, unknown>;
};

export type EvalScoreAggregate = {
  run_count: number;
  passed_count: number;
  failed_count: number;
  pass_rate: number;
  latest_started_at: string | null;
  model_name?: string;
  node_id?: string;
  suite_id?: string;
  suite_name?: string;
  case_id?: string;
  case_name?: string;
};

export type EvalScoreRunRecord = {
  run_id: string;
  suite_id: string;
  suite_name: string;
  case_id: string;
  case_name: string;
  model_name: string;
  node_id: string;
  status: string;
  passed: boolean;
  score: number | null;
  reason?: string | null;
  missing_or_mismatched?: string[];
  response_preview?: string;
  response_json?: unknown;
  started_at: string;
  duration_ms: number | null;
};

export type EvalScoreHistoryRecord = {
  total_runs: number;
  placements: EvalScoreAggregate[];
  suites: EvalScoreAggregate[];
  cases: EvalScoreAggregate[];
  recent_runs: EvalScoreRunRecord[];
};

export type WarningRecord = {
  warning_id: string;
  warning_type: string;
  severity: string;
  node_id: string | null;
  status?: string;
  summary: string;
};

export type FullState = {
  nodes: NodeRecord[];
  runs: RunRecord[];
  models: ModelRecord[];
  routing: RoutingRuleRecord[];
  warnings: WarningRecord[];
};

export const emptyFullState: FullState = {
  nodes: [],
  runs: [],
  models: [],
  routing: [],
  warnings: [],
};

export function coerceFullState(candidate: Partial<FullState> | null | undefined): FullState {
  return {
    nodes: candidate?.nodes ?? [],
    runs: candidate?.runs ?? [],
    models: candidate?.models ?? [],
    routing: candidate?.routing ?? [],
    warnings: candidate?.warnings ?? [],
  };
}

export function mergeFullState(current: FullState, patch: Partial<FullState>): FullState {
  return {
    nodes: patch.nodes ?? current.nodes,
    runs: patch.runs ?? current.runs,
    models: patch.models ?? current.models,
    routing: patch.routing ?? current.routing,
    warnings: patch.warnings ?? current.warnings,
  };
}

function buildRunsSearchParams(query: RunsQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.status) {
    params.set("status", query.status);
  }
  if (query.node_id) {
    params.set("node_id", query.node_id);
  }
  if (query.detail_type) {
    params.set("detail_type", query.detail_type);
  }
  if (query.limit) {
    params.set("limit", String(query.limit));
  }
  if (query.offset) {
    params.set("offset", String(query.offset));
  }
  return params;
}

export function buildRunExportUrl(format: "csv" | "json", query: RunsQuery): string {
  const params = buildRunsSearchParams({
    status: query.status,
    node_id: query.node_id,
    detail_type: query.detail_type,
  });
  const suffix = params.toString();
  return `/api/runs/export.${format}${suffix ? `?${suffix}` : ""}`;
}

export async function fetchRuns(query: RunsQuery): Promise<RunsQueryResult> {
  const params = buildRunsSearchParams(query);
  const suffix = params.toString();
  const response = await fetch(`/api/runs${suffix ? `?${suffix}` : ""}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Runs request failed with status ${response.status}`);
  }

  return (await response.json()) as RunsQueryResult;
}

export async function submitRefreshNode(nodeId: string): Promise<ActionRunRecord> {
  const response = await fetch(`/api/actions/refresh-node/${encodeURIComponent(nodeId)}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Refresh request failed with status ${response.status}`);
  }

  return (await response.json()) as ActionRunRecord;
}

export async function setNodeEnabled(nodeId: string, enabled: boolean): Promise<ActionRunRecord> {
  const response = await fetch(`/api/actions/nodes/${encodeURIComponent(nodeId)}/enabled`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ enabled }),
  });

  if (!response.ok) {
    throw new Error(`Node ${enabled ? "re-enable" : "quarantine"} failed with status ${response.status}`);
  }

  return (await response.json()) as ActionRunRecord;
}

export async function setLocalOllamaEndpointDisabled(
  nodeId: string,
  endpointUrl: string,
  disabled: boolean,
): Promise<ActionRunRecord> {
  const response = await fetch(`/api/actions/nodes/${encodeURIComponent(nodeId)}/local-ollama-endpoint`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      endpoint_url: endpointUrl,
      disabled,
    }),
  });

  if (!response.ok) {
    throw new Error(`Local Ollama endpoint update failed with status ${response.status}`);
  }

  return (await response.json()) as ActionRunRecord;
}

export async function submitCapabilityCheck(modelName: string, nodeId: string): Promise<RunRecord> {
  const response = await fetch("/api/models/capability-check", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model_name: modelName,
      node_id: nodeId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Capability check failed with status ${response.status}`);
  }

  return (await response.json()) as RunRecord;
}


export async function updateRoutingRule(ruleId: string, preferredNodes: string[]): Promise<RoutingRuleRecord> {
  const response = await fetch(`/api/routing/${encodeURIComponent(ruleId)}`, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      preferred_nodes: preferredNodes,
    }),
  });

  if (!response.ok) {
    throw new Error(`Routing update failed with status ${response.status}`);
  }

  return (await response.json()) as RoutingRuleRecord;
}

export async function acknowledgeWarning(warningId: string): Promise<WarningRecord & { run_id: string }> {
  const response = await fetch(`/api/warnings/${encodeURIComponent(warningId)}/acknowledge`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Warning acknowledgement failed with status ${response.status}`);
  }

  return (await response.json()) as WarningRecord & { run_id: string };
}

export async function fetchEvalSuites(): Promise<EvalSuiteRecord[]> {
  const response = await fetch("/api/evals/suites", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval suites request failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord[];
}

export async function fetchEvalScoreHistory(): Promise<EvalScoreHistoryRecord> {
  const response = await fetch("/api/evals/score-history", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval score history request failed with status ${response.status}`);
  }

  return (await response.json()) as EvalScoreHistoryRecord;
}

export async function fetchEvalSchedules(): Promise<EvalScheduleRecord[]> {
  const response = await fetch("/api/evals/schedules", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval schedules request failed with status ${response.status}`);
  }

  return (await response.json()) as EvalScheduleRecord[];
}

export async function createEvalSuite(payload: { name: string; description: string }): Promise<EvalSuiteRecord> {
  const response = await fetch("/api/evals/suites", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval suite creation failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord;
}

export async function createEvalSchedule(payload: {
  suite_id: string;
  model_name: string;
  node_id: string;
  interval_minutes: number;
  enabled: boolean;
  auto_execute: boolean;
}): Promise<EvalScheduleRecord> {
  const response = await fetch("/api/evals/schedules", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval schedule creation failed with status ${response.status}`);
  }

  return (await response.json()) as EvalScheduleRecord;
}

export async function updateEvalSchedule(scheduleId: string, payload: { enabled: boolean }): Promise<EvalScheduleRecord> {
  const response = await fetch(`/api/evals/schedules/${encodeURIComponent(scheduleId)}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval schedule update failed with status ${response.status}`);
  }

  return (await response.json()) as EvalScheduleRecord;
}

export async function queueEvalScheduleNow(scheduleId: string): Promise<EvalScheduleQueueRecord> {
  const response = await fetch(`/api/evals/schedules/${encodeURIComponent(scheduleId)}/queue-now`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval schedule queue-now failed with status ${response.status}`);
  }

  return (await response.json()) as EvalScheduleQueueRecord;
}

export async function createEvalCase(
  suiteId: string,
  payload: { name: string; prompt: string; expected_json: Record<string, unknown> },
): Promise<EvalSuiteRecord> {
  const response = await fetch(`/api/evals/suites/${encodeURIComponent(suiteId)}/cases`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval case creation failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord;
}

export async function queueEvalAttempt(
  suiteId: string,
  payload: { model_name: string; node_id: string },
): Promise<EvalAttemptRecord> {
  const response = await fetch(`/api/evals/suites/${encodeURIComponent(suiteId)}/attempts`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval attempt queueing failed with status ${response.status}`);
  }

  return (await response.json()) as EvalAttemptRecord;
}

export async function executeEvalRun(runId: string): Promise<RunRecord> {
  const response = await fetch(`/api/evals/runs/${encodeURIComponent(runId)}/execute`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval run execution failed with status ${response.status}`);
  }

  return (await response.json()) as RunRecord;
}
