# Eval Schedule Auto Execution

## Goal
Let recurring eval schedules opt into automated execution while keeping queue-only scheduling as the safe default.

## Tasks
- [x] Add backend auto-execution tests -> Verify: due auto schedules execute and score runs.
- [x] Add schedule `auto_execute` persistence and API payloads -> Verify: schedule create/list exposes the flag.
- [x] Execute due auto schedules in the scheduler worker -> Verify: backend eval tests pass.
- [x] Add frontend auto-execute controls -> Verify: Eval Lab test creates an auto-execute schedule.
- [x] Update docs and roadmap -> Verify: automation boundary is documented.
- [x] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Operators can choose queue-only or auto-execute behavior per recurring eval schedule.
