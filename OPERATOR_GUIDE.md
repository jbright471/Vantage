# Vantage Operator Guide

Vantage is a local-first AI control plane for operators running private models across multiple machines. This guide is the daily manual for reading the web UI, tuning the bootstrap configuration, and performing common operating tasks safely.

The examples below use `jedi` as an example control-plane node name and `bastet` as an example remote worker node name. Replace them with names from your own homelab.

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

Operational note: pruning runs inside the FastAPI process using the lifespan-managed background worker. It does not require Redis, Celery, or a separate container.

### Agent Authentication

| Setting | Current Default | Operator Guidance |
| --- | --- | --- |
| `agent_auth_token_env` | `VANTAGE_AGENT_SHARED_TOKEN` | Name of the environment variable that stores the shared token used for remote agent requests. Keep the token in `.env`, not in git. |

If a remote node starts returning unauthorized responses, confirm that both the control-plane backend and remote agent process are using the same token value.

## Navigating the UI

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

For remote workers such as example node `bastet`, the Remote Focus section shows agent endpoint health, Ollama status, host memory, CPU usage, GPU telemetry, and recent remote runs. GPU telemetry is especially useful for confirming whether a model host is actually available for local inference work.

Use `Refresh node` when you want Vantage to retry one collector pass for that node. The action creates a durable Run record and closes as `success` when Vantage verifies a fresh observation, or `failed` when the collector cannot complete. `submitted_unverified` remains reserved for actions that have been accepted but not independently confirmed.

Use `Quarantine node` when a node should stop receiving work while you investigate. Quarantine writes a runtime enabled-state override, disables the node in Vantage's configured registry, stops normal polling for that node, removes it from routing preference lists, and creates a durable `Run`. It does not stop Ollama, the remote agent, Docker containers, or any host-level service. Use `Re-enable node` when the host is ready to be observed again; routing preferences are not restored automatically.

Use `Disable endpoint` from Diagnostics when a local Ollama base URL is known bad or intentionally retired. Vantage writes a runtime endpoint override, skips that URL during local polling and capability checks, and creates a durable `Run`. This does not stop the Ollama service or edit `config/vantage.bootstrap.toml`. Remote worker endpoints must still be managed by the remote agent or host configuration.

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

### Models

The Models dashboard shows merged inventory across all registered nodes. Vantage does not assume that a model tag on one node is identical to the same tag on another node unless placement details prove it.

Key fields:

- `Model Name`: The observed model tag.
- `Node Placement`: Nodes where the model is currently visible.
- `Coverage`: Whether the model is on a single node or replicated.
- `Presence`: Whether visibility is node-local or cluster-wide.
- `Actions`: Capability checks against a specific node placement.

For replicated models across example nodes such as `jedi` and `bastet`, check placement before routing work. A model can exist on multiple nodes, but performance, VRAM, digest, and availability can still differ.

### Routing

The Routing dashboard shows preferred node order for each policy lane. It is a visibility and light-control surface for where classes of work should prefer to run.

Priority classes:

- `batch`: Long-running or less interactive work.
- `interactive`: Operator-facing or latency-sensitive work.
- `scheduled`: Automated jobs and recurring tasks.

Route order is evaluated from left to right. For example, `bastet -> jedi` means Vantage should prefer the example `bastet` worker first, then the example `jedi` node as the next option.

Changing route preference is a configuration-impacting action. Vantage requires a confirmation modal before saving the new preferred order. Treat routing edits as operational changes, not casual UI clicks.

The confirmation modal repeats target node state using text, color, and state icons. If the target node is stale, degraded, or otherwise not live and healthy, Vantage changes the final action to `Confirm override`. That lower-emphasis button is deliberate friction: read the warning and proceed only when the risk is intentional.

### Evals

The Eval Lab is the Phase 2 foundation for prompt-suite testing. The current surface lets operators create prompt suites, add prompt cases, queue eval attempt `Run` records for a selected model placement, execute queued runs, compare recent pass rates by model placement, identify low-performing cases, inspect recent scored responses, and create recurring schedules.

Treat eval scores as simple JSON-subset checks. A passing score means the response parsed as JSON and contained the expected key/value pairs for that case; it does not prove broader model quality.

Use `Inspect score` on a recent scored run when you need to see the exact case, target placement, score reason, missing or mismatched expected fields, response preview, and parsed response JSON.

Recurring eval schedules create queued eval attempts when due. Queue-only is the safe default. If `Auto-execute when due` is enabled for a schedule, Vantage immediately executes and scores each due eval case through the normal eval runner. Use auto-execute only for trusted suites and placements because it will trigger real model calls on the configured interval.

If an auto-executed schedule produces failed eval runs, Vantage creates an active `eval_schedule_failure` warning so the issue appears in the normal operator attention lane. A later clean scheduled execution resolves that warning automatically.

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
7. Use `Confirm override` only when you intentionally want to route toward a stale or degraded node.
8. Confirm only if the new order matches the intended operational change.
9. Watch for the saved message and verify the route order updates.
10. Monitor Runs and Nodes after the change to confirm the new preference does not push work toward a stale or overloaded node.

Safe operating rule: never promote a node that is stale, unreachable, missing the target model, or showing unhealthy GPU/agent telemetry unless you are intentionally testing failure behavior.

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

### Add a New Remote Worker Node

1. Deploy the lightweight Vantage agent on the remote Linux worker.
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
