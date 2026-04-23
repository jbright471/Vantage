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

export type WarningRecord = {
  warning_id: string;
  warning_type: string;
  severity: string;
  node_id: string | null;
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
