from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_violation_columns(engine) -> None:
    """Idempotently add new columns to the `violations` table for legacy
    SQLite databases that pre-date the Core Fixes milestone. Safe to call on
    every startup — it checks `PRAGMA table_info` before issuing ALTER TABLE.

    Fresh installs get the columns automatically via `Base.metadata.create_all`
    in main.py; this helper is a no-op on those databases.
    """
    desired = {
        "bbox": "VARCHAR",
        "detections": "TEXT",
        "source": "VARCHAR",
        "review_status": "VARCHAR NOT NULL DEFAULT 'open'",
        "acknowledged_at": "DATETIME",
        "escalated_at": "DATETIME",
        "archived_at": "DATETIME",
        "mask_assessment": "VARCHAR",
    }
    try:
        with engine.connect() as conn:
            existing = {
                row[1]
                for row in conn.exec_driver_sql(
                    "PRAGMA table_info(violations)"
                ).fetchall()
            }
            for col, sqltype in desired.items():
                if col not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE violations ADD COLUMN {col} {sqltype}"
                    )
            conn.commit()
    except Exception:
        # Do not start an API with an incompatible schema if migration fails.
        raise


def init_db():
    import db.models
    Base.metadata.create_all(bind=engine)


def ensure_alert_settings_columns(engine):
    """Add policy persistence to legacy settings without rewriting any rows."""
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(alert_settings)')}
        if 'required_ppe' not in columns:
            conn.exec_driver_sql('ALTER TABLE alert_settings ADD COLUMN required_ppe VARCHAR')
        if 'frame_skip' not in columns:
            conn.exec_driver_sql('ALTER TABLE alert_settings ADD COLUMN frame_skip INTEGER')


def ensure_alert_log_columns(engine):
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info(alert_logs)')}
        for name in ('message', 'transport'):
            if name not in columns:
                conn.exec_driver_sql(f'ALTER TABLE alert_logs ADD COLUMN {name} VARCHAR')
