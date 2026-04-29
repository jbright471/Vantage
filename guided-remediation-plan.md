# Guided Remediation

## Goal
Add Phase 1.7 allowlisted remediation controls that are explicit, reversible, and auditable.

## Tasks
- [x] Add durable warning acknowledgement -> Verify: warning status changes to acknowledged.
- [x] Keep acknowledged drift suppressed until resolved -> Verify: reconciliation reuses acknowledged warnings.
- [x] Add an API endpoint for warning acknowledgement -> Verify: backend test covers PATCH.
- [x] Add frontend warning acknowledge action -> Verify: UI can hide acknowledged warning.
- [x] Update docs and roadmap -> Verify: Phase 1.7 describes shipped controls.
- [x] Verification -> Verify: frontend tests/build and backend tests pass.

## Done When
- [x] Operators can acknowledge a warning from Vantage without deleting history or mutating host services.
