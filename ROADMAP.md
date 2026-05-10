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

Status: shipped.

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
- Managed saved presets for common Eval Intelligence scopes, stored in Vantage settings with browser-local fallback.
- Visual pass-rate tone bands and compact trend signal rails so weak placements stand out without reading every row.

Future tuning:

- Add fuller chart visualizations once more real eval history accumulates.

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

Status: shipped.

- Demo mode with seeded public-safe sample nodes, runs, models, warnings, eval data, and routing policies.
- First-run onboarding checklist in the UI with stream, node, model, run, and routing checks.
- First-run setup wizard for token generation, node registry snippets, local Ollama endpoint config, and verification.
- Product screenshot guidance, public screenshot captures, and redaction rules for public media.
- Polished README positioning Vantage as a local AI command center.
- MIT license and open-source repository posture.
- Versioned changelog and release announcement template.
- Getting started guide for demo mode and real-node connection.
- GitHub issue templates and pull request template.
- Support guide and code of conduct.
- Security posture summary for local-first deployments.
- Static product microsite under `docs/product/`.
- Product-ready install walkthrough script and shot list under `docs/walkthrough/`.
- GitHub Pages workflow for publishing product docs and public walkthrough assets.
- Remotion-ready walkthrough video scaffold with manifest and screenshot references.

## Phase 6: Trust, Audit, And Security Hardening

Status: shipped.

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

Completed foundation:

- `/api/runs/export.bundle.json` signed audit bundle endpoint with canonical payload digest and HMAC-SHA256 signature metadata.
- Optional HMAC remote-agent auth using signed method/path/timestamp/nonce/body-hash messages.
- Agent replay protection through nonce cache and timestamp skew checks.
- Backend remote client support for bearer, HMAC, and `bearer_or_hmac` migration mode.
- Agent action allowlist covering read endpoints, capability checks, and eval attempts.
- Critical `agent_auth_failed` warnings when remote agent auth rejects collection.
- Token rotation helper script and documented rotation workflow.
- Explicit idempotency-key strategy documentation for current and future actions.
- Vulnerability reporting workflow, release security checklist, and mTLS research note.
- UI controls for downloading signed audit bundles next to CSV and JSON exports.
- Bundle verification helper script for checking payload digests and HMAC signatures.
- Persisted security-event rate counters for repeated auth failures and other security event aggregation.

## Phase 7: Integrations And Automation

Status: shipped.

- Webhook export for warnings, failed runs, and eval regressions.
- n8n integration examples.
- Slack, Discord, or email notification adapters.
- Scheduled report generation.
- API tokens for external tools.
- Import hooks for existing router logs.
- Optional Obsidian-friendly Markdown export for incident notes and eval reports.
- Plugin-style collector interface for adding new model runtimes beyond Ollama.

Completed foundation:

- Optional `VANTAGE_EXTERNAL_API_TOKEN` guard for `/api/integrations/*`.
- Normalized integration event export for warnings, failed runs, and failed eval attempts surfaced as regression candidates.
- Generic, Slack, Discord, and SMTP email dispatch adapters.
- Router-log import endpoint that stores external routing activity as durable `router_request` Run records.
- Obsidian-friendly Markdown operator report export.
- Built-in scheduled Markdown report worker for operators who do not use n8n or cron.
- Integration health endpoint and UI panel with configured target status, last dispatch, and security-event counters.
- Collector registry descriptor endpoint with the built-in Ollama collector registered.
- Richer collector descriptor contracts covering capabilities, endpoints, auth, config keys, and status.
- n8n examples for scheduled event pulls, webhook dispatch, router-log import, and Markdown report export.

## Later Research

Status: exploratory.

- Rust remote agent as a single drop-in binary for easier distribution.
- Multi-user UI authentication and roles.
- Multi-control-plane or team deployments.
- Postgres support if SQLite becomes limiting.
- Advanced local-LLM eval judges with strict guardrails.
- Cross-node model synchronization planning.
- Host service remediation through a privileged local agent with explicit allowlists.
