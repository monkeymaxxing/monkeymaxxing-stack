CREATE TABLE users (
 id uuid PRIMARY KEY, email text UNIQUE NOT NULL, password_hash text NOT NULL,
 is_admin boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE records (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), title text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX records_owner ON records(owner_id);
CREATE TABLE documents (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id), file_name text NOT NULL,
 object_key text UNIQUE NOT NULL, sha256 text NOT NULL, byte_length integer NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_owner ON documents(owner_id);
CREATE TABLE jobs (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','COMPLETED')),
 output text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz, archived_at timestamptz
);
CREATE INDEX jobs_pending ON jobs(created_at) WHERE state='PENDING';
CREATE TABLE controls (id integer PRIMARY KEY CHECK(id=1),worker_paused boolean NOT NULL DEFAULT true);
INSERT INTO controls(id) VALUES(1);
CREATE TABLE scheduled_runs (
 occurrence_at timestamptz PRIMARY KEY, completed_at timestamptz NOT NULL DEFAULT now(), archived_reports integer NOT NULL
);
