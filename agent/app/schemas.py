from datetime import datetime

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


class RunInfo(BaseModel):
    run_id: str
    source_type: str
    detail_type: str
    source_id: str
    node_id: str
    model_name: str | None = None
    action_type: str | None = None
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    summary: str
    metadata_json: dict


class RunsResponse(BaseModel):
    runs: list[RunInfo]


class CapabilityCheckRequest(BaseModel):
    model_name: str
    prompt: str | None = None


class EvalAttemptRequest(BaseModel):
    model_name: str
    prompt: str
    expected_json: dict | None = None
    score_type: str | None = None
    score_config_json: dict | None = None
