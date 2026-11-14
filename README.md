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

Create the development and test databases in PostgreSQL. On a fresh database,
`sql/setup.sql` creates the `customers` table and adds sample records. Do not
rerun it against an existing database.

Registration adds `users` through the separate, additive `sql/create_users.sql`.
Run this script once in each development and dedicated test database using
your PostgreSQL client, for example:

```bash
psql -h localhost -U postgres -d customer_api -v ON_ERROR_STOP=1 -f sql/create_users.sql
psql -h localhost -U postgres -d customer_api_test -v ON_ERROR_STOP=1 -f sql/create_users.sql
```

These commands prompt for credentials when needed; do not put passwords in
command lines. The script creates only the new table and unique index inside
a transaction, without changing customer records. It deliberately fails if
`users` already exists rather than silently accepting an incompatible schema.
No migration framework or automatic startup DDL is configured.

Create a `.env` file in the project root:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/customer_api
PAGINATION_TOKEN_KEY=replace-with-a-generated-key
JWT_SECRET_KEY=replace-with-independently-generated-hex-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Generate a pagination key once with:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep this key secret and stable across application restarts and workers.
Changing it invalidates previously issued page tokens.

Generate a separate JWT signing key once with:

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Store the generated value as `JWT_SECRET_KEY` in the local `.env` or your secret
manager. It must be hexadecimal encoding of at least 32 securely random bytes
(64 hex characters for 32 bytes). HS256 uses the decoded bytes, not the literal
hex text. Never use a password, example value, or the pagination key. Format and
length checks reject malformed, short and repeated-byte placeholders, but cannot
prove a key's randomness; use the secure generator above. Reusing the pagination
key's decoded bytes for JWT signing is also rejected, even across encodings.
Keep the key private and
stable across restarts and workers. Rotating it makes existing tokens fail
signature verification with the new key. Do not commit `.env`.

`ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30 and accepts a positive integer minute
count whose expiration can be represented. Missing or invalid JWT settings cause
login to return a generic `503 Service Unavailable`; registration and customer
endpoints continue to work. Settings are cached, so restart workers after changes.

For tests, create `.env.test` with a connection to a separate test database:

```dotenv
TEST_DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/customer_api_test
```

The test database must contain both `customers` and `users`. Tests delete and
reseed customer records and delete test users, so never point
`TEST_DATABASE_URL` at development or production data. A safety guard requires
an explicit PostgreSQL database name containing a `test` segment (separated by
underscores or hyphens), different from `DATABASE_URL`. Names such as
`customers_latest` do not qualify. Both URLs must name their databases directly;
`dbname` and `service` query overrides are rejected because they can make the
URL path misleading. The guard checks the connected database identity and required
tables before fixtures write data. Use a dedicated test database even when these
checks pass; a name check cannot establish that a database contains disposable data.

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
| `POST` | `/auth/register` | Register a user account |
| `POST` | `/auth/login` | Authenticate an active user and issue an access token |
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

## User registration

```http
POST /auth/register
Content-Type: application/json

{
  "email": "person@example.com",
  "password": "a long secure passphrase"
}
```

Successful response (`201 Created`):

```json
{
  "id": 1,
  "email": "person@example.com"
}
```

Email addresses are validated and normalised by Pydantic's `EmailStr` and
`email-validator`, including Unicode local parts and internationalised domains.
Surrounding whitespace is removed and the entire normalised address is lowercased,
including the local part. The stored address is limited to 254 characters;
`email-validator` also applies its protocol length and syntax checks. For example,
`É@example.com` and `É@example.com` both become `é@example.com`, and
`person@xn--bcher-kva.de` becomes `person@bücher.de`.

PostgreSQL's unique `uq_users_email_lower` index on `lower(email)` prevents
duplicates according to the database's collation and case-conversion rules.
API registrations reject addresses that normalise to the same stored value,
including the case, canonical-equivalence, and Unicode/punycode examples above.
Lowercasing is not full Unicode case folding: distinct addresses such as
`straße@example.com` and `strasse@example.com` are not merged by the API.
Writes outside the API must use the same normalisation: the index
does not perform Unicode canonical or IDNA normalisation, and Unicode case
conversion depends on the database locale. Some locales lowercase only ASCII
letters, so the index alone does not guarantee Unicode case-insensitive uniqueness.
An existing email returns `409 Conflict` with
`{"detail": "Email already registered"}`. Invalid inputs return `422`; registration
validation errors omit submitted values to avoid exposing passwords.

Email syntax validation does not verify mailbox ownership or deliverability.
Unicode lookalikes can still represent distinct addresses; do not use their visual
appearance to establish identity. Future mail delivery must support SMTPUTF8 for
Unicode local parts and appropriate IDNA handling for internationalised domains.

Passwords must contain 15–128 characters. Spaces and Unicode are allowed;
passwords are never trimmed or silently truncated, and there are no required
character classes. `argon2-cffi` hashes with Argon2id using the RFC 9106 low-memory
profile (64 MiB, three iterations, parallelism four), with a fresh random salt
generated by the library. `email-validator` provides Pydantic email validation;
both are declared runtime dependencies installed by `uv sync`. Hashing needs
native bindings, supplied by `argon2-cffi-bindings`.

The registration service owns commit/rollback. Only the specific PostgreSQL
email uniqueness violation becomes a duplicate error; other database failures
are rolled back and propagate as server errors. SQLAlchemy exception output
hides bound parameters. Only ID and email are returned; passwords and hashes
are never included in the response. Users default to active and receive a
server-generated timezone-aware creation timestamp.

## User login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "person@example.com",
  "password": "a long secure passphrase"
}
```

