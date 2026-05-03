# Phase 1.7 Node Quarantine

## Goal
Add an allowlisted action that lets an operator disable or re-enable a node in Vantage's configured registry while preserving an audit `Run`.

## Tasks
- [x] Add backend action tests -> Verify: disabling a node records success, re-enabling records success, and disabling the last enabled node is rejected.
- [x] Add backend action endpoint -> Verify: `Node.enabled` changes only through an audited action path.
- [x] Add frontend confirmation flow -> Verify: operators must explicitly confirm quarantine or re-enable actions from Nodes.
- [x] Add local endpoint suppression -> Verify: known-bad local Ollama endpoints can be disabled from Diagnostics and skipped during polling/capability checks.
- [x] Update docs and roadmap -> Verify: Phase 1.7 describes node quarantine and endpoint suppression as bounded control-plane actions.
- [ ] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Operators can quarantine a problematic node from routing/polling without touching host services, disable known-bad local Ollama endpoints, then verify all actions in Runs.
