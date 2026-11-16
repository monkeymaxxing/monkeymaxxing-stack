CREATE TABLE users (
 id text PRIMARY KEY, email text UNIQUE NOT NULL, password_hash text,
 password_algorithm text NOT NULL DEFAULT 'bcrypt' CHECK(password_algorithm IN ('bcrypt','firebase_scrypt')),
 firebase_password_hash text, firebase_password_salt text, disabled boolean NOT NULL DEFAULT false,
 CHECK ((password_algorithm='bcrypt' AND password_hash IS NOT NULL) OR
        (password_algorithm='firebase_scrypt' AND firebase_password_hash IS NOT NULL AND firebase_password_salt IS NOT NULL)),
 is_admin boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE identities (
 issuer text NOT NULL, subject text NOT NULL, user_id text NOT NULL REFERENCES users(id),
 PRIMARY KEY (issuer,subject)
);
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, owner_id text NOT NULL REFERENCES users(id),
 expires_at timestamptz NOT NULL, revoked_at timestamptz
);
CREATE TABLE records (
 id text PRIMARY KEY, owner_id text NOT NULL REFERENCES users(id), title text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX records_owner ON records(owner_id);
CREATE TABLE documents (
 id text PRIMARY KEY, owner_id text NOT NULL REFERENCES users(id), filename text NOT NULL,
 object_key text UNIQUE NOT NULL, sha256 char(64) NOT NULL, byte_length integer NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE jobs (
 id text PRIMARY KEY, owner_id text NOT NULL REFERENCES users(id),
 state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','RUNNING','COMPLETED')),
 output text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 archived boolean NOT NULL DEFAULT false
);
CREATE INDEX jobs_claim ON jobs(state,created_at);
CREATE TABLE controls (
 id integer PRIMARY KEY CHECK(id=1), worker_paused boolean NOT NULL DEFAULT true,
 scheduler_paused boolean NOT NULL DEFAULT false, maintenance_enabled boolean NOT NULL DEFAULT false
);
INSERT INTO controls(id) VALUES(1);
CREATE TABLE schedules (
 id text PRIMARY KEY, next_run_at timestamptz NOT NULL, last_run_at timestamptz
);
INSERT INTO schedules(id,next_run_at) VALUES('archive_reports', now()+interval '1 day');
CREATE TABLE scheduled_runs (
 schedule_id text NOT NULL REFERENCES schedules(id), occurrence_at timestamptz NOT NULL,
 completed_at timestamptz NOT NULL DEFAULT now(), archived_count integer NOT NULL,
 PRIMARY KEY(schedule_id,occurrence_at)
);

-- The project signer key is secret and belongs in the same protected database as password hashes.
CREATE TABLE firebase_auth_config (
 id integer PRIMARY KEY CHECK(id=1), source_project_id text NOT NULL,
 hash_algorithm text NOT NULL CHECK(hash_algorithm='SCRYPT'), signer_key text NOT NULL,
 salt_separator text NOT NULL, rounds integer NOT NULL, memory_cost integer NOT NULL
);
CREATE TABLE source_documents (collection_name text NOT NULL, source_document_id text NOT NULL, data jsonb NOT NULL, PRIMARY KEY(collection_name,source_document_id));
CREATE TABLE source_auth_users (firebase_uid text PRIMARY KEY REFERENCES users(id), data jsonb NOT NULL);
