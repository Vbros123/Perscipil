"""Out-of-time model validation metrics and release policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


RELEASE_THRESHOLDS = {
    "minimum_records": 500,
    "minimum_distress_events": 50,
    "minimum_roc_auc": 0.70,
    "minimum_pr_auc_lift": 1.50,
    "maximum_brier_score": 0.20,
    "maximum_calibration_error": 0.08,
    "maximum_false_negative_rate": 0.25,
    "minimum_coverage": 0.80,
    "minimum_subgroup_records": 50,
    "maximum_subgroup_auc_gap": 0.10,
}


@dataclass(frozen=True)
class ValidationRecord:
    company_id: str
    distress_probability: float
    distress_within_12m: int
    evidence_coverage: float
    subgroup: str = "all"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ValidationRecord":
        record = cls(
            company_id=str(payload["company_id"]),
            distress_probability=float(payload["distress_probability"]),
            distress_within_12m=int(payload["distress_within_12m"]),
            evidence_coverage=float(payload["evidence_coverage"]),
            subgroup=str(payload.get("subgroup") or "all"),
        )
        if not 0 <= record.distress_probability <= 1:
            raise ValueError("distress_probability must be between 0 and 1")
        if record.distress_within_12m not in {0, 1}:
            raise ValueError("distress_within_12m must be 0 or 1")
        if not 0 <= record.evidence_coverage <= 1:
            raise ValueError("evidence_coverage must be between 0 and 1")
        return record


def _roc_auc(records: list[ValidationRecord]) -> float | None:
    positives = [item for item in records if item.distress_within_12m == 1]
    negatives = [item for item in records if item.distress_within_12m == 0]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive.distress_probability > negative.distress_probability:
                wins += 1
            elif positive.distress_probability == negative.distress_probability:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _pr_auc(records: list[ValidationRecord]) -> float | None:
    positive_count = sum(item.distress_within_12m for item in records)
    if positive_count == 0:
        return None
    ranked = sorted(records, key=lambda item: item.distress_probability, reverse=True)
    true_positives = 0
    false_positives = 0
    previous_recall = 0.0
    area = 0.0
    index = 0
    while index < len(ranked):
        threshold = ranked[index].distress_probability
        group: list[ValidationRecord] = []
        while index < len(ranked) and ranked[index].distress_probability == threshold:
            group.append(ranked[index])
            index += 1
        true_positives += sum(item.distress_within_12m for item in group)
        false_positives += sum(1 - item.distress_within_12m for item in group)
        recall = true_positives / positive_count
        precision = true_positives / (true_positives + false_positives)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def _brier(records: list[ValidationRecord]) -> float:
    return sum((item.distress_probability - item.distress_within_12m) ** 2 for item in records) / len(records)


def _expected_calibration_error(records: list[ValidationRecord], bins: int = 10) -> float:
    total = len(records)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            item for item in records
            if lower <= item.distress_probability < upper
            or (index == bins - 1 and item.distress_probability == 1)
        ]
        if not members:
            continue
        predicted = sum(item.distress_probability for item in members) / len(members)
        observed = sum(item.distress_within_12m for item in members) / len(members)
        error += len(members) / total * abs(predicted - observed)
    return error


def _false_negative_rate(records: list[ValidationRecord], threshold: float) -> float | None:
    positives = [item for item in records if item.distress_within_12m == 1]
    if not positives:
        return None
    false_negatives = sum(item.distress_probability < threshold for item in positives)
    return false_negatives / len(positives)


def evaluate_records(
    rows: Iterable[ValidationRecord | dict[str, Any]],
    decision_threshold: float = 0.50,
) -> dict[str, Any]:
    records = [item if isinstance(item, ValidationRecord) else ValidationRecord.from_dict(item) for item in rows]
    if not records:
        raise ValueError("At least one validation record is required")
    company_ids = [item.company_id for item in records]
    if len(company_ids) != len(set(company_ids)):
        raise ValueError("The holdout contains duplicate company_id values")

    events = sum(item.distress_within_12m for item in records)
    prevalence = events / len(records)
    roc_auc = _roc_auc(records)
    pr_auc = _pr_auc(records)
    pr_lift = pr_auc / prevalence if pr_auc is not None and prevalence > 0 else None
    subgroup_auc: dict[str, float] = {}
    eligible_subgroups = []
    for subgroup in sorted({item.subgroup for item in records}):
        members = [item for item in records if item.subgroup == subgroup]
        if len(members) < RELEASE_THRESHOLDS["minimum_subgroup_records"]:
            continue
        eligible_subgroups.append(subgroup)
        value = _roc_auc(members)
        if value is not None:
            subgroup_auc[subgroup] = value
    subgroup_gap = max(subgroup_auc.values()) - min(subgroup_auc.values()) if len(subgroup_auc) >= 2 else 0.0

    metrics = {
        "records": len(records),
        "distress_events": events,
        "prevalence": prevalence,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "pr_auc_lift": pr_lift,
        "brier_score": _brier(records),
        "expected_calibration_error": _expected_calibration_error(records),
        "false_negative_rate": _false_negative_rate(records, decision_threshold),
        "coverage": sum(item.evidence_coverage >= 0.70 for item in records) / len(records),
        "subgroup_roc_auc": subgroup_auc,
        "subgroup_auc_coverage": len(subgroup_auc) / len(eligible_subgroups) if eligible_subgroups else 1.0,
        "subgroup_auc_gap": subgroup_gap,
        "decision_threshold": decision_threshold,
    }
    checks = {
        "sample_size": metrics["records"] >= RELEASE_THRESHOLDS["minimum_records"],
        "event_count": metrics["distress_events"] >= RELEASE_THRESHOLDS["minimum_distress_events"],
        "roc_auc": metrics["roc_auc"] is not None and metrics["roc_auc"] >= RELEASE_THRESHOLDS["minimum_roc_auc"],
        "pr_auc_lift": metrics["pr_auc_lift"] is not None and metrics["pr_auc_lift"] >= RELEASE_THRESHOLDS["minimum_pr_auc_lift"],
        "brier_score": metrics["brier_score"] <= RELEASE_THRESHOLDS["maximum_brier_score"],
        "calibration": metrics["expected_calibration_error"] <= RELEASE_THRESHOLDS["maximum_calibration_error"],
        "false_negative_rate": metrics["false_negative_rate"] is not None and metrics["false_negative_rate"] <= RELEASE_THRESHOLDS["maximum_false_negative_rate"],
        "coverage": metrics["coverage"] >= RELEASE_THRESHOLDS["minimum_coverage"],
        "subgroup_gap": metrics["subgroup_auc_gap"] <= RELEASE_THRESHOLDS["maximum_subgroup_auc_gap"],
        "subgroup_outcomes": metrics["subgroup_auc_coverage"] == 1.0,
    }
    return {
        "schema": "privatelens.model-validation.v1",
        "metrics": metrics,
        "thresholds": RELEASE_THRESHOLDS,
        "checks": checks,
        "approved": all(checks.values()),
    }
