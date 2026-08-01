import pytest

from services.model_validation import evaluate_records


def record(index, probability, outcome, subgroup="software", coverage=1.0):
    return {
        "company_id": f"company-{index}",
        "distress_probability": probability,
        "distress_within_12m": outcome,
        "evidence_coverage": coverage,
        "subgroup": subgroup,
    }


def test_validation_harness_reports_discrimination_and_calibration():
    rows = []
    for index in range(250):
        rows.append(record(index, 0.96, 1, "software" if index % 2 else "services"))
    for index in range(250, 500):
        rows.append(record(index, 0.04, 0, "software" if index % 2 else "services"))

    result = evaluate_records(rows)

    assert result["metrics"]["roc_auc"] == 1
    assert result["metrics"]["pr_auc"] == 1
    assert result["metrics"]["false_negative_rate"] == 0
    assert result["approved"] is True


def test_validation_harness_rejects_duplicate_companies():
    rows = [record(1, 0.8, 1), record(1, 0.2, 0)]
    with pytest.raises(ValueError, match="duplicate company_id"):
        evaluate_records(rows)


def test_small_or_uninformative_holdout_cannot_approve_release():
    rows = [record(index, 0.5, index % 2) for index in range(40)]
    result = evaluate_records(rows)

    assert result["checks"]["sample_size"] is False
    assert result["checks"]["event_count"] is False
    assert result["approved"] is False


def test_tied_predictions_do_not_get_order_dependent_precision_credit():
    rows = [record(index, 0.5, 1 if index < 250 else 0) for index in range(500)]
    result = evaluate_records(rows)

    assert result["metrics"]["roc_auc"] == 0.5
    assert result["metrics"]["pr_auc"] == 0.5
    assert result["checks"]["roc_auc"] is False
