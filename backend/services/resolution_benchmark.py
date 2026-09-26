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


async def collect(cases, resolver=None):
    """Run the production resolver; expected IDs remain independent labels.

    Cases choose id_field (lei, cik, domain, or canonical_name); no fuzzy match
    is substituted for the label. Unresolved/ambiguous decisions abstain.
    """
    from services.resolver import resolve_company
    resolver = resolver or resolve_company
    outputs=[]
    for case in cases:
        result=await resolver(case['query'],country_code=case.get('country_code'))
        field=case.get('id_field','canonical_name')
        if field not in {'lei','cik','domain','canonical_name'}:
            raise ValueError('Unsupported identity label field')
        predicted=None
        if result.resolution_status=='resolved' and not result.needs_disambiguation:
            predicted=result.identifiers.get(field) if field in {'lei','cik'} else getattr(result,field)
        outputs.append({**case,'predicted_id':predicted,'confidence':result.resolution_confidence/100,
                        'resolution_status':result.resolution_status})
    return {'evaluation':evaluate(outputs),'outputs':outputs}
