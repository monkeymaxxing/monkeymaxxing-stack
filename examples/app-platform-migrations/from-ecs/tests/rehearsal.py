#!/usr/bin/env python3
"""Exercise transfer tools against two disposable PostgreSQL databases and buckets."""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlparse, unquote
from urllib.request import urlopen

app_dir = Path(__file__).resolve().parents[1]
os.umask(0o077)
export_dir = Path(os.environ['EXPORT_DIR']).resolve()
source_settings = json.loads(Path(os.environ['SOURCE_SETTINGS_FILE']).read_text())
destination_settings = json.loads(Path(os.environ['DESTINATION_SETTINGS_FILE']).read_text())
password = Path(os.environ['FIXTURE_PASSWORD_FILE']).read_text().strip()
source = {**os.environ, **source_settings, 'APP_DIR': str(app_dir), 'FIXTURE_PASSWORD': password}
destination = {**os.environ, **destination_settings, 'APP_DIR': str(app_dir), 'FIXTURE_PASSWORD': password}
if source.get('QUEUE_BACKEND') != 'sqs' or destination.get('QUEUE_BACKEND') != 'postgres':
    raise SystemExit('Use source QUEUE_BACKEND=sqs and destination QUEUE_BACKEND=postgres')
if source['DATABASE_URL'] == destination['DATABASE_URL'] or source['BUCKET_NAME'] == destination['BUCKET_NAME']:
    raise SystemExit('Source and destination must use separate disposable databases and buckets')

def run(arguments, env):
    subprocess.run(arguments, cwd=app_dir, env=env, check=True)

def node(entry, env, *arguments):
    run(['node', entry, *arguments], env)

def start_web(env, port):
    child = subprocess.Popen(['node', 'server.mjs'], cwd=app_dir,
                             env={**env, 'PORT': str(port), 'WEB_CONCURRENCY': '1', 'COOKIE_SECURE': 'false'})
    processes.append(child)
    for _ in range(100):
        if child.poll() is not None:
            raise RuntimeError('Web process exited before health check')
        try:
            with urlopen(f'http://127.0.0.1:{port}/healthz', timeout=1) as response:
                if response.status == 200:
                    return child
        except OSError:
            pass
        time.sleep(0.1)
    raise RuntimeError('Web health check did not become ready')

def stop(child):
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=15)

processes = []
try:
    node('database.mjs', source)
    web = start_web(source, 18001)
    node('seed-test-data.mjs', {**source, 'APP_ENV': 'staging', 'APP_URL': 'http://127.0.0.1:18001'})
    node('scripts/control.mjs', source, 'freeze')
    stop(web)
    inventory_file = export_dir.with_suffix('.source-inventory.json')
    inventory_file.write_text(json.dumps({
        'fixture_kind': 'standalone-synthetic', 'source_execution_stopped': True,
        'schedule_state': 'DISABLED', 'queue_backend': 'sqs',
        'limits': 'No AWS deployment or SQS worker in this tool rehearsal.'}))
    node('scripts/export-source.mjs', {**source, 'SOURCE_INVENTORY_FILE': str(inventory_file)})
    node('scripts/verify-export.mjs', destination)
    url = urlparse(destination['DATABASE_URL'])
    restore_env = {**destination, 'PGHOST': url.hostname, 'PGPORT': str(url.port or 5432),
                   'PGUSER': unquote(url.username or ''), 'PGPASSWORD': unquote(url.password or ''),
                   'PGDATABASE': unquote(url.path[1:])}
    run(['pg_restore', '--no-owner', '--no-acl', '--exit-on-error', '--single-transaction',
         '--dbname=' + restore_env['PGDATABASE'], str(export_dir / 'database.dump')], restore_env)
    node('scripts/compare-database.mjs', destination)
    node('scripts/import-objects.mjs', destination)
    start_web(destination, 18001)
    start_web(destination, 18002)
    run(['node', '--test', 'tests/portal.test.mjs'], {
        **destination, 'APP_URL': 'http://127.0.0.1:18001', 'SECOND_APP_URL': 'http://127.0.0.1:18002'})
    print('STANDALONE_REHEARSAL_PASS: source stopped, exact restore, accounts, private bytes, jobs and schedule')
finally:
    for process in processes:
        stop(process)
