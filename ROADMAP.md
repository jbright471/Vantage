# Roadmap

Vantage is moving from visibility-first local AI operations toward carefully bounded operator actions. The guiding rule remains: observe and explain first, then allow deliberate remediation only when the risk is clear.

## Phase 1: Control Plane Foundation

Status: shipped.

- FastAPI control-plane backend with SQLite persistence.
- Vite/React frontend with dark operator-console UI.
- Docker Compose development environment for backend and frontend.
- Lightweight remote FastAPI agent for Linux worker nodes.
- Agent authentication through a shared bearer token.
- SSE full-state stream with reconnect-friendly state synchronization.
- Node registry from `config/vantage.bootstrap.toml`.
- Local and remote node polling.
- GPU, CPU, memory, Ollama, model, and run telemetry collection.
- Core dashboards for Nodes, Runs, Models, and Routing.
- Durable `Run` schema for actions, checks, router events, scheduler jobs, and eval attempts.
- `NodeSnapshot` persistence with bounded pruning.
- CSV and JSON run export.
- Operator guide drawer rendered from Markdown inside the app.

## Phase 1.5: Operator Attention

Status: shipped.

- Attention ribbon for degraded, stale, warning, and pending states.
- Capped warning strip for config drift and operator notices.
- Strict semantic colors: amber for warning/stale states, red for hard failures.
- Heartbeat freshness meters with visual decay.
- Monospace signal-age telemetry to prevent visual jitter.
- Strict routing confirmation with target-node safety context.
- Redundant routing modal warnings using text, color, and state icons.

## Phase 1.6: Node Diagnostics

Status: shipped.

- Node diagnostics drawer for degraded, stale, and unreachable nodes.
- Observed-state explanations for failing subsystems.
- Failing Ollama endpoint visibility.
- Remote agent error visibility.
- Freshness and last-observed diagnostics.
- Suggested remediation steps without mutating host state.
- Future-action framing through durable `Run` records.

## Phase 1.7: Guided Remediation

Status: shipped.

- Allowlisted operator actions with durable audit records.
- Warning acknowledgement while preserving warning history.
- Verified node refresh action that retries one collector pass and closes as `success` or `failed`.
- Node quarantine and re-enable actions.
- Quarantined nodes are removed from routing preference lists.
- Strict confirmation for configured-state changes.
- Local Ollama endpoint suppression from Diagnostics.
- Disabled local Ollama endpoints are skipped during polling, capability checks, and eval execution.
- Host-level service control remains behind a future local node agent, not the Docker backend container.

## Phase 2: Evaluations

Status: shipped.

Completed foundation:

- Eval Lab API and UI foundation.
- Prompt suites and prompt cases.
- Queued `Run` storage for eval attempts.
- Executable eval runs with deterministic scoring.
- Score history aggregated from eval `Run` records.
- Placement comparison views across models and nodes.
- Case-level failure analysis and score-detail drilldowns.
- Recurring eval schedules without external task infrastructure.
- Manual `Queue now` control for enabled eval schedules without advancing recurring `next_run_at`.
- Lifecycle cleanup for eval schedules, prompt cases, and empty prompt suites while preserving historical eval `Run` records.
- Opt-in auto-execution for due eval schedules while keeping queue-only scheduling as the safe default.
- Eval schedule health warnings that surface failed auto-executions in the operator attention lane.
- Edit prompt suite name and description.
- Edit prompt case name, prompt, expected JSON, and sort order.
- Edit eval schedule interval, target placement, enabled state, and auto-execute setting.
- Duplicate suites and individual cases for fast test iteration.
- Execute all queued runs for an attempt or schedule batch.
- Add richer score types beyond JSON-subset checks, such as exact match, contains, regex, numeric threshold, and JSON schema validation.
- Add baseline comparisons so operators can detect regressions against a known-good model placement.
- Add eval result export in CSV and JSON.
- Add suite import/export for sharing prompt packs across Vantage installs.
- Add clearer empty, loading, and error states for Eval Lab lifecycle actions.
- Snapshot model digests at eval queue time so comparisons remain tied to the observed model version.

## Phase 2.5: Eval Intelligence

Status: shipped with future tuning planned.

Completed foundation:

