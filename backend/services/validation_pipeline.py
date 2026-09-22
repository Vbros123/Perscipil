"""Outcome evaluation infrastructure. Research scores are never probabilities.
Input probability must come from a separately fitted, frozen model; not score/1000.
"""

import math, random
from datetime import datetime


def metrics(rows, threshold=0.5):
    if not rows:
        raise ValueError("Empty evaluation cohort")
    y = [r["outcome"] for r in rows]
    p = [r["probability"] for r in rows]
    if any(v not in (0, 1) for v in y) or any(
        not math.isfinite(v) or not 0 <= v <= 1 for v in p
    ):
        raise ValueError("Binary outcomes and bounded probabilities required")
    positives = sum(y)
    negatives = len(y) - positives
    tp = sum(a == 1 and b >= threshold for a, b in zip(y, p))
    fp = sum(a == 0 and b >= threshold for a, b in zip(y, p))
    # O(n log n) rank groups preserve exact ties without pairwise expansion.
    grouped = {}
    for outcome, probability in zip(y, p):
        pos, neg = grouped.get(probability, (0, 0))
        grouped[probability] = (pos + outcome, neg + 1 - outcome)
    below = 0
    credit = 0.0
    for score in sorted(grouped):
        pos, neg = grouped[score]
        credit += pos * (below + 0.5 * neg)
        below += neg
    auc = credit / (positives * negatives) if positives and negatives else None
    ap = 0.0
    hits = total = 0
    for score in sorted(grouped, reverse=True):
        pos, neg = grouped[score]
        hits += pos
        total += pos + neg
        if positives:
            ap += (pos / positives) * hits / total
    ece = 0
    for i in range(10):
        pairs = [(a, b) for a, b in zip(y, p) if min(9, int(b * 10)) == i]
        if pairs:
            ece += (
                len(pairs)
                / len(y)
                * abs(
                    sum(a for a, b in pairs) / len(pairs)
                    - sum(b for a, b in pairs) / len(pairs)
                )
            )
    return {
        "n": len(y),
        "roc_auc": auc,
        "average_precision": ap if positives else None,
        "brier": sum((a - b) ** 2 for a, b in zip(y, p)) / len(y),
        "calibration_error_10_bins": ece,
        "false_negative_rate": (positives - tp) / positives if positives else None,
        "false_positive_rate": fp / negatives if negatives else None,
    }


def evaluate(rows, split_date, fixture=True, seed=42):
    boundary = datetime.fromisoformat(split_date)
    train = []
    test = []
    seen = set()
    for row in rows:
        if row["entity_id"] in seen:
            raise ValueError("Duplicate entity: use an entity-disjoint cohort")
        seen.add(row["entity_id"])
        observed = datetime.fromisoformat(row["observed_at"])
        outcome = datetime.fromisoformat(row["outcome_at"])
        if outcome <= observed:
            raise ValueError("Outcome must follow observation")
        # Training labels must be available before the model freeze date.
        if observed < boundary:
            if outcome >= boundary:
                raise ValueError("Training-label leakage across split")
            train.append(row)
        else:
            test.append(row)
    if not train or not test:
        raise ValueError("Both time partitions required")
    train_metrics = metrics(train)
    test_metrics = metrics(test)
    prevalence = sum(r["outcome"] for r in train) / len(train)
    baseline = metrics([{**r, "probability": prevalence} for r in test])
    rng = random.Random(seed)
    errors = [(r["outcome"] - r["probability"]) ** 2 for r in test]
    boot = [sum(rng.choices(errors, k=len(errors))) / len(errors) for _ in range(200)]
    boot.sort()
    groups = {
        g: metrics([r for r in test if r.get("subgroup", "unspecified") == g])
        for g in sorted({r.get("subgroup", "unspecified") for r in test})
    }
    histogram = lambda data: [
        sum(min(9, int(r["probability"] * 10)) == i for r in data) / len(data)
        for i in range(10)
    ]
    a, b = histogram(train), histogram(test)
    return {
        "status": "NOT VALIDATED ON REAL OUTCOMES"
        if fixture
        else "UNREVIEWED OUTCOME EVALUATION - NOT PRODUCT VALIDATION",
        "split_date": split_date,
        "train": train_metrics,
        "out_of_time": test_metrics,
        "baseline_train_prevalence": baseline,
        "brier_bootstrap_95_percentile_interval": [boot[5], boot[194]],
        "subgroups": groups,
        "probability_distribution_train": a,
        "probability_distribution_test": b,
        "population_stability_index": sum(
            (x - y) * math.log((x + 1e-6) / (y + 1e-6)) for x, y in zip(a, b)
        ),
        "limitations": "200 entity bootstrap samples; intervals are exploratory. Average precision is the PR summary. Requires independent model fitting and representative lawful labels.",
    }
