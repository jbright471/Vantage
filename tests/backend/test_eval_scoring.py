from backend.app.services.evals import score_expected_json


def test_score_expected_json_passes_for_expected_subset() -> None:
    score = score_expected_json('{"answer": 42, "notes": "ok"}', {"answer": 42})

    assert score["passed"] is True
    assert score["score"] == 1.0


def test_score_expected_json_fails_when_response_is_not_json() -> None:
    score = score_expected_json("not json", {"answer": 42})

    assert score["passed"] is False
    assert score["score"] == 0.0
    assert score["reason"] == "response_not_json"


def test_score_expected_json_fails_for_missing_expected_values() -> None:
    score = score_expected_json('{"answer": 24}', {"answer": 42})

    assert score["passed"] is False
    assert score["missing_or_mismatched"] == ["answer"]