- Lightweight trend charts and rows for pass rate, failure rate, and latency by model placement.
- Regression alerts when a model placement drops below its baseline.
- Case flakiness detection across repeated runs.
- Per-case failure clustering by reason and missing fields.
- Model-versus-model comparison reports.
- Schedule health summaries across recent runs.
- Deterministic operator summary derived from regressions, flaky cases, and failure clusters.
- Optional local-LLM-assisted eval summaries that explain likely failure causes without replacing raw score data.
- Assisted summaries are manual, model-placement-selected, and stored as durable `eval_assisted_summary` Run records.
- Richer visual chart controls for selecting score-history time windows and placement filters.
- Configurable Eval Intelligence thresholds for flakiness sensitivity and failure-cluster size.
- Eval CSV/JSON exports and assisted summaries inherit the same active score-history scope as the UI.
- Browser-local saved presets for common Eval Intelligence scopes.
- Visual pass-rate tone bands for trend cards so weak placements stand out without reading every row.

Future tuning:

- Add more expressive chart visualizations once more real eval history accumulates.
- Promote presets into managed operator settings if browser-local storage becomes too limiting.

## Phase 3: Routing And Policy Control

Status: shipped.

- Route simulation before saving routing policy changes.
- Policy validation against current node health, freshness, enabled-state, model placement, and eval pass-rate constraints.
- Routing rule editor for adding, disabling, enabling, and deleting policy lanes.
- Model-specific routing rules beyond the priority-class defaults.
- Failover flags for explicitly allowing degraded, stale, or unreachable nodes.
- Strict default failover behavior that rejects stale, degraded, unreachable, disabled, or model-incompatible nodes.
- Routing dry-run API that explains why a node would be selected, skipped, or rejected.
- Route history showing when and why preferences changed.
- Capability-aware routing that can use eval scores, model availability, and node health as constraints.
- Safer scheduled-work policy lanes that remain strict unless an operator explicitly enables degraded, stale, or unreachable failover allowances.

## Phase 4: Production Deployment And Packaging

Status: shipped.

Completed foundation:

- Control-plane liveness endpoint for process-level service checks.
- Control-plane readiness endpoint for SQLite, required schema tables, and bootstrap config verification.
- Backward-compatible basic health endpoint.
- Structured JSON backend logs with timestamps and exception details.
- Production Docker Compose profile with immutable backend and frontend images.
- Backend production image that runs Alembic migrations before Uvicorn starts.
- Nginx-served frontend image with `/api` proxying for REST and SSE.
- Compose healthcheck wiring for backend readiness and frontend static serving.
- Initial Alembic migration baseline for the current SQLite schema.
- Generic remote-agent install script and systemd service template.
- SQLite backup and restore guidance using the SQLite backup API.
- Portainer deployment guide.
- Hardened environment variable and secret handling through ignored env files, required production token injection, and public-safe examples.
- Setup checker for Docker, Compose config, SQLite path, agent token, backend readiness, and remote node reachability.
- Docker, Portainer, and systemd log rotation guidance.
- Optional local node agent boundary document for host-level actions that Docker backend containers should not perform directly.
- First-class release artifacts through local release bundle script and GitHub release workflow.

## Phase 5: Share/Sell Readiness

Status: planned.

- Demo mode with seeded sample data.
- First-run setup wizard for node registry, token setup, and local Ollama discovery.
- Product screenshots and walkthrough media.
- Polished README positioning Vantage as a local AI command center.
- License and distribution decision.
- Versioned changelog.
- Onboarding checklist for other homelab operators.
- Security posture summary for local-first deployments.
- Optional landing page or product microsite.
- Release announcement template and product-ready install walkthrough.
- Demo-friendly sample eval suites and routing policies.

## Phase 6: Trust, Audit, And Security Hardening

Status: planned.

- Signed audit export for run history.
- Optional immutable audit bundle with JSON plus signature metadata.
- Stronger agent authentication options beyond a shared bearer token.
- Token rotation workflow.
- Agent request replay protection.
- More explicit action idempotency-key strategy per action type.
- Least-privilege agent action allowlist.
- Security event warnings for unauthorized agent calls or repeated auth failures.
- Vulnerability reporting workflow and release security checklist.
- Optional mTLS research for multi-operator or less-trusted networks.

## Phase 7: Integrations And Automation

Status: planned.

- Webhook export for warnings, failed runs, and eval regressions.
- n8n integration examples.
- Slack, Discord, or email notification adapters.
- Scheduled report generation.
- API tokens for external tools.
- Import hooks for existing router logs.
- Optional Obsidian-friendly Markdown export for incident notes and eval reports.
- Plugin-style collector interface for adding new model runtimes beyond Ollama.

## Later Research

Status: exploratory.

- Rust remote agent as a single drop-in binary for easier distribution.
- Multi-user UI authentication and roles.
- Multi-control-plane or team deployments.
- Postgres support if SQLite becomes limiting.
- Advanced local-LLM eval judges with strict guardrails.
- Cross-node model synchronization planning.
- Host service remediation through a privileged local agent with explicit allowlists.
