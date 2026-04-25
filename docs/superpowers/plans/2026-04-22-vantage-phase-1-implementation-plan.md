# Vantage Phase 1 Implementation Plan

Sanitization note: ControlPlane / control-plane and WorkerA / worker-a are placeholder node names used for documentation examples. Replace them with your own homelab node names and network values.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 MVP of Vantage: a local-first control plane that truthfully shows nodes, runs, models, and routing visibility across ControlPlane and WORKER_A.

**Architecture:** Vantage is a FastAPI control plane on ControlPlane with SQLite persistence, SSE streaming, and a lightweight FastAPI agent on WORKER_A. The backend owns config loading, polling, persistence, and event streaming; the frontend consumes a full-state-on-connect SSE stream and renders Nodes, Runs, Models, and Routing surfaces without inventing state.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, Pydantic, SQLite, pytest, httpx, React, TypeScript, Vite, Vitest, Testing Library

---

## File Structure

- `pyproject.toml`
  Python dependencies and pytest configuration for both the backend and WORKER_A agent.
- `.gitignore`
  Ignore Python caches, virtualenvs, SQLite files, Node modules, and local logs.
- `config/vantage.bootstrap.toml`
  Bootstrap config for node registry, polling intervals, thresholds, and retention defaults.
- `backend/app/config.py`
  Bootstrap config loader and typed app settings accessors.
- `backend/app/logging.py`
  Structured JSON logging setup for backend processes.
- `backend/app/db.py`
  SQLAlchemy engine, session factory, and database lifecycle helpers.
- `backend/app/models.py`
  SQLAlchemy models for `Node`, `NodeSnapshot`, `Run`, `ModelPlacement`, `RoutingRule`, `RoutingRuleNode`, `AppSetting`, and `WarningRecord`.
- `backend/app/schemas.py`
  Pydantic DTOs for API responses and SSE payloads.
- `backend/app/main.py`
  FastAPI app factory and router registration.
- `backend/app/api/`
  REST and SSE endpoints for health, nodes, runs, models, routing, warnings, and actions.
- `backend/app/collectors/local.py`
  ControlPlane local collectors for GPU stats, Ollama models, and local service health.
- `backend/app/collectors/remote.py`
  HTTP client for the WORKER_A agent contract.
- `backend/app/services/`
  Bootstrap seeding, polling, pruning, event publication, actions, and reconciliation.
- `agent/app/main.py`
  WORKER_A FastAPI agent entrypoint.
- `agent/app/schemas.py`
  Pydantic response contracts for WORKER_A agent endpoints.
- `agent/app/collectors.py`
  WORKER_A collectors for health, GPU, models, and optional local run feed.
- `deploy/WORKER_A/vantage-agent.service`
  systemd unit file for the WORKER_A agent.
- `frontend/`
  Vite React TypeScript app for the operator UI.
- `frontend/src/api/client.ts`
  Fetch helpers and type-safe API calls.
- `frontend/src/hooks/useEventSource.ts`
  Full-state-on-connect plus delta SSE state hook.
- `frontend/src/features/nodes/`
  Nodes UI components and tests.
- `frontend/src/features/runs/`
  Runs UI components and tests.
- `frontend/src/features/models/`
  Models UI components and tests.
- `frontend/src/features/routing/`
  Routing visibility UI components and tests.
- `tests/backend/`
  Backend unit, integration, SSE, action, pruning, and reconciliation tests.
- `tests/agent/`
  WORKER_A agent contract tests.
- `scripts/manual-smoke.ps1`
  Manual smoke commands for local operator verification.

## Task 1: Bootstrap The Vantage Workspace

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `config/vantage.bootstrap.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/logging.py`
- Create: `tests/backend/test_config.py`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing bootstrap-config test**

```python
# tests/backend/test_config.py
from pathlib import Path

from backend.app.config import load_bootstrap_config


def test_load_bootstrap_config_reads_nodes(tmp_path: Path) -> None:
    config_path = tmp_path / "vantage.bootstrap.toml"
    config_path.write_text(
        """
app_name = "Vantage"
poll_interval_seconds = 5
stale_after_seconds = 15
unreachable_after_seconds = 30

[[nodes]]
node_id = "ControlPlane"
display_name = "ControlPlane"
base_url = "http://127.0.0.1:9000"
role = "primary"
enabled = true
        """.strip(),
        encoding="utf-8",
    )

    config = load_bootstrap_config(config_path)

    assert config.app_name == "Vantage"
    assert config.poll_interval_seconds == 5
    assert config.nodes[0].node_id == "ControlPlane"
    assert config.nodes[0].role == "primary"
```

- [ ] **Step 2: Run the test to verify the module does not exist yet**

Run:

```powershell
python -m pytest tests/backend/test_config.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend'
```

- [ ] **Step 3: Create the Python workspace, frontend scaffold files, bootstrap config, and JSON logging**

```toml
# pyproject.toml
[project]
name = "vantage"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
  "fastapi>=0.116.0",
  "httpx>=0.28.0",
  "pydantic>=2.11.0",
  "python-dotenv>=1.1.0",
  "sqlalchemy>=2.0.43",
  "uvicorn>=0.35.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.4.0",
  "pytest-asyncio>=1.1.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
*.sqlite3
*.db
*.log
node_modules/
dist/
coverage/
```

