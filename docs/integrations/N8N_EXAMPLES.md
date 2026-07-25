# n8n Examples

These examples assume Vantage is reachable from n8n on a trusted LAN or VPN and `VANTAGE_EXTERNAL_API_TOKEN` is configured.

## Pull Events On A Schedule

1. Add a Schedule Trigger node.
2. Add an HTTP Request node.
3. Set method to `GET`.
4. Set URL:

```text
http://<vantage-host>:5173/api/integrations/events?limit=50
```

5. Add header:

```text
X-Vantage-Api-Key: <external-api-token>
```

6. Filter events by `event_type`, `severity`, or `node_id`.

## Send Warnings To Slack Or Discord

Use Vantage's built-in webhook dispatcher when you want Vantage to format the notification:

```http
POST http://<vantage-host>:5173/api/integrations/webhooks/dispatch
```

Body:

```json
{
  "adapter": "slack",
  "include_warnings": true,
  "include_failed_runs": true,
  "include_eval_regressions": true,
  "limit": 10
}
```

Set `VANTAGE_SLACK_WEBHOOK_URL` in the Vantage backend environment.
The target hostname must be present in `VANTAGE_WEBHOOK_ALLOWED_HOSTS`. For a private RFC1918/ULA receiver, also set `VANTAGE_WEBHOOK_ALLOW_PRIVATE_NETWORKS=1`.

## Import Router Logs

If an external local AI router emits logs, normalize them in n8n and post:

```http
POST http://<vantage-host>:5173/api/integrations/import/router-runs
```

Body:

```json
{
  "entries": [
    {
      "run_id": "router-20260510-0001",
      "node_id": "gpu-worker-a",
      "model_name": "qwen:latest",
      "status": "success",
      "summary": "Router selected gpu-worker-a",
      "started_at": "2026-05-10T01:00:00Z",
      "duration_ms": 1240,
      "metadata_json": {
        "priority_class": "interactive",
        "route_reason": "lowest_latency"
      }
    }
  ]
}
```

Vantage stores each entry as a durable `router_request` Run.

## Export Markdown To Obsidian

Use an HTTP Request node:

```text
GET http://<vantage-host>:5173/api/integrations/reports/operator.md
```

Then write the response body into an Obsidian vault folder using your preferred file integration.
