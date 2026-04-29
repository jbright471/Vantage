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

Status: in progress.

- Add allowlisted actions such as retry poll, acknowledge warning, and disable a known-bad endpoint.
- Require strict confirmation for any action that changes configured state.
- Keep host-level service control behind a local node agent rather than the Docker backend container.
- Shipped first allowlisted action: acknowledge active warnings while preserving durable history.

## Phase 2: Evaluations

Status: foundation in progress.

- Eval Lab API and UI foundation.
- Prompt suites.
- Run storage for eval attempts.
- Score history.
- Comparison views across model placements and nodes.
