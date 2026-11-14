from datetime import UTC, datetime, timedelta
from base64 import urlsafe_b64encode
from secrets import token_bytes, token_hex

import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.auth import service, tokens
from app.auth.constants import JWT_ALGORITHM, MAX_PASSWORD_LENGTH
from app.auth.models import UserModel
from app.auth.schemas import TokenResponse, UserLogin
from app.core import config
from app.core.config import (
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    MIN_JWT_KEY_BYTES,
    get_environment,
    get_jwt_configuration,
)
from app.main import app

EMAIL = "person@example.com"
PASSWORD = "  a Unicode passphrase \U0001f512  "


@pytest.fixture(autouse=True)
def jwt_settings(monkeypatch):
    environment = get_environment()
    monkeypatch.setattr(
        environment, "jwt_secret_key", SecretStr(token_hex(MIN_JWT_KEY_BYTES))
    )
    monkeypatch.setattr(
        environment, "access_token_expire_minutes", DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    )


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


@pytest.fixture
def user(client, db_session):
    response = client.post(
        "/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == status.HTTP_201_CREATED
    return db_session.get(UserModel, response.json()["id"])


def decode_token(token):
    key, _ = get_jwt_configuration()
    return jwt.decode(
        token,
        key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )


def test_login_issues_signed_token(client, user, caplog):
    before = datetime.now(UTC)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    after = datetime.now(UTC)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert set(body) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"
    assert response.headers["cache-control"] == "no-store"
    claims = decode_token(body["access_token"])
    assert set(claims) == {"sub", "iat", "exp"}
    assert claims["sub"] == str(user.id)
    assert int(before.timestamp()) <= claims["iat"] <= int(after.timestamp())
    assert (
        claims["exp"] - claims["iat"]
        == timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds()
    )
    assert jwt.get_unverified_header(body["access_token"])["alg"] == JWT_ALGORITHM
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            body["access_token"],
            token_bytes(MIN_JWT_KEY_BYTES),
            algorithms=[JWT_ALGORITHM],
        )
    secret = get_environment().jwt_secret_key.get_secret_value()
    for sensitive in (PASSWORD, user.password_hash, secret):
        assert sensitive not in response.text
        assert sensitive not in caplog.text
    assert body["access_token"] not in caplog.text
    assert body["access_token"] not in repr(TokenResponse(**body))


@pytest.mark.parametrize("failure", ["password", "unknown", "inactive", "corrupt_hash"])
def test_login_failures_are_generic_and_do_not_write(
    client, user, db_session, failure, caplog
):
    email, password = EMAIL, PASSWORD
    if failure == "password":
        password = "incorrect"
    elif failure == "unknown":
        email = "unknown@example.com"
    elif failure == "inactive":
        user.is_active = False
        db_session.commit()
    else:
        user.password_hash = "invalid hash"
        db_session.commit()
    snapshot = (user.email, user.password_hash, user.is_active, user.created_at)
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Invalid credentials"}
    assert response.headers["www-authenticate"] == "Bearer"
    db_session.refresh(user)
    assert (user.email, user.password_hash, user.is_active, user.created_at) == snapshot
    assert db_session.scalar(select(func.count()).select_from(UserModel)) == 1
    for sensitive in (password, user.password_hash):
        assert sensitive not in response.text
        assert sensitive not in caplog.text


def test_unknown_user_still_verifies_argon2(client, monkeypatch):
    calls = []
    original = service.verify_password

    def verify(password, password_hash):
        calls.append(password_hash)
        return original(password, password_hash)

    monkeypatch.setattr(service, "verify_password", verify)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert calls == [service._DUMMY_PASSWORD_HASH]
    assert calls[0].startswith("$argon2id$")


@pytest.mark.parametrize(
    ("registered", "login_email"),
    [
        (EMAIL, "  PERSON@EXAMPLE.COM  "),
        ("\u00e9@example.com", "  E\u0301@EXAMPLE.COM  "),
        ("\u00e9@example.com", "\u00c9@example.com"),
        ("person@b\u00fccher.de", "PERSON@xn--bcher-kva.de"),
        ("person@xn--bcher-kva.de", "person@B\u00dcCHER.DE"),
    ],
)
def test_login_reuses_registration_normalisation(client, registered, login_email):
    registered_response = client.post(
        "/auth/register", json={"email": registered, "password": PASSWORD}
    )
    assert registered_response.status_code == status.HTTP_201_CREATED
    response = client.post(
        "/auth/login", json={"email": login_email, "password": PASSWORD}
    )
    assert response.status_code == status.HTTP_200_OK
    assert decode_token(response.json()["access_token"])["sub"] == str(
        registered_response.json()["id"]
    )


