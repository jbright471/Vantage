# Phase 6: Trust, Audit, And Security Hardening

## Goal
Make Vantage's audit exports tamper-evident and harden node-agent trust without breaking the current local-first Docker/LAN workflow.

## Tasks
- [x] Add signed run-history audit bundles → Verify: API test checks payload hash and HMAC signature metadata.
- [x] Add optional HMAC agent auth with timestamp/nonce replay protection → Verify: agent tests cover bearer compatibility, HMAC acceptance, replay rejection, and allowlist denial.
- [x] Teach the backend remote client to sign agent requests → Verify: client test checks generated Vantage auth headers.
- [x] Surface remote-agent auth failures as security warnings → Verify: runtime test persists an `agent_auth_failed` warning.
- [x] Add token-rotation workflow and explicit idempotency/security docs → Verify: docs mention rotation, replay protection, action allowlists, and mTLS research.
- [x] Update env examples and release/security checklist → Verify: setup docs expose no secrets and name required env vars.
- [x] Run backend/frontend verification → Verify: pytest, frontend tests, and build complete.

## Done When
- [x] Operators can export signed audit bundles.
- [x] Agents can run bearer auth today or HMAC auth when configured.
- [x] Security-relevant agent failures show up as first-class warnings.
- [x] Documentation is current enough for a public open-source release.
