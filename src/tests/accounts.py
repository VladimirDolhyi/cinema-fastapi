import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from src.main import app
from src.database.models.accounts import (
    User, UserGroup, ActivationToken, UserGroupEnum
)
from src.database import Base


# Setting up the test database (SQLite in-memory)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """ Creates a fresh database session for each test. """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def auth_headers(db_session: Session):
    """ Creates a test user and returns authorization headers for authentication. """
    user_group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(user_group)
    db_session.commit()

    user = User(email="test@example.com", group_id=user_group.id)
    user.password = "Password123!"
    db_session.add(user)
    db_session.commit()

    payload = {"email": "test@example.com", "password": "Password123!"}
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_user(db_session):
    """ Tests user creation in the database. """
    user = User(email="user@example.com", group_id=1)
    user.password = "SecureP@ss123"
    db_session.add(user)
    db_session.commit()

    saved_user = db_session.query(User).filter_by(email="user@example.com").first()
    assert saved_user is not None
    assert saved_user.email == "user@example.com"


def test_create_activation_token(db_session):
    """ Tests the creation of an activation token. """
    user = User(email="activate@example.com", group_id=1)
    user.password = "SecurePass123!"
    db_session.add(user)
    db_session.commit()

    token = ActivationToken.generate_new_token(user.id)
    db_session.add(token)
    db_session.commit()

    saved_token = db_session.query(ActivationToken).filter_by(user_id=user.id).first()
    assert saved_token is not None
    assert saved_token.user_id == user.id


def test_user_group_assignment(db_session):
    """ Verifies that a user belongs to a specific group. """
    group = UserGroup(name=UserGroupEnum.USER)
    db_session.add(group)
    db_session.commit()

    user = User(email="groupuser@example.com", group_id=group.id)
    user.password = "SuperSecurePass1!"
    db_session.add(user)
    db_session.commit()

    saved_user = db_session.query(User).filter_by(email="groupuser@example.com").first()
    assert saved_user is not None
    assert saved_user.has_group(UserGroupEnum.USER)
