from datetime import UTC, datetime
import subprocess


def _parse_ollama_list_output(output: str) -> list[dict]:
    rows: list[dict] = []
    lines = output.strip().splitlines()
    for line in lines[1:]:
        parts = line.split()
        if not parts:
            continue
        rows.append(
            {
                "name": parts[0],
                "digest": None,
            }
        )
    return rows


def collect_local_snapshot(node_id: str) -> dict:
    result = subprocess.run(
        ["ollama", "list"],
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
        "ollama_json": {"status": "ok", "models": _parse_ollama_list_output(result.stdout)},
    }
