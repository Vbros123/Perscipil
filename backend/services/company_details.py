"""Descriptive company facts from the selected entity's Wikidata statements."""
import re
from datetime import date


def _value(snak):
    return (snak.get("datavalue") or {}).get("value")


def _dated_count(statement):
    qualifiers = statement.get("qualifiers") or {}
    # Scoped or estimated quantities can describe just one division or site.
    if set(qualifiers) != {"P585"} or len(qualifiers["P585"]) != 1:
        return None
    when = _value(qualifiers["P585"][0]) or {}
    quantity = _value(statement.get("mainsnak", {})) or {}
    if not isinstance(quantity, dict) or not isinstance(when, dict):
        return None
    amount = quantity.get("amount", "")
    if quantity.get("unit") != "1" or not isinstance(amount, str) or not re.fullmatch(r"\+?\d{1,12}", amount):
        return None
    if any(quantity.get(k, amount) != amount for k in ("lowerBound", "upperBound")):
        return None
    precision = when.get("precision")
    if precision not in (9, 10, 11):
        return None
    timestamp = str(when.get("time", ""))
    if not timestamp.startswith("+"):
        return None
    stamp = timestamp[1:][: {9: 4, 10: 7, 11: 10}[precision]]
    try:
        start = date.fromisoformat(stamp + {9: "-01-01", 10: "-01", 11: ""}[precision])
    except ValueError:
        return None
    if start > date.today():
        return None
    return stamp, int(amount)


def company_details(claims, qid):
    source = f"https://www.wikidata.org/wiki/{qid}"
    observations = {}
    for claim in claims.get("P1128", []):
        if claim.get("rank") == "deprecated" or not claim.get("references"):
            continue
        observed = _dated_count(claim)
        if observed:
            stamp, count = observed
            observations.setdefault(stamp, set()).add(count)
    headcount = None
    if observations:
        latest = max(observations)
        if len(observations[latest]) == 1:
            headcount = {"value": next(iter(observations[latest])), "asOf": latest,
                         "sourceUrl": source + "#P1128"}

    addresses = []
    for claim in claims.get("P6375", []):
        if claim.get("rank") == "deprecated" or claim.get("qualifiers") or not claim.get("references"):
            continue
        value = _value(claim.get("mainsnak", {}))
        address = value.get("text", "").strip() if isinstance(value, dict) else ""
        if address and address not in addresses:
            addresses.append(address)
    return {"employeeCount": headcount, "streetAddresses": addresses, "addressSource": source + "#P6375"}
