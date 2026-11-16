create table users (
 id uuid primary key, email text unique not null, password_hash text not null,
 email_confirmed_at timestamptz not null, banned_until timestamptz,
 source_identity jsonb not null default '{}'::jsonb
);
create table sessions (token_hash text primary key,user_id uuid not null references users(id),expires_at timestamptz not null);
create table records (id uuid primary key default gen_random_uuid(),owner_id uuid not null references users(id),title text not null check(length(title) between 1 and 200),created_at timestamptz not null default now());
create table documents (id uuid primary key,owner_id uuid not null references users(id),file_name text not null,object_key text unique not null,sha256 text not null,byte_length bigint not null,created_at timestamptz not null default now());
create table report_jobs (id uuid primary key default gen_random_uuid(),owner_id uuid not null references users(id),status text not null default 'PENDING' check(status in ('PENDING','COMPLETED')),output text,created_at timestamptz not null default now(),completed_at timestamptz);
create table schedule_occurrences (occurrence_minute timestamptz primary key,ran_at timestamptz not null default now());
create table source_schedules (jobname text primary key,schedule text not null,command text not null,source_was_active boolean not null,source_definition jsonb not null);
create table import_receipts (snapshot_sha256 text primary key,imported_at timestamptz not null default now());
