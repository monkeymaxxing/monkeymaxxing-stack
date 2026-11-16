CREATE TABLE password_reset_requests (
 email text PRIMARY KEY, requested_at timestamptz NOT NULL DEFAULT now(),
 pending boolean NOT NULL DEFAULT true, next_attempt_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE password_reset_tokens (
 token_hash text PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id),
 expires_at timestamptz NOT NULL, used_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX password_reset_owner ON password_reset_tokens(owner_id);
CREATE TABLE source_imports (
 source_site_id text PRIMARY KEY, manifest_sha256 text NOT NULL,
 imported_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE source_schema_migrations (
 version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL
);

CREATE TABLE source_identity_metadata (
 user_id uuid PRIMARY KEY REFERENCES users(id), metadata jsonb NOT NULL
);
