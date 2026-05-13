# Vantage Operator Guide

Vantage is a local-first AI control plane for operators running private models across multiple machines. This guide is the daily manual for reading the web UI, tuning the bootstrap configuration, and performing common operating tasks safely.

The examples below use `control-plane` as an example control-plane node name and `remote-worker` as an example remote worker node name. Replace them with names from your own homelab.

## Core Concepts

### Truth Over Appearance

Vantage should report what it knows, not what looks reassuring. A node can be configured, previously healthy, and currently stale at the same time. The UI keeps those facts separate so operators can make decisions from real state instead of optimistic state.

When the UI shows uncertainty, treat that uncertainty as operational data. `submitted_unverified`, `stale`, `degraded`, and `unreachable` are not cosmetic labels. They are the control plane telling you the difference between a confirmed fact and an assumption.

### Observed State vs Configured State

Configured state is what Vantage is told to manage. It comes from `config/vantage.bootstrap.toml` and includes registered nodes, node roles, polling cadence, retention limits, and agent authentication settings.

Observed state is what Vantage has actually seen. It comes from polling local collectors, remote agents, Ollama endpoints, GPU telemetry, and run ingestion. Observed state can lag, fail, or disagree with configured state.

Use this rule when troubleshooting: configuration explains intent; observation proves current reality.

## Application Settings (Bootstrap Config)

Primary operator configuration lives in `config/vantage.bootstrap.toml`. Vantage reads this file at backend startup, so most changes require restarting the backend container or process.

### Polling and Freshness

| Setting | Current Default | Operator Guidance |
| --- | ---: | --- |
| `poll_interval_seconds` | `5` | How often Vantage polls nodes. Lower values make the UI feel more live but increase database writes and agent traffic. For a small homelab, `5` seconds is appropriate. |
| `stale_after_seconds` | `15` | How long since last observation before state is marked `stale`. Keep this several times larger than the poll interval to avoid false stale events during brief delays. |
| `unreachable_after_seconds` | `30` | How long since last observation before a node is treated as `unreachable`. Tune this based on network reliability and how quickly you want operator attention. |

Recommended relationship:

```text
poll_interval_seconds < stale_after_seconds < unreachable_after_seconds
```

### Snapshot Retention and Pruning

Vantage stores `NodeSnapshot` rows for node health, model visibility, Ollama state, and telemetry history. Snapshot pruning protects the SQLite database from growing indefinitely.

| Setting | Current Default | Operator Guidance |
| --- | ---: | --- |
| `snapshot_retention_hours` | `24` | Age-based retention window. Increase this if you want more short-term telemetry history. Decrease it if the database grows too quickly. |
| `snapshot_max_per_node` | `5000` | Count cap per node. This protects against high-frequency polling or noisy nodes. |
| `snapshot_min_per_node` | `1` | Safety floor. Vantage keeps at least this many snapshots per node even if they are older than the retention window. |
| `snapshot_prune_interval_seconds` | `900` | How often the background pruning worker runs. `900` seconds is 15 minutes. Lower only if snapshots accumulate unusually fast. |
| `eval_schedule_interval_seconds` | `60` | How often the background eval scheduler checks for due schedules. Keep this modest; schedules can queue work and may auto-execute trusted eval suites when explicitly enabled. |
| `report_schedule_interval_seconds` | `3600` | How often the optional scheduled report worker writes Markdown operator reports when `VANTAGE_REPORT_SCHEDULE_ENABLED=1`. |

Operational note: pruning runs inside the FastAPI process using the lifespan-managed background worker. It does not require Redis, Celery, or a separate container.

### Agent Authentication

| Setting | Current Default | Operator Guidance |
| --- | --- | --- |
| `agent_auth_token_env` | `VANTAGE_AGENT_SHARED_TOKEN` | Name of the environment variable that stores the shared token used for remote agent requests. Keep the token in `.env`, not in git. |

If a remote node starts returning unauthorized responses, confirm that both the control-plane backend and remote agent process are using the same token value.

For stronger node-to-node trust, set `VANTAGE_AGENT_AUTH_MODE=hmac` in the backend and agent environments. HMAC mode signs each request, checks timestamp freshness, and rejects replayed nonces. Use `VANTAGE_AGENT_ALLOWED_ACTIONS` to keep the agent least-privilege; the default allows read telemetry, capability checks, and eval attempts only.