@pytest.mark.parametrize("password", [PASSWORD.strip(), "", "short"])
def test_login_password_not_trimmed_or_registration_minimum_enforced(
    client, user, password
):
    response = client.post("/auth/login", json={"email": EMAIL, "password": password})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"password": PASSWORD},
        {"email": EMAIL},
        {"email": "invalid", "password": PASSWORD},
        {"email": "a\u202eb@example.com", "password": PASSWORD},
        {"email": EMAIL, "password": None},
        {"email": EMAIL, "password": [PASSWORD]},
        {"email": EMAIL, "password": {"secret": PASSWORD}},
        {"email": EMAIL, "password": PASSWORD * MAX_PASSWORD_LENGTH},
        [PASSWORD],
    ],
)
def test_login_validation_does_not_echo_secrets(client, payload, caplog):
    response = client.post("/auth/login", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert PASSWORD not in response.text
    assert PASSWORD not in caplog.text
    assert all(
        set(error) == {"type", "loc", "msg"} for error in response.json()["detail"]
    )


def test_malformed_login_json_is_sanitised(client):
    response = client.post(
        "/auth/login",
        content='{"password": "' + PASSWORD,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert PASSWORD not in response.text
    assert all(
        "input" not in error and "ctx" not in error
        for error in response.json()["detail"]
    )


@pytest.mark.parametrize(
    "secret",
    [
        None,
        "",
        "not-a-hex-key",
        token_hex(MIN_JWT_KEY_BYTES - 1),
        "00" * MIN_JWT_KEY_BYTES,
    ],
)
def test_missing_or_invalid_key_fails_safely(client, user, monkeypatch, secret, caplog):
    monkeypatch.setattr(
        get_environment(),
        "jwt_secret_key",
        SecretStr(secret) if secret is not None else None,
    )
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "Authentication unavailable"}
    unknown = client.post(
        "/auth/login", json={"email": "unknown@example.com", "password": PASSWORD}
    )
    assert unknown.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert PASSWORD not in response.text
    assert PASSWORD not in caplog.text
    if secret:
        assert secret not in response.text
        assert secret not in caplog.text


def test_reencoded_pagination_key_cannot_sign_jwts(client, user, monkeypatch):
    key = token_bytes(MIN_JWT_KEY_BYTES)
    monkeypatch.setattr(get_environment(), "jwt_secret_key", SecretStr(key.hex()))
    monkeypatch.setattr(
        get_environment(), "pagination_token_key", urlsafe_b64encode(key).decode()
    )
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "Authentication unavailable"}


@pytest.mark.parametrize("pagination_key", [None, "invalid-key", "\u00e9"])
def test_invalid_pagination_key_does_not_disable_login(
    client, user, monkeypatch, pagination_key
):
    monkeypatch.setattr(get_environment(), "pagination_token_key", pagination_key)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_200_OK
    assert decode_token(response.json()["access_token"])["sub"] == str(user.id)


@pytest.mark.parametrize(
    "minutes", ["", "invalid", "0", "-1", "1.5", "10000000000", "9" * 30]
)
def test_invalid_token_lifetime_fails_safely(client, user, monkeypatch, minutes):
    monkeypatch.setattr(get_environment(), "access_token_expire_minutes", minutes)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "Authentication unavailable"}
    unknown = client.post(
        "/auth/login", json={"email": "unknown@example.com", "password": PASSWORD}
    )
    assert unknown.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_configured_lifetime_and_environment_loading(client, user, monkeypatch):
    custom_minutes = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES + 1
    secret = token_hex(MIN_JWT_KEY_BYTES)
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(custom_minutes))
    monkeypatch.setattr(config, "saved_environment", None)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_200_OK
    claims = decode_token(response.json()["access_token"])
    assert (
        claims["exp"] - claims["iat"]
        == timedelta(minutes=custom_minutes).total_seconds()
    )
    assert secret not in repr(get_environment())
    assert secret not in repr(get_environment().jwt_secret_key)
    assert PASSWORD not in repr(UserLogin(email=EMAIL, password=PASSWORD))


def test_expired_token_is_rejected(client, user, monkeypatch):
    past = datetime.now(UTC) - timedelta(days=1)

    class PastClock:
        @staticmethod
        def now(tz):
            assert tz is UTC
            return past

    monkeypatch.setattr(tokens, "datetime", PastClock)
    response = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == status.HTTP_200_OK
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(response.json()["access_token"])


def test_jwt_misconfiguration_does_not_break_other_routes(client, monkeypatch):
    monkeypatch.setattr(get_environment(), "jwt_secret_key", None)
    assert (
        client.post(
            "/auth/register", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == status.HTTP_201_CREATED
    )
    assert client.get("/customers").status_code == status.HTTP_200_OK
