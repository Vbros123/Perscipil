"""Watchlist routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.company import SavedCompany
from models.user import User
from schemas.company import WatchlistCreate, WatchlistOut, WatchlistUpdate
from services.reports import normalize_company

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])


@router.get("", response_model=list[WatchlistOut])
def list_watchlist(
    limit: int = Query(default=100, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SavedCompany)
        .filter(SavedCompany.user_id == current_user.id)
        .order_by(SavedCompany.updated_at.desc())
        .limit(limit)
        .all()
    )


@router.post("", response_model=WatchlistOut, status_code=201)
def add_watchlist_item(
    payload: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized = normalize_company(payload.company_name)
    existing = (
        db.query(SavedCompany)
        .filter(
            SavedCompany.user_id == current_user.id,
            SavedCompany.normalized_name == normalized,
        )
        .first()
    )
    if existing:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field != "company_name":
                setattr(existing, field, value)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    item = SavedCompany(
        user_id=current_user.id,
        company_name=payload.company_name.strip(),
        normalized_name=normalized,
        private_score=payload.private_score,
        rating=payload.rating,
        color=payload.color,
        notes=payload.notes,
        tags=payload.tags,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=WatchlistOut)
def update_watchlist_item(
    item_id: int,
    payload: WatchlistUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(SavedCompany, item_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(SavedCompany, item_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Watchlist item not found.")
    db.delete(item)
    db.commit()
    return None