Use `scripts/rotate-agent-token.ps1` when rotating `VANTAGE_AGENT_SHARED_TOKEN`. Rotation is a coordinated workflow: update the control-plane env, update every agent env, restart both sides, and verify `/health`.

### Health Checks

Use the backend health endpoints when starting, updating, or troubleshooting Vantage:

| Endpoint | Use |
| --- | --- |
| `/api/health` | Basic backward-compatible status check. |
| `/api/health/live` | Confirms the backend process is alive. |
| `/api/health/ready` | Confirms the backend can reach the configured database, see required tables, and load bootstrap config. |

Treat `/api/health/ready` as the deployment gate. If readiness returns HTTP `503`, inspect the failed check before trusting UI state or making routing changes.

### Production Packaging Settings

Production deployments use `docker-compose.prod.yml`, `.env.production`, and the `vantage_data` Docker volume by default. Development deployments use `docker-compose.yml`, `.env`, bind-mounted source code, Vite HMR, and FastAPI reload.

| Asset | Operator Use |
| --- | --- |
| `docker-compose.yml` | Local development with hot reload. |
| `docker-compose.prod.yml` | Production-style stack for Portainer or a Docker host. |
| `.env.example` | Development environment template with no real secrets. |
| `.env.production.example` | Production environment template with no real secrets. |
| `config/vantage.bootstrap.example.toml` | Public-safe node registry sample for releases and other operators. |
| `scripts/check-setup.ps1` | Preflight check for Docker, Compose config, token presence, auth mode, optional audit signing key, optional SQLite path, backend readiness, and remote-agent reachability. |
| `scripts/build-release.ps1` | Creates a shareable release zip and `SHA256SUMS.txt`. |
| `scripts/rotate-agent-token.ps1` | Generates a new high-entropy agent token and optionally updates an env file. |
| `scripts/verify-audit-bundle.py` | Verifies signed audit bundle payload digests and HMAC signatures. |

Production Compose requires `VANTAGE_AGENT_SHARED_TOKEN` to be supplied externally. Keep that value in `.env.production`, Portainer secrets, or Portainer environment variables. Do not paste real tokens into Compose YAML, screenshots, tickets, or documentation.

Production Compose runs Alembic migrations before Uvicorn starts. Back up SQLite before updates, especially before pulling a release that changes database models.

### Demo Mode

Set `VANTAGE_DEMO_MODE=1` when you want to evaluate Vantage, capture screenshots, or prepare a public walkthrough without exposing real node names, private IP addresses, local prompts, or filesystem paths.

Demo mode seeds:

- `demo-control` and `demo-worker` nodes.
- Synthetic GPU, CPU, memory, Ollama, and model placement data.
- Example success, failed, and `SUBMITTED_UNVERIFIED` run records.
- Demo eval suite and schedule records.
- Demo routing policies for interactive and batch lanes.
- A warning record showing degraded-node handling.

Keep demo mode disabled for production unless you are intentionally running a public demo instance. For a frozen screenshot environment, combine demo mode with `VANTAGE_ENABLE_BACKGROUND_POLLING=0`.

## Navigating the UI

### First-Run Onboarding

The onboarding panel appears in the command shell until dismissed in browser-local storage. It checks whether the API stream is live, nodes are registered, models are observed, runs are auditable, and routing policy is visible. Use it as the first five-minute checklist for new installs or public demo instances.

The `Read operator guide` button opens this guide in the slide-out drawer so you can keep the live dashboard visible while reading setup guidance.

Use `Launch setup wizard` for first-run configuration. The wizard generates a shared-token `.env` line, a `config/vantage.bootstrap.toml` node block, local Ollama endpoint settings, and restart/verification commands. It does not write files or store secrets; the operator still reviews and applies each generated snippet deliberately.

### Command Header and Warnings

The command header gives the fastest read on whether Vantage needs operator attention. The attention ribbon summarizes degraded nodes, stale nodes, active warnings, and pending runs without requiring you to scan every section first.

Active warnings appear in a compact warning strip below the fleet summary. Vantage shows the first two warnings by default to avoid pushing live telemetry below the fold. Use the `+N more` control when you need to expand the list during drift review.

Use `Acknowledge` when you have reviewed a warning and want it removed from the active operator queue. Acknowledgement does not delete history; Vantage stores the warning as acknowledged and creates an audit run for the action. If the underlying condition clears later, reconciliation resolves the warning.

