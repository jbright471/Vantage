# Eval Schedules

## Goal
Add recurring eval schedules that persist in SQLite and queue due eval attempt runs on a lightweight backend timer.

## Tasks
- [x] Add backend schedule tests -> Verify: schedule create/list and due queueing are covered.
- [x] Add schedule persistence and service logic -> Verify: backend eval tests pass.
- [x] Wire scheduler worker into FastAPI lifespan -> Verify: worker can be stopped cleanly.
- [x] Add frontend schedule types/API/UI -> Verify: Eval Lab test creates a schedule.
- [x] Update docs and roadmap -> Verify: recurring evals are described.
- [x] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Operators can create recurring eval schedules and Vantage can queue due eval runs without external task infrastructure.
