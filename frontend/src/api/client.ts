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
  enabled: boolean;
  allow_degraded: boolean;
  allow_stale: boolean;
  allow_unreachable: boolean;
  minimum_eval_pass_rate: number | null;
  preferred_nodes: string[];
};

export type RoutingRulePayload = {
  rule_id: string;
  priority_class: string;
  model_name?: string | null;
  preferred_nodes: string[];
  enabled?: boolean;
  allow_degraded?: boolean;
  allow_stale?: boolean;
  allow_unreachable?: boolean;
  minimum_eval_pass_rate?: number | null;
};

export type RoutingRulePatch = Partial<Omit<RoutingRulePayload, "rule_id">>;

export type RoutingHistoryRecord = {
  history_id: number;
  rule_id: string;
  action_type: string;
  changed_at: string;
  summary: string;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
};

export type RoutingSimulationDecision = {
  node_id: string;
  display_name: string;
  decision: "selected" | "skipped" | "rejected";
  observed_status: string;
  freshness: string;
  signal_age_seconds: number | null;
  model_available: boolean | null;
  eval_pass_rate: number | null;
  reasons: string[];
};

export type RoutingSimulationRecord = {
  rule_id: string;
  priority_class: string;
  model_name: string | null;
  candidate_order: string[];
  selected_node: string | null;
  decisions: RoutingSimulationDecision[];
  warnings: string[];
  policy?: {
    allow_degraded: boolean;
    allow_stale: boolean;
    allow_unreachable: boolean;
    minimum_eval_pass_rate: number | null;
  };
};

export type EvalCaseRecord = {
  case_id: string;
  name: string;
  prompt: string;
  expected_json: Record<string, unknown>;
  score_type: string;
  score_config_json: Record<string, unknown>;
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

export type EvalBatchExecuteRecord = {
  attempt_id: string;
  runs_executed: number;
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
  score_type?: string;
  model_digest?: string | null;
};

export type EvalRegressionRecord = {
  suite_id: string;
  suite_name: string;
  model_name: string;
  node_id: string;
  minimum_pass_rate: number;
  current_pass_rate: number;
};

export type EvalTrendRecord = {
  bucket: string;
  model_name: string;
  node_id: string;
  run_count: number;
  passed_count: number;
  failed_count: number;
  pass_rate: number;
  avg_duration_ms: number | null;
};

export type EvalFailureClusterRecord = {
  reason: string;
  missing_or_mismatched: string[];
  run_count: number;
  latest_started_at: string | null;
  example_case: string;
  example_suite: string;
};

export type EvalHistoryQuery = {
  window_days?: number;
  model_name?: string | null;
  node_id?: string | null;
  flakiness_min_rate?: number;
  failure_cluster_min_count?: number;
  recent_limit?: number;
};

export type EvalIntelligencePresetRecord = {
  id: string;
  name: string;
  controls: {
    window_days: string;
    placement_key: string;
    flakiness_min_rate: string;
    failure_cluster_min_count: string;
  };
  storage?: string;
  created_at?: string;
  updated_at?: string;
};

export type EvalScheduleHealthRecord = {
  schedule_id: string;
  suite_id: string;
  model_name: string;
  node_id: string;
  enabled: boolean;
  auto_execute: boolean;
  next_run_at: string;
  last_queued_at: string | null;
  last_runs_executed: number;
  last_runs_failed: number;
  status: string;
};

export type EvalScoreHistoryRecord = {
  total_runs: number;
  placements: EvalScoreAggregate[];
  suites: EvalScoreAggregate[];
  cases: EvalScoreAggregate[];
  recent_runs: EvalScoreRunRecord[];
  regressions?: EvalRegressionRecord[];
  trends?: EvalTrendRecord[];
  flaky_cases?: (EvalScoreAggregate & { flakiness_rate: number })[];
  failure_clusters?: EvalFailureClusterRecord[];
  model_reports?: EvalScoreAggregate[];
  schedule_health?: EvalScheduleHealthRecord[];
  filters?: {
    window_days: number;
    model_name: string | null;
    node_id: string | null;
    recent_limit: number;
  };
  thresholds?: {
    flakiness_min_rate: number;
    failure_cluster_min_count: number;
  };
  operator_summary?: {
    headline: string;
    regression_count: number;
    flaky_case_count: number;
    failure_cluster_count: number;
  };
};

export type IntegrationHealthRecord = {
  format: string;
  external_api_token_configured: boolean;
  webhook_allowed_hosts_configured: boolean;
  configured_targets: Record<string, boolean>;
  last_dispatch: null | {
    adapter?: string;
    event_count?: number;
    status_code?: number;
    dispatched_at?: string;
  };
  security_event_counters: Array<{
    event_type: string;
    node_id: string | null;
    count: number;
    last_seen_at: string;
  }>;
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

function buildEvalHistorySearchParams(query: EvalHistoryQuery = {}): URLSearchParams {
  const params = new URLSearchParams();
  if (query.window_days && query.window_days !== 30) {
    params.set("window_days", String(query.window_days));
  }
  if (query.model_name) {
    params.set("model_name", query.model_name);
  }
  if (query.node_id) {
    params.set("node_id", query.node_id);
  }
  if (query.flakiness_min_rate !== undefined && query.flakiness_min_rate !== 0.2) {
    params.set("flakiness_min_rate", String(query.flakiness_min_rate));
  }
  if (query.failure_cluster_min_count !== undefined && query.failure_cluster_min_count !== 2) {
    params.set("failure_cluster_min_count", String(query.failure_cluster_min_count));
  }
  if (query.recent_limit && query.recent_limit !== 20) {
    params.set("recent_limit", String(query.recent_limit));
  }
  return params;
}

export function buildEvalHistoryExportUrl(format: "csv" | "json", query: EvalHistoryQuery = {}): string {
  const params = buildEvalHistorySearchParams(query);
  const suffix = params.toString();
  return `/api/evals/export.${format}${suffix ? `?${suffix}` : ""}`;
}

export function buildRunExportUrl(format: "csv" | "json" | "bundle.json", query: RunsQuery): string {
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


export async function simulateRoutingRule(
  ruleId: string,
  preferredNodes: string[],
): Promise<RoutingSimulationRecord> {
  const response = await fetch(`/api/routing/${encodeURIComponent(ruleId)}/dry-run`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      preferred_nodes: preferredNodes,
    }),
  });

  if (!response.ok) {
    throw new Error(`Routing dry-run failed with status ${response.status}`);
  }

  return (await response.json()) as RoutingSimulationRecord;
}

