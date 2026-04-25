from fastapi.testclient import TestClient

from backend.app.main import app


def test_operator_guide_markdown_is_served_from_api() -> None:
    with TestClient(app) as client:
        response = client.get("/api/docs/operator-guide.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Vantage Operator Guide" in response.text
