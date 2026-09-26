"""Shared, expiring capacity leases. Failure to acquire always fails closed."""
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from core.database import SessionLocal
from models.operations import OperationLease


def acquire(key, seconds):
    now = datetime.now(timezone.utc)
    token = secrets.token_hex(24)
    with SessionLocal.begin() as db:
        insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
        query = insert(OperationLease).values(key=key, token=token, expires_at=now+timedelta(seconds=seconds))
        query = query.on_conflict_do_update(index_elements=['key'],
            set_={'token':token, 'expires_at':now+timedelta(seconds=seconds)},
            where=OperationLease.expires_at <= now).returning(OperationLease.token)
        return token if db.execute(query).scalar_one_or_none() else None


def release(key, token):
    with SessionLocal.begin() as db:
        db.execute(update(OperationLease).where(OperationLease.key==key, OperationLease.token==token)
            .values(expires_at=datetime.now(timezone.utc)))
