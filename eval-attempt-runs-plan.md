# Eval Attempt Runs

## Goal
Let operators queue eval suite attempts as durable `Run` records without executing or scoring model output yet.

## Tasks
- [x] Add eval attempt API -> Verify: backend test creates queued runs for each case.
- [x] Add frontend client and Eval Lab controls -> Verify: frontend test queues an eval attempt.
- [x] Surface recent eval attempts in the Eval Lab -> Verify: queued runs appear without leaving the page.
- [x] Update docs and roadmap -> Verify: Phase 2 scope describes queued attempts.
- [x] Verification -> Verify: frontend tests/build and backend tests pass.

## Done When
- [x] Operators can select a suite, model placement, and queue eval attempt Run records from the Eval Lab.
