"""
Database configuration and session management for Construction Material Intelligence Platform.
Supports PostgreSQL (when DATABASE_URL is set) and SQLite (data/construction.db) as local default.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from python_app.config import settings

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# If DATABASE_URL is postgresql, use it. Otherwise use SQLite in data/construction.db
db_url = settings.DATABASE_URL
if not db_url or "localhost" in db_url or "postgresql" not in db_url:
    sqlite_path = DATA_DIR / "construction.db"
    db_url = f"sqlite:///{sqlite_path.as_posix()}"

engine_kwargs = {}
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(db_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
