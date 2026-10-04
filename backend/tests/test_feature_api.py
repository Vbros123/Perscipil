import time

from conftest import strong_password


async def fake_score_company(company_name: str, identity=None, refresh=False, selected_title=None):
    normalized = company_name.strip().lower()
    score = 760 if normalized.startswith("alpha") else 640
    return {
        "company_name": company_name.strip(),
        "normalized_name": normalized,
        "private_score": score,
        "scoring_status": "rated",
        "rating": "Strong" if score >= 700 else "Adequate",
        "color": "#00C896",
        "summary": "Synthetic integration-test score.",
        "breakdown": [],
        "category_summary": {},
        "risk_flags": [],
        "meta": {
            "total_signals": 0,
            "real_signals": 0,
            "scored_signals": 0,
            "simulated_signals": 0,
            "confidence": 1,
            "scored_weight": 1,
            "minimum_rating_coverage": 0.5,
            "scoring_status": "rated",
            "model_version": "test",
            "cached": False,
        },
        "elapsed_seconds": 0.01,
        "report": {"headline": "Synthetic report", "risk_level": "Low"},
    }


def test_full_authenticated_workspace_flow(api, monkeypatch):
    import routers.compare as compare_router
    import routers.score as score_router

    monkeypatch.setattr(score_router, "score_company", fake_score_company)
    monkeypatch.setattr(compare_router, "score_company", fake_score_company)

    root = api.get("/")
    assert root.status_code == 200
    assert root.headers["x-content-type-options"] == "nosniff"
    assert api.get("/api/health").json()["status"] == "ok"
    assert api.get("/api/metrics").status_code == 404
    assert api.get("/api/compliance/status").status_code == 200
    assert len(api.get("/api/signals").json()["signals"]) == 13
    providers = api.get("/api/providers").json()
    assert providers["effective_data_mode"] == "public"
    assert len(providers["providers"]) >= 9
    assert any(item["key"] == "wikipedia" for item in providers["providers"])
    assert any(item["key"] == "gleif" and item["configured"] is True for item in providers["providers"])
    assert all(item["status"] == "unavailable" for item in providers["providers"] if item["track"] == "licensed")
    assert api.get("/api/cache/stats").status_code == 200

    assert api.get("/api/watchlist").status_code == 401
    assert api.get("/api/settings").status_code == 401

    email = f"feature-{int(time.time() * 1000)}@example.com"
    password = strong_password("Feature")
    signup_payload = {
        "email": email,
        "password": password,
        "first_name": "Feature",
        "last_name": "Tester",
    }
    signup = api.post("/api/auth/signup", json=signup_payload)
    assert signup.status_code == 201
    assert api.post("/api/auth/signup", json=signup_payload).status_code == 409
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    me = api.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    updated = api.patch(
        "/api/users/me",
        headers=headers,
        json={"company": "Perscipil", "role": "Analyst"},
    )
    assert updated.json()["company"] == "Perscipil"

    settings = api.get("/api/settings", headers=headers)
    assert settings.status_code == 200
    settings_update = api.patch(
        "/api/settings",
        headers=headers,
        json={"default_view": "watchlist", "risk_threshold": 610, "weekly_digest": False},
    )
    assert settings_update.json()["risk_threshold"] == 610
    assert api.patch("/api/settings", headers=headers, json={"risk_threshold": 1001}).status_code == 422

    scored = api.get("/api/score?company=Alpha%20Industries", headers=headers)
    assert scored.status_code == 200
    assert scored.json()["private_score"] == 760

    detailed = api.post(
        "/api/score",
        headers=headers,
        json={"legal_name": "Alpha Industries", "country_code": "US", "registration_number": "A-123"},
    )
    assert detailed.status_code == 200
    assert api.post(
        "/api/score",
        headers=headers,
        json={"legal_name": "Alpha Industries", "provider_ids": {"unknown": "entity-1"}},
    ).status_code == 422

    compared = api.get("/api/compare?companies=Alpha%20Industries,Beta%20Labs", headers=headers)
    assert compared.status_code == 200
    assert compared.json()["winner"] == "Alpha Industries"
    assert api.get("/api/compare?companies=OnlyOne", headers=headers).status_code == 400
    assert api.get("/api/compare?companies=A,B,C,D,E", headers=headers).status_code == 400

    created = api.post(
        "/api/watchlist",
        headers=headers,
        json={"company_name": "Alpha Industries", "private_score": 760, "rating": "Strong"},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    duplicate = api.post(
        "/api/watchlist",
        headers=headers,
        json={"company_name": " alpha industries ", "notes": "Updated note"},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == item_id
    patched = api.patch(
        f"/api/watchlist/{item_id}",
        headers=headers,
        json={"notes": "Reviewed", "tags": ["priority"]},
    )
    assert patched.json()["tags"] == ["priority"]
    assert len(api.get("/api/watchlist", headers=headers).json()) == 1
    assert api.delete(f"/api/watchlist/{item_id}", headers=headers).status_code == 204
    assert api.delete(f"/api/watchlist/{item_id}", headers=headers).status_code == 404

    history = api.get("/api/history?limit=100", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 4
    history_id = history.json()[0]["id"]
    assert api.delete(f"/api/history/{history_id}", headers=headers).status_code == 204
    assert api.delete("/api/history", headers=headers).status_code == 204
    assert api.get("/api/history", headers=headers).json() == []

    assert api.post("/api/auth/logout", headers=headers).status_code == 200
