# Audit Exports

Vantage keeps operator actions, remote agent activity, eval attempts, and model checks as durable `Run` records. Operators can export that history in three formats:

| Format | Endpoint | Purpose |
| --- | --- | --- |
| JSON | `/api/runs/export.json` | Machine-readable run history with nested metadata. |
| CSV | `/api/runs/export.csv` | Spreadsheet-friendly operator review. |
| Signed bundle | `/api/runs/export.bundle.json` | Tamper-evident audit evidence. |

## Signed Bundle

Signed bundles require:

```text
VANTAGE_AUDIT_SIGNING_KEY=<high-entropy-secret>
VANTAGE_AUDIT_KEY_ID=<operator-chosen-key-id>
```

The bundle includes:

- `format`: currently `vantage.audit.bundle.v1`
- `exported_at`: export timestamp
- `filters`: export filters used by the operator
- `count`: number of exported runs
- `payload_sha256`: SHA-256 digest of the canonical payload
- `payload`: exported run data
- `signature`: HMAC-SHA256 signature metadata

The signature is calculated over canonical JSON excluding the `signature` field. Store the signing key outside the repository and rotate it if disclosed.

## Operator Guidance

- Use CSV for quick human inspection.
- Use JSON for integrations, incident notes, or SIEM-style ingestion.
- Use signed bundles when preserving evidence across machines or release boundaries.
- Do not edit signed bundle files after export; editing invalidates the signature.
- Keep signing keys separate from exported bundles.

## Verify A Bundle

Use the verification helper when receiving a bundle from another machine or preserving incident evidence:

```powershell
$env:VANTAGE_AUDIT_SIGNING_KEY = "<same-secret-used-to-sign>"
python scripts/verify-audit-bundle.py <path-to-bundle.json>
```

You can also pass the key directly for one-off local verification:

```powershell
python scripts/verify-audit-bundle.py <path-to-bundle.json> --key "<same-secret-used-to-sign>"
```

The helper confirms:

- the bundle format is supported
- `payload_sha256` matches the canonical payload
- the HMAC signature matches the provided key
- the output includes `verified`, `key_id`, exported run count, and payload digest

If verification fails, treat the file as untrusted until the signing key, export source, and transfer path are reviewed.
