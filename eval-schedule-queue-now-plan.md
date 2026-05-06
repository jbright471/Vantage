# Eval Schedule Queue Now

## Goal
Let operators manually queue an enabled eval schedule immediately without waiting for the background due-schedule worker.

## Tasks
- [x] Add backend schedule queue-now tests -> Verify: an enabled schedule queues runs immediately and a disabled schedule is rejected.
- [x] Add schedule queue-now service/API -> Verify: queued runs preserve schedule metadata and do not move `next_run_at`.
- [x] Make local eval execution honor endpoint overrides -> Verify: disabled local Ollama endpoints are skipped during eval execution.
- [x] Add frontend queue-now control -> Verify: operators can queue a schedule from the Eval Lab schedule table.
- [x] Update docs and roadmap -> Verify: Phase 2 describes manual schedule queueing.
- [x] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Operators can click `Queue now` on an enabled eval schedule and see queued eval `Run` records without changing the recurring schedule cadence.
