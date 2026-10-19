import json

import pytest
from app.customers.pagination import token_cipher
from app.core.config import get_environment
from fastapi import status
from fastapi.testclient import TestClient

from app.customers.constants import (
    CURSOR_VERSION,
    DEFAULT_PAGE_SIZE,
    MAX_CUSTOMER_ID,
    MAX_NAME_LENGTH,
    MAX_PAGE_SIZE,
)
from app.customers.models import CustomerModel
from app.main import app

# -------------------------
# Test data
# -------------------------

EXISTING_CUSTOMERS = [(101, "John"), (102, "Mary"), (103, "David")]
EXISTING_CUSTOMER_IDS = [customer_id for customer_id, _ in EXISTING_CUSTOMERS]
NON_EXISTING_CUSTOMER_ID = 3
INVALID_CUSTOMER_IDS = [-1, 0, MAX_CUSTOMER_ID + 1, "abc"]
INVALID_NAMES = ["", " ", 123]
NAME_WITH_WHITESPACE = "  John Doe  ", "John Doe"
MISSING_CUSTOMER_DATA = [{"name": "Ben"}, {"customer_id": 104}, {}]


# -------------------------
# Fixtures
# -------------------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_customers(db_session):
    db_session.query(CustomerModel).delete()

    for customer_id, name in EXISTING_CUSTOMERS:
        db_session.add(CustomerModel(customer_id=customer_id, name=name))

    db_session.commit()


# =========================
# GET
# =========================


def test_get_existing_customer(client):
    customer_id, expected_name = EXISTING_CUSTOMERS[0]
    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"customer_id": customer_id, "name": expected_name}


def test_get_non_existing_customer(client):
    response = client.get(f"/customers/{NON_EXISTING_CUSTOMER_ID}")

    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert response.json() == {"detail": "Customer not found"}


@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_get_invalid_customer_id(client, customer_id):
    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_list_customers(client):
    response = client.get("/customers")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "customers": [
            {"customer_id": cid, "name": name} for cid, name in EXISTING_CUSTOMERS
        ],
        "next_page_token": "",
    }


@pytest.mark.parametrize(
    "query,ids",
    [
        ("Mary", [102]),
        ("ar", [102]),
        ("mArY", [102]),
        (" Mary ", [102]),
        ("", [101, 102, 103]),
        ("   ", [101, 102, 103]),
        ("Nobody", []),
        ("%", []),
        ("_", []),
        ("' OR 1=1 --", []),
    ],
)
def test_list_search(client, query, ids):
    response = client.get("/customers", params={"q": query})
    assert response.status_code == status.HTTP_200_OK
    assert [row["customer_id"] for row in response.json()["customers"]] == ids
    assert response.json()["next_page_token"] == ""


def test_list_literal_wildcards(client, db_session):
    db_session.add(CustomerModel(customer_id=104, name="Mary_100%/"))
    db_session.commit()
    for query in ("_", "%", "/"):
        result = client.get("/customers", params={"q": query}).json()
        assert [row["customer_id"] for row in result["customers"]] == [104]


def test_list_empty(client, db_session):
    db_session.query(CustomerModel).delete()
    db_session.commit()
    assert client.get("/customers").json() == {"customers": [], "next_page_token": ""}


@pytest.mark.parametrize("size", [1, 2, 3])
def test_list_walk_pages(client, size):
    ids = []
    token = ""
    for _ in range(len(EXISTING_CUSTOMERS) + 1):
        response = client.get(
            "/customers", params={"page_size": size, "page_token": token}
        )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result["customers"]) <= size
        ids.extend(row["customer_id"] for row in result["customers"])
        token = result["next_page_token"]
        if not token:
            break
    assert token == ""
    assert ids == [101, 102, 103]


def test_list_filtered_pages_and_changed_size(client, db_session):
    db_session.add_all(
        [
            CustomerModel(customer_id=90, name="Mary Jane"),
            CustomerModel(customer_id=104, name="Mary Smith"),
        ]
    )
    db_session.commit()
    first = client.get("/customers", params={"q": "Mary", "page_size": 1}).json()
    assert [row["customer_id"] for row in first["customers"]] == [90]
    second = client.get(
        "/customers",
        params={
            "q": "Mary",
            "page_size": 2,
            "page_token": first["next_page_token"],
        },
    )
    assert second.status_code == status.HTTP_200_OK
    assert [row["customer_id"] for row in second.json()["customers"]] == [102, 104]
    assert second.json()["next_page_token"] == ""
    assert (
        client.get(
            "/customers",
            params={
                "q": "John",
                "page_token": first["next_page_token"],
            },
        ).status_code
        == status.HTTP_400_BAD_REQUEST
    )