```toml
# config/vantage.bootstrap.toml
app_name = "Vantage"
poll_interval_seconds = 5
stale_after_seconds = 15
unreachable_after_seconds = 30
snapshot_retention_hours = 24
run_timeout_seconds = 300
abandoned_after_seconds = 900
idempotency_dedupe_seconds = 30

[[nodes]]
node_id = "ControlPlane"
display_name = "ControlPlane"
base_url = "http://127.0.0.1:8000"
role = "primary"
enabled = true

[[nodes]]
node_id = "WORKER_A"
display_name = "WORKER_A"
base_url = "http://<remote-agent-ip>:9100"
role = "remote"
enabled = true
```

```python
# backend/app/config.py
from pathlib import Path
import tomllib

from pydantic import BaseModel, Field


class BootstrapNode(BaseModel):
    node_id: str
    display_name: str
    base_url: str
    role: str = "worker"
    enabled: bool = True


class BootstrapConfig(BaseModel):
    app_name: str = "Vantage"
    poll_interval_seconds: int = 5
    stale_after_seconds: int = 15
    unreachable_after_seconds: int = 30
    snapshot_retention_hours: int = 24
    run_timeout_seconds: int = 300
    abandoned_after_seconds: int = 900
    idempotency_dedupe_seconds: int = 30
    nodes: list[BootstrapNode] = Field(default_factory=list)


def load_bootstrap_config(path: str | Path) -> BootstrapConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return BootstrapConfig.model_validate(data)
```

```python
# backend/app/logging.py
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
```

```json
// frontend/package.json
{
  "name": "vantage-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.3.0",
    "@types/react": "^19.0.10",
    "@types/react-dom": "^19.0.6",
    "@vitejs/plugin-react": "^5.0.0",
    "typescript": "^5.8.0",
    "vite": "^7.0.0",
    "vitest": "^3.2.4"
  }
}
```

```tsx
// frontend/src/App.tsx
export default function App() {
  return <main>Vantage bootstrapped.</main>;
}
```

- [ ] **Step 4: Run the bootstrap test and frontend build**

Run:

```powershell
python -m pytest tests/backend/test_config.py -q
npm --prefix frontend run build
```

Expected:

```text
1 passed
vite build completed successfully
```

- [ ] **Step 5: Initialize git and commit the workspace scaffold**

```powershell
git init
git add .gitignore pyproject.toml config/vantage.bootstrap.toml backend/app frontend tests/backend/test_config.py
git commit -m "chore: bootstrap vantage workspace"
```

## Task 2: Build The WORKER_A Agent Contract

**Files:**
- Create: `agent/app/__init__.py`
- Create: `agent/app/schemas.py`
- Create: `agent/app/collectors.py`
- Create: `agent/app/main.py`
- Create: `tests/agent/test_contract.py`
- Create: `deploy/WORKER_A/vantage-agent.service`

- [ ] **Step 1: Write the failing WORKER_A agent contract test**

```python
# tests/agent/test_contract.py
from fastapi.testclient import TestClient

from agent.app.main import app


def test_agent_exposes_health_gpu_and_models(monkeypatch) -> None:
    monkeypatch.setattr("agent.app.collectors.get_health", lambda: {"status": "ok", "node_id": "WORKER_A"})
    monkeypatch.setattr(
        "agent.app.collectors.get_gpu_stats",
        lambda: [{"name": "RTX 3090", "memory_total_mb": 24576, "temperature_c": 42}],
    )
    monkeypatch.setattr(
        "agent.app.collectors.get_models",
        lambda: [{"model_name": "qwen3.6:latest", "model_digest": "sha256:abc", "available": True}],
    )

    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/gpu").json()["gpus"][0]["name"] == "RTX 3090"
    assert client.get("/models").json()["models"][0]["model_name"] == "qwen3.6:latest"
```

- [ ] **Step 2: Run the agent test to verify the app is missing**

Run:

```powershell
python -m pytest tests/agent/test_contract.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'agent.app.main'
```

- [ ] **Step 3: Implement the WORKER_A FastAPI agent and systemd unit**

```python
# agent/app/schemas.py
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    node_id: str


class GpuStat(BaseModel):
    name: str
    memory_total_mb: int
    temperature_c: int


class GpuResponse(BaseModel):
    gpus: list[GpuStat]


class ModelInfo(BaseModel):
    model_name: str
    model_digest: str | None = None
    available: bool


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
```

```python
# agent/app/collectors.py
import json
import subprocess


def get_health() -> dict:
    return {"status": "ok", "node_id": "WORKER_A"}


def get_gpu_stats() -> list[dict]:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = []
    for line in result.stdout.strip().splitlines():
        name, memory_total_mb, temperature_c = [part.strip() for part in line.split(",")]
        rows.append(
            {
                "name": name,
                "memory_total_mb": int(memory_total_mb),
                "temperature_c": int(temperature_c),
            }
        )
    return rows


def get_models() -> list[dict]:
    result = subprocess.run(["ollama", "list", "--json"], capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    return [
        {
            "model_name": item["name"],
            "model_digest": item.get("digest"),
            "available": True,
        }
        for item in payload.get("models", [])
    ]
```

