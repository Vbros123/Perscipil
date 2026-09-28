"""Database session management for Perspicil."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import get_settings

settings = get_settings()
database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    **({"pool_size": 5, "max_overflow": 5, "pool_timeout": 5} if not database_url.startswith("sqlite") else {}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from models.company import CompanyReport, CompanySearch, SavedCompany  # noqa: F401
    from models.settings import UserSettings  # noqa: F401
    from models.user import AuthAuditEvent, SecurityToken, User  # noqa: F401

    from models import consent, mfa, operations, organizations, workflows  # noqa: F401
    Base.metadata.create_all(bind=engine)

# SQLite must enforce the same ownership cascade constraints as Postgres.
if database_url.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