export async function createRoutingRule(payload: RoutingRulePayload): Promise<RoutingRuleRecord> {
  const response = await fetch("/api/routing", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Routing rule creation failed with status ${response.status}`);
  }

  return (await response.json()) as RoutingRuleRecord;
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

export async function patchRoutingRule(ruleId: string, payload: RoutingRulePatch): Promise<RoutingRuleRecord> {
  const response = await fetch(`/api/routing/${encodeURIComponent(ruleId)}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Routing rule update failed with status ${response.status}`);
  }

  return (await response.json()) as RoutingRuleRecord;
}

export async function deleteRoutingRule(ruleId: string): Promise<{ rule_id: string; deleted: boolean }> {
  const response = await fetch(`/api/routing/${encodeURIComponent(ruleId)}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Routing rule deletion failed with status ${response.status}`);
  }

  return (await response.json()) as { rule_id: string; deleted: boolean };
}

export async function fetchRoutingHistory(ruleId: string): Promise<RoutingHistoryRecord[]> {
  const response = await fetch(`/api/routing/${encodeURIComponent(ruleId)}/history`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Routing history request failed with status ${response.status}`);
  }

  return (await response.json()) as RoutingHistoryRecord[];
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

export async function fetchEvalScoreHistory(query: EvalHistoryQuery = {}): Promise<EvalScoreHistoryRecord> {
  const params = buildEvalHistorySearchParams(query);
  const suffix = params.toString();
  const response = await fetch(`/api/evals/score-history${suffix ? `?${suffix}` : ""}`, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval score history request failed with status ${response.status}`);
  }

  return (await response.json()) as EvalScoreHistoryRecord;
}

export async function fetchEvalIntelligencePresets(): Promise<EvalIntelligencePresetRecord[]> {
  const response = await fetch("/api/evals/intelligence-presets", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval intelligence presets request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as { presets?: EvalIntelligencePresetRecord[] } | EvalIntelligencePresetRecord[];
  const presets = Array.isArray(payload) ? payload : (payload.presets ?? []);
  return presets.filter(
    (preset): preset is EvalIntelligencePresetRecord =>
      typeof preset?.id === "string" && typeof preset.name === "string" && Boolean(preset.controls),
  );
}

export async function saveEvalIntelligencePreset(
  payload: {
    id?: string;
    name: string;
    controls: EvalIntelligencePresetRecord["controls"];
  },
): Promise<EvalIntelligencePresetRecord> {
  const response = await fetch("/api/evals/intelligence-presets", {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval intelligence preset save failed with status ${response.status}`);
  }

  return (await response.json()) as EvalIntelligencePresetRecord;
}

