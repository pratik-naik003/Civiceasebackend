from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import UserRoleEnum
from app.models.user import User, UserRole

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def reporter_user(db_session: Session) -> User:
    user = User(firebase_uid="user-reporter", email="reporter@test.com", display_name="Reporter")
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role=UserRoleEnum.REPORTER.value))
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def main_admin_user(db_session: Session) -> User:
    user = User(firebase_uid="user-admin", email="admin@test.com", display_name="Admin")
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role=UserRoleEnum.MAIN_ADMIN.value))
    db_session.add(UserRole(user_id=user.id, role=UserRoleEnum.REPORTER.value))
    db_session.commit()
    db_session.refresh(user)
    return user


def set_current_user(user: User):
    app.dependency_overrides[get_current_user] = lambda: user
