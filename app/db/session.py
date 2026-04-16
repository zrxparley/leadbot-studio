from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base

settings = get_settings()
engine_kwargs: dict = {"future": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        _ensure_sqlite_lead_columns()


def _ensure_sqlite_lead_columns() -> None:
    column_definitions = {
        "demand_summary": "TEXT",
        "demand_posted_at": "DATETIME",
        "buyer_contact_name": "VARCHAR(255)",
        "contact_email": "VARCHAR(255)",
        "contact_phone": "VARCHAR(255)",
        "demand_type": "VARCHAR(40)",
    }
    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(leads)").fetchall()
        existing_columns = {row[1] for row in rows}
        for column_name, ddl in column_definitions.items():
            if column_name in existing_columns:
                continue
            connection.exec_driver_sql(f"ALTER TABLE leads ADD COLUMN {column_name} {ddl}")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
