import json
import subprocess


def get_health() -> dict:
    return {"status": "ok", "node_id": "bastet"}


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
        if not line.strip():
            continue
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
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = []
    lines = result.stdout.strip().splitlines()
    for line in lines[1:]:
        parts = line.split()
        if not parts:
            continue
        rows.append(
            {
                "model_name": parts[0],
                "model_digest": None,
                "available": True,
            }
        )
    return rows


def get_runs() -> list[dict]:
    return []
