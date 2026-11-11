from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    """Database dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()
    except Exception:
        pass  # Ignore if already locked during reload

