import json
import logging

from backend.app.logging import JsonFormatter


def test_json_formatter_includes_operational_fields() -> None:
    record = logging.LogRecord(
        name="vantage.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="health_check",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "vantage.test"
    assert payload["message"] == "health_check"
    assert "timestamp" in payload