Color semantics are intentionally strict:

- Green indicates current healthy state.
- Amber indicates stale observations, degraded health, config drift, or other warning-level conditions.
- Red is reserved for hard failure states such as unreachable nodes and failed runs.

### Nodes

The Nodes dashboard shows machine health across the local fleet. Use it first when something feels wrong.

Freshness labels:

- `LIVE`: Vantage has a current observation for the node.
- `STALE`: Vantage has seen the node before, but the last observation is older than `stale_after_seconds`.
- `UNREACHABLE`: The node has exceeded `unreachable_after_seconds` without a fresh observation.

Health and freshness are separate. A node can have a last-known healthy snapshot but still be stale or unreachable. Trust the freshness label when deciding whether the data is current.

Each node card includes a heartbeat freshness meter and monospace signal age. The meter fades as freshness decays so stale data looks physically weaker before a node becomes unreachable. Treat the heartbeat as a visual confidence indicator, not just decoration.

For remote workers such as example node `remote-worker`, the Remote Focus section shows agent endpoint health, Ollama status, host memory, CPU usage, GPU telemetry, and recent remote runs. GPU telemetry is especially useful for confirming whether a model host is actually available for local inference work.

Use `Refresh node` when you want Vantage to retry one collector pass for that node. The action creates a durable Run record and closes as `success` when Vantage verifies a fresh observation, or `failed` when the collector cannot complete. `submitted_unverified` remains reserved for actions that have been accepted but not independently confirmed.

Use `Quarantine node` when a node should stop receiving work while you investigate. Quarantine writes a runtime enabled-state override, disables the node in Vantage's configured registry, stops normal polling for that node, removes it from routing preference lists, and creates a durable `Run`. It does not stop Ollama, the remote agent, Docker containers, or any host-level service. Use `Re-enable node` when the host is ready to be observed again; routing preferences are not restored automatically.

Use `Disable endpoint` from Diagnostics when a local Ollama base URL is known bad or intentionally retired. Vantage writes a runtime endpoint override, skips that URL during local polling, capability checks, and eval execution, and creates a durable `Run`. This does not stop the Ollama service or edit `config/vantage.bootstrap.toml`. Remote worker endpoints must still be managed by the remote agent or host configuration.

Use `Diagnose` when a node is degraded, stale, unreachable, or has observed subsystem errors. The diagnostics drawer explains the primary issue from current observed state, lists endpoint-level failures such as Ollama connection errors, and provides suggested remediation steps. Diagnostics do not mutate configuration or restart services; they are the safe bridge between visibility and future allowlisted remediation actions.

### Runs

Runs are the durable audit log for operator actions, capability checks, remote agent activity, and model-related events. Use Runs when you need to answer: what happened, when, on which node, and with what metadata?

Important statuses:

- `success`: The run completed successfully.
- `failed`: The run failed and should be investigated.
- `running`: The run is active or currently observed as loaded/running.
- `submitted_unverified`: Vantage submitted the action but has not verified the final outcome.
- `timed_out` or `abandoned`: The run did not produce a clean terminal signal in the expected window.

The table shows recent runs by default. Use `View All Runs` to expand the list in place. Click a row to open the run details drawer, which includes the full Run ID, exact timestamps, observed metadata JSON, and the full run record JSON.

Use exports when you need external review:

- `Export CSV`: Best for spreadsheet inspection and operator handoff.
- `Export JSON`: Best for preserving nested metadata, traces, model details, and future SIEM-style ingestion.
- `Export signed bundle`: Best for tamper-evident evidence when `VANTAGE_AUDIT_SIGNING_KEY` is configured. The bundle includes JSON payload data, a SHA-256 payload digest, and HMAC signature metadata.

### Models

The Models dashboard shows merged inventory across all registered nodes. Vantage does not assume that a model tag on one node is identical to the same tag on another node unless placement details prove it.

Key fields:

- `Model Name`: The observed model tag.
- `Node Placement`: Nodes where the model is currently visible.
- `Coverage`: Whether the model is on a single node or replicated.
- `Presence`: Whether visibility is node-local or cluster-wide.
- `Actions`: Capability checks against a specific node placement.

For replicated models across example nodes such as `control-plane` and `remote-worker`, check placement before routing work. A model can exist on multiple nodes, but performance, VRAM, digest, and availability can still differ.

