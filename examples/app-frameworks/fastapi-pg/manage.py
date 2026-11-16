import argparse
import os
from pathlib import Path
import signal
import sys
import time
import psycopg
from psycopg_pool import PoolTimeout
import accounts
import database
import storage

ROOT=Path(__file__).resolve().parent

def migrate(through):
    with database.connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(20261104)')
        c.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY)')
        for path in sorted((ROOT/'migrations').glob('*.sql')):
            if int(path.name[:4])>through:continue
            if c.execute('SELECT 1 FROM schema_migrations WHERE version=%s',(path.name,)).fetchone():continue
            c.execute(path.read_text())
            c.execute('INSERT INTO schema_migrations VALUES(%s)',(path.name,))
            print('Applied '+path.name,flush=True)

def seed(account_count):
    if os.environ.get('APP_ENV') not in ('development','staging'):raise ValueError('seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data')
    if account_count < 2:raise ValueError('Usage: seed-test-data [--accounts N], where N is a whole number of at least 2')
    password=os.environ['FIXTURE_PASSWORD']
    accounts.credentials('fixture@example.com',password)
    password_hash=accounts.hasher.hash(password)
    database.open_pool()
    with database.transaction() as c:
        c.execute('SELECT pg_advisory_xact_lock(20261105)')
        for slug,name,ordinal in [('barbara','Barbara','First'),('michael','Michael','Second')]:
            c.execute('INSERT INTO accounts(email,password_hash) VALUES(%s,%s) ON CONFLICT(email) DO NOTHING',(slug+'@example.com',password_hash))
            owner=c.execute('SELECT id FROM accounts WHERE email=%s',(slug+'@example.com',)).fetchone()['id']
            if not c.execute('SELECT 1 FROM records WHERE account_id=%s',(owner,)).fetchone():
                c.execute('INSERT INTO records(account_id,title,description) VALUES(%s,%s,%s)',(owner,name+' invoice',ordinal+' synthetic record'))
            key='fixture/'+slug+'-note.txt'
            if not c.execute('SELECT 1 FROM documents WHERE object_key=%s',(key,)).fetchone():
                values=storage.put_document(owner,slug+'-note.txt',(name+' synthetic document\n').encode(),key)
                c.execute('INSERT INTO documents(account_id,object_key,filename,sha256,byte_count) VALUES(%s,%s,%s,%s,%s)',values)
            c.execute('INSERT INTO report_jobs(account_id,fixture_key) VALUES(%s,%s) ON CONFLICT(fixture_key) DO NOTHING',(owner,slug))
        c.execute("""INSERT INTO accounts(email,password_hash)
            SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com',%s
            FROM generate_series(3,%s::bigint) AS n ON CONFLICT(email) DO NOTHING""",(password_hash,account_count))
        c.execute("""INSERT INTO records(account_id,title,description)
            SELECT a.id,'Test record ' || n::text,'Generated test record'
            FROM generate_series(3,%s::bigint) AS n
            JOIN accounts a ON a.email='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
            WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.account_id=a.id)""",(account_count,))
    print('Synthetic fixture ready',flush=True)

def jobs():
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    while not stopping:
        try:
            with database.transaction() as c:
                job=c.execute('SELECT id,account_id FROM report_jobs WHERE completed_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1').fetchone()
                if job:
                    count=c.execute('SELECT count(*) AS count FROM records WHERE account_id=%s',(job['account_id'],)).fetchone()['count']
                    c.execute('UPDATE report_jobs SET output=%s,completed_at=now() WHERE id=%s',(f'record_count={count}\n',job['id']))
            if not job:time.sleep(.2)
        except (psycopg.Error,PoolTimeout):
            # Queue state is durable. A later iteration locks a still-pending row.
            print('Job database unavailable; unfinished transactions remain queued',file=sys.stderr,flush=True)
            time.sleep(.5)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['migrate','jobs','seed-test-data'])
    parser.add_argument('--through',type=int,default=2,choices=[1,2])
    parser.add_argument('--accounts',type=int,default=2)
    args=parser.parse_args()
    if args.command=='migrate':migrate(args.through)
    else:
        if args.command=='jobs':database.open_pool()
        try:jobs() if args.command=='jobs' else seed(args.accounts)
        finally:database.close_pool()
