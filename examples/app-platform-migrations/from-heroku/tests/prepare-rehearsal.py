#!/usr/bin/env python3
"""Create a new local database and private settings for one disposable rehearsal.

Run as root in an isolated Linux test machine with local PostgreSQL 17 running.
No source credential is read. Existing databases and roles are never removed.
"""
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess

os.umask(0o077)
name = os.environ['REHEARSAL_NAME']
# PostgreSQL identifiers and S3 bucket names each have a 63-character boundary.
if len(name) > 63 or not re.fullmatch(r'heroku_[a-z0-9_]*[a-z0-9]', name):
    raise SystemExit('REHEARSAL_NAME must start with heroku_, end with a letter or digit, and contain at most 63 lowercase letters, digits or underscores')
directory = Path(os.environ['REHEARSAL_SETTINGS_DIR'])
directory.mkdir(mode=0o700)  # Refuse overwriting an existing kit.
password = secrets.token_urlsafe(32)
sql = f"CREATE ROLE {name} LOGIN PASSWORD '{password}';\nCREATE DATABASE {name} OWNER {name};\n"
result = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-X', '-v', 'ON_ERROR_STOP=1'], input=sql, text=True, capture_output=True)
if result.returncode:
    raise SystemExit('Database creation failed. Check whether the requested role/database already exists. No existing database was changed.')
settings = dict(
    DATABASE_URL=f'postgresql://{name}:{password}@127.0.0.2:5432,127.0.0.1:5432/{name}?target_session_attrs=read-write&connect_timeout=1',
    NODE_ENV='test', PORT=os.environ.get('REHEARSAL_FIRST_PORT','18081'), WEB_CONCURRENCY='2',
    REHEARSAL_FIRST_PORT=os.environ.get('REHEARSAL_FIRST_PORT','18081'), DATABASE_SSL='false', COOKIE_SECURE='false', JOBS_PAUSED='true', ARCHIVE_DAILY_UTC_TIME='00:00',
    S3_ENDPOINT='http://127.0.0.1:9090', S3_REGION='us-east-1',
    S3_BUCKET=name.replace('_', '-'), S3_FORCE_PATH_STYLE='true',
    S3_ACCESS_KEY_ID=secrets.token_hex(12), S3_SECRET_ACCESS_KEY=secrets.token_urlsafe(32),
)
(directory / 'destination.env').write_text(''.join(f'export {key}={shlex.quote(value)}\n' for key, value in settings.items()))
(directory / 'settings-summary.json').write_text(json.dumps({'database': name, 'bucket': settings['S3_BUCKET'], 'storage_endpoint': settings['S3_ENDPOINT'], 'unreachable_first_database_host': '127.0.0.2', 'credential_values_omitted': True}, indent=2)+'\n')
print('PREPARE_PASS new PostgreSQL database and mode-600 destination.env created')
