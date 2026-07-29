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
- [ ] `VANTAGE_CONTROL_PLANE_TOKEN` and `VANTAGE_SESSION_SIGNING_KEY` are independently generated outside the repository and are not equal.
- [ ] `VANTAGE_EXTERNAL_API_TOKEN` is distinct from operator and agent secrets when integration automation is enabled.
- [ ] `VANTAGE_AUDIT_SIGNING_KEY` is generated outside the repository if signed bundles are used.
- [ ] Signed audit bundle verification has been tested against a sample export.
- [ ] Token rotation steps are documented in the release notes if auth behavior changed.

## Agent Boundary

- [ ] Remote agent endpoints are reachable only from trusted LAN/VPN paths.
- [ ] HMAC mode is documented for operators who need replay protection.
- [ ] Agent action allowlists are reviewed.
- [ ] No host-level remediation action ships without an explicit allowlist and durable `Run` audit record.

## Runtime Hardening

- [ ] Production publishes only the frontend and binds to loopback unless trusted remote access is deliberate.
- [ ] TLS is terminated by a trusted proxy and `VANTAGE_SESSION_COOKIE_SECURE=1` is set before non-loopback browser access.
- [ ] Backend and frontend containers run as non-root with read-only filesystems, dropped capabilities, and `no-new-privileges`.
- [ ] Webhook authorities are explicitly allowlisted and production egress rules restrict unnecessary destinations.
- [ ] LLM/eval rate, concurrency, prompt, output-token, and response-size limits are reviewed for the deployment.

## Build Verification

- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Frontend production build passes.
- [ ] `docker compose -f docker-compose.prod.yml config --quiet` passes.
- [ ] `scripts/check-setup.ps1` passes or reports only expected warnings.
- [ ] `scripts/build-release.ps1 -Version <version>` produces zip and SHA256 files.
- [ ] Release bundle scan finds no real secrets, local paths, private IPs, or database files.
- [ ] The SHA-pinned GitHub security workflow is green for the exact release commit.
- [ ] Gitleaks, dependency review, npm/pip/OSV audits, Semgrep, CodeQL, and Trivy report no blocking findings.
- [ ] Backend and frontend CycloneDX SBOM artifacts are retained with the release evidence.
