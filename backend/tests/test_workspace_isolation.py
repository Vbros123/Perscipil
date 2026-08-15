import time

from conftest import strong_password


async def fake_score_company(company_name: str, identity=None, refresh=False):
    return {
        "company_name": company_name,
        "normalized_name": company_name.lower(),
        "private_score": 712,
        "scoring_status": "rated",
        "rating": "Strong",
        "color": "#2dd4bf",
        "summary": "Synthetic test score.",
        "breakdown": [],
        "category_summary": {},
        "risk_flags": [],
        "meta": {
            "total_signals": 0,
            "real_signals": 0,
            "simulated_signals": 0,
            "confidence": 0,
            "model_version": "test",
            "cached": False,
        },
        "elapsed_seconds": 0.01,
        "report": {"headline": "Synthetic report", "risk_level": "Low"},
    }


def signup(api, label):
    email = f"{label}-{int(time.time() * 1000)}@example.com"
    response = api.post("/api/auth/signup", json={"email": email, "password": strong_password()})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_history_and_watchlist_are_user_isolated(api, monkeypatch):
    import routers.compare as compare_router
    import routers.score as score_router

    monkeypatch.setattr(score_router, "score_company", fake_score_company)
    monkeypatch.setattr(compare_router, "score_company", fake_score_company)

    user_one = signup(api, "one")
    user_two = signup(api, "two")

    score = api.get("/api/score?company=Acme", headers=user_one)
    assert score.status_code == 200

    watch = api.post(
        "/api/watchlist",
        headers=user_one,
        json={"company_name": "Acme", "private_score": 712, "rating": "Strong"},
    )
    assert watch.status_code == 201

    user_one_history = api.get("/api/history", headers=user_one)
    user_two_history = api.get("/api/history", headers=user_two)
    assert len(user_one_history.json()) == 1
    assert user_two_history.json() == []

    user_one_watchlist = api.get("/api/watchlist", headers=user_one)
    user_two_watchlist = api.get("/api/watchlist", headers=user_two)
    assert len(user_one_watchlist.json()) == 1
    assert user_two_watchlist.json() == []
