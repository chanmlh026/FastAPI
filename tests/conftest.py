import os

import pytest
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db.database import get_db
from app.main import app
from app.core.config import get_environment
from app.customers import pagination
from tests.database_safety import validate_database_urls

load_dotenv(".env.test")

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

test_engine = create_engine(TEST_DATABASE_URL, hide_parameters=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def confirm_test_database():
    try:
        validate_database_urls(TEST_DATABASE_URL, get_environment().database_url)
    except ValueError as exc:
        pytest.exit(str(exc))
    test_url = make_url(TEST_DATABASE_URL)
    with test_engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != test_url.database:
            pytest.exit("Test database identity does not match configuration.")
        if not {"customers", "users"}.issubset(inspect(connection).get_table_names()):
            pytest.exit(
                "Create customers and users in the dedicated test database first."
            )


@pytest.fixture(autouse=True)
def pagination_key(monkeypatch):
    monkeypatch.setattr(pagination, "saved_token_cipher", None)
    monkeypatch.setattr(
        get_environment(), "pagination_token_key", Fernet.generate_key().decode()
    )


def override_get_db():
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def db_session():
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()