export async function deleteEvalIntelligencePreset(presetId: string): Promise<void> {
  const response = await fetch(`/api/evals/intelligence-presets/${encodeURIComponent(presetId)}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval intelligence preset delete failed with status ${response.status}`);
  }
}

export async function fetchIntegrationHealth(): Promise<IntegrationHealthRecord> {
  const response = await fetch("/api/integrations/health", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Integration health request failed with status ${response.status}`);
  }

  return (await response.json()) as IntegrationHealthRecord;
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

export async function createEvalAssistedSummary(payload: {
  model_name: string;
  node_id: string;
  filter_model_name?: string | null;
  filter_node_id?: string | null;
  window_days?: number;
  flakiness_min_rate?: number;
  failure_cluster_min_count?: number;
}): Promise<RunRecord> {
  const response = await fetch("/api/evals/assisted-summary", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval assisted summary failed with status ${response.status}`);
  }

  return (await response.json()) as RunRecord;
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

export async function updateEvalSuite(
  suiteId: string,
  payload: { name?: string; description?: string },
): Promise<EvalSuiteRecord> {
  const response = await fetch(`/api/evals/suites/${encodeURIComponent(suiteId)}`, {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval suite update failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord;
}

export async function duplicateEvalSuite(suiteId: string): Promise<EvalSuiteRecord> {
  const response = await fetch(`/api/evals/suites/${encodeURIComponent(suiteId)}/duplicate`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval suite duplication failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord;
}

export async function importEvalSuite(payload: Record<string, unknown>): Promise<EvalSuiteRecord> {
  const response = await fetch("/api/evals/suites/import", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Eval suite import failed with status ${response.status}`);
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

export async function updateEvalSchedule(
  scheduleId: string,
  payload: {
    enabled?: boolean;
    auto_execute?: boolean;
    model_name?: string;
    node_id?: string;
    interval_minutes?: number;
  },
): Promise<EvalScheduleRecord> {
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

export async function deleteEvalSchedule(scheduleId: string): Promise<void> {
  const response = await fetch(`/api/evals/schedules/${encodeURIComponent(scheduleId)}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval schedule deletion failed with status ${response.status}`);
  }
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

export async function deleteEvalSuite(suiteId: string): Promise<void> {
  const response = await fetch(`/api/evals/suites/${encodeURIComponent(suiteId)}`, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval suite deletion failed with status ${response.status}`);
  }
}

export async function createEvalCase(
  suiteId: string,
  payload: {
    name: string;
    prompt: string;
    expected_json: Record<string, unknown>;
    score_type?: string;
    score_config_json?: Record<string, unknown>;
  },
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

export async function updateEvalCase(
  suiteId: string,
  caseId: string,
  payload: {
    name?: string;
    prompt?: string;
    expected_json?: Record<string, unknown>;
    score_type?: string;
    score_config_json?: Record<string, unknown>;
    sort_order?: number;
  },
): Promise<EvalSuiteRecord> {
  const response = await fetch(
    `/api/evals/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(caseId)}`,
    {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    throw new Error(`Eval case update failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord;
}

export async function duplicateEvalCase(suiteId: string, caseId: string): Promise<EvalSuiteRecord> {
  const response = await fetch(
    `/api/evals/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(caseId)}/duplicate`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(`Eval case duplication failed with status ${response.status}`);
  }

  return (await response.json()) as EvalSuiteRecord;
}

export async function deleteEvalCase(suiteId: string, caseId: string): Promise<EvalSuiteRecord> {
  const response = await fetch(
    `/api/evals/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(caseId)}`,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(`Eval case deletion failed with status ${response.status}`);
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

export async function executeEvalAttemptBatch(attemptId: string): Promise<EvalBatchExecuteRecord> {
  const response = await fetch(`/api/evals/attempts/${encodeURIComponent(attemptId)}/execute`, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Eval attempt batch execution failed with status ${response.status}`);
  }

  return (await response.json()) as EvalBatchExecuteRecord;
}

export async function createEvalBaseline(payload: {
  suite_id: string;
  model_name: string;
  node_id: string;
  minimum_pass_rate: number;
}): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/evals/suites/${encodeURIComponent(payload.suite_id)}/baseline`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model_name: payload.model_name,
      node_id: payload.node_id,
      minimum_pass_rate: payload.minimum_pass_rate,
    }),
  });

  if (!response.ok) {
    throw new Error(`Eval baseline creation failed with status ${response.status}`);
  }

  return (await response.json()) as Record<string, unknown>;
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
