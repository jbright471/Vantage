# Release Security Checklist

Run this checklist before publishing a GitHub release or sharing a release bundle.

## Secrets And Local Data

- [ ] `.env`, `.env.production`, and `vantage-agent.env` are not included.
- [ ] `vantage.sqlite3`, WAL files, local logs, and node modules are not included.
- [ ] Release examples use placeholder IP addresses and example node names only.
- [ ] Screenshots were captured from demo mode or have been redacted.
- [ ] No prompts, model outputs, tokens, private hostnames, or local filesystem paths are visible.

## Trust And Audit

- [ ] `VANTAGE_AGENT_SHARED_TOKEN` is generated outside the repository.
- [ ] `VANTAGE_AUDIT_SIGNING_KEY` is generated outside the repository if signed bundles are used.
- [ ] Signed audit bundle verification has been tested against a sample export.
- [ ] Token rotation steps are documented in the release notes if auth behavior changed.

## Agent Boundary

- [ ] Remote agent endpoints are reachable only from trusted LAN/VPN paths.
- [ ] HMAC mode is documented for operators who need replay protection.
- [ ] Agent action allowlists are reviewed.
- [ ] No host-level remediation action ships without an explicit allowlist and durable `Run` audit record.

## Build Verification

- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Frontend production build passes.
- [ ] `docker compose -f docker-compose.prod.yml config --quiet` passes.
- [ ] `scripts/check-setup.ps1` passes or reports only expected warnings.
- [ ] `scripts/build-release.ps1 -Version <version>` produces zip and SHA256 files.
- [ ] Release bundle scan finds no real secrets, local paths, private IPs, or database files.
