# Remote Agent Contract

The Vantage remote agent is a lightweight FastAPI service intended to run on Linux worker nodes.

The examples below use `jedi` as an example control-plane node name and `bastet` as an example remote worker node name. Replace them with names from your own homelab.

Example remote agent endpoint:

```text
http://<remote-agent-ip>:9110
```

## Authentication

When `VANTAGE_AGENT_SHARED_TOKEN` is set on the agent, every endpoint requires:

```http
Authorization: Bearer <token>
```

Missing or invalid tokens return:

```json
{
  "detail": "Agent authentication required"
}
```

with HTTP status `401`.

If the token is not configured, the agent allows unauthenticated access. Production and shared homelab deployments should configure the token.

## GET /health

Returns basic agent health.

### Response

```json
{
  "status": "ok",
  "node_id": "bastet"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Agent health status. Current healthy value is `ok`. |
| `node_id` | string | Stable node identifier reported by the agent. |

## GET /gpu

Returns GPU telemetry collected from `nvidia-smi`.

### Response

```json
{
  "gpus": [
    {
      "name": "NVIDIA GeForce RTX 3090",
      "memory_total_mb": 24576,
      "temperature_c": 57
    }
  ]
}
```

| Field | Type | Description |
| --- | --- | --- |
| `gpus` | array | GPU records for the node. |
| `gpus[].name` | string | GPU name from `nvidia-smi`. |
| `gpus[].memory_total_mb` | integer | Total GPU memory in MB. |
| `gpus[].temperature_c` | integer | Current GPU temperature in Celsius. |

## GET /models

Returns model inventory discovered from configured Ollama endpoints.

### Response

```json
{
  "models": [
    {
      "model_name": "gemma4:e4b",
      "model_digest": "sha256-or-ollama-digest",
      "available": true
    }
  ]
}
```

| Field | Type | Description |
| --- | --- | --- |
| `models` | array | Observed models on this node. |
| `models[].model_name` | string | Ollama model tag. |
| `models[].model_digest` | string or null | Ollama digest when available. |
| `models[].available` | boolean | Whether the model was visible during this collection. |

## GET /runs

Returns recent agent-side operational events.

Current examples include loaded Ollama models, capability-check runs, and eval-attempt runs.

### Response

```json
{
  "runs": [
    {
      "run_id": "086af75060fb0680c77aad586646becf8d7e80b2c01bd4c096e724e27ce3e6e8",
      "source_type": "remote_agent",
      "detail_type": "ollama_loaded_model",
      "source_id": "ollama-ps:http://<ollama-host>:11435:gemma4:e4b",
      "node_id": "bastet",
      "model_name": "gemma4:e4b",
      "action_type": "infer",
      "status": "running",
      "started_at": "2026-04-23T15:12:23.118701Z",
      "ended_at": null,
      "duration_ms": null,
      "summary": "Model gemma4:e4b is currently loaded on bastet",
      "metadata_json": {
        "base_url": "http://<ollama-host>:11435"
      }
    }
  ]
}
```

| Field | Type | Description |
| --- | --- | --- |
| `run_id` | string | Stable or generated run identifier. |
| `source_type` | string | Source category such as `remote_agent` or `inference`. |
| `detail_type` | string | Queryable subtype such as `ollama_loaded_model` or `capability_check`. |
| `source_id` | string | Source-specific identifier. |
| `node_id` | string | Node that produced the run. |
| `model_name` | string or null | Model involved, if any. |
| `action_type` | string or null | Action category such as `infer`. |
| `status` | string | Run lifecycle status. |
| `started_at` | datetime | Start or observation time. |
| `ended_at` | datetime or null | End time when available. |
| `duration_ms` | integer or null | Duration when available. |
| `summary` | string | Human-readable run summary. |
| `metadata_json` | object | Detail-specific metadata. |

## POST /capability-check

Runs a compact inference check against a model available to the agent.

### Request

```json
{
  "model_name": "gemma4:e4b",
  "prompt": "Optional override prompt"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `model_name` | string | Yes | Ollama model tag to check. |
| `prompt` | string or null | No | Optional prompt override. |

### Response

Returns a `RunInfo` object with `detail_type` set to `capability_check` and `status` set to `success` or `failed`.

## POST /eval-attempt

Runs one prompt-suite eval case against a model available to the agent.

### Request

```json
{
  "model_name": "gemma4:e4b",
  "prompt": "Return a compact JSON object with an answer field.",
  "expected_json": {
    "answer": 42
  }
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `model_name` | string | Yes | Ollama model tag to evaluate. |
| `prompt` | string | Yes | Prompt text from the eval case. |
| `expected_json` | object or null | No | Expected key/value subset used for simple JSON scoring. |

### Response

Returns a `RunInfo` object with `detail_type` set to `eval_attempt`. The agent stores the raw response preview, parsed JSON when available, and a simple `score` object in `metadata_json`.

## Failure States

The control plane treats remote agent errors as operational state:

- connection failure: node eventually becomes `stale` then `unreachable`
- one endpoint failure while others respond: node becomes `degraded`
- auth failure: remote collection fails until token configuration matches
- failed capability check: durable `Run` record with `status: failed`
- failed eval attempt: durable `Run` record with `status: failed` and score/error metadata
