# Phase 8 LLM Judge Evals

## Goal
Add a guarded `llm_judge` eval score type that asks a selected local model to judge another model response while preserving deterministic audit metadata and strict JSON validation.

## Tasks
- [x] Add judge score contract and prompt guardrails in `backend/app/services/evals.py` → Verify: malformed config and malformed judge JSON fail closed.
- [x] Execute judge calls through existing local/remote eval paths → Verify: backend tests mock local Ollama judge calls.
- [x] Surface `llm_judge` in Eval Lab score type choices and docs → Verify: frontend tests/build pass and guide explains required config.
- [x] Replace raw-only judge JSON editing with guided Eval Lab controls → Verify: frontend test covers generated `score_config_json`.
- [x] Update ROADMAP and operator docs → Verify: Later Research item is promoted into a shipped Phase 8 foundation note.
- [x] Run full verification → Verify: backend tests, frontend tests, frontend build, and browser smoke check pass.

## Done When
- [x] Operators can create an eval case using `score_type = "llm_judge"` with explicit judge model, node, rubric, and pass threshold.
- [x] Operators can configure `llm_judge` through guided UI controls while retaining raw JSON visibility for audit/debug use.
- [x] Judge output is accepted only as valid bounded JSON and stored in run metadata.
- [x] Invalid judge output cannot be reported as success.