### Routing

The Routing dashboard shows preferred node order for each policy lane. It is a visibility and light-control surface for where classes of work should prefer to run.

Priority classes:

- `batch`: Long-running or less interactive work.
- `interactive`: Operator-facing or latency-sensitive work.
- `scheduled`: Automated jobs and recurring tasks.

Route order is evaluated from left to right. For example, `remote-worker -> control-plane` means Vantage should prefer the example `remote-worker` worker first, then the example `control-plane` node as the next option.

Operators can create model-specific routing lanes from the policy editor. A model-specific lane combines priority class, target model, preferred nodes, optional eval pass-rate threshold, and explicit failover allowances. Leave failover allowances off unless you intentionally want the rule to consider degraded, stale, or unreachable nodes.

Changing route preference is a configuration-impacting action. Vantage requires a confirmation modal before saving the new preferred order. Treat routing edits as operational changes, not casual UI clicks.

The confirmation modal repeats target node state using text, color, and state icons. It also runs a dry-run simulation against current observed node state before saving. The simulation explains which node would be selected, which nodes would be skipped or rejected, and why. If the target node is stale, degraded, or otherwise not live and healthy, Vantage changes the final action to `Confirm override`. That lower-emphasis button is deliberate friction: read the warning and proceed only when the risk is intentional.

Use `History` on a routing row to inspect create, update, and delete events for that rule. Route history is the operator-facing audit trail for policy preference changes.

### Evals

The Eval Lab is the Phase 2 surface for prompt-suite testing. Operators can create, edit, duplicate, import, export, and clean up prompt suites; add or duplicate prompt cases; queue eval attempt `Run` records for a selected model placement; execute queued runs; compare recent pass rates; inspect scored responses; create recurring schedules; and review deterministic Eval Intelligence summaries.

Eval scores are auditable checks, not broad model-quality guarantees. Deterministic score types include `json_subset`, `exact_match`, `contains`, `regex`, `numeric_threshold`, and `json_schema`. The guarded `llm_judge` score type can ask a selected local model to judge a candidate response, but it must return strict JSON and Vantage fails the run closed if the judge output is malformed.

Use the guided score controls when they are available. For `llm_judge`, Vantage renders an operator workbench for judge placement, pass threshold, context budget, and rubric, then writes the generated contract into `Score config JSON`. Keep the JSON visible as the audit/debug escape hatch; the guided controls are the safer daily path.

Use `Score config JSON` for score-type-specific settings:

- `exact_match` and `contains`: set `expected_text`.
- `regex`: set `pattern`.
- `numeric_threshold`: set `json_path`, `operator`, and `value`.
- `json_schema`: set `required` and optional `properties` with `const` values.
- `llm_judge`: set `judge_model_name`, `judge_node_id`, `rubric`, and optional `pass_threshold` and `max_context_chars`.
- `json_subset`: usually uses `Expected JSON` and can leave score config empty.

Example guarded judge config:

```json
{
  "judge_model_name": "example-judge-model:latest",
  "judge_node_id": "control-plane",
  "rubric": "Pass only when the answer is accurate, concise, and follows the requested format.",
  "pass_threshold": 0.8
}
```

Treat `llm_judge` results as advisory-but-auditable. The judge model receives only a bounded JSON context containing the rubric, candidate prompt, candidate response, expected JSON, and pass threshold. It is instructed not to follow candidate text as instructions. Vantage accepts only JSON with `passed`, `score`, `reason`, and optional `evidence`, then stores the judge decision inside the eval Run metadata.

Use `Inspect score` on a recent scored run when you need to see the exact case, target placement, score reason, missing or mismatched expected fields, response preview, and parsed response JSON.

Recurring eval schedules create queued eval attempts when due. Queue-only is the safe default. Use `Queue now` on an enabled schedule when you want to run the schedule immediately without waiting for the next due time. Manual queueing creates normal eval `Run` records, records `last_queued_at`, and does not advance `next_run_at`.

If `Auto-execute when due` is enabled for a schedule, Vantage immediately executes and scores each due eval case through the normal eval runner. Use auto-execute only for trusted suites and placements because it will trigger real model calls on the configured interval.

If an auto-executed schedule produces failed eval runs, Vantage creates an active `eval_schedule_failure` warning so the issue appears in the normal operator attention lane. A later clean scheduled execution resolves that warning automatically.

