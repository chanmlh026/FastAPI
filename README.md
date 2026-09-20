# Customer API

A REST API for creating, reading, searching, updating, and deleting customers.
It is built with FastAPI, SQLAlchemy, PostgreSQL, and Pydantic, with opaque
cursor-based pagination for customer listings.

## Requirements

- Python 3.14 or later
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL

## Setup

Install the application and development dependencies:

```bash
uv sync
```

Create the development and test databases in PostgreSQL. The SQL in
`sql/setup.sql` creates the `customers` table and adds sample records; run it
against the development database before starting the API.

Create a `.env` file in the project root:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/customer_api
PAGINATION_TOKEN_KEY=replace-with-a-generated-key
```

Generate a pagination key once with:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep this key secret and stable across application restarts and workers.
Changing it invalidates previously issued page tokens.

For tests, create `.env.test` with a connection to a separate test database:

```dotenv
TEST_DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/customer_api_test
```

The test database must contain the same `customers` table. Tests delete and
reseed its customer records, so never point `TEST_DATABASE_URL` at development
or production data.

## Running the API

```bash
uv run uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive documentation is
available at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/customers` | List or search customers |
| `GET` | `/customers/{customer_id}` | Get one customer |
| `POST` | `/customers` | Create a customer |
| `PATCH` | `/customers/{customer_id}` | Update a customer's name |
| `DELETE` | `/customers/{customer_id}` | Delete a customer |

Customer IDs must be integers from 1 through 2,147,483,647. Names are trimmed,
must contain at least one non-whitespace character, and may be at most 50
characters long.

Create a customer:

```http
POST /customers
Content-Type: application/json

{
  "customer_id": 104,
  "name": "Mary Jane"
}
```

Update a customer:

```http
PATCH /customers/104
Content-Type: application/json

{
  "name": "Mary Smith"
}
```

## Search and pagination

Search performs a case-insensitive substring match on customer names:

```http
GET /customers?q=Mary&page_size=20
```

Surrounding whitespace in `q` is ignored. Omitting `q`, or passing a blank
value, lists all customers. `%` and `_` are treated as literal characters.
Results are ordered by `customer_id` in ascending order.

A list response has this shape:

```json
{
  "customers": [
    {
      "customer_id": 102,
      "name": "Mary"
    }
  ],
  "next_page_token": ""
}
```

Pagination follows [AIP-132](https://google.aip.dev/132) and
[AIP-158](https://google.aip.dev/158):

- `page_size` defaults to 50. A value of `0` also uses the default.
- The maximum page size is 1,000; larger values are capped at 1,000.
- Negative and non-integer page sizes return `400 Bad Request`.
- Pass a non-empty `next_page_token` back as `page_token` to get the next page.
- Keep `q` unchanged while following a page token. `page_size` may change.
- An empty `next_page_token` means there are no more results.
- Invalid, altered, or mismatched page tokens return `400 Bad Request`.

Page tokens are encrypted, authenticated, URL-safe, and opaque to clients.
Pagination does not provide a fixed snapshot, so concurrent inserts, updates,
or deletes can affect later pages. If `PAGINATION_TOKEN_KEY` is missing or
invalid, the list endpoint returns `503 Service Unavailable`.

## Testing

Run the complete test suite with:

```bash
uv run pytest
```

## Project structure

```text
.
|-- app/
|   |-- core/
|   |   `-- config.py          # Environment configuration
|   |-- customers/
|   |   |-- models.py          # SQLAlchemy customer model
|   |   |-- pagination.py      # Opaque page-token handling
|   |   |-- router.py          # Customer endpoints
|   |   `-- schemas.py         # Request and response models
|   |-- db/
|   |   `-- database.py        # Database engine and sessions
|   `-- main.py                # FastAPI application
|-- sql/
|   `-- setup.sql              # Customer table and sample data
|-- tests/
|   |-- conftest.py            # Test database configuration
|   `-- test_main.py           # API tests
|-- .env                       # Local application configuration
|-- .env.test                  # Local test configuration
|-- pyproject.toml             # Dependencies and tool configuration
|-- uv.lock                    # Locked dependencies
`-- README.md
```
