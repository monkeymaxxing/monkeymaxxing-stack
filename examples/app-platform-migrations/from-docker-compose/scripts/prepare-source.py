#!/usr/bin/env python3
"""Create a disposable synthetic Compose source. Run from the example directory."""
import os
import secrets
import subprocess
import time
from pathlib import Path

os.umask(0o077)
secret_dir = Path(os.environ['SOURCE_SECRETS_DIR']).resolve()
uploads_dir = Path(os.environ['SOURCE_UPLOADS_DIR']).resolve()
secret_dir.mkdir(mode=0o700)  # An existing directory must be inspected, never overwritten.
uploads_dir.mkdir(mode=0o700)
os.chown(uploads_dir, 1000, 1000)
admin_password = secrets.token_hex(24)
app_password = secrets.token_hex(24)
fixture_password = secrets.token_hex(18)
for name, value in {
    'postgres_password': admin_password,
    'database_url': f'postgresql://portal:{app_password}@postgres:5432/portal?target_session_attrs=read-write&connect_timeout=3',
    'fixture_password': fixture_password,
}.items():
    path = secret_dir / name
    path.write_text(value + '\n')
    path.chmod(0o600)
    if name != 'postgres_password':
        os.chown(path, 1000, 1000)  # Docker file-backed secrets retain host ownership.
compose = ['docker', 'compose', '-f', 'source/compose.yaml', '-f', 'source/compose.production.yaml']
subprocess.run(compose + ['build', 'web'], check=True, stdin=subprocess.DEVNULL)
subprocess.run(compose + ['up', '-d', 'postgres'], check=True, stdin=subprocess.DEVNULL)
# The image starts a temporary socket-only database before the final TCP server.
for attempt in range(90):
    result = subprocess.run(compose + ['exec', '-T', 'postgres', 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', '-d', 'portal'],
                            capture_output=True, stdin=subprocess.DEVNULL)
    if result.returncode == 0:
        break
    time.sleep(1)
else:
    raise SystemExit('Source PostgreSQL TCP server did not become ready')
result = subprocess.run(compose + ['exec', '-T', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'portal'],
                        input=f"CREATE ROLE portal LOGIN PASSWORD '{app_password}';\nALTER DATABASE portal OWNER TO portal;\nCREATE ROLE portal_reader NOLOGIN;\n",
                        text=True, capture_output=True)
if result.returncode:
    raise SystemExit('Source role preparation failed; inspect the protected source database')
subprocess.run(compose + ['run', '--rm', '--no-deps', 'web', 'database.mjs'], check=True, stdin=subprocess.DEVNULL)
subprocess.run(compose + ['up', '-d', 'web', 'worker'], check=True, stdin=subprocess.DEVNULL)
for attempt in range(60):
    result = subprocess.run(['curl', '-fsS', 'http://127.0.0.1:18001/healthz'], capture_output=True, stdin=subprocess.DEVNULL)
    if result.returncode == 0:
        break
    time.sleep(1)
else:
    raise SystemExit('Source web process did not become ready')
subprocess.run(compose + ['run', '--rm', '--no-deps', '-e', 'APP_ENV=development', '-e', 'APP_URL=http://web:8080',
                         '-e', 'FIXTURE_PASSWORD_FILE=/run/secrets/fixture_password',
                         '-v', str(secret_dir / 'fixture_password') + ':/run/secrets/fixture_password:ro',
                         'web', 'seed-test-data.mjs'], check=True, stdin=subprocess.DEVNULL)
print('SOURCE_READY: two synthetic accounts, owned records, private files and pending reports')
