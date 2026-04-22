from fastapi import FastAPI

from agent.app import collectors
from agent.app.schemas import GpuResponse, HealthResponse, ModelsResponse, RunsResponse

app = FastAPI(title="Vantage Bastet Agent")


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