Use `Set baseline` from a scored run to pin a minimum acceptable pass rate for that suite, model, and node. Baselines are stored with the suite metadata and compared against recent scored runs. If current pass rate drops below the baseline, the Eval Lab surfaces a regression alert.

Eval Intelligence panels summarize the same durable run data from several angles:

- Placement comparison shows pass rates by model and node.
- Model report rolls scored runs up by model name.
- Trends visualize and list recent scored runs by day, model, and node.
- Lowest passing cases highlight weak prompt cases.
- Mixed-result cases identify flaky cases with both passes and failures.
- Failure clustering groups repeated failures by reason and missing or mismatched fields.
- Schedule health shows the latest scheduler execution counts and failures.

Use `Eval intelligence window` controls when you need to scope the analysis. The time-window selector changes the pass-rate window used by score history. The placement filter narrows charts, regressions, schedules, exports, and assisted summaries to a specific model/node pair. Flakiness sensitivity controls how mixed-result cases are surfaced, and failure-cluster minimum controls how many matching failures are required before a cluster is treated as repeated. Use `Save preset` for managed shortcuts to common scopes, such as a seven-day flaky-case review or a single-placement regression check. Presets are stored in Vantage settings with a browser-local fallback if the settings API is unavailable.

Use `Generate summary` when you want an optional local model to explain the current eval signals in operator language. This is a manual action only. Vantage sends a compact eval snapshot using the active Eval Intelligence scope to the selected model placement, stores the result as an `eval_assisted_summary` Run, and displays the returned Markdown in the Eval Lab. Treat it as advisory: the deterministic score tables, baselines, and run metadata remain the source of truth.

Lifecycle cleanup is deliberately guarded. You can delete schedules and individual prompt cases directly from Eval Lab. Prompt suite deletion is available only when the suite has no remaining cases and no active schedules. Cleanup does not delete historical eval `Run` records, so scored runs and audit evidence remain available after a suite or case is removed from the active definition list.

Use `Export eval CSV` for spreadsheet review and `Export eval JSON` when you need nested score details, baselines, trend rows, failure clusters, and regression data. Eval history exports inherit the active Eval Intelligence scope. Suite-level export/import is available through the eval API for sharing prompt packs across Vantage installs.

### Integrations

The Integrations API is for n8n, scripts, local notification receivers, and incident-note workflows. It is intentionally API-first rather than UI-first so Vantage remains useful even when the web UI is closed.

Set `VANTAGE_EXTERNAL_API_TOKEN` before exposing `/api/integrations/*` to automation tools. Use `Authorization: Bearer <token>` or `X-Vantage-Api-Key: <token>`.

Key endpoints:

- `/api/integrations/events`: normalized warnings, failed runs, and eval-regression candidates.
- `/api/integrations/webhooks/dispatch`: opt-in dispatch for generic, Slack, Discord, and SMTP email payloads.
- `/api/integrations/import/router-runs`: imports external router activity as durable `router_request` Runs.
- `/api/integrations/reports/operator.md`: Markdown report for Obsidian, incident notes, or handoff.
- `/api/integrations/health`: integration configuration health, configured targets, last dispatch status, and security-event counters.
- `/api/integrations/collectors`: registered collector descriptors, starting with the built-in Ollama collector.

Use n8n or cron when you want external orchestration. If you do not use either, enable `VANTAGE_REPORT_SCHEDULE_ENABLED=1` and set `VANTAGE_REPORT_OUTPUT_DIR` so Vantage writes scheduled Markdown reports from its own background worker.

The Integration Health panel in the app shows whether an external API token is configured, which dispatch targets are present, the latest dispatch result, and repeated security-event counters such as agent auth failures. Treat missing integration health as a signal that the backend is unavailable or the health endpoint cannot be reached.

### Docs Drawer

The `Docs` button in the application header opens this Operator Guide as live Markdown from `/api/docs/operator-guide.md`. The drawer is designed for quick reference while the dashboard remains visible behind it.

If the guide fails to load, verify the backend is running and `/api/health/ready` returns `ok`. The drawer reads the repository-root `OPERATOR_GUIDE.md`, so documentation updates are available in the app after the backend can read the updated file.

## Daily Operations

### Audit a Failed Capability Check Using the Run ID