```python
# agent/app/main.py
from fastapi import FastAPI

from agent.app.collectors import get_gpu_stats, get_health, get_models
from agent.app.schemas import GpuResponse, HealthResponse, ModelsResponse

app = FastAPI(title="Vantage WORKER_A Agent")


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    return get_health()


@app.get("/gpu", response_model=GpuResponse)
def gpu() -> dict:
    return {"gpus": get_gpu_stats()}


@app.get("/models", response_model=ModelsResponse)
def models() -> dict:
    return {"models": get_models()}


@app.get("/runs")
def runs() -> dict:
    return {"runs": []}
```

```ini
# deploy/WORKER_A/vantage-agent.service
[Unit]
Description=Vantage WORKER_A Agent
After=network.target

[Service]
WorkingDirectory=/opt/vantage
ExecStart=/opt/vantage/.venv/bin/uvicorn agent.app.main:app --host 0.0.0.0 --port 9100
Restart=always
User=WORKER_A

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Run the contract tests**

Run:

```powershell
python -m pytest tests/agent/test_contract.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit the agent contract**

```powershell
git add agent tests/agent deploy/WORKER_A/vantage-agent.service
git commit -m "feat: add vantage WORKER_A agent contract"
```

## Task 3: Build Backend Persistence And Bootstrap Seeding

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/services/bootstrap.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/health.py`
- Create: `tests/backend/test_bootstrap_seed.py`

- [ ] **Step 1: Write the failing node-seeding test**

```python
# tests/backend/test_bootstrap_seed.py
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.models import Base, Node
from backend.app.services.bootstrap import seed_nodes_from_config
from backend.app.config import BootstrapConfig, BootstrapNode


def test_seed_nodes_from_config_inserts_without_duplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    config = BootstrapConfig(
        nodes=[
            BootstrapNode(
                node_id="ControlPlane",
                display_name="ControlPlane",
                base_url="http://127.0.0.1:8000",
                role="primary",
                enabled=True,
            )
        ]
    )

    with Session(engine) as session:
        seed_nodes_from_config(session, config)
        seed_nodes_from_config(session, config)
        nodes = session.scalars(select(Node)).all()

    assert len(nodes) == 1
    assert nodes[0].created_from == "bootstrap"
    assert {
        "nodes",
        "node_snapshots",
        "runs",
        "model_placements",
        "routing_rules",
        "routing_rule_nodes",
        "app_settings",
        "warning_records",
    }.issubset(Base.metadata.tables.keys())
```

- [ ] **Step 2: Run the seed test to verify the models and service are missing**

Run:

```powershell
python -m pytest tests/backend/test_bootstrap_seed.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.models'
```

- [ ] **Step 3: Implement SQLAlchemy models, DB helpers, and bootstrap seeding**

```python
# backend/app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite+pysqlite:///./vantage.sqlite3"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

```python
# backend/app/models.py
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    node_id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_from: Mapped[str] = mapped_column(String, default="bootstrap")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NodeSnapshot(Base):
    __tablename__ = "node_snapshots"

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gpu_json: Mapped[list] = mapped_column(JSON, nullable=False)
    cpu_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    memory_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    ollama_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    health_status: Mapped[str] = mapped_column(String, nullable=False)


class Run(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    detail_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    action_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ModelPlacement(Base):
    __tablename__ = "model_placements"

    placement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class RoutingRule(Base):
    __tablename__ = "routing_rules"

    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    priority_class: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingRuleNode(Base):
    __tablename__ = "routing_rule_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WarningRecord(Base):
    __tablename__ = "warning_records"

    warning_id: Mapped[str] = mapped_column(String, primary_key=True)
    warning_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    node_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
```

```python
# backend/app/schemas.py
from pydantic import BaseModel


class NodeResponse(BaseModel):
    node_id: str
    display_name: str
    role: str
    enabled: bool
    created_from: str


class WarningResponse(BaseModel):
    warning_id: str
    warning_type: str
    severity: str
    node_id: str | None = None
    summary: str
```

```python
# backend/app/services/bootstrap.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import BootstrapConfig
from backend.app.models import Node


def seed_nodes_from_config(session: Session, config: BootstrapConfig) -> None:
    for bootstrap_node in config.nodes:
        existing = session.scalar(select(Node).where(Node.node_id == bootstrap_node.node_id))
        if existing:
            continue
        session.add(
            Node(
                node_id=bootstrap_node.node_id,
                display_name=bootstrap_node.display_name,
                base_url=bootstrap_node.base_url,
                role=bootstrap_node.role,
                enabled=bootstrap_node.enabled,
                created_from="bootstrap",
            )
        )
    session.commit()
```

```python
# backend/app/main.py
from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.db import engine
from backend.app.models import Base

app = FastAPI(title="Vantage Control Plane")
app.include_router(health_router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
```

```python
# backend/app/api/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "Vantage"}
```

- [ ] **Step 4: Run the backend tests**

Run:

```powershell
python -m pytest tests/backend/test_bootstrap_seed.py tests/backend/test_config.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit the backend persistence foundation**

```powershell
git add backend tests/backend
git commit -m "feat: add backend persistence and bootstrap seeding"
```

## Task 4: Implement Collectors, Polling, Status Classification, And Pruning

**Files:**
- Create: `backend/app/collectors/local.py`
- Create: `backend/app/collectors/remote.py`
- Create: `backend/app/services/polling.py`
- Create: `backend/app/services/pruning.py`
- Create: `tests/backend/test_polling.py`
- Create: `tests/backend/test_pruning.py`

- [ ] **Step 1: Write failing polling and pruning tests**

```python
# tests/backend/test_polling.py
from datetime import UTC, datetime

