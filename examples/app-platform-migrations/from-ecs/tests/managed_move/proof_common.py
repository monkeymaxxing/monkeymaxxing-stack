"""Protected local settings and PostgreSQL JSON reads for migration evidence."""
import json
import os
from pathlib import Path
import subprocess


def read_settings(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError('Settings must have mode 600')
    return json.loads(path.read_text())


def write_private(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(value)


def postgres(settings, statements, diagnostic_dir):
    # Passwords belong in PG* environment variables or PGPASSFILE, never argv.
    if any(not key.startswith('PG') for key in settings):
        raise ValueError('postgres_env accepts only PostgreSQL PG* variables')
    env = {**os.environ, **settings, 'PGTZ': 'UTC', 'PGDATESTYLE': 'ISO, YMD'}
    result = subprocess.run(
        ['psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
        input=statements, env=env, capture_output=True, text=True)
    if result.returncode:
        diagnostic = Path(diagnostic_dir) / 'proof-psql-error.log'
        write_private(diagnostic, result.stderr)
        raise RuntimeError('PostgreSQL proof failed; inspect protected proof-psql-error.log')
    return result.stdout.strip()


def postgres_json(settings, statements, diagnostic_dir):
    return json.loads(postgres(settings, statements, diagnostic_dir))


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"
