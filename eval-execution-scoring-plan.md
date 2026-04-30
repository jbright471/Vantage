# Eval Execution Scoring

## Goal
Execute queued eval attempt runs, store response metadata, and compute a simple JSON-subset score.

## Tasks
- [x] Add eval scoring tests -> Verify: JSON subset matches pass and mismatches fail.
- [x] Add eval execution API -> Verify: backend test executes a queued eval run.
- [x] Add remote agent eval endpoint -> Verify: agent contract exposes `/eval-attempt`.
- [x] Add frontend execute controls -> Verify: frontend test executes a queued eval run.
- [x] Update docs and roadmap -> Verify: Phase 2 describes execution and simple scoring.
- [x] Verification -> Verify: frontend tests/build and backend tests pass.

## Done When
- [x] Operators can execute a queued eval run and see response/score metadata in Vantage.
