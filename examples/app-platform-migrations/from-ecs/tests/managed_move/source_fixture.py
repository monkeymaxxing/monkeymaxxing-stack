#!/usr/bin/env python3
"""Create or capture source objects that normal logical table copying omits."""
import argparse
import json
from pathlib import Path

from proof_common import postgres, postgres_json, read_settings, write_private

EXTRA_ROLE = 'migration_evidence_reader'
ROLE_SQL = """DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='migration_evidence_reader') THEN
  CREATE ROLE migration_evidence_reader NOLOGIN;
 END IF;
 IF (SELECT rolcanlogin FROM pg_roles WHERE rolname='migration_evidence_reader') THEN
  RAISE EXCEPTION 'migration_evidence_reader must be NOLOGIN';
 END IF;
END $$;
"""

CREATE_SQL = """BEGIN;
CREATE SCHEMA migration_evidence AUTHORIZATION portal;
SET ROLE portal;
CREATE SEQUENCE migration_evidence.event_id_sequence START WITH 9001;
CREATE TABLE migration_evidence.events (
 id bigint PRIMARY KEY DEFAULT nextval('migration_evidence.event_id_sequence'),
 description text NOT NULL,
 payload_bytes bytea NOT NULL,
 large_object_oid oid NOT NULL,
 occurred_at timestamptz NOT NULL
);
ALTER SEQUENCE migration_evidence.event_id_sequence OWNED BY migration_evidence.events.id;
WITH object AS (
 SELECT lo_from_bytea(0, decode(repeat('000102ff6d6967726174696f6e2d65766964656e6365000a',4096), 'hex')) AS oid
)
INSERT INTO migration_evidence.events(description,payload_bytes,large_object_oid,occurred_at)
 SELECT E'Non-public schema fixture: café\\nsecond line',
 decode('00ff102070726f6265000a','hex'),oid,'2026-11-06 01:02:03.123456+00' FROM object;
INSERT INTO migration_evidence.events(description,payload_bytes,large_object_oid,occurred_at)
 SELECT 'Second full fixture row',decode('fedcba9876543210','hex'),large_object_oid,
 '2026-11-06 01:02:04.654321+00' FROM migration_evidence.events;
SELECT setval('migration_evidence.event_id_sequence', 9041, true) AS fixture_sequence_advanced \\gset
GRANT USAGE ON SCHEMA migration_evidence TO migration_evidence_reader, database_moving_in_replication;
GRANT SELECT ON ALL TABLES IN SCHEMA migration_evidence TO migration_evidence_reader, database_moving_in_replication;
GRANT USAGE, SELECT ON SEQUENCE migration_evidence.event_id_sequence TO migration_evidence_reader;
DO $$ DECLARE object_oid oid; BEGIN
 SELECT large_object_oid INTO object_oid FROM migration_evidence.events LIMIT 1;
 EXECUTE format('GRANT SELECT ON LARGE OBJECT %s TO migration_evidence_reader',object_oid);
END $$;
RESET ROLE;
COMMIT;
"""

# aclexplode converts object ACLs to role names, because role OIDs differ by cluster.
# row_to_json keeps PostgreSQL microseconds intact instead of passing through JS Date.
FIXTURE_SQL = """SELECT json_build_object(
 'schema', (SELECT json_build_object('name',nspname,'owner',pg_get_userbyid(nspowner),
   'acl',coalesce((SELECT json_agg(a ORDER BY a.grantee,a.privilege_type) FROM
    (SELECT pg_get_userbyid(grantor) grantor,
      CASE WHEN grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(grantee) END grantee,
      privilege_type,is_grantable FROM aclexplode(nspacl)) a),'[]'::json))
   FROM pg_namespace WHERE nspname='migration_evidence'),
 'relations', (SELECT coalesce(json_agg(r ORDER BY r.name),'[]'::json) FROM
   (SELECT c.relname name,c.relkind kind,pg_get_userbyid(c.relowner) owner,
    coalesce((SELECT json_agg(a ORDER BY a.grantee,a.privilege_type) FROM
     (SELECT pg_get_userbyid(grantor) grantor,
       CASE WHEN grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(grantee) END grantee,
       privilege_type,is_grantable FROM aclexplode(c.relacl)) a),'[]'::json) acl
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='migration_evidence' AND c.relkind IN ('r','S')) r),
 'sequence', (SELECT json_build_object('last_value',last_value,'is_called',is_called)
              FROM migration_evidence.event_id_sequence),
 'rows', (SELECT coalesce(json_agg(row_to_json(e) ORDER BY e.id),'[]'::json)
          FROM migration_evidence.events e),
 'large_objects', (SELECT coalesce(json_agg(o ORDER BY o.oid),'[]'::json) FROM
   (SELECT m.oid,pg_get_userbyid(m.lomowner) owner,encode(lo_get(m.oid),'hex') bytes_hex,
    coalesce((SELECT json_agg(a ORDER BY a.grantee,a.privilege_type) FROM
     (SELECT pg_get_userbyid(grantor) grantor,
       CASE WHEN grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(grantee) END grantee,
       privilege_type,is_grantable FROM aclexplode(m.lomacl)) a),'[]'::json) acl
    FROM pg_largeobject_metadata m
    WHERE m.oid IN (SELECT large_object_oid FROM migration_evidence.events)) o),
 'extra_role', (SELECT json_build_object('name',rolname,'can_login',rolcanlogin,
    'superuser',rolsuper,'create_database',rolcreatedb,'create_role',rolcreaterole,
    'replication',rolreplication,'bypass_row_security',rolbypassrls)
    FROM pg_roles WHERE rolname='migration_evidence_reader')
)"""

RECORDS_SQL = """SELECT coalesce(json_agg(row_to_json(r) ORDER BY r.id),'[]'::json)
FROM public.records r"""


def capture(postgres_env, diagnostic_dir):
    # Single snapshot: source rows and fixture state represent one fenced source.
    sql = ("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n"
           "SET LOCAL bytea_output='hex';\n"
           "SELECT json_build_object('fixture',(" + FIXTURE_SQL + "),"
           "'records',(" + RECORDS_SQL + "));\nCOMMIT;")
    return postgres_json(postgres_env, sql, diagnostic_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['roles', 'create', 'capture'])
    parser.add_argument('settings_file', type=Path)
    parser.add_argument('--output', type=Path,
                        help='Protected JSON facts file, required for create/capture')
    args = parser.parse_args()
    settings = read_settings(args.settings_file)
    env = settings['postgres_env']
    if args.phase == 'roles':
        postgres(env, ROLE_SQL, args.settings_file.parent)
        print('Required NOLOGIN grantee exists: ' + EXTRA_ROLE)
        return
    if not args.output:
        parser.error('--output is required for create/capture')
    if args.phase == 'create':
        postgres(env, ROLE_SQL + CREATE_SQL, args.settings_file.parent)
    facts = capture(env, args.settings_file.parent)
    write_private(args.output, json.dumps(facts, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'phase': args.phase, 'record_count': len(facts['records']),
                      'fixture_row_count': len(facts['fixture']['rows']),
                      'large_object_count': len(facts['fixture']['large_objects']),
                      'facts_file': str(args.output)}))


if __name__ == '__main__':
    main()
