#!/usr/bin/env python3
"""Create a fresh local PostgreSQL database and protected synthetic settings."""
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess

os.umask(0o077)
name = os.environ['REHEARSAL_NAME']
# PostgreSQL identifiers allow 63 bytes; the role suffix needs five of them.
if not re.fullmatch(r'[a-z][a-z0-9_]*', name) or len(name) > 58:
    raise ValueError('REHEARSAL_NAME must fit a PostgreSQL identifier with the _role suffix')
if len(name) < 3:
    raise ValueError('REHEARSAL_NAME must also meet the three-character S3 bucket minimum')
port = int(os.environ['REHEARSAL_FIRST_PORT'])
if not 1 <= port < 65535:
    raise ValueError('REHEARSAL_FIRST_PORT must leave a valid port for the second web process')
directory = Path(os.environ['REHEARSAL_SETTINGS_DIR'])
directory.mkdir(mode=0o700)
native = json.loads(Path(os.environ['COOLIFY_NATIVE_INVENTORY_FILE']).read_text())
production = {e['key']: e for e in native['envs'] if not e.get('is_preview')}
def recovered(key):
    value = production[key].get('real_value') or production[key].get('value')
    if not isinstance(value, str) or not value or '{{' in value:
        raise ValueError(f'Missing resolved production value: {key}')
    return value
password = secrets.token_hex(24)
postgres_port = os.environ.get('REHEARSAL_POSTGRES_PORT', '5432')
settings = {
    'DATABASE_URL': f'postgresql://{name}_role:{password}@127.0.0.1:{postgres_port}/{name}?target_session_attrs=read-write&connect_timeout=3',
    'SESSION_SIGNING_KEY': recovered('SESSION_SIGNING_KEY'),
    'PORTAL_NOTICE': recovered('PORTAL_NOTICE'),
    'FILE_STORAGE': 's3',
    'AWS_ENDPOINT_URL_S3': os.environ['REHEARSAL_S3_ENDPOINT'],
    'AWS_REGION': 'us-east-1',
    'AWS_ACCESS_KEY_ID': 'synthetic-rehearsal',
    'AWS_SECRET_ACCESS_KEY': 'synthetic-rehearsal',
    'S3_FORCE_PATH_STYLE': 'true',
    'BUCKET_NAME': name.replace('_', '-'),
    'NODE_ENV': 'production',
    'APP_ENV': 'production',
    'WEB_CONCURRENCY': '1',
    'COOKIE_SECURE': 'false',
    'APP_URL': f'http://127.0.0.1:{port}',
    'SECOND_APP_URL': f'http://127.0.0.1:{port+1}',
    'FIXTURE_PASSWORD': Path(os.environ['FIXTURE_PASSWORD_FILE']).read_text().strip(),
    'EXPORT_DIR': os.environ['EXPORT_DIR'],
    'APP_DIR': str(Path.cwd()),
}
(directory / 'settings.env').write_text(''.join(f'export {key}={shlex.quote(value)}\n' for key, value in settings.items()))
(directory / 'resource-inventory.json').write_text(json.dumps({'database': name, 'role': name+'_role', 'bucket': settings['BUCKET_NAME'], 'web_ports': [port, port+1]}, indent=2)+'\n')
sql = f"CREATE ROLE {name}_role LOGIN PASSWORD '{password}';\nCREATE DATABASE {name} OWNER {name}_role;\n"
result = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', postgres_port, '-v', 'ON_ERROR_STOP=1'], input=sql.encode(), capture_output=True)
if result.returncode:
    raise RuntimeError('Database preparation failed; keep the saved resource inventory and inspect local PostgreSQL state')
print('Created a fresh rehearsal database and protected settings; the bucket still needs creation')
