"""
In-memory search history store.
Tracks last 100 unique company searches per session.
"""
from collections import deque
from datetime import datetime, timezone
from threading import Lock

from models.company import CompanyReport, CompanySearch


class HistoryStore:
    def __init__(self, maxlen: int = 100):
        self._history: deque = deque(maxlen=maxlen)
        self._lock = Lock()

    def add(self, company: str, score: int, rating: str, color: str) -> None:
        entry = {
            "company_name": company,
            "private_score": score,
            "rating": rating,
            "color": color,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            # Remove previous entry for same company
            self._history = deque(
                (e for e in self._history if e["company_name"].lower() != company.lower()),
                maxlen=self._history.maxlen
            )
            self._history.appendleft(entry)

    def recent(self, limit: int = 10) -> list:
        with self._lock:
            return list(self._history)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


history_store = HistoryStore()


def store_company_event(db, user, score_data: dict, query_type: str = "score") -> None:
    """Persist a score or compare event for an authenticated user."""
    if user is None:
        return

    db.add(
        CompanySearch(
            user_id=user.id,
            company_name=score_data["company_name"],
            normalized_name=score_data["normalized_name"],
            private_score=score_data["private_score"],
            rating=score_data["rating"],
            color=score_data["color"],
            query_type=query_type,
        )
    )
    db.add(
        CompanyReport(
            user_id=user.id,
            company_name=score_data["company_name"],
            normalized_name=score_data["normalized_name"],
            private_score=score_data["private_score"],
            rating=score_data["rating"],
            report_json=score_data.get("report", {}),
            scoring_status=score_data.get("scoring_status"),
            model_version=score_data.get("meta", {}).get("model_version"),
            input_snapshot_hash=score_data.get("meta", {}).get("input_snapshot_hash"),
            evidence_json=score_data.get("evidence", {}),
        )
    )
    db.commit()
