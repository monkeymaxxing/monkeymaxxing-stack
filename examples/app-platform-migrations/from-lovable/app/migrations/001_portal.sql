CREATE TABLE users (
 id uuid PRIMARY KEY, email text NOT NULL UNIQUE, password_hash text NOT NULL,
 email_confirmed_at timestamptz, banned_until timestamptz
);
CREATE UNIQUE INDEX users_email_normalized ON users(lower(email));
CREATE TABLE sessions (
 token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id), expires_at timestamptz NOT NULL
);
CREATE TABLE records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
 title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 200),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX records_owner ON records(user_id);
CREATE TABLE documents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
 record_id uuid REFERENCES records(id) ON DELETE SET NULL,
 file_name text NOT NULL CHECK (char_length(file_name) BETWEEN 1 AND 255),
 object_key text NOT NULL UNIQUE CHECK (split_part(object_key,'/',1)=user_id::text),
 sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
 byte_count bigint NOT NULL CHECK (byte_count>=0), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_owner ON documents(user_id);
CREATE TABLE report_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES users(id),
 status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED')),
 requested_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz,
 output text, attempts integer NOT NULL DEFAULT 0, archived_at timestamptz
);
CREATE INDEX jobs_owner_status ON report_jobs(user_id,status);
CREATE TABLE imported_schedules (name text PRIMARY KEY, definition jsonb NOT NULL);
CREATE TABLE source_migrations (source_row jsonb NOT NULL);