1. Open the Runs dashboard.
2. Select the `Failed` filter.
3. Find the failed capability check and copy the short or full Run ID.
4. Click the row to open the Run Details drawer.
5. Review `Status`, `Target Node`, `Started`, `Ended`, and `Observed metadata (JSON)`.
6. Use `Copy Payload` if you need to paste the metadata into a ticket, note, or debugging session.
7. Cross-check the target node in Nodes for freshness, Ollama status, GPU telemetry, and recent remote runs.
8. Open `Diagnose` on the target node if it is degraded, stale, or showing endpoint errors.
9. Use `Refresh node` to retry one collector pass and confirm whether the condition is still present.
10. If the failure is node-specific, run the same model capability check from Models on another placement.

Interpretation guide:

- Failure on one node usually points to node health, model placement, or model runtime state.
- Failure on all nodes usually points to model compatibility, prompt format, routing assumptions, or shared Ollama/API behavior.
- `submitted_unverified` is not success. Wait for a later observation or inspect the relevant node before treating the action as complete.

### Safely Override a Routing Policy

1. Open the Routing dashboard.
2. Identify the priority class: `batch`, `interactive`, or `scheduled`.
3. Review the current route order.
4. Click `Prefer <node>` for the node that should become first choice.
5. Read the confirmation modal carefully.
6. Check the target node state tokens and warning copy.
7. Review the route simulation. Confirm that selected, skipped, and rejected nodes match the intended operational change.
8. Use `Confirm override` only when you intentionally want to route toward a stale or degraded node.
9. Confirm only if the new order matches the intended operational change.
10. Watch for the saved message and verify the route order updates.
11. Monitor Runs and Nodes after the change to confirm the new preference does not push work toward a stale or overloaded node.

Safe operating rule: never promote a node that is stale, unreachable, missing the target model, or showing unhealthy GPU/agent telemetry unless you are intentionally testing failure behavior.

### Create a Model-Specific Routing Lane

1. Open the Routing dashboard.
2. In `Policy editor`, enter a unique `Rule ID`.
3. Select `batch`, `interactive`, or `scheduled`.
4. Enter the model tag, such as `qwen3.5:27b`.
5. Enter preferred nodes as a comma-separated list, such as `remote-worker, control-plane`.
6. Optionally set `Min eval pass rate` as a decimal between `0` and `1`.
7. Leave degraded, stale, and unreachable allowances disabled unless you are intentionally testing failover behavior.
8. Click `Create rule`.
9. Use `Prefer <node>` on the new row and read the dry-run result before saving future preference changes.

### Review Route History

1. Open the Routing dashboard.
2. Click `History` on the rule you want to audit.
3. Review the latest create, update, and delete events.
4. Cross-check the Runs dashboard if the route change was part of a broader incident or remediation workflow.

### Quarantine a Problem Node

1. Open the Nodes dashboard.
2. Open `Diagnose` and confirm the issue is node-specific.
3. Click `Quarantine node`.
4. Read the confirmation modal. The action changes runtime-managed configured state and removes the node from routing preference lists.
5. Click `Confirm quarantine` only if the node should stop receiving new work.
6. Open Runs and verify the quarantine action closed as `success`.
7. Investigate or repair the host outside Vantage.
8. When ready, click `Re-enable node`.
9. Wait for the node to become `LIVE`.
10. Re-add the node to routing only after telemetry and model inventory look correct.

### Disable a Known-Bad Local Ollama Endpoint

1. Open the Nodes dashboard.
2. Open `Diagnose` on the local control-plane node.
3. Review the observed endpoint error and confirm the endpoint is known bad or intentionally retired.
4. Click `Disable endpoint`.
5. Read the confirmation modal. This action changes runtime-managed collection behavior but does not stop Ollama.
6. Click `Confirm disable endpoint`.
7. Open Runs and verify the endpoint action closed as `success`.
8. Use `Refresh node` to verify the node can collect without the disabled endpoint.
9. Edit `config/vantage.bootstrap.toml` later if the endpoint should be permanently removed from bootstrap config.

### Manually Queue an Eval Schedule

1. Open Eval Lab.
2. Create or locate an enabled recurring eval schedule.
3. Confirm the suite, target model, target node, interval, and mode are correct.
4. Click `Queue now`.
5. Verify the schedule row shows a `Last queued` timestamp.
6. Review Recent queued attempts for the new eval `Run` records.
7. Execute the queued runs manually unless the schedule was intentionally configured for auto-execution.
8. Check Runs if queueing fails or the eval result needs full metadata review.

