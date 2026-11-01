import re

from sqlalchemy.engine import make_url


def validate_database_urls(test_database_url: str, runtime_database_url: str) -> None:
    """Reject ambiguous targets before any test connection or destructive fixture."""
    test_url = make_url(test_database_url)
    runtime_url = make_url(runtime_database_url)
    if (
        test_url.get_backend_name() != "postgresql"
        or runtime_url.get_backend_name() != "postgresql"
        or not test_url.database
        or not runtime_url.database
        or not re.search(r"(?:^|[_-])test(?:$|[_-])", test_url.database.lower())
        or test_url.database == runtime_url.database
        # These libpq parameters can override the database named in the URL path.
        or {"dbname", "service"}.intersection(test_url.query)
        or {"dbname", "service"}.intersection(runtime_url.query)
    ):
        raise ValueError(
            "Refusing destructive tests: use explicit, separate PostgreSQL database "
            "names, a test name with a 'test' segment, and no dbname/service query overrides."
        )
