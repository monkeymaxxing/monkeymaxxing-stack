\set ON_ERROR_STOP on
-- Run only on the disposable synthetic source, as its database administrator.
SET ROLE portal;
CREATE TABLE migration_load (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  payload text NOT NULL,
  payload_md5 text NOT NULL
);
-- Prevent TOAST compression so the copy exercises at least 3 GiB of real storage.
ALTER TABLE migration_load ALTER COLUMN payload SET STORAGE EXTERNAL;
INSERT INTO migration_load(payload,payload_md5)
SELECT repeat(md5(n::text),2048),md5(repeat(md5(n::text),2048)) FROM generate_series(1,49152) n;
CREATE SCHEMA migration_history AUTHORIZATION portal;
CREATE TABLE migration_history.events(id bigint PRIMARY KEY,note text NOT NULL);
INSERT INTO migration_history.events VALUES
  (1,'non-public row must not be restored twice'),(2,'retained migration history');
GRANT USAGE ON SCHEMA migration_history TO portal_reader;
GRANT SELECT ON migration_history.events TO portal_reader;
CREATE SEQUENCE migration_unused START 700;
CREATE SEQUENCE migration_descending START -10 INCREMENT -5;
SELECT nextval('migration_descending');
GRANT SELECT ON migration_load TO portal_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO portal_reader;
SELECT lo_from_bytea(44101,convert_to(repeat('large-object-original-',50000),'UTF8'));
GRANT SELECT ON LARGE OBJECT 44101 TO portal_reader;
RESET ROLE;
SELECT pg_database_size(current_database()) AS database_bytes,
       pg_total_relation_size('migration_load') AS load_table_bytes;
