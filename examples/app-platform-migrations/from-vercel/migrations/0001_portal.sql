CREATE TABLE accounts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), email text NOT NULL UNIQUE,
 password_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts(id),
 expires_at timestamptz NOT NULL
);
CREATE TABLE records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), account_id uuid NOT NULL REFERENCES accounts(id),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 title text NOT NULL CHECK (length(title) BETWEEN 1 AND 200)
);
CREATE TABLE documents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), account_id uuid NOT NULL REFERENCES accounts(id),
 object_key text NOT NULL UNIQUE, file_name text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 sha256 text NOT NULL, byte_count bigint NOT NULL
);
CREATE TABLE report_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), account_id uuid NOT NULL REFERENCES accounts(id),
 fixture_key text UNIQUE, output text,
 created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, archived_at timestamptz
);
CREATE INDEX waiting_report_jobs ON report_jobs(id) WHERE finished_at IS NULL;

CREATE TABLE scheduled_task_runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), task_name text NOT NULL,
 affected_reports integer NOT NULL, completed_at timestamptz NOT NULL DEFAULT now(),
 scheduled_for date UNIQUE
);
CREATE TABLE migration_imports (
 snapshot_sha256 text PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now(),
 source_manifest jsonb NOT NULL
);
