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
cd ./vantage
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

Schema changes must include an Alembic migration under `migrations/versions/`. Generate the draft, review it, and run it against a disposable SQLite database before committing:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
```

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

## Deployment And Release Changes

Production packaging files include:

- [docker-compose.prod.yml](./docker-compose.prod.yml)
- [Dockerfile.backend.prod](./Dockerfile.backend.prod)
- [frontend/Dockerfile.prod](./frontend/Dockerfile.prod)
- [frontend/nginx.conf](./frontend/nginx.conf)
- [scripts/check-setup.ps1](./scripts/check-setup.ps1)
- [scripts/build-release.ps1](./scripts/build-release.ps1)
- [deploy/agent/](./deploy/agent)
- [.github/workflows/release.yml](./.github/workflows/release.yml)

When changing deployment behavior, update [OPERATIONS.md](./OPERATIONS.md), [PORTAINER.md](./PORTAINER.md), [RELEASE.md](./RELEASE.md), and [SECURITY.md](./SECURITY.md) as needed.

Verify production packaging:

```powershell
$env:VANTAGE_AGENT_SHARED_TOKEN = "setup-check-placeholder-token"
docker compose -f docker-compose.prod.yml config --quiet
.\scripts\check-setup.ps1 -ComposeFile docker-compose.prod.yml
.\scripts\build-release.ps1 -Version dev-check
```

## Pull Request Checklist

- Tests pass.
- Frontend build passes when UI code changes.
- Docs are updated when contracts, deployment, or security behavior changes.
- The in-app Operator Guide remains current when operator workflows change.
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
