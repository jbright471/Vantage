# Contributing

Vantage is early-stage, but it already has a few rules that keep the project coherent.

## Local Setup

Install dependencies:

```powershell
python -m pip install -e ".[dev]"
cd frontend
npm install
```

Run the Docker development stack:

```powershell
cd C:\Users\brigh\Documents\JoJo\30-Projects\Vantage
Copy-Item .env.example .env
python -c "import secrets; print('VANTAGE_AGENT_SHARED_TOKEN=' + secrets.token_urlsafe(48))" | Set-Content .env
docker compose up --build -d
```

Run tests:

```powershell
python -m pytest tests -q
cd frontend
npm run build
```

## Core Engineering Rules

- Preserve the separation between configured state, observed state, and derived display state.
- Passive polling belongs in `NodeSnapshot`.
- Meaningful actions, inferences, remote events, and scheduler work belong in `Run`.
- Do not make the frontend invent operational truth that is not present in backend state.
- Keep remote agent responses strict and Pydantic-validated.
- Keep secrets out of git.

## Backend Changes

Use the existing FastAPI and SQLAlchemy structure:

- API routes live under `backend/app/api/`
- collectors live under `backend/app/collectors/`
- operational logic lives under `backend/app/services/`
- SQLAlchemy tables live in `backend/app/models.py`

When changing persistence behavior, add focused tests under `tests/backend/`.

When changing polling, state derivation, or pruning, verify:

```powershell
python -m pytest tests/backend -q
```

## Agent Contract Changes

Agent routes live in [agent/app/main.py](./agent/app/main.py).

Pydantic contracts live in [agent/app/schemas.py](./agent/app/schemas.py).

Any contract change must update:

- `agent/app/schemas.py`
- `backend/app/collectors/remote.py`
- relevant tests under `tests/agent/` and `tests/backend/`
- [AGENT_CONTRACT.md](./AGENT_CONTRACT.md)

Backward compatibility matters because remote agents may be deployed independently from the control plane.

## Frontend Changes

The UI is an operator tool, not a landing page. Prioritize:

- dense but readable information
- stable dimensions
- clear freshness and status labels
- predictable controls
- no invented state

Feature code lives under:

- `frontend/src/features/nodes/`
- `frontend/src/features/runs/`
- `frontend/src/features/models/`
- `frontend/src/features/routing/`

Shared API types and fetch helpers live in:

```text
frontend/src/api/client.ts
```

Run targeted UI tests and a build:

```powershell
cd frontend
npm run test -- --run
npm run build
```

## Pull Request Checklist

- Tests pass.
- Frontend build passes when UI code changes.
- Docs are updated when contracts, deployment, or security behavior changes.
- New actions create auditable `Run` records.
- New node observations preserve freshness and last-known-state semantics.
- Secrets are not committed.

## Commit Style

Use short conventional-style messages when practical:

```text
feat: add remote run ingestion
fix: preserve stale node telemetry
docs: add agent contract
chore: update compose defaults
```
