# Phase 1.7 Verified Refresh

## Goal
Upgrade the allowlisted node refresh action from submitted-only to a verified one-node poll with durable success/failure state.

## Tasks
- [x] Add backend action tests -> Verify: refresh records success and failure outcomes.
- [x] Add single-node polling helper -> Verify: action endpoint persists fresh observations.
- [x] Update frontend refresh messaging -> Verify: Nodes test expects verified completion.
- [x] Update docs and roadmap -> Verify: Phase 1.7 mentions verified refresh.
- [x] Verification -> Verify: backend tests, frontend tests, build, and diff check pass.

## Done When
- [x] Operators can retry a node poll from the UI and see whether Vantage verified the result.
