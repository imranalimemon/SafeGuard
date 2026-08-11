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
        # SQLite is forgiving, but if the DB is locked or the table doesn't
        # exist yet (first run before create_all), skip silently — the
        # caller will fall back to create_all semantics.
        pass


def init_db():
    import db.models
    Base.metadata.create_all(bind=engine)
