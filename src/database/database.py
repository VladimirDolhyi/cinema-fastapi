from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.config.dependencies import get_settings
from src.database.models.base import Base

settings = get_settings()

DATABASE_URL = f"sqlite:///./src/database/cinema.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
connection = engine.connect()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_contextmanager() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_database():
    with connection.begin():
        Base.metadata.drop_all(bind=connection)
        Base.metadata.create_all(bind=connection)
