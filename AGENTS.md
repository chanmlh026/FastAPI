# Repository guidance

## Project and stack

- Customer CRUD and search API built with Python 3.14+, FastAPI, Pydantic,
  synchronous SQLAlchemy 2, PostgreSQL via psycopg, and Fernet pagination tokens.
- Use `uv sync` for dependencies, `uv run uvicorn app.main:app --reload` for local
  development, and `uv run pytest` for tests. Dependencies are declared in
  `pyproject.toml` and locked in `uv.lock`; pytest and Black are dev dependencies.

## Architecture and conventions

- `app/main.py` assembles the app; `app/customers/router.py` owns customer routes.
  Keep ORM models in `models.py`, Pydantic models in `schemas.py`, shared limits
  in `constants.py`, and cursor handling in `pagination.py`.
  Add feature-specific packages such as `app/auth/` when needed, following the
  same separation of responsibilities and registering routers in `app/main.py`.
- `app/core/config.py` loads and caches environment settings. `app/db/database.py`
  owns the engine, declarative base, and request-scoped sessions through `get_db`.
- Follow existing type annotations, snake_case names, and Black-compatible
  formatting. Prefer small changes and existing helpers over new abstractions.
- Preserve response shapes, status codes, validation, and database behaviour
  unless a task explicitly requests a change. Retain session cleanup and rollback
  after failed writes.
- Preserve trimmed names (1 to 50 characters), IDs from 1 through 2**31 - 1,
  literal case-insensitive substring search, and ascending-ID cursor pagination.
  Page size defaults to 50 (also for zero) and is capped at 1,000. Keep cursors
  opaque, authenticated, versioned, and bound to the trimmed search query.

## Dependencies and database

- Avoid unnecessary dependencies; prefer existing tools. Justified additions
  are permitted with task-specific approval: explain the need and tradeoffs
  before adding them, using approval already given when applicable. Use uv for
  dependency changes and keep `pyproject.toml` and `uv.lock` consistent.
- Use SQLAlchemy expressions and the injected session; never interpolate user
  input into SQL. Preserve escaped literal search wildcards.
- `sql/setup.sql` defines the customer table and sample data; no migration
  framework is configured. Keep ORM and SQL definitions consistent when schema
  changes are requested, and document how existing databases should be updated.
- Never run seed, reset, or destructive SQL against existing user data without
  explicit authorization.

## Security

- Never hardcode, commit, or expose credentials, connection strings containing
  passwords, or pagination keys. Keep `.env` and `.env.test` local and ignored.
- Runtime settings are `DATABASE_URL` and `PAGINATION_TOKEN_KEY`; tests use
  `TEST_DATABASE_URL`. Keep the pagination key stable across restarts and workers;
  rotating it invalidates issued tokens.
- Preserve input validation, rejection of invalid or mismatched tokens with 400,
  and list-endpoint failure with 503 for missing or invalid key configuration.
- Add or change authentication and authorization only when explicitly in scope
  for the task; follow that task's requirements and existing project conventions.

## Testing

- For runtime changes, add or update relevant pytest/TestClient coverage and run
  `uv run pytest` after confirming database isolation. Cover affected success,
  validation, error, persistence, search, and pagination behaviour as applicable.
- Tests override `get_db` using `TEST_DATABASE_URL` loaded from `.env.test`.
  Use a dedicated PostgreSQL test database with the `customers` table already
  created, separate from development and production. Fixtures delete and reseed
  records and commit changes; they do not provide transaction rollback isolation.
- App imports also load `DATABASE_URL`; configure it before running tests. Test
  fixtures generate pagination keys. Never use production secrets for testing.
- If isolation or prerequisites cannot be confirmed, do not run destructive tests;
  report the blocker. Documentation-only changes do not require runtime tests.

## Documentation and completion

- For requested API, configuration, setup, or schema changes, update the relevant
  README examples and FastAPI descriptions to match the implementation. Respect
  task scope restrictions on which files may change.
- Finish with files created or modified, a concise change summary, important
  design decisions, checks run and their results (or why skipped), and any
  assumptions, blockers, or outstanding concerns. State whether application code
  changed. Preserve unrelated user edits and never claim unrun tests passed.
