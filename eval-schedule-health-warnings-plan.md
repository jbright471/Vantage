# Eval Schedule Health Warnings

## Goal
Surface failed auto-executed eval schedules as active operator warnings and resolve them after a clean scheduled run.

## Tasks
- [x] Add backend warning tests -> Verify: failed auto schedule creates an active warning.
- [x] Add warning upsert/resolve logic -> Verify: backend eval tests pass.
- [x] Publish warning state after scheduler cycles -> Verify: full state includes eval warning records.
- [x] Update docs and roadmap -> Verify: eval schedule health warnings are documented.
- [x] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Failed scheduled eval automation appears in Vantage warnings without creating duplicate warning spam.
