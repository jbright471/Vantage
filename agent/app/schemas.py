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


class RunsResponse(BaseModel):
    runs: list[dict]
