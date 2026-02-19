from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path
import importlib
import sys

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings, get_state_db_url, resolve_paths
from db.models import Base

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def _sqlite_pragma_on_connect(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        settings = resolve_paths(get_settings())
        settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
        _ENGINE = create_engine(
            get_state_db_url(settings),
            connect_args={"check_same_thread": False},
            future=True,
            pool_pre_ping=True,
        )
        event.listen(_ENGINE, "connect", _sqlite_pragma_on_connect)
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            future=True,
            expire_on_commit=False,
        )
    return _SESSION_FACTORY


@contextmanager
def session_scope() -> Session:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_migrations() -> None:
    settings = resolve_paths(get_settings())
    ini_path = settings.project_root / "alembic.ini"

    # Avoid local ./alembic script folder shadowing the alembic package.
    removed_entries = []
    for entry in ("", str(settings.project_root)):
        while entry in sys.path:
            sys.path.remove(entry)
            removed_entries.append(entry)

    try:
        alembic_config_mod = importlib.import_module("alembic.config")
        alembic_command_mod = importlib.import_module("alembic.command")
    except ModuleNotFoundError:
        # Local dev fallback when alembic package is unavailable in host Python.
        Base.metadata.create_all(bind=get_engine())
        return
    finally:
        for entry in reversed(removed_entries):
            sys.path.insert(0, entry)

    cfg = alembic_config_mod.Config(str(ini_path))
    cfg.set_main_option("script_location", str(settings.project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_state_db_url(settings))

    if settings.state_db_path.exists():
        conn = sqlite3.connect(settings.state_db_path)
        try:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tables = {row[0] for row in rows}
            if "documents" in tables:
                if "alembic_version" not in tables:
                    alembic_command_mod.stamp(cfg, "head")
                return
        finally:
            conn.close()

    alembic_command_mod.upgrade(cfg, "head")


def ensure_storage_paths() -> None:
    settings = resolve_paths(get_settings())
    Path(settings.state_db_path).parent.mkdir(parents=True, exist_ok=True)
