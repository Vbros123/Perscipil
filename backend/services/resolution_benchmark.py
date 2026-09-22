"""Benchmark labeled outputs without weakening the production resolver."""

REQUIRED_CASES = {
    "exact_name",
    "suffix",
    "alias",
    "parent_subsidiary",
    "same_name",
    "wrong_country",
    "wrong_postcode",
    "wrong_registration",
    "wrong_domain",
    "person",
    "nonprofit",
    "government",
    "inactive",
    "provider_disagreement",
}


def evaluate(cases):
    missing = REQUIRED_CASES - {c["category"] for c in cases}
    if missing:
        raise ValueError("Missing case categories: " + ",".join(sorted(missing)))
    counts = dict(
        correct_match=0,
        false_positive=0,
        false_negative=0,
        abstention=0,
        correct_rejection=0,
    )
    squared = []
    for c in cases:
        expected, actual = c["expected_id"], c["predicted_id"]
        confidence = c["confidence"]
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence outside [0,1]")
        if actual is None:
            counts["abstention"] += 1
            counts["correct_rejection" if expected is None else "false_negative"] += 1
        elif actual == expected:
            counts["correct_match"] += 1
        else:
            counts["false_positive"] += 1
        if actual is not None:
            squared.append((confidence - int(actual == expected)) ** 2)
    return {
        "status": "LABELED BENCHMARK ONLY - REPRESENTATIVENESS NOT ESTABLISHED",
        "cases": len(cases),
        **counts,
        "match_confidence_brier": sum(squared) / len(squared) if squared else None,
    }
