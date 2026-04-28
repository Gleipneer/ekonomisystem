"""
Database configuration for the household economics backend.

This module exposes a SQLAlchemy engine, session factory and a base class for
declarative models. Runtime configuration is sourced from ``app.settings`` so
the database URL, upload path and other environment-backed settings stay
centralized.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .settings import get_settings

settings = get_settings()

DATABASE_URL = settings.database_url

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()

def init_db() -> None:
    """Create all tables when auto-bootstrap is enabled.

    Alembic is now the supported migration path. ``create_all`` remains
    available as a local bootstrap and test convenience while the app still
    runs in single-process SQLite-first mode.
    """
    from . import models  # noqa: F401 - imported for side effects
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
