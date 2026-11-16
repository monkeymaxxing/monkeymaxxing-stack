#!/usr/bin/env python3
"""Real-service checks. Use only an empty, disposable PostgreSQL 17 database/bucket.
Requires psycopg 3 in the test runner. Retains synthetic rows for restore checks.
"""
import concurrent.futures
import contextlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
import psycopg
from check_portal import Client, main as check_http

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ['bin/portal']
PROCESSES = []
LOGS = []
ENV = os.environ.copy()
A, B = [f'http://127.0.0.1:{port}' for port in ENV.get('TEST_WEB_PORTS', '8071,8072').split(',')]
ORIGIN = ENV['APP_ORIGIN']

def run(*args, env=None):
    subprocess.run(COMMAND + list(args), cwd=ROOT, env=env or ENV, check=True)

def start(command, port=None):
    env = ENV.copy()
    if port:
        env['PORT'] = port.rsplit(':', 1)[1]
    log = open(Path(ENV.get('TEST_LOG_DIR', '/tmp')) / f'portal-{command}-{len(PROCESSES)}.log', 'w+')
    LOGS.append(log)
    process = subprocess.Popen(COMMAND + [command], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    PROCESSES.append(process)
    return process

def wait(predicate, label, seconds=25):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError(label)

def healthy(base):
    try:
        with urllib.request.urlopen(base + '/healthz', timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

def db():
    return psycopg.connect(ENV['DATABASE_URL'], autocommit=True)

def pending_count(connection):
    return connection.execute('SELECT count(*) FROM report_jobs WHERE completed_at IS NULL').fetchone()[0]

def blocked_by(connection):
    # Activity snapshots are cached within a transaction. Refresh before polling.
    connection.execute('SELECT pg_stat_clear_snapshot()')
    return connection.execute('SELECT count(*) FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid))', (connection.info.backend_pid,)).fetchone()[0] > 0

def fixed_rows(fixed_ids):
    with db() as c:
        return {table: c.execute('SELECT * FROM '+table+' WHERE id = ANY(%s) ORDER BY id', (ids,)).fetchall()
                for table, ids in fixed_ids.items()}

def check():
    with db() as c:
        assert c.execute("SELECT to_regclass('auth_user')").fetchone()[0] is None, 'database must be empty'
    # Run the first migration alone and then the additive release.
    subprocess.run([sys.executable,'manage.py','migrate','portal','0001','--noinput'], cwd=ROOT, env=ENV, check=True)
    with db() as c:
        c.execute("INSERT INTO auth_user(password,last_login,is_superuser,username,first_name,last_name,email,is_staff,is_active,date_joined) VALUES ('!unusable',now(),false,'migration@example.com','','','migration@example.com',false,true,now())")
        c.execute("INSERT INTO records(account_id,title) SELECT id,'Old release record' FROM auth_user WHERE email='migration@example.com'")
    migrations = [subprocess.Popen(COMMAND + ['migrate'], cwd=ROOT, env=ENV) for _ in range(2)]
    assert all(process.wait(timeout=30) == 0 for process in migrations)
    run('migrate')
    with db() as c:
        assert c.execute("SELECT count(*) FROM django_migrations WHERE app='portal'").fetchone() == (2,)
        assert c.execute("SELECT description FROM records WHERE title='Old release record'").fetchone() == ('',)
        c.execute("INSERT INTO records(account_id,title) SELECT id,'Old release insert' FROM auth_user WHERE email='migration@example.com'")
    for app_env in ('production', None):
        rejected = ENV.copy()
        rejected.pop('APP_ENV', None)
        if app_env is not None: rejected['APP_ENV'] = app_env
        result = subprocess.run(COMMAND+['seed-test-data'],cwd=ROOT,env=rejected,capture_output=True,text=True)
        assert result.returncode != 0 and 'APP_ENV must be development or staging' in result.stderr
    for count in ('1', '2.5'):
        result = subprocess.run(COMMAND+['seed-test-data','--accounts',count],cwd=ROOT,env=ENV,capture_output=True,text=True)
        assert result.returncode != 0 and '--accounts' in result.stderr
    run('seed-test-data', env=ENV | {'APP_ENV':'development'})
    with db() as c:
        account_ids = [row[0] for row in c.execute("SELECT id FROM auth_user WHERE email IN ('barbara@example.com','michael@example.com')").fetchall()]
        fixed_ids = {'auth_user': account_ids}
        for table in ('records','documents','report_jobs'):
            fixed_ids[table] = [row[0] for row in c.execute('SELECT id FROM '+table+' WHERE account_id = ANY(%s)', (account_ids,)).fetchall()]
    fixture_rows = fixed_rows(fixed_ids)
    run('seed-test-data', env=ENV | {'APP_ENV':'staging'})
    assert fixed_rows(fixed_ids) == fixture_rows, 'complete fixed rows survive the second run'
    run('seed-test-data', env=ENV | {'FIXTURE_PASSWORD': ENV['FIXTURE_PASSWORD']+'changed'})
    assert fixed_rows(fixed_ids) == fixture_rows, 'complete fixed rows and password hashes survive a different fixture password'
    with db() as c:
        assert c.execute('SELECT count(*) FROM auth_user').fetchone() == (3,)
        assert c.execute('SELECT count(*) FROM documents').fetchone() == (2,)
        assert c.execute('SELECT count(*) FROM report_jobs').fetchone() == (2,)
        rows=c.execute('SELECT a.email,r.title,r.description,d.filename,d.sha256 FROM auth_user a JOIN records r ON r.account_id=a.id JOIN documents d ON d.account_id=a.id ORDER BY a.email').fetchall()
        import hashlib
        for row,slug,name,ordinal in zip(rows,('barbara','michael'),('Barbara','Michael'),('First','Second')):
            assert row == (slug+'@example.com', name+' invoice',ordinal+' synthetic record',slug+'-note.txt',hashlib.sha256((name+' synthetic document\n').encode()).hexdigest())
    run('seed-test-data','--accounts','1000')
    assert fixed_rows(fixed_ids) == fixture_rows, 'complete fixed rows survive volume runs'
    run('seed-test-data','--accounts','1000')
    assert fixed_rows(fixed_ids) == fixture_rows, 'complete fixed rows survive volume runs'
    run('seed-test-data','--accounts','2')
    assert fixed_rows(fixed_ids) == fixture_rows, 'complete fixed rows survive volume runs'
    with db() as c:
        assert c.execute('SELECT count(*) FROM auth_user').fetchone() == (1001,)
        assert c.execute('SELECT count(*) FROM records').fetchone() == (1002,)
        assert c.execute("SELECT count(*) FROM records r JOIN auth_user a ON a.id=r.account_id WHERE a.email LIKE 'test-account-%@example.com' AND r.description='Generated test record' AND r.title='Test record ' || substring(a.email from '[0-9]+')::bigint::text").fetchone() == (998,)
        assert c.execute("SELECT count(DISTINCT password) FROM auth_user WHERE email LIKE 'test-account-%@example.com'").fetchone() == (1,)
        assert c.execute('SELECT count(*) FROM documents').fetchone() == (2,)
        assert c.execute('SELECT count(*) FROM report_jobs').fetchone() == (2,)
    print('PASS migrations, additive compatibility, guarded idempotent exact fixture', flush=True)
    web_a=start('web',A); web_b=start('web',B)
    wait(lambda: healthy(A) and healthy(B),'web readiness')
    with db() as c:
        owner=c.execute("SELECT id FROM auth_user WHERE email='barbara@example.com'").fetchone()[0]
        c.execute('INSERT INTO report_jobs(account_id) SELECT %s FROM generate_series(1,20)',(owner,))
    worker_a=start('jobs'); worker_b=start('jobs')
    with db() as c:
        wait(lambda: pending_count(c)==0, 'two-worker completion')
        assert c.execute("SELECT count(*) FROM report_jobs WHERE output='record_count=1'||chr(10)").fetchone() == (22,)
    original=sys.argv
    sys.argv=['check_portal.py','--server-a',A,'--server-b',B,'--origin',ORIGIN]
    try: check_http()
    finally: sys.argv=original
    # Stop both workers, lock records, then kill a worker inside a job transaction.
    for worker in (worker_a,worker_b):
        worker.send_signal(signal.SIGTERM);assert worker.wait(timeout=15)==0
    with db() as c:
        c.execute('INSERT INTO report_jobs(account_id) VALUES (%s)',(owner,))
        c.execute('BEGIN');c.execute('LOCK TABLE records IN ACCESS EXCLUSIVE MODE')
        locked_worker=start('jobs')
        wait(lambda: blocked_by(c),'worker did not hold job transaction')
        locked_worker.kill();locked_worker.wait(timeout=10)
        c.execute('COMMIT')
        recovery_worker=start('jobs')
        wait(lambda: pending_count(c)==0,'interrupted job not recovered')
        recovery_worker.send_signal(signal.SIGTERM);assert recovery_worker.wait(timeout=15)==0
        c.execute('INSERT INTO report_jobs(account_id) VALUES (%s)',(owner,))
        c.execute('BEGIN');c.execute('LOCK TABLE records IN ACCESS EXCLUSIVE MODE')
        draining_worker=start('jobs')
        wait(lambda: blocked_by(c),'graceful job did not start')
        draining_worker.send_signal(signal.SIGTERM);time.sleep(.2)
        assert draining_worker.poll() is None
        c.execute('COMMIT');assert draining_worker.wait(timeout=15)==0
        assert pending_count(c)==0
    print('PASS two workers, interrupted transaction recovery, graceful in-flight job',flush=True)
    # Terminate Puma while a real HTTP write is in flight, then release its lock.
    client=Client(ORIGIN);client.request(A,'/login',fields={'email':'barbara@example.com','password':ENV['FIXTURE_PASSWORD']})
    with db() as c, concurrent.futures.ThreadPoolExecutor() as pool:
        c.execute('BEGIN');c.execute('LOCK TABLE records IN ACCESS EXCLUSIVE MODE')
        future=pool.submit(client.request,A,'/records',{'title':'shutdown write'},expected=201)
        wait(lambda:blocked_by(c),'web write did not block')
        web_a.send_signal(signal.SIGTERM);time.sleep(.2);c.execute('COMMIT')
        assert future.result(timeout=15)['id']
        assert web_a.wait(timeout=30)==0
    print('PASS graceful web shutdown retains in-flight write',flush=True)
    # Optional owned primary-promotion command. Never run against a shared service.
    if ENV.get('TEST_PROMOTE_ARGV'):
        persistent_worker=start('jobs')
        before=[p.pid for p in PROCESSES if p.poll() is None]
        started=time.monotonic()
        subprocess.run(json.loads(ENV['TEST_PROMOTE_ARGV']),check=True)
        wait(lambda:healthy(B),'recovery after promotion',seconds=60)
        client.request(B,'/records',fields={'title':'after promotion'},expected=201)
        client.request(B,'/documents')
        client.request(B,'/reports',body=b'',expected=201)
        with db() as c:
            wait(lambda:pending_count(c)==0,'job after promotion')
        assert all(p.poll() is None for p in PROCESSES if p.pid in before)
        print('PASS primary change, existing session/fresh write, no web restart; recovery_seconds='+str(round(time.monotonic()-started,3)),flush=True)
    print('SERVICE_CHECKS_PASSED',flush=True)

if __name__=='__main__':
    os.chdir(ROOT)
    try:
        check()
    finally:
        for p in reversed(PROCESSES):
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:p.wait(timeout=30)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        for log in LOGS:log.close()
