import pytest
from fastapi.testclient import TestClient
from main import app, customers

# -------------------------
# Fixtures
# -------------------------

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def reset_customers():
    customers.clear()
    customers.update({101: "John", 102: "Mary", 103: "David"})

# -------------------------
# Test data
# -------------------------

EXISTING_CUSTOMERS = [(101, "John"), (102, "Mary"), (103, "David")]
EXISTING_CUSTOMER_IDS = [customer_id for customer_id, _ in EXISTING_CUSTOMERS]
NON_EXISTING_CUSTOMERS = [(1, "Leo"), (104, "Roy"), (2**31-1, "Kelly"), (105, "B"), (106, "B"*50)]
NON_EXISTING_CUSTOMER_IDS = [customer_id for customer_id, _ in NON_EXISTING_CUSTOMERS]
INVALID_CUSTOMER_IDS = [-1, 0, 2**31, "abc", " "]
INVALID_NAMES = ["", " ", 123]
TOO_LONG_NAMES = ["B"*51]
NAMES_WITH_WHITESPACE = [
    (" Ben", "Ben"),
    ("Ben ", "Ben"),
    (" Ben ", "Ben"),
    (" Ben Jones", "Ben Jones"),
    ("Ben Jones ", "Ben Jones"),
    (" Ben Jones ", "Ben Jones")
     ]
MISSING_CUSTOMER_DATA = [{"name": "Ben"}, {"customer_id": 104}, {}]

# =========================
# GET
# =========================

@pytest.mark.parametrize("customer_id, expected_name", EXISTING_CUSTOMERS)
def test_get_existing_customer(client, customer_id, expected_name):
    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == 200

    assert response.json() == {
        "customer_id": customer_id,
         "name": expected_name
         }

@pytest.mark.parametrize("customer_id", NON_EXISTING_CUSTOMER_IDS)
def test_get_non_existing_cusotmer(client, customer_id):
    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == 404

    assert response.json() == {"detail": "Customer not found"}

@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_get_invalid_customer_id(client, customer_id):
    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == 422

def test_get_missing_customer_id(client):
    response = client.get("/customers/")

    assert response.status_code == 405

# =========================
# POST
# =========================

@pytest.mark.parametrize("customer_id, name", NON_EXISTING_CUSTOMERS)
def test_post_customer(client, customer_id, name):
    response = client.post("/customers", json={"customer_id": customer_id, "name": name})

    assert response.status_code == 200

    assert response.json() == {"customer_id": customer_id, "name": name}

    # Confirm the customer was actually stored
    assert customers[customer_id] == name

@pytest.mark.parametrize("customer_id, name", EXISTING_CUSTOMERS)
def test_post_existing_customer(client, customer_id, name):
    response = client.post("/customers", json={"customer_id": customer_id, "name": name})

    assert response.status_code == 409

    assert response.json() == {"detail": "Customer ID already exists"}

@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_post_invalid_customer_id(client, customer_id):
    response = client.post("/customers", json={"customer_id": customer_id, "name": "Ben"})

    assert response.status_code == 422


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_post_invalid_name(client, name):
    response = client.post("/customers", json={"customer_id": 104, "name": name})

    assert response.status_code == 422

@pytest.mark.parametrize("name", TOO_LONG_NAMES)
def test_post_too_long_name(client, name):
    response = client.post("/customers", json={"customer_id": 104, "name": name})

    assert response.status_code == 422

@pytest.mark.parametrize("input_name, expected_name", NAMES_WITH_WHITESPACE)
def test_post_names_with_whitespace(client, input_name, expected_name):
    response = client.post("/customers", json={"customer_id": 104, "name": input_name})

    assert response.status_code == 200

    assert response.json() == {"customer_id": 104, "name": expected_name}

    # Confirm the stripped name was actually stored
    assert customers[104] == expected_name

@pytest.mark.parametrize("data", MISSING_CUSTOMER_DATA)
def test_post_missing_customer_data(client, data):
    response = client.post("/customers", json=data)

    assert response.status_code == 422

# =========================
# PATCH
# =========================

@pytest.mark.parametrize("customer_id", EXISTING_CUSTOMER_IDS)
def test_patch_existing_customer(client, customer_id):
    response = client.patch(f"/customers/{customer_id}", json={"name": "Ben"})

    assert response.status_code == 200

    assert response.json() == {"name": "Ben"}

    # Confirm the customer was actually updated
    assert customers[customer_id] == "Ben"

@pytest.mark.parametrize("customer_id", NON_EXISTING_CUSTOMER_IDS)
def test_patch_non_existing_customer(client, customer_id):
    response = client.patch(f"/customers/{customer_id}", json={"name": "Ben"})

    assert response.status_code == 404

    assert response.json() == {"detail": "Customer not found"}

@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_patch_invalid_customer_id(client, customer_id):
    response = client.patch(f"/customers/{customer_id}", json={"name": "Ben"})

    assert response.status_code == 422

@pytest.mark.parametrize("name", INVALID_NAMES)
def test_patch_invalid_name(client, name):
    response = client.patch(f"/customers/101", json={"name": name})

    assert response.status_code == 422

@pytest.mark.parametrize("name", TOO_LONG_NAMES)
def test_patch_too_long_name(client, name):
    response = client.patch(f"/customers/101", json={"name": name})

    assert response.status_code == 422

@pytest.mark.parametrize("input_name, expected_name", NAMES_WITH_WHITESPACE)
def test_patch_names_with_whitespace(client, input_name, expected_name):
    response = client.patch(f"/customers/101", json={"name": input_name})

    assert response.status_code == 200

    assert response.json() == {"name": expected_name}

    # Confirm the stripped name was actually stored
    assert customers[101] == expected_name

def test_patch_missing_customer_id(client):
    response = client.patch("/customers/", json={"name": "Ben"})

    assert response.status_code == 405

# =========================
# DELETE
# =========================

@pytest.mark.parametrize("customer_id", EXISTING_CUSTOMER_IDS)
def test_delete_existing_customer(client, customer_id):
    response = client.delete(f"/customers/{customer_id}")

    assert response.status_code == 200

    assert response.json() == {"message": "Customer deleted"}

@pytest.mark.parametrize("customer_id", NON_EXISTING_CUSTOMER_IDS)
def test_delete_non_existing_cusotmer(client, customer_id):
    response = client.delete(f"/customers/{customer_id}")

    assert response.status_code == 404

    assert response.json() == {"detail": "Customer not found"}

@pytest.mark.parametrize("customer_id", INVALID_CUSTOMER_IDS)
def test_delete_invalid_customer_id(client, customer_id):
    response = client.delete(f"/customers/{customer_id}")

    assert response.status_code == 422


def test_delete_missing_customer_id(client):
    response = client.delete("/customers/")

    assert response.status_code == 405