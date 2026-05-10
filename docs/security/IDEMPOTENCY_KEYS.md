# Action Idempotency Keys

Vantage treats operator actions as audit events first. Each mutating or verification action creates or reuses a `Run` record with an idempotency key so double-clicks, retries, and reconnects do not create misleading duplicate action history.

## Key Shape

The current key is a SHA-256 hash of:

```json
{
  "action_type": "<action-type>",
  "target_node_id": "<node-id>",
  "target_resource_id": "<node|endpoint|rule>",
  "payload": {},
  "dedupe_window": 30
}
```

The backend deduplicates matching keys only inside `idempotency_dedupe_seconds`, which is configured in `config/vantage.bootstrap.toml`.

## Per-Action Strategy

| Action | Target Resource | Payload Fields | Operator Intent |
| --- | --- | --- | --- |
| `refresh-node` | `node` | `node_id` | Verify one node's current observed state. |
| `set-node-enabled` | `node` | `node_id`, `enabled` | Quarantine or re-enable a node. |
| `set-local-ollama-endpoint-disabled` | endpoint URL | `node_id`, `endpoint_url`, `disabled` | Suppress or re-enable one local Ollama endpoint. |
| routing policy changes | rule ID | before/after route preference | Change configured routing state. |
| warning acknowledgement | warning ID | `warning_id` | Mark a reviewed warning as acknowledged. |

## Rules For New Actions

- Include the action type, target node, target resource, semantic payload, and dedupe window.
- Do not include random run IDs or timestamps in the key material.
- Store the final key on the `Run` row.
- Keep the original action payload in `metadata_json` so the audit record remains explainable.
- Use strict confirmation for configured-state changes, even when idempotency makes retries safe.
