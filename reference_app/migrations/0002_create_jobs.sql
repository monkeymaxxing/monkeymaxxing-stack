-- The job queue. A job whose finished_at is empty waits for a worker; a
-- worker that runs it keeps its row locked until it records finished_at,
-- so no other worker takes it, and a worker that dies first leaves it
-- waiting again for the next one.
create table jobs (
  id bigserial primary key,
  added_at timestamptz not null default now(),
  added_on_server text not null,
  finished_at timestamptz,
  finished_on_server text
);

-- The workers look for the oldest waiting job every second.
create index jobs_waiting on jobs (id) where finished_at is null;