### Clean Up Eval Definitions

1. Open Eval Lab.
2. Delete stale recurring schedules first.
3. Delete prompt cases that should no longer be part of future eval attempts.
4. Confirm the suite row shows `No cases`.
5. Delete the prompt suite only after all cases and schedules are gone.
6. Use Runs if you need to review historical eval outcomes; cleanup does not remove those records.

### Review an Eval Regression

1. Open Eval Lab.
2. Check the intelligence summary for baseline or failure-cluster warnings.
3. Review `Baseline misses` to identify the suite, model, node, current pass rate, and minimum pass rate.
4. Open `Recent scored runs` and inspect failed runs for that suite and placement.
5. Check `Failure clustering` for repeated score reasons or missing fields.
6. Check `Mixed-result cases` to determine whether the issue is flaky or consistently failing.
7. Compare the same suite on another placement in `Placement comparison`.
8. Optionally generate a local model summary if you want a concise hypothesis list before deeper inspection.
9. Export eval JSON before making larger prompt or model changes if you need a durable incident artifact.

### Add a New Remote Worker Node

1. Deploy the lightweight Vantage agent on the remote Linux worker with `deploy/agent/install.sh`.
2. Configure the agent to use the same shared token referenced by `agent_auth_token_env`.
3. Confirm the agent exposes the expected endpoints, including health, GPU, models, and runs.
4. Add a new `[[nodes]]` entry to `config/vantage.bootstrap.toml`.

Example:

```toml
[[nodes]]
node_id = "new-worker"
display_name = "New Worker"
base_url = "http://<remote-agent-ip>:9110"
role = "remote"
enabled = true
```

5. Restart the Vantage backend container or process so the bootstrap config is reloaded.
6. Open Nodes and confirm the new worker appears.
7. Wait for the node to become `LIVE`.
8. Confirm GPU telemetry and observed model count.
9. Open Models and confirm expected model placements.
10. Update Routing only after the node is live and model inventory is visible.

If the node appears but remains stale or unreachable, check network reachability, firewall rules, the agent service, the shared token, and the configured `base_url`.

### Verify Backend Readiness After Restart

1. Restart the backend container, service, or development stack.
2. Call `/api/health/live` to confirm the process is running.
3. Call `/api/health/ready` to confirm the configured database, schema tables, and bootstrap config are usable.
4. Open the UI only after readiness reports `ok`.
5. If readiness fails, check Docker, Portainer, or systemd logs for JSON records from the backend.

### Run a Production Setup Check

1. Set `VANTAGE_AGENT_SHARED_TOKEN` in the current shell or `.env.production`.
2. Run `scripts/check-setup.ps1`.
3. Pass `-RemoteAgentUrl http://<remote-agent-ip>:9110` when you want the checker to verify a worker agent.
4. Pass `-SqlitePath <path-to-vantage.sqlite3>` when you use a host-mounted SQLite path instead of the default Docker volume.
5. Treat failures as deployment blockers. Warnings are usually optional checks, such as a remote agent URL not being supplied.

Example:

```powershell
$env:VANTAGE_AGENT_SHARED_TOKEN = "<same-token-as-control-plane>"
.\scripts\check-setup.ps1 `
  -ComposeFile docker-compose.prod.yml `
  -RemoteAgentUrl http://<remote-agent-ip>:9110 `
  -ControlPlaneUrl http://<control-plane-host>:8000
```

### Back Up SQLite Before Updating

1. Stop write-heavy activity such as eval batches or manual remediation.
2. Use the SQLite backup API command from `OPERATIONS.md`, not a raw file copy while Vantage is writing.
3. Store the backup outside the active Docker volume.
4. Deploy the update or release bundle.
5. Verify `/api/health/ready`.
6. Keep the backup until the new deployment has been stable through normal polling and UI use.

### Use Postgres Instead Of SQLite

SQLite is the default and recommended database for a single local operator. Use Postgres only when the run ledger, snapshot history, backup requirements, or future multi-process deployment needs exceed SQLite.

1. Install the optional Postgres driver when running outside the bundled Docker image: `pip install "vantage[postgres]"`.
2. Set `VANTAGE_DATABASE_URL=postgresql+psycopg://vantage:<password>@<postgres-host>:5432/vantage`.
3. Run migrations before starting normal polling or eval schedules.
4. Call `/api/health/ready` and confirm the database and schema checks pass.
5. Do not treat Postgres alone as multi-control-plane support. Multiple active control planes still require ownership leases and control-plane identity before they are safe.

