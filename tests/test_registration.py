from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from time import monotonic

import pytest
from psycopg.errors import UniqueViolation
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.models import UserModel
from app.auth.passwords import hash_password, verify_password
from app.auth.schemas import UserCreate
from app.auth.service import register_user
from app.auth import service
from app.db.database import get_db
from app.main import app

PASSWORD = "a long secure passphrase"
EMAIL = "person@example.com"


@pytest.fixture(autouse=True)
def reset_users(db_session):
    db_session.query(UserModel).delete()
    db_session.commit()
    yield
    db_session.rollback()
    db_session.query(UserModel).delete()
    db_session.commit()


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_registration_persists_safe_user(client, db_session):
    response = client.post(
        "/auth/register", json={"email": "  Person@Example.com  ", "password": PASSWORD}
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email"}
    assert body["email"] == EMAIL
    assert isinstance(body["id"], int) and body["id"] > 0
    user = db_session.get(UserModel, body["id"])
    assert user.email == EMAIL
    assert user.is_active is True
    assert user.created_at.utcoffset() is not None
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(PASSWORD, user.password_hash)
    assert not verify_password("incorrect password", user.password_hash)
    assert PASSWORD not in response.text
    assert user.password_hash not in response.text


def test_hashes_use_random_salts():
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)
    assert first != second
    assert verify_password(PASSWORD, first)
    assert verify_password(PASSWORD, second)
    assert not verify_password(PASSWORD, "invalid hash")


@pytest.mark.parametrize("email", [EMAIL, "PERSON@EXAMPLE.COM"])
def test_duplicate_registration(client, db_session, email):
    assert (
        client.post(
            "/auth/register", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == 201
    )
    response = client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert db_session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_database_enforces_case_insensitive_uniqueness(db_session):
    password_hash = hash_password(PASSWORD)
    db_session.add(UserModel(email=EMAIL, password_hash=password_hash))
    db_session.commit()
    db_session.add(UserModel(email=EMAIL.upper(), password_hash=password_hash))
    with pytest.raises(IntegrityError) as error:
        db_session.commit()
    db_session.rollback()
    assert error.value.orig.diag.constraint_name == "uq_users_email_lower"


def test_concurrent_email_inserts_cannot_both_commit(db_session):
    # Use the fixture's verified test engine for every connection, including workers.
    bind = db_session.get_bind()
    password_hash = hash_password(PASSWORD)
    loser_pid_queue = Queue()

    def competing_insert():
        with Session(bind) as loser:
            # Bound database waits even if coordination or assertions fail.
            loser.execute(text("SET LOCAL statement_timeout = '15s'"))
            loser_pid_queue.put(loser.scalar(select(func.pg_backend_pid())))
            loser.add(UserModel(email=EMAIL.upper(), password_hash=password_hash))
            try:
                loser.commit()
            except IntegrityError:
                loser.rollback()
                assert loser.is_active
                raise

    with Session(bind) as winner:
        winner.add(UserModel(email=EMAIL, password_hash=password_hash))
        winner.flush()
        winner_pid = winner.scalar(select(func.pg_backend_pid()))
        with ThreadPoolExecutor(max_workers=1) as executor:
            attempt = executor.submit(competing_insert)
            try:
                loser_pid = loser_pid_queue.get(timeout=10)
                deadline = monotonic() + 10
                # Observe a real PostgreSQL lock dependency before releasing the winner.
                while winner_pid not in db_session.scalar(
                    select(func.pg_blocking_pids(loser_pid))
                ):
                    if attempt.done():
                        attempt.result()  # Surface worker failures without waiting out the deadline.
                        pytest.fail("Competing insert committed before the winner")
                    assert monotonic() < deadline, "Competing insert never blocked"
                winner.commit()
                with pytest.raises(IntegrityError) as error:
                    attempt.result(timeout=20)
            finally:
                # Release locks before joining the worker, including on assertion failures.
                winner.rollback()

    assert isinstance(error.value.orig, UniqueViolation)
    assert error.value.orig.sqlstate == "23505"
    assert error.value.orig.diag.constraint_name == "uq_users_email_lower"
    assert db_session.scalar(select(func.count()).select_from(UserModel)) == 1


@pytest.mark.parametrize(
    "email",
    [
        "",
        " ",
        "invalid",
        "a@",
        "@example.com",
        "a b@example.com",
        "é@example.com",
        123,
        None,
        "a" * 245 + "@example.com",
    ],
)
def test_invalid_email(client, email):
    response = client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert all("input" not in error for error in response.json()["detail"])


@pytest.mark.parametrize(
    "password", ["", "tiny-secret", "a" * 14, "a" * 129, 123, None, ["secret"]]
)
def test_invalid_password(client, password):
    response = client.post(
        "/auth/register", json={"email": EMAIL, "password": password}
    )
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])
    if isinstance(password, str) and password:
        assert password not in response.text


@pytest.mark.parametrize("payload", [{}, {"email": EMAIL}, {"password": PASSWORD}])
def test_missing_fields(client, payload):
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert PASSWORD not in response.text


@pytest.mark.parametrize("password", ["a" * 15, "a" * 128, "  a Unicode phrase 🔒  "])
def test_password_boundaries_and_no_trimming(client, db_session, password):
    response = client.post(
        "/auth/register", json={"email": EMAIL, "password": password}
    )
    assert response.status_code == 201
    user = db_session.get(UserModel, response.json()["id"])
    assert verify_password(password, user.password_hash)
    if password != password.strip():
        assert not verify_password(password.strip(), user.password_hash)


def test_duplicate_rolls_back_and_session_remains_usable(
    client, db_session, monkeypatch
):
    def same_session():
        yield db_session

    monkeypatch.setitem(app.dependency_overrides, get_db, same_session)
    payload = {"email": EMAIL, "password": PASSWORD}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409
    assert db_session.is_active
    payload["email"] = "another@example.com"
    assert client.post("/auth/register", json=payload).status_code == 201
    assert db_session.scalar(select(func.count()).select_from(UserModel)) == 2


def test_unrelated_integrity_error_is_not_duplicate(db_session, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(service, "hash_password", lambda password: None)
        with pytest.raises(IntegrityError):
            register_user(db_session, UserCreate(email=EMAIL, password=PASSWORD))
    assert db_session.is_active
    assert db_session.scalar(select(func.count()).select_from(UserModel)) == 0
    assert register_user(db_session, UserCreate(email=EMAIL, password=PASSWORD)).id > 0


def test_commit_failure_rolls_back(db_session, monkeypatch):
    with monkeypatch.context() as patch:

        def fail_commit():
            raise SQLAlchemyError("simulated commit failure")

        patch.setattr(db_session, "commit", fail_commit)
        with pytest.raises(SQLAlchemyError, match="simulated commit failure"):
            register_user(db_session, UserCreate(email=EMAIL, password=PASSWORD))
    assert db_session.is_active
    assert db_session.scalar(select(func.count()).select_from(UserModel)) == 0
