CREATE TABLE users (
  id uuid PRIMARY KEY,
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sessions (
  token_hash text PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES users(id),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);
CREATE TABLE records (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES users(id),
  title text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE documents (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES users(id),
  file_name text NOT NULL,
  object_key text NOT NULL UNIQUE,
  sha256 text NOT NULL,
  byte_length integer NOT NULL CHECK (byte_length >= 0),
  content_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE report_jobs (
  id uuid PRIMARY KEY,
  owner_id uuid NOT NULL REFERENCES users(id),
  state text NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING','COMPLETED')),
  output text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  archived_at timestamptz
);
CREATE INDEX pending_report_jobs ON report_jobs(created_at) WHERE state='PENDING';
CREATE TABLE schedule_runs (
  task_name text NOT NULL,
  occurrence_date date NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT now(),
  archived_job_count integer NOT NULL,
  PRIMARY KEY (task_name, occurrence_date)
);
