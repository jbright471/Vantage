export type NodeRecord = {
  node_id: string;
  display_name: string;
  role: string;
  enabled: boolean;
  created_from: string;
  observed_status: string;
  freshness: string;
  last_seen_at: string | null;
};

export type RunRecord = {
  run_id: string;
  summary: string;
  status: string;
  node_id: string | null;
  started_at: string | null;
};

export type ActionRunRecord = RunRecord & {
  idempotency_key: string | null;
};

export type ModelRecord = {
  model_name: string;
  placements: string[];
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