def test_list_page_size_limits(client, db_session):
    db_session.add_all(
        CustomerModel(customer_id=i, name="Extra")
        for i in range(MAX_PAGE_SIZE, 2 * MAX_PAGE_SIZE + 1)
    )
    db_session.commit()
    for params, expected in [
        ({}, DEFAULT_PAGE_SIZE),
        ({"page_size": 0}, DEFAULT_PAGE_SIZE),
        ({"page_size": MAX_PAGE_SIZE}, MAX_PAGE_SIZE),
        ({"page_size": MAX_PAGE_SIZE + 1}, MAX_PAGE_SIZE),
    ]:
        response = client.get("/customers", params=params)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["customers"]) == expected
        assert response.json()["next_page_token"]


@pytest.mark.parametrize("size", [-1, "abc", "1.5", ""])
def test_list_invalid_page_size(client, size):
    assert (
        client.get("/customers", params={"page_size": size}).status_code
        == status.HTTP_400_BAD_REQUEST
    )


@pytest.mark.parametrize("token", ["invalid", "☃"])
def test_list_invalid_token(client, token):
    assert (
        client.get("/customers", params={"page_token": token}).status_code
        == status.HTTP_400_BAD_REQUEST
    )


def test_list_tampered_token(client):
    token = client.get("/customers", params={"page_size": 1}).json()["next_page_token"]
    pos = len(token) // 2
    token = token[:pos] + ("A" if token[pos] != "A" else "B") + token[pos + 1 :]
    assert (
        client.get("/customers", params={"page_token": token}).status_code
        == status.HTTP_400_BAD_REQUEST
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"version": CURSOR_VERSION + 1, "last_id": 101, "q": ""},
        {"version": True, "last_id": 101, "q": ""},
        {"version": CURSOR_VERSION, "last_id": "101", "q": ""},
        {"version": CURSOR_VERSION, "last_id": MAX_CUSTOMER_ID + 1, "q": ""},
        {"version": CURSOR_VERSION, "last_id": 101, "q": None},
        {"version": CURSOR_VERSION, "last_id": True, "q": ""},
        {"version": CURSOR_VERSION, "last_id": 0, "q": ""},
        {},
        [],
    ],
)
def test_list_invalid_cursor_payload(client, payload):
    token = token_cipher().encrypt(json.dumps(payload).encode()).decode()
    assert (
        client.get("/customers", params={"page_token": token}).status_code
        == status.HTTP_400_BAD_REQUEST
    )


@pytest.mark.parametrize("key", [None, "invalid", "☃"])
def test_list_invalid_key_configuration(client, monkeypatch, key):
    monkeypatch.setattr(get_environment(), "pagination_token_key", key)
    assert client.get("/customers").status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_list_openapi_page_size(client):
    parameters = client.get("/openapi.json").json()["paths"]["/customers"]["get"][
        "parameters"
    ]
    page_size = next(
        parameter for parameter in parameters if parameter["name"] == "page_size"
    )
    assert page_size["schema"]["type"] == "integer"
    assert page_size["schema"]["default"] == DEFAULT_PAGE_SIZE


def test_list_deleted_cursor_customer(client, db_session):
    token = client.get("/customers", params={"page_size": 1}).json()["next_page_token"]
    db_session.delete(db_session.get(CustomerModel, 101))
    db_session.commit()
    result = client.get("/customers", params={"page_token": token}).json()
    assert [row["customer_id"] for row in result["customers"]] == [102, 103]
    assert result["next_page_token"] == ""


# =========================
# POST
# =========================


