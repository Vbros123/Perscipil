"""Independently recompute every published Perspicil Score from the mock gateway's
raw inputs and compare against what the API returned."""
import json
import urllib.parse
import urllib.request

API = "http://127.0.0.1:8099"

PROFILES = {
    "Healthy Corp":    dict(credit=92, dbt=0,  status="active",    bk=0, li=0, tx=0, lit=0,
                            cr=2.4, dscr=2.2, ocf=0.22, mc=18, rg=0.45),
    "Distressed Corp": dict(credit=8,  dbt=75, status="dissolved", bk=1, li=6, tx=3, lit=12,
                            cr=0.3, dscr=0.2, ocf=-0.35, mc=0.5, rg=-0.55),
    "Average Corp":    dict(credit=55, dbt=12, status="active",    bk=0, li=1, tx=0, lit=2,
                            cr=1.2, dscr=1.1, ocf=0.05, mc=6, rg=0.10),
    "Burn Startup":    dict(credit=48, dbt=5,  status="active",    bk=0, li=0, tx=0, lit=0,
                            cr=1.8, dscr=0.4, ocf=-0.28, mc=14, rg=0.90),
    "Declining Corp":  dict(credit=70, dbt=18, status="active",    bk=0, li=2, tx=1, lit=3,
                            cr=1.6, dscr=1.5, ocf=0.12, mc=9, rg=-0.30),
}

W = {"credit": 0.30, "pay": 0.20, "cash": 0.20, "ident": 0.15, "legal": 0.15}
STATUS = {"active": 100, "registered": 95, "inactive": 25, "dissolved": 10, "revoked": 5}
BANDS = [(850, "Exceptional"), (700, "Strong"), (550, "Adequate"),
         (400, "Weak"), (250, "Distressed"), (0, "Critical")]


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def expected(p):
    credit = clamp(p["credit"])
    pay = clamp(100 - max(0, p["dbt"]) * 2.5)
    ident = STATUS[p["status"]]
    legal = clamp(100 - min(100, p["bk"] * 100) - min(45, p["li"] * 12)
                  - min(60, p["tx"] * 25) - min(35, p["lit"] * 7))
    comps = [clamp(p["cr"] / 2 * 100), clamp(p["dscr"] / 2 * 100),
             clamp((p["ocf"] + 0.10) / 0.35 * 100), clamp(p["mc"] / 12 * 100),
             clamp((p["rg"] + 0.20) / 0.70 * 100)]
    cash = sum(comps) / len(comps)
    # Transforms round each signal to 2dp before the weighted sum.
    parts = {"credit": round(credit, 2), "pay": round(pay, 2), "cash": round(cash, 2),
             "ident": round(ident, 2), "legal": round(legal, 2)}
    weighted = sum(parts[k] * W[k] for k in parts)
    normalized = weighted / sum(W.values())
    score = max(0, min(1000, int(round(normalized * 10))))
    rating = next(label for thr, label in BANDS if score >= thr)
    return parts, score, rating


def get(company):
    url = f"{API}/api/score?company={urllib.parse.quote(company)}&registration_number=REG-{abs(hash(company))%9999}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


NAME_MAP = {"Commercial Credit Risk": "credit", "B2B Payment Behavior": "pay",
            "Cash Flow & Liquidity": "cash", "Business Identity & Standing": "ident",
            "Liens, Bankruptcy & Litigation": "legal"}

fails = 0
print(f"{'COMPANY':17} {'API':>5} {'EXPECT':>6} {'RATING (api / expected)':32} SIGNAL CHECK")
print("-" * 100)
for company, profile in PROFILES.items():
    data = get(company)
    parts, exp_score, exp_rating = expected(profile)
    api_score = data["private_score"]
    api_rating = data["rating"]

    signal_issues = []
    for item in data["breakdown"]:
        key = NAME_MAP.get(item["signal"])
        if key is None:
            continue
        if not item["used_in_score"]:
            signal_issues.append(f"{key}:unscored")
            continue
        if abs(item["raw_score"] - round(parts[key], 1)) > 0.051:
            signal_issues.append(f"{key}: api={item['raw_score']} exp={parts[key]}")

    ok = api_score == exp_score and api_rating == exp_rating and not signal_issues
    fails += 0 if ok else 1
    print(f"{company:17} {api_score:>5} {exp_score:>6} {api_rating + ' / ' + exp_rating:32} "
          f"{'OK' if not signal_issues else '; '.join(signal_issues)}  {'PASS' if ok else 'FAIL'}")
    print(f"{'':17} raws api={{"
          + ", ".join(f"{NAME_MAP[i['signal']]}={i['raw_score']}" for i in data["breakdown"]
                      if i['signal'] in NAME_MAP)
          + "}")
    print(f"{'':17} raws exp={parts}")
    print(f"{'':17} coverage={data['meta']['evidence_coverage']} providers={data['meta']['provider_diversity']} "
          f"confidence={data['meta']['confidence']} gates={data['meta']['gates']}")

print("\nFAILURES:", fails)

# Ordering sanity: distress must rank below health.
scores = {c: get(c)["private_score"] for c in PROFILES}
print("\nRanking:", sorted(scores.items(), key=lambda kv: -kv[1]))
assert scores["Healthy Corp"] > scores["Average Corp"] > scores["Distressed Corp"], "ordering broken"
print("Ordering sane: Healthy > Average > Distressed")
