# Eval Lifecycle Management

## Goal
Let operators safely remove stale eval schedules, prompt cases, and empty prompt suites without damaging durable run history.

## Tasks
- [x] Add backend delete tests -> Verify: schedules delete cleanly, cases return updated suite payloads, and non-empty suites are protected.
- [x] Add backend delete API handlers -> Verify: deletes are explicit and do not mutate historical `Run` records.
- [x] Add frontend delete client functions -> Verify: UI calls the expected DELETE endpoints.
- [x] Add Eval Lab lifecycle controls -> Verify: operators can delete schedules, cases, and empty suites from the existing surface.
- [x] Update docs and roadmap -> Verify: Eval Lab lifecycle behavior is documented.
- [x] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Operators can clean up eval schedules and cases directly from Eval Lab.
- [x] Prompt suite deletion is blocked until the suite has no cases or active schedules.
