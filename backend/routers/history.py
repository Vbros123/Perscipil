"""Search history routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, get_optional_user
from models.company import CompanySearch
from models.user import User
from schemas.company import HistoryOut
from services.history import history_store

router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("", response_model=list[HistoryOut] | dict)
def get_history(
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if current_user is None:
        return {"history": history_store.recent(limit)}
    return (
        db.query(CompanySearch)
        .filter(CompanySearch.user_id == current_user.id)
        .order_by(CompanySearch.created_at.desc())
        .limit(limit)
        .all()
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(CompanySearch).filter(CompanySearch.user_id == current_user.id).delete()
    db.commit()
    return None


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history_item(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(CompanySearch, history_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="History item not found.")
    db.delete(item)
    db.commit()
    return None
