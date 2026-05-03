# Roadmap

Vantage is moving from visibility-first operations toward carefully bounded operator actions. The guiding rule remains: observe and explain first, then allow deliberate remediation only when the risk is clear.

## Phase 1.5: Operator Attention

Status: shipped.

- Attention ribbon for degraded, stale, warning, and pending states.
- Capped warning strip for config drift and operator notices.
- Heartbeat freshness meters with visual decay.
- Strict routing confirmation with target-node safety context.

## Phase 1.6: Node Diagnostics

Status: shipped.

- Add a node diagnostics drawer for degraded, stale, and unreachable nodes.
- Explain failing subsystems using observed state, not guesses.
- Surface failing Ollama endpoints, remote agent errors, and freshness issues.
- Provide suggested remediation steps without mutating host state.
- Record future remediation attempts as `Run` records.

## Phase 1.7: Guided Remediation

Status: shipped.

- Add allowlisted actions such as retry poll, acknowledge warning, and disable a known-bad endpoint.
- Require strict confirmation for any action that changes configured state.
- Keep host-level service control behind a local node agent rather than the Docker backend container.
- Shipped first allowlisted action: acknowledge active warnings while preserving durable history.
- Shipped verified refresh action: retry one node poll and close the action run as `success` or `failed`.
- Shipped node quarantine action: disable or re-enable a node in Vantage, remove quarantined nodes from routing preference lists, and record the action as `success`.
- Shipped local endpoint suppression action: disable a known-bad local Ollama endpoint from Diagnostics and skip it during polling and capability checks.

## Phase 2: Evaluations

Status: foundation in progress.

- Eval Lab API and UI foundation.
- Prompt suites and prompt cases.
- Queued `Run` storage for eval attempts.
- Executable eval runs with simple JSON-subset scoring.
- Score history aggregated from eval `Run` records.
- Placement comparison views across models and nodes.
- Case-level failure analysis and score-detail drilldowns.
- Recurring eval schedules that queue due eval attempts without external task infrastructure.
- Opt-in auto-execution for due eval schedules while keeping queue-only scheduling as the safe default.
- Eval schedule health warnings that surface failed auto-executions in the operator attention lane.
