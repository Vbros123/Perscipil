import pytest
from services.validation_pipeline import evaluate, metrics
from services.resolution_benchmark import evaluate as resolution, REQUIRED_CASES


def test_known_metrics_and_temporal_leakage():
    assert (
        metrics(
            [{"outcome": 0, "probability": 0.1}, {"outcome": 1, "probability": 0.9}]
        )["roc_auc"]
        == 1
    )
    assert (
        metrics(
            [{"outcome": 0, "probability": 0.5}, {"outcome": 1, "probability": 0.5}]
        )["roc_auc"]
        == 0.5
    )
    rows = [
        {
            "entity_id": str(i),
            "observed_at": "2024-01-01" if i < 10 else "2025-02-01",
            "outcome_at": "2024-09-01" if i < 10 else "2025-09-01",
            "outcome": i % 2,
            "probability": 0.3 + 0.4 * (i % 2),
        }
        for i in range(20)
    ]
    result = evaluate(rows, "2025-01-01")
    assert result["status"] == "NOT VALIDATED ON REAL OUTCOMES"
    assert result["out_of_time"]["n"] == 10
    with pytest.raises(ValueError):
        evaluate(rows + [rows[0]], "2025-01-01")
    rows[0]["outcome_at"] = "2025-03-01"
    with pytest.raises(ValueError):
        evaluate(rows, "2025-01-01")


def test_resolution_harness_counts():
    cases = [
        {"category": c, "expected_id": "a", "predicted_id": "a", "confidence": 0.9}
        for c in REQUIRED_CASES
    ]
    cases[0]["predicted_id"] = None
    cases[1]["predicted_id"] = "wrong"
    result = resolution(cases)
    assert result["false_positive"] == 1
    assert result["false_negative"] == 1
    assert result["abstention"] == 1