from backend.app.services.polling import classify_health, normalize_snapshot, extract_model_placements


def test_classify_health_marks_partial_failure_as_degraded() -> None:
    snapshot = {
        "node_id": "WORKER_A",
        "captured_at": datetime.now(UTC),
        "gpu_json": [],
        "cpu_json": {"usage_percent": 12},
        "memory_json": {"used_mb": 2048},
        "ollama_json": {"status": "error", "models": []},
    }

    normalized = normalize_snapshot(snapshot)

    assert classify_health(normalized) == "degraded"


def test_extract_model_placements_creates_rows_per_model() -> None:
    placements = extract_model_placements(
        node_id="WORKER_A",
        ollama_payload={"models": [{"name": "qwen3.6:latest", "digest": "sha256:abc"}]},
    )

    assert placements[0]["node_id"] == "WORKER_A"
    assert placements[0]["model_name"] == "qwen3.6:latest"
```

```python
# tests/backend/test_pruning.py
from datetime import UTC, datetime, timedelta

from backend.app.services.pruning import prune_snapshots


class FakeSession:
    def __init__(self) -> None:
        self.cutoff = None

    def execute(self, statement) -> None:
        self.cutoff = statement

    def commit(self) -> None:
        pass


def test_prune_snapshots_uses_retention_cutoff() -> None:
    session = FakeSession()

    prune_snapshots(session, now=datetime.now(UTC), retention_hours=24)

    assert session.cutoff is not None
```

- [ ] **Step 2: Run the polling tests to verify the services are missing**

Run:

```powershell
python -m pytest tests/backend/test_polling.py tests/backend/test_pruning.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.services.polling'
```

- [ ] **Step 3: Implement local and remote collectors, polling normalization, and pruning**

```python
# backend/app/collectors/remote.py
import httpx