### Verify a Signed Audit Bundle

1. Open Runs.
2. Click `Export signed bundle`.
3. Store the downloaded bundle with the related incident notes or release evidence.
4. Set `VANTAGE_AUDIT_SIGNING_KEY` in a local shell that has access to the verification key.
5. Run:

```powershell
python scripts/verify-audit-bundle.py <path-to-bundle.json>
```

6. Confirm `verified` is `true`, the `payload_sha256` matches the bundle, and the `key_id` is the expected signing key label.
7. Treat a failed verification as evidence that the file was edited, truncated, signed with a different key, or exported without matching metadata.

### Configure Email Dispatch and Scheduled Reports

1. Set `VANTAGE_EXTERNAL_API_TOKEN` before connecting scripts or automation.
2. Configure SMTP values in `.env` or `.env.production`: `VANTAGE_EMAIL_SMTP_HOST`, `VANTAGE_EMAIL_SMTP_PORT`, `VANTAGE_EMAIL_SMTP_USERNAME`, `VANTAGE_EMAIL_SMTP_PASSWORD`, `VANTAGE_EMAIL_FROM`, `VANTAGE_EMAIL_TO`, and `VANTAGE_EMAIL_USE_TLS`.
3. Restart the backend so environment variables are loaded.
4. Open the Integration Health panel and confirm the email target appears as configured.
5. Send a test dispatch through `/api/integrations/webhooks/dispatch` with adapter `email`.
6. If you want Vantage to write reports without n8n or cron, set `VANTAGE_REPORT_SCHEDULE_ENABLED=1` and `VANTAGE_REPORT_OUTPUT_DIR=<report-directory>`.
7. Confirm new Markdown reports appear in the output directory at the cadence set by `report_schedule_interval_seconds`.

### Deploy Through Portainer

1. Review `PORTAINER.md`.
2. Make sure `VANTAGE_AGENT_SHARED_TOKEN` is configured as a Portainer environment variable or secret.
3. Deploy `docker-compose.prod.yml` as the stack definition.
4. Confirm backend and frontend containers become `healthy`.
5. Open the UI and verify Nodes, Runs, Models, Routing, Evals, and Docs load.
6. Watch backend logs while Alembic runs during startup.

### Build a Release Bundle

1. Confirm backend tests, frontend tests, and frontend build pass.
2. Run `scripts/build-release.ps1 -Version <version>`.
3. Inspect `dist/releases/vantage-<version>.zip`.
4. Confirm the generated bundle contains public-safe config and does not include `.env`, `.env.production`, SQLite databases, node modules, or local logs.
5. Share the zip with `SHA256SUMS.txt` so operators can verify the artifact.

### Respect the Local Node Agent Boundary

Do not make the Docker backend privileged to restart host services or scrape privileged host state. If Vantage needs host-level remediation on the control-plane machine, use a systemd-managed local node agent with authenticated, allowlisted actions.

The current local node-agent document is a boundary and extension plan, not a broad host-control feature. Host-level actions should not be added until their contracts, confirmations, audit `Run` records, and tests are explicit.

## Operator Checklist

Use this quick sequence during daily checks:

1. Confirm the header stream status is `Live`.
2. Check the attention ribbon for degraded nodes, stale nodes, warnings, and pending runs.
3. Expand the warning strip if more than two warnings are active.
4. Acknowledge warnings only after reviewing their summary and affected node.
5. Confirm Nodes are `LIVE` and not merely last-known healthy.
6. Use `Diagnose` for degraded, stale, unreachable, or subsystem-error nodes.
7. Check Remote Focus for GPU telemetry and Ollama status.
8. Review Runs for new `failed`, `submitted_unverified`, `timed_out`, or `abandoned` records.
9. Confirm Models show expected placements before running capability checks.
10. Check Eval Lab for prompt-suite readiness when comparing model behavior.
11. Review Routing before changing where work is preferred.
12. Export Runs as CSV or JSON before deeper incident review.
13. Check `/api/health/ready` before and after deployments.
14. Back up SQLite before production updates.
15. Use the Docs drawer when you need the current guide without leaving the dashboard.
