import pytest

from tests.database_safety import validate_database_urls

RUNTIME_URL = "postgresql+psycopg://localhost/customer_api"
TEST_URL = "postgresql+psycopg://localhost/customer_api_test"


@pytest.mark.parametrize(
    "name", ["test", "test_customers", "customer_api_test", "customer-test-db"]
)
def test_explicit_separate_test_database_is_allowed(name):
    validate_database_urls(f"postgresql+psycopg://localhost/{name}", RUNTIME_URL)


@pytest.mark.parametrize("name", ["customer_api", "customers_latest", "contest"])
def test_incidental_test_substring_is_not_permission_to_delete(name):
    with pytest.raises(ValueError, match="Refusing destructive tests"):
        validate_database_urls(f"postgresql+psycopg://localhost/{name}", RUNTIME_URL)


def test_same_database_name_is_rejected_even_with_different_host_alias():
    with pytest.raises(ValueError, match="Refusing destructive tests"):
        validate_database_urls(TEST_URL, TEST_URL.replace("localhost", "127.0.0.1"))


@pytest.mark.parametrize("target", ["test", "runtime"])
@pytest.mark.parametrize("override", ["dbname=customer_api_test", "service=production"])
def test_database_routing_overrides_are_rejected(target, override):
    test_url = TEST_URL + f"?{override}" if target == "test" else TEST_URL
    runtime_url = RUNTIME_URL + f"?{override}" if target == "runtime" else RUNTIME_URL
    with pytest.raises(ValueError, match="Refusing destructive tests"):
        validate_database_urls(test_url, runtime_url)


@pytest.mark.parametrize("target", ["test", "runtime"])
@pytest.mark.parametrize(
    "url", ["postgresql+psycopg://localhost/", "sqlite:///test.db"]
)
def test_missing_or_non_postgresql_database_is_rejected(target, url):
    with pytest.raises(ValueError, match="Refusing destructive tests"):
        validate_database_urls(
            url if target == "test" else TEST_URL,
            url if target == "runtime" else RUNTIME_URL,
        )


def test_non_routing_connection_options_are_allowed():
    validate_database_urls(TEST_URL + "?sslmode=require", RUNTIME_URL)