def test_post_customer(client, db_session):
    expected_name = "Larry"
    response = client.post(
        "/customers",
        json={"customer_id": NON_EXISTING_CUSTOMER_ID, "name": expected_name},
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert response.json() == {
        "customer_id": NON_EXISTING_CUSTOMER_ID,
        "name": expected_name,
    }

    # Confirm the customer was actually stored
    db_session.expire_all()
    stored_customer = db_session.get(CustomerModel, NON_EXISTING_CUSTOMER_ID)

    assert stored_customer is not None
    assert stored_customer.name == expected_name


def test_post_existing_customer(client):
    customer_id, _ = EXISTING_CUSTOMERS[0]
    response = client.post(
        "/customers", json={"customer_id": customer_id, "name": "RANDOM"}
    )

    assert response.status_code == status.HTTP_409_CONFLICT

    assert response.json() == {"detail": "Customer ID already exists"}


@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_post_invalid_customer_id(client, customer_id):
    response = client.post(
        "/customers", json={"customer_id": customer_id, "name": "Ben"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_post_invalid_name(client, name):
    response = client.post(
        "/customers", json={"customer_id": NON_EXISTING_CUSTOMER_ID, "name": name}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_post_too_long_name(client):
    response = client.post(
        "/customers",
        json={
            "customer_id": NON_EXISTING_CUSTOMER_ID,
            "name": "B" * (MAX_NAME_LENGTH + 1),
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_post_names_with_whitespace(client, db_session):
    input_name, expected_name = NAME_WITH_WHITESPACE
    response = client.post(
        "/customers", json={"customer_id": NON_EXISTING_CUSTOMER_ID, "name": input_name}
    )

    assert response.status_code == status.HTTP_201_CREATED

    assert response.json() == {
        "customer_id": NON_EXISTING_CUSTOMER_ID,
        "name": expected_name,
    }

    # Confirm the stripped name was actually stored
    db_session.expire_all()
    stored_customer = db_session.get(CustomerModel, NON_EXISTING_CUSTOMER_ID)

    assert stored_customer is not None
    assert stored_customer.name == expected_name


@pytest.mark.parametrize("data", MISSING_CUSTOMER_DATA)
def test_post_missing_customer_data(client, data):
    response = client.post("/customers", json=data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =========================
# PATCH
# =========================


def test_patch_existing_customer(client, db_session):
    customer_id = EXISTING_CUSTOMER_IDS[0]
    response = client.patch(f"/customers/{customer_id}", json={"name": "Ben"})

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"customer_id": customer_id, "name": "Ben"}

    # Confirm the customer was actually updated
    db_session.expire_all()
    stored_customer = db_session.get(CustomerModel, customer_id)

    assert stored_customer is not None
    assert stored_customer.name == "Ben"


def test_patch_non_existing_customer(client):
    response = client.patch(
        f"/customers/{NON_EXISTING_CUSTOMER_ID}", json={"name": "Ben"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert response.json() == {"detail": "Customer not found"}


@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_patch_invalid_customer_id(client, customer_id):
    response = client.patch(f"/customers/{customer_id}", json={"name": "Ben"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_patch_invalid_name(client, name):
    response = client.patch("/customers/101", json={"name": name})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_patch_too_long_name(client):
    response = client.patch(
        "/customers/101", json={"name": "BA" * (MAX_NAME_LENGTH + 1)}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_patch_names_with_whitespace(client, db_session):
    input_name, expected_name = NAME_WITH_WHITESPACE

    response = client.patch("/customers/101", json={"name": input_name})

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"customer_id": 101, "name": expected_name}

    # Confirm the stripped name was actually stored
    db_session.expire_all()
    stored_customer = db_session.get(CustomerModel, 101)

    assert stored_customer is not None
    assert stored_customer.name == expected_name


def test_patch_missing_customer_id(client):
    response = client.patch("/customers/", json={"name": "Ben"})

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# =========================
# DELETE
# =========================


def test_delete_existing_customer(client, db_session):
    customer_id = EXISTING_CUSTOMER_IDS[0]
    response = client.delete(f"/customers/{customer_id}")

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"message": "Customer deleted"}

    # Confirm the customer was actually deleted
    db_session.expire_all()
    deleted_customer = db_session.get(CustomerModel, customer_id)

    assert deleted_customer is None


def test_delete_non_existing_customer(client):
    response = client.delete(f"/customers/{NON_EXISTING_CUSTOMER_ID}")

    assert response.status_code == status.HTTP_404_NOT_FOUND

    assert response.json() == {"detail": "Customer not found"}


@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_delete_invalid_customer_id(client, customer_id):
    response = client.delete(f"/customers/{customer_id}")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_token_cipher_is_reused():
    assert token_cipher() is token_cipher()
