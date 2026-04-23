from fastapi import Depends, FastAPI

from agent.app.auth import require_agent_auth
from agent.app import collectors
from agent.app.schemas import CapabilityCheckRequest, GpuResponse, HealthResponse, ModelsResponse, RunInfo, RunsResponse

app = FastAPI(title="Vantage Bastet Agent", dependencies=[Depends(require_agent_auth)])


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    return collectors.get_health()


@app.get("/gpu", response_model=GpuResponse)
def gpu() -> dict:
    return {"gpus": collectors.get_gpu_stats()}


@app.get("/models", response_model=ModelsResponse)
def models() -> dict:
    return {"models": collectors.get_models()}


@app.get("/runs", response_model=RunsResponse)
def runs() -> dict:
    return {"runs": collectors.get_runs()}


@app.post("/capability-check", response_model=RunInfo)
def capability_check(request: CapabilityCheckRequest) -> dict:
    return collectors.run_capability_check(request.model_name, prompt=request.prompt)
