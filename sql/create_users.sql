-- Additive setup for existing development databases and dedicated test databases.
-- Does not touch customers or seed any data. Run once per database.
BEGIN;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(254) NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));

COMMIT;
