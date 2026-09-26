"""Minimal deletion ledger; export separately from the backup being restored."""
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, delete, update
from models.operations import DeletionMarker
from models.user import User, AuthAuditEvent
from models import company, settings  # noqa: F401; register account relationships for CLI use
from models.organizations import Membership
from models.workflows import Correction


def identity_key(user):
    # Creation time and email prevent a reused SQLite integer ID matching a new user.
    stamp = user.created_at.replace(tzinfo=timezone.utc).isoformat() if user.created_at else ''
    return hashlib.sha256(f'{user.id}|{user.email.lower()}|{stamp}'.encode()).hexdigest()


def erase(db, user, record=True):
    if record:
        key=identity_key(user)
        if not db.get(DeletionMarker,key):
            db.add(DeletionMarker(key=key,deleted_at=datetime.now(timezone.utc)))
    db.execute(delete(Membership).where(Membership.user_id==user.id))
    db.execute(update(AuthAuditEvent).where(AuthAuditEvent.user_id==user.id).values(email=None,ip_address=None,user_agent=None))
    db.execute(update(Correction).where(Correction.user_id==user.id).values(details='[removed on account deletion]',review_history=[]))
    db.delete(user)


def replay(db, keys):
    removed=0
    for user in db.scalars(select(User)).yield_per(100):
        if identity_key(user) in keys:
            erase(db,user)
            removed+=1
    db.flush()
    return removed