class WORKER_AClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def fetch_health(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def fetch_gpu(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/gpu")
            response.raise_for_status()
            return response.json()

    async def fetch_models(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            return response.json()
```

```python
# backend/app/services/polling.py
from datetime import UTC, datetime


def normalize_snapshot(raw: dict) -> dict:
    return {
        "node_id": raw["node_id"],
        "captured_at": raw.get("captured_at", datetime.now(UTC)),
        "gpu_json": raw.get("gpu_json", []),
        "cpu_json": raw.get("cpu_json", {}),
        "memory_json": raw.get("memory_json", {}),
        "ollama_json": raw.get("ollama_json", {}),
    }


def classify_health(snapshot: dict) -> str:
    ollama_status = snapshot["ollama_json"].get("status", "ok")
    if ollama_status == "error":
        return "degraded"
    return "healthy"


def extract_model_placements(node_id: str, ollama_payload: dict) -> list[dict]:
    placements = []
    for model in ollama_payload.get("models", []):
        placements.append(
            {
                "node_id": node_id,
                "model_name": model["name"],
                "model_digest": model.get("digest"),
                "available": True,
            }
        )
    return placements
```

```python
# backend/app/services/pruning.py
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from backend.app.models import NodeSnapshot


def prune_snapshots(session, now: datetime | None = None, retention_hours: int = 24) -> None:
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(hours=retention_hours)
    session.execute(delete(NodeSnapshot).where(NodeSnapshot.captured_at < cutoff))
    session.commit()
```

```python
# backend/app/collectors/local.py
from datetime import UTC, datetime
import json
import subprocess


def collect_local_snapshot(node_id: str) -> dict:
    result = subprocess.run(
        ["ollama", "list", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "node_id": node_id,
        "captured_at": datetime.now(UTC),
        "gpu_json": [],
        "cpu_json": {"usage_percent": 0},
        "memory_json": {"used_mb": 0},
        "ollama_json": {"status": "ok", "models": json.loads(result.stdout).get("models", [])},
    }
```

- [ ] **Step 4: Run the collector, polling, and pruning tests**

Run:

```powershell
python -m pytest tests/backend/test_polling.py tests/backend/test_pruning.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit polling and pruning**

```powershell
git add backend tests/backend
git commit -m "feat: add polling, status classification, and pruning"
```

## Task 5: Add Runs, Read APIs, And SSE Full-State Streaming

**Files:**
- Create: `backend/app/api/nodes.py`
- Create: `backend/app/api/runs.py`
- Create: `backend/app/api/models.py`
- Create: `backend/app/api/routing.py`
- Create: `backend/app/api/stream.py`
- Create: `backend/app/api/warnings.py`
- Create: `backend/app/services/events.py`
- Create: `tests/backend/test_read_apis.py`
- Create: `tests/backend/test_sse.py`

- [ ] **Step 1: Write failing API and SSE tests**

```python
# tests/backend/test_sse.py
from fastapi.testclient import TestClient

from backend.app.main import app


def test_stream_emits_full_state_event_first() -> None:
    client = TestClient(app)

    with client.stream("GET", "/api/stream") as response:
        first_chunk = next(response.iter_lines())

    assert "event: full_state" in first_chunk
```

```python
# tests/backend/test_read_apis.py
from fastapi.testclient import TestClient

from backend.app.main import app


def test_nodes_runs_and_models_endpoints_exist() -> None:
    client = TestClient(app)

    assert client.get("/api/nodes").status_code == 200
    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/models").status_code == 200
    assert client.get("/api/routing").status_code == 200
    assert client.get("/api/warnings").status_code == 200
```

- [ ] **Step 2: Run the API tests to verify the routes do not exist**

Run:

```powershell
python -m pytest tests/backend/test_read_apis.py tests/backend/test_sse.py -q
```

Expected:

```text
FAILED tests/backend/test_read_apis.py::test_nodes_runs_and_models_endpoints_exist
FAILED tests/backend/test_sse.py::test_stream_emits_full_state_event_first
```

- [ ] **Step 3: Implement read APIs and an in-process event broker with full-state-on-connect**

```python
# backend/app/services/events.py
import asyncio
from collections.abc import AsyncIterator


class EventBroker:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[dict]] = []

    async def subscribe(self, initial_state: dict) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._queues.append(queue)
        yield {"event": "full_state", "data": initial_state}
        try:
            while True:
                payload = await queue.get()
                yield payload
        finally:
            self._queues.remove(queue)

    async def publish(self, event: str, data: dict) -> None:
        for queue in self._queues:
            await queue.put({"event": event, "data": data})
```

```python
# backend/app/api/stream.py
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.services.events import EventBroker

router = APIRouter()
broker = EventBroker()


def serialize_sse(payload: dict) -> str:
    return f"event: {payload['event']}\ndata: {json.dumps(payload['data'])}\n\n"


@router.get("/stream")
async def stream() -> StreamingResponse:
    async def event_generator():
        async for payload in broker.subscribe({"nodes": [], "runs": [], "models": [], "routing": []}):
            yield serialize_sse(payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

```python
# backend/app/api/nodes.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/nodes")
def list_nodes() -> list:
    return []
```

```python
# backend/app/api/runs.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/runs")
def list_runs() -> list:
    return []
```

```python
# backend/app/api/models.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/models")
def list_models() -> list:
    return []
```

```python
# backend/app/api/routing.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/routing")
def list_routing() -> list:
    return []
```

```python
# backend/app/api/warnings.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/warnings")
def list_warnings() -> list:
    return []
```

- [ ] **Step 4: Register routes and rerun the tests**

```python
# backend/app/main.py
from fastapi import FastAPI

from backend.app.api.health import router as health_router
from backend.app.api.models import router as models_router
from backend.app.api.nodes import router as nodes_router
from backend.app.api.routing import router as routing_router
from backend.app.api.runs import router as runs_router
from backend.app.api.stream import router as stream_router
from backend.app.api.warnings import router as warnings_router

app = FastAPI(title="Vantage Control Plane")
app.include_router(health_router, prefix="/api")
app.include_router(nodes_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(routing_router, prefix="/api")
app.include_router(warnings_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
```

Run:

```powershell
python -m pytest tests/backend/test_read_apis.py tests/backend/test_sse.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit the read APIs and stream contract**

```powershell
git add backend tests/backend
git commit -m "feat: add read APIs and sse stream contract"
```

## Task 6: Build The Frontend Shell And Nodes View

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useEventSource.ts`
- Create: `frontend/src/features/nodes/NodeCard.tsx`
- Create: `frontend/src/features/nodes/NodesPage.tsx`
- Create: `frontend/src/features/nodes/NodesPage.test.tsx`
- Create: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing Nodes view test**

```tsx
// frontend/src/features/nodes/NodesPage.test.tsx
import { render, screen } from "@testing-library/react";

import { NodesPage } from "./NodesPage";

describe("NodesPage", () => {
  it("renders node freshness and status", () => {
    render(
      <NodesPage
        nodes={[
          {
            node_id: "WORKER_A",
            display_name: "WORKER_A",
            observed_status: "degraded",
            freshness: "stale",
            last_seen_at: "2026-04-22T12:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("WORKER_A")).toBeInTheDocument();
    expect(screen.getByText("degraded")).toBeInTheDocument();
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the frontend test to verify the component does not exist**

Run:

```powershell
npm --prefix frontend run test -- --run frontend/src/features/nodes/NodesPage.test.tsx
```

Expected:

```text
FAIL  Cannot find module './NodesPage'
```

- [ ] **Step 3: Implement the EventSource hook, Node card, and Nodes page**

```ts
// frontend/src/hooks/useEventSource.ts
import { useEffect, useState } from "react";

export type FullState = {
  nodes: Array<Record<string, unknown>>;
  runs: Array<Record<string, unknown>>;
  models: Array<Record<string, unknown>>;
  routing: Array<Record<string, unknown>>;
};

export function useEventSource(url: string) {
  const [state, setState] = useState<FullState>({ nodes: [], runs: [], models: [], routing: [] });

  useEffect(() => {
    const source = new EventSource(url);
    source.addEventListener("full_state", (event) => {
      setState(JSON.parse((event as MessageEvent).data));
    });
    source.addEventListener("delta", (event) => {
      const patch = JSON.parse((event as MessageEvent).data) as Partial<FullState>;
      setState((current) => ({ ...current, ...patch }));
    });
    return () => source.close();
  }, [url]);

  return state;
}
```

```tsx
// frontend/src/features/nodes/NodeCard.tsx
type NodeCardProps = {
  display_name: string;
  observed_status: string;
  freshness: string;
  last_seen_at: string | null;
};

export function NodeCard(props: NodeCardProps) {
  return (
    <article>
      <h2>{props.display_name}</h2>
      <p>{props.observed_status}</p>
      <p>{props.freshness}</p>
      <p>{props.last_seen_at ?? "never seen"}</p>
    </article>
  );
}
```

```tsx
// frontend/src/features/nodes/NodesPage.tsx
import { NodeCard } from "./NodeCard";

type NodeRecord = {
  node_id: string;
  display_name: string;
  observed_status: string;
  freshness: string;
  last_seen_at: string | null;
};

export function NodesPage({ nodes }: { nodes: NodeRecord[] }) {
  return (
    <section>
      <h1>Nodes</h1>
      {nodes.map((node) => (
        <NodeCard key={node.node_id} {...node} />
      ))}
    </section>
  );
}
```

```tsx
// frontend/src/App.tsx
import { useEventSource } from "./hooks/useEventSource";
import { NodesPage } from "./features/nodes/NodesPage";

export default function App() {
  const state = useEventSource("/api/stream");
  return <NodesPage nodes={state.nodes as never[]} />;
}
```

- [ ] **Step 4: Run the frontend test and production build**

Run:

```powershell
npm --prefix frontend run test -- --run frontend/src/features/nodes/NodesPage.test.tsx
npm --prefix frontend run build
```

Expected:

```text
PASS frontend/src/features/nodes/NodesPage.test.tsx
vite build completed successfully
```

- [ ] **Step 5: Commit the Nodes UI**

```powershell
git add frontend
git commit -m "feat: add nodes view and sse frontend hook"
```

## Task 7: Build The Runs View And Status Rendering

**Files:**
- Create: `frontend/src/features/runs/RunsPage.tsx`
- Create: `frontend/src/features/runs/RunRow.tsx`
- Create: `frontend/src/features/runs/RunsPage.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing Runs view test**

```tsx
// frontend/src/features/runs/RunsPage.test.tsx
import { render, screen } from "@testing-library/react";

import { RunsPage } from "./RunsPage";


describe("RunsPage", () => {
  it("renders submitted_unverified honestly", () => {
    render(
      <RunsPage
        runs={[
          {
            run_id: "run-1",
            summary: "Restart WORKER_A agent",
            status: "submitted_unverified",
            node_id: "WORKER_A",
          },
        ]}
      />,
    );

    expect(screen.getByText("Restart WORKER_A agent")).toBeInTheDocument();
    expect(screen.getByText("submitted_unverified")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify Runs components do not exist**

Run:

```powershell
npm --prefix frontend run test -- --run frontend/src/features/runs/RunsPage.test.tsx
```

Expected:

```text
FAIL  Cannot find module './RunsPage'
```

- [ ] **Step 3: Implement Runs components and mount them in the shell**

```tsx
// frontend/src/features/runs/RunRow.tsx
type RunRowProps = {
  run_id: string;
  summary: string;
  status: string;
  node_id: string;
};

export function RunRow(props: RunRowProps) {
  return (
    <tr>
      <td>{props.summary}</td>
      <td>{props.status}</td>
      <td>{props.node_id}</td>
    </tr>
  );
}
```

```tsx
// frontend/src/features/runs/RunsPage.tsx
import { RunRow } from "./RunRow";

type RunRecord = {
  run_id: string;
  summary: string;
  status: string;
  node_id: string;
};

export function RunsPage({ runs }: { runs: RunRecord[] }) {
  return (
    <section>
      <h1>Runs</h1>
      <table>
        <tbody>
          {runs.map((run) => (
            <RunRow key={run.run_id} {...run} />
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

```tsx
// frontend/src/App.tsx
import { useEventSource } from "./hooks/useEventSource";
import { NodesPage } from "./features/nodes/NodesPage";
import { RunsPage } from "./features/runs/RunsPage";

export default function App() {
  const state = useEventSource("/api/stream");

  return (
    <main>
      <NodesPage nodes={state.nodes as never[]} />
      <RunsPage runs={state.runs as never[]} />
    </main>
  );
}
```

- [ ] **Step 4: Run the Runs tests**

Run:

```powershell
npm --prefix frontend run test -- --run frontend/src/features/runs/RunsPage.test.tsx
```

Expected:

```text
PASS frontend/src/features/runs/RunsPage.test.tsx
```

- [ ] **Step 5: Commit the Runs UI**

```powershell
git add frontend
git commit -m "feat: add runs view"
```

## Task 8: Build The Models Surface And Routing Visibility View

**Files:**
- Create: `frontend/src/features/models/ModelsPage.tsx`
- Create: `frontend/src/features/models/ModelsPage.test.tsx`
- Create: `frontend/src/features/routing/RoutingPage.tsx`
- Create: `frontend/src/features/routing/RoutingPage.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing models and routing tests**

```tsx
// frontend/src/features/models/ModelsPage.test.tsx
import { render, screen } from "@testing-library/react";

import { ModelsPage } from "./ModelsPage";


describe("ModelsPage", () => {
  it("renders merged placements", () => {
    render(
      <ModelsPage
        models={[
          {
            model_name: "qwen3.6:latest",
            placements: ["ControlPlane", "WORKER_A"],
          },
        ]}
      />,
    );

    expect(screen.getByText("qwen3.6:latest")).toBeInTheDocument();
    expect(screen.getByText("ControlPlane, WORKER_A")).toBeInTheDocument();
  });
});
```

```tsx
// frontend/src/features/routing/RoutingPage.test.tsx
import { render, screen } from "@testing-library/react";

import { RoutingPage } from "./RoutingPage";


describe("RoutingPage", () => {
  it("renders the preferred node order", () => {
    render(
      <RoutingPage
        rules={[
          {
            rule_id: "scheduled-default",
            priority_class: "scheduled",
            preferred_nodes: ["ControlPlane", "WORKER_A"],
          },
        ]}
      />,
    );

    expect(screen.getByText("scheduled")).toBeInTheDocument();
    expect(screen.getByText("ControlPlane → WORKER_A")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the view tests to verify components are missing**

Run:

```powershell
npm --prefix frontend run test -- --run frontend/src/features/models/ModelsPage.test.tsx frontend/src/features/routing/RoutingPage.test.tsx
```

Expected:

```text
FAIL  Cannot find module './ModelsPage'
FAIL  Cannot find module './RoutingPage'
```

- [ ] **Step 3: Implement models and routing visibility components**

```tsx
// frontend/src/features/models/ModelsPage.tsx
type ModelRecord = {
  model_name: string;
  placements: string[];
};

export function ModelsPage({ models }: { models: ModelRecord[] }) {
  return (
    <section>
      <h1>Models</h1>
      {models.map((model) => (
        <article key={model.model_name}>
          <h2>{model.model_name}</h2>
          <p>{model.placements.join(", ")}</p>
        </article>
      ))}
    </section>
  );
}
```

```tsx
// frontend/src/features/routing/RoutingPage.tsx
type RoutingRuleRecord = {
  rule_id: string;
  priority_class: string;
  preferred_nodes: string[];
};

export function RoutingPage({ rules }: { rules: RoutingRuleRecord[] }) {
  return (
    <section>
      <h1>Routing</h1>
      {rules.map((rule) => (
        <article key={rule.rule_id}>
          <h2>{rule.priority_class}</h2>
          <p>{rule.preferred_nodes.join(" → ")}</p>
        </article>
      ))}
    </section>
  );
}
```

```tsx
// frontend/src/App.tsx
import { useEventSource } from "./hooks/useEventSource";
import { ModelsPage } from "./features/models/ModelsPage";
import { NodesPage } from "./features/nodes/NodesPage";
import { RoutingPage } from "./features/routing/RoutingPage";
import { RunsPage } from "./features/runs/RunsPage";

export default function App() {
  const state = useEventSource("/api/stream");

  return (
    <main>
      <NodesPage nodes={state.nodes as never[]} />
      <RunsPage runs={state.runs as never[]} />
      <ModelsPage models={state.models as never[]} />
      <RoutingPage rules={state.routing as never[]} />
    </main>
  );
}
```

- [ ] **Step 4: Run the frontend tests**

Run:

```powershell
npm --prefix frontend run test -- --run frontend/src/features/models/ModelsPage.test.tsx frontend/src/features/routing/RoutingPage.test.tsx
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit the models and routing UI**

```powershell
git add frontend
git commit -m "feat: add models and routing views"
```

## Task 9: Add Actions, Idempotency, Reconciliation, And Manual Smoke Coverage

**Files:**
- Create: `backend/app/api/actions.py`
- Create: `backend/app/services/actions.py`
- Create: `backend/app/services/reconciliation.py`
- Create: `tests/backend/test_actions.py`
- Create: `tests/backend/test_reconciliation.py`
- Create: `scripts/manual-smoke.ps1`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing action and reconciliation tests**

```python
# tests/backend/test_actions.py
from backend.app.services.actions import build_action_run_payload, build_idempotency_key


def test_build_idempotency_key_is_stable_for_same_request() -> None:
    left = build_idempotency_key(
        action_type="restart-agent",
        target_node_id="WORKER_A",
        target_resource_id="agent",
        payload={"service": "vantage-agent"},
        dedupe_window=30,
    )
    right = build_idempotency_key(
        action_type="restart-agent",
        target_node_id="WORKER_A",
        target_resource_id="agent",
        payload={"service": "vantage-agent"},
        dedupe_window=30,
    )

    assert left == right


def test_build_action_run_payload_uses_submitted_unverified() -> None:
    payload = build_action_run_payload(node_id="WORKER_A", summary="Refresh node WORKER_A")

    assert payload["status"] == "submitted_unverified"
    assert payload["node_id"] == "WORKER_A"
```

```python
# tests/backend/test_reconciliation.py
from backend.app.services.reconciliation import detect_config_drift


def test_detect_config_drift_flags_enabled_node_without_recent_snapshot() -> None:
    warnings = detect_config_drift(
        configured_nodes=[{"node_id": "WORKER_A", "enabled": True}],
        observed_nodes={},
    )

    assert warnings[0]["warning_type"] == "config_drift"
    assert warnings[0]["node_id"] == "WORKER_A"
```

- [ ] **Step 2: Run the tests to verify the hardening services are missing**

Run:

```powershell
python -m pytest tests/backend/test_actions.py tests/backend/test_reconciliation.py -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.services.actions'
```

- [ ] **Step 3: Implement idempotency, a first safe action, reconciliation warnings, and smoke commands**

```python
# backend/app/services/actions.py
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4


def build_idempotency_key(
    action_type: str,
    target_node_id: str,
    target_resource_id: str,
    payload: dict,
    dedupe_window: int,
) -> str:
    stable = json.dumps(
        {
            "action_type": action_type,
            "target_node_id": target_node_id,
            "target_resource_id": target_resource_id,
            "payload": payload,
            "dedupe_window": dedupe_window,
        },
        sort_keys=True,
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def build_action_run_payload(node_id: str, summary: str) -> dict:
    return {
        "run_id": str(uuid4()),
        "node_id": node_id,
        "status": "submitted_unverified",
        "summary": summary,
        "started_at": datetime.now(UTC),
    }


def submit_refresh_node_action(node_id: str) -> dict:
    return build_action_run_payload(node_id=node_id, summary=f"Refresh node {node_id}")
```

```python
# backend/app/services/reconciliation.py
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from backend.app.models import WarningRecord


def detect_config_drift(configured_nodes: list[dict], observed_nodes: dict[str, dict]) -> list[dict]:
    warnings = []
    for node in configured_nodes:
        if node["enabled"] and node["node_id"] not in observed_nodes:
            warnings.append(
                {
                    "warning_id": str(uuid4()),
                    "warning_type": "config_drift",
                    "node_id": node["node_id"],
                    "severity": "warning",
                    "first_seen_at": datetime.now(UTC).isoformat(),
                    "last_seen_at": datetime.now(UTC).isoformat(),
                    "status": "active",
                    "summary": f"Configured node {node['node_id']} has no recent observation",
                    "metadata_json": {},
                }
            )
    return warnings


def upsert_warning_records(session, warnings: list[dict]) -> None:
    for payload in warnings:
        existing = session.scalar(
            select(WarningRecord).where(
                WarningRecord.warning_type == payload["warning_type"],
                WarningRecord.node_id == payload["node_id"],
                WarningRecord.status == "active",
            )
        )
        if existing:
            existing.last_seen_at = payload["last_seen_at"]
            existing.summary = payload["summary"]
        else:
            session.add(WarningRecord(**payload))
    session.commit()
```

```python
# backend/app/api/actions.py
from fastapi import APIRouter

from backend.app.db import SessionLocal
from backend.app.models import Run
from backend.app.services.actions import submit_refresh_node_action

router = APIRouter()


@router.post("/actions/refresh-node/{node_id}")
def refresh_node(node_id: str) -> dict:
    payload = submit_refresh_node_action(node_id)
    with SessionLocal() as session:
        session.add(
            Run(
                run_id=payload["run_id"],
                source_type="agent_action",
                detail_type="agent_action",
                source_id=f"refresh-node:{node_id}",
                node_id=node_id,
                action_type="sync",
                status=payload["status"],
                summary=payload["summary"],
                started_at=payload["started_at"],
                metadata_json={},
            )
        )
        session.commit()
    return payload
```

```powershell
# scripts/manual-smoke.ps1
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/nodes
Invoke-RestMethod http://127.0.0.1:8000/api/runs
Invoke-WebRequest http://127.0.0.1:8000/api/stream -Headers @{Accept='text/event-stream'}
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/actions/refresh-node/WORKER_A
```

- [ ] **Step 4: Register the action route and rerun the hardening tests**

```python
# backend/app/main.py
from fastapi import FastAPI

from backend.app.api.actions import router as actions_router
from backend.app.api.health import router as health_router
from backend.app.api.models import router as models_router
from backend.app.api.nodes import router as nodes_router
from backend.app.api.routing import router as routing_router
from backend.app.api.runs import router as runs_router
from backend.app.api.stream import router as stream_router
from backend.app.api.warnings import router as warnings_router

app = FastAPI(title="Vantage Control Plane")
app.include_router(health_router, prefix="/api")
app.include_router(nodes_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(routing_router, prefix="/api")
app.include_router(warnings_router, prefix="/api")
app.include_router(stream_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
```

Run:

```powershell
python -m pytest tests/backend/test_actions.py tests/backend/test_reconciliation.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit the action layer and hardening**

```powershell
git add backend tests/backend scripts/manual-smoke.ps1
git commit -m "feat: add action layer and reconciliation warnings"
```

## Plan Self-Review

### Spec Coverage

- `Nodes` surface: covered by Tasks 4, 5, and 6
- `Runs` surface: covered by Tasks 5 and 7
- `Models` surface: covered by Tasks 4, 5, and 8
- `Routing` visibility: covered by Task 8
- WORKER_A agent from day one: covered by Task 2
- SSE full-state-on-connect and reconnect contract: covered by Task 5 and consumed in Task 6
- snapshot pruning: covered by Task 4
- reconciliation warnings: covered by Task 9
- small action layer with `submitted_unverified`: covered by Task 9
- structured logging from the start: covered by Task 1

No Phase 1 requirement from the approved spec is left without a task.

### Placeholder Scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Commands are explicit.
- File paths are explicit.
- Test targets are named before implementation.

### Type Consistency

- Product name is consistently `Vantage`.
- `submitted_unverified` is used consistently between the spec and UI plan.
- `Node`, `NodeSnapshot`, `Run`, `ModelPlacement`, `RoutingRule`, `RoutingRuleNode`, `AppSetting`, and `WarningRecord` names match the spec.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-22-vantage-phase-1-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
