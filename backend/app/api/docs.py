from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse


router = APIRouter()


def operator_guide_path() -> Path:
    return Path(__file__).resolve().parents[3] / "OPERATOR_GUIDE.md"


@router.get("/docs/operator-guide.md", response_class=PlainTextResponse)
def get_operator_guide() -> PlainTextResponse:
    guide_path = operator_guide_path()

    if not guide_path.exists():
        raise HTTPException(status_code=404, detail="Operator guide not found")

    return PlainTextResponse(
        guide_path.read_text(encoding="utf-8"),
        media_type="text/markdown; charset=utf-8",
    )
