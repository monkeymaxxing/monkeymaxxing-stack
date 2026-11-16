#!/usr/bin/env python3
"""Prepare only the fresh synthetic RDS fixture; secret values stay in files/stdin."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def literal(value):
    if '\n' in value or '\r' in value:
        raise ValueError('Generated passwords must fit a PostgreSQL passfile')
    return "'" + value.replace("'", "''") + "'"


def statements(settings, phase):
    if phase == 'roles':
        return """BEGIN;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('portal','database_moving_in_replication'))
 OR EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public') THEN
  RAISE EXCEPTION 'Use a fresh dedicated fixture; roles or app tables already exist';
 END IF;
END $$;
CREATE ROLE portal LOGIN CREATEDB PASSWORD %s;
GRANT portal TO postgres;
ALTER DATABASE portal OWNER TO portal;
ALTER ROLE portal NOCREATEDB;
CREATE ROLE database_moving_in_replication LOGIN PASSWORD %s;
GRANT rds_replication TO database_moving_in_replication;
COMMIT;
""" % (literal(settings['app_password']), literal(settings['replication_password']))
    return """GRANT CONNECT ON DATABASE portal TO database_moving_in_replication;
GRANT USAGE ON SCHEMA public TO database_moving_in_replication;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO database_moving_in_replication;
ALTER DEFAULT PRIVILEGES FOR ROLE portal IN SCHEMA public
 GRANT SELECT ON TABLES TO database_moving_in_replication;
CREATE PUBLICATION database_moving_in FOR ALL TABLES;
ALTER ROLE portal RESET default_transaction_read_only;
ALTER ROLE portal IN DATABASE portal RESET default_transaction_read_only;
ALTER DATABASE portal RESET default_transaction_read_only;
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['roles', 'publication'])
    parser.add_argument('settings_file', type=Path)
    args = parser.parse_args()
    if args.settings_file.stat().st_mode & 0o077:
        parser.error('Protect the settings file with mode 600')
    settings = json.loads(args.settings_file.read_text())
    env = {**os.environ, **settings['administrator_env']}
    if env.get('PGUSER') != 'postgres' or env.get('PGSSLMODE') != 'verify-full':
        parser.error('Use the source postgres administrator with verified provider TLS')
    env['PGDATABASE'] = 'portal'
    # No URL/password appears in arguments; SQL and generated passwords use stdin.
    result = subprocess.run(['psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
                            input=statements(settings, args.phase), env=env,
                            capture_output=True, text=True)
    if result.returncode:
        diagnostic = args.settings_file.parent / 'bootstrap-error.log'
        diagnostic.write_text(result.stderr)
        diagnostic.chmod(0o600)
        raise SystemExit('Source bootstrap failed; protected diagnostics: ' + str(diagnostic))
    print('Fresh source preparation completed: ' + args.phase)


if __name__ == '__main__':
    main()
