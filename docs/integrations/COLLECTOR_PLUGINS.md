# Collector Plugins

Vantage's collector registry is the first seam for adding runtimes beyond Ollama without hard-coding every future provider into the polling loop.

## Current Shape

The registry exposes descriptors:

```json
{
  "name": "ollama",
  "runtime": "local_or_agent",
  "description": "Built-in Ollama model, loaded-model, and capability telemetry collector.",
  "config_keys": ["local_ollama_base_urls", "VANTAGE_AGENT_OLLAMA_BASE_URLS"],
  "capabilities": ["models", "loaded_models", "capability_checks", "runs"],
  "endpoints": ["/api/models", "/api/ps", "/api/generate", "/api/runs"],
  "auth_modes": ["none", "agent_bearer", "agent_hmac"],
  "built_in": true,
  "status": "available"
}
```

Operators can inspect registered collectors at:

```http
GET /api/integrations/collectors
```

## Rules For Future Collectors

- Preserve Vantage's observer-first architecture.
- Return structured telemetry; do not mutate host state during collection.
- Keep runtime-specific failures in observed metadata instead of hiding them.
- Store meaningful actions and imports as durable `Run` records.
- Use strict Pydantic schemas at API boundaries.
- Describe capabilities, auth modes, required config keys, and runtime endpoints before exposing UI assumptions.
- Mark experimental collectors as unavailable or partial instead of pretending they are production-ready.
- Add tests for degraded, unreachable, and partial-failure behavior.

## Candidate Future Collectors

- llama.cpp server
- vLLM
- LM Studio
- custom Ollama router logs
- GPU exporter sidecars
- queue/scheduler event logs

Collector plugins should extend the registry and normalization layer before adding UI-specific assumptions.
