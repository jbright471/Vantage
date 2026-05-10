# Integrations

Vantage integrations are pull-first and local-first. External tools can read normalized events, import router logs, dispatch webhooks, and export Markdown reports without becoming required dependencies for the control plane.

## Authentication

Set an external API token before exposing integration endpoints to scripts or automation tools:

```text
VANTAGE_EXTERNAL_API_TOKEN=<high-entropy-token>
```

Then call integration endpoints with either header:

```http
Authorization: Bearer <token>
X-Vantage-Api-Key: <token>
```

If `VANTAGE_EXTERNAL_API_TOKEN` is empty, integration endpoints are open to the same network surface as the backend. That is convenient for development but not recommended for shared deployments.

## Event Export

```http
GET /api/integrations/events
```

Returns normalized events for:

- active or acknowledged warnings
- failed runs
- failed eval attempts surfaced as `eval_regression` candidates

Useful query params:

```text
include_warnings=true
include_failed_runs=true
include_eval_regressions=true
limit=50
```

## Webhook Dispatch

```http
POST /api/integrations/webhooks/dispatch
```

Supported adapters:

- `generic`: posts the full Vantage event envelope
- `slack`: posts a compact Slack-compatible text payload
- `discord`: posts a compact Discord embed payload
- `email`: sends a compact text report through explicit SMTP configuration

Configure targets through environment variables:

```text
VANTAGE_WEBHOOK_URL=
VANTAGE_SLACK_WEBHOOK_URL=
VANTAGE_DISCORD_WEBHOOK_URL=
VANTAGE_WEBHOOK_ALLOWED_HOSTS=
VANTAGE_EMAIL_SMTP_HOST=
VANTAGE_EMAIL_SMTP_PORT=587
VANTAGE_EMAIL_SMTP_USERNAME=
VANTAGE_EMAIL_SMTP_PASSWORD=
VANTAGE_EMAIL_FROM=
VANTAGE_EMAIL_TO=
VANTAGE_EMAIL_USE_TLS=1
```

Use `VANTAGE_WEBHOOK_ALLOWED_HOSTS` to restrict dispatch destinations by hostname.

Successful dispatch attempts are recorded as integration health state so operators can see the latest adapter, event count, status, and timestamp in the UI.

## Integration Health

```http
GET /api/integrations/health
```

Returns a public-safe health envelope for the web UI:

- whether `VANTAGE_EXTERNAL_API_TOKEN` is configured
- whether webhook host allowlisting is configured
- configured target status for generic, Slack, Discord, and email adapters
- latest dispatch status
- persisted security-event counters such as repeated agent auth failures

## Router Log Import

```http
POST /api/integrations/import/router-runs
```

Imports external router logs as durable `Run` records with:

- `source_type = router`
- `detail_type = router_request`
- raw source payload preserved in `metadata_json.raw_router_log`

Duplicate `run_id` values are skipped instead of creating duplicate audit records.

## Markdown Reports

```http
GET /api/integrations/reports/operator.md
```

Returns an Obsidian-friendly Markdown report with:

- fleet summary
- active warnings
- recent failed runs
- recent eval runs
- blank operator notes section

Operators who do not use n8n or cron can enable the built-in scheduled report worker:

```text
VANTAGE_REPORT_SCHEDULE_ENABLED=1
VANTAGE_REPORT_OUTPUT_DIR=reports
```

The worker uses `report_schedule_interval_seconds` from `config/vantage.bootstrap.toml` and writes timestamped Markdown reports to the configured output directory.

## Collector Registry

```http
GET /api/integrations/collectors
```

Lists built-in and future collector descriptors. The first built-in collector is `ollama`. Descriptors include runtime, capabilities, endpoints, auth mode, configuration keys, and whether the collector is currently built in.
