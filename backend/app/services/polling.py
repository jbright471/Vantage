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