Successful response (`200 OK`):

```json
{
  "access_token": "<signed-jwt>",
  "token_type": "bearer"
}
```

Login uses exactly the registration Unicode email normalisation and looks up the
stored normalised address. Passwords are verified with the existing Argon2id
verifier and are never trimmed. Login allows short or empty strings to fail as
credentials with `401`, rather than applying registration's password minimum;
the existing maximum password length still applies. Invalid request shapes,
emails or overlong passwords return `422` with submitted values omitted, including
for malformed JSON. Registration's validation and response contract are unchanged.

Unknown emails, incorrect passwords and inactive users all return
`401 Unauthorized` with `{"detail": "Invalid credentials"}` and
`WWW-Authenticate: Bearer`. No account fields or password hashes are returned.
Login performs no database writes, including hash upgrades. Unknown users undergo
one dummy Argon2id verification using a random hash generated once per worker;
existing users are verified before checking active status. This reduces the main
timing difference, but does not guarantee constant-time authentication.

Tokens are signed with HS256 using `PyJWT`, and contain only `sub` (string user
ID), `iat`, and `exp`. Timestamps originate from timezone-aware UTC datetimes and
are encoded as JWT NumericDate seconds. The default lifetime is 30 minutes.
Responses use `Cache-Control: no-store` and `Pragma: no-cache`. JWTs are signed,
not encrypted; their claims are readable. Any token consumer must explicitly
verify the HS256 signature, required claims, and expiration.

Customer endpoints are **not JWT-protected** yet; no endpoint currently consumes
the token. Employee approval, RBAC, refresh tokens, logout, revocation and email
verification are not implemented. Inactivating a user blocks future logins but
does not revoke issued tokens. Unicode email and direct-write normalisation
limitations described above still apply. Serve over HTTPS and configure
infrastructure to avoid logging request bodies, authorization headers, responses
containing tokens, or secrets. Public deployment still needs abuse controls,
rate limiting and a measured Argon2 concurrency budget (each concurrent
verification uses about 64 MiB).

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

After creating both tables in the isolated test database, run registration tests
alone with:

```bash
uv run pytest tests/test_registration.py
```

Application imports also require `DATABASE_URL` in `.env` or the environment.
Test fixtures generate their own pagination and JWT keys; no production secrets
are needed. Login tests also cover token signatures, claims, expiration, generic
failures, validation secrecy, Unicode normalisation and invalid configuration.

## Project structure

```text
.
|-- app/
|   |-- auth/
|   |   |-- constants.py       # Auth limits, index name and JWT algorithm
|   |   |-- models.py          # SQLAlchemy user model
|   |   |-- passwords.py       # Argon2id hashing and verification
|   |   |-- router.py          # Registration and login HTTP endpoints
|   |   |-- schemas.py         # Public request and response models
|   |   |-- service.py         # Registration transaction and login workflow
|   |   `-- tokens.py          # JWT creation
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
|   |-- create_users.sql       # Additive users table setup
|   `-- setup.sql              # Customer table and sample data
|-- tests/
|   |-- conftest.py            # Test database configuration
|   |-- test_registration.py   # Registration and password tests
|   |-- test_login.py          # Login and JWT tests
|   `-- test_customers.py      # API tests
|-- .env                       # Local application configuration
|-- .env.test                  # Local test configuration
|-- pyproject.toml             # Dependencies and tool configuration
|-- uv.lock                    # Locked dependencies
`-- README.md
```
