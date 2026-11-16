CREATE TABLE accounts (
 id bigserial PRIMARY KEY, email text NOT NULL UNIQUE,
 password_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id),
 expires_at timestamptz NOT NULL
);
CREATE TABLE records (
 id bigserial PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id),
 title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200)
);
CREATE TABLE documents (
 id bigserial PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id),
 object_key text NOT NULL UNIQUE, file_name text NOT NULL,
 sha256 text NOT NULL, byte_count bigint NOT NULL
);
CREATE TABLE report_jobs (
 id bigserial PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id),
 fixture_key text UNIQUE, output text,
 created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
CREATE INDEX waiting_report_jobs ON report_jobs(id) WHERE finished_at IS NULL;
