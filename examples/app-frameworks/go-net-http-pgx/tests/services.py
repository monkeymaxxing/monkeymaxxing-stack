import concurrent.futures,importlib.util,json,os,subprocess,time,urllib.error,urllib.request
from pathlib import Path
import psycopg
root=Path(os.environ['TEST_LOG_DIR']);root.mkdir(parents=True,exist_ok=True);os.umask(0o077)
source=Path(__file__).resolve().parents[1];evidence=root
seed_env={k:os.environ[k] for k in ('DATABASE_URL','APP_ORIGIN','APP_ENV','FIXTURE_PASSWORD','R2_ENDPOINT','R2_BUCKET','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY')}
(root/'go.env').write_text(''.join(f'{k}={v}\n' for k,v in seed_env.items()))
spec=importlib.util.spec_from_file_location('check_portal',source/'check_portal.py');check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
results=json.loads((evidence/'checks.json').read_text()) if (evidence/'checks.json').exists() else [];owned=json.loads((evidence/'owned-processes.json').read_text()) if (evidence/'owned-processes.json').exists() else []
def event(language,check_name,**details):
 row=dict(language=language,check=check_name,**details);results.append(row)
 (evidence/'checks.json').write_text(json.dumps(results,indent=2));print('PASS',language,check_name,details,flush=True)
def pod(*args):return subprocess.run(['podman',*args],capture_output=True,text=True,check=True).stdout.strip()
def env_for(language):return dict(line.split('=',1) for line in (root/f'{language}.env').read_text().splitlines())
def start(language,role,command,port=None):
 name=f'portal-{language}-{role}';env=env_for(language);env['DATABASE_URL']+='&application_name='+name
 if port:env['PORT']=str(port)
 file=root/f'{name}.env';file.write_text(''.join(f'{k}={v}\n' for k,v in env.items()));file.chmod(0o600)
 identifier=pod('run','-d','--name',name,'--network','host','--env-file',str(file),f'localhost/portal-{language}:integration','customer_portal',command)
 owned.append(dict(name=name,id=identifier,pid=int(pod('inspect',name,'--format','{{.State.Pid}}'))))
 (evidence/'owned-processes.json').write_text(json.dumps(owned,indent=2));return name
def command(language,subcommand,*args,app_env=None):
 return pod('run','--rm','--network','host','--env-file',str(root/f'{language}.env'),*(['--env','APP_ENV='+app_env] if app_env else []),f'localhost/portal-{language}:integration','customer_portal',subcommand,*args)
def wait(predicate,message,seconds=15):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if predicate():return
  time.sleep(.1)
 raise AssertionError(message)
def status(url):
 try:
  with urllib.request.urlopen(url,timeout=5) as response:return response.status
 except urllib.error.HTTPError as error:return error.code
 except urllib.error.URLError:return 0
def scalar(conn,sql,args=()):return conn.execute(sql,args).fetchone()[0]
def until_job(conn,identifier):
 wait(lambda:scalar(conn,'select finished_at is not null from report_jobs where id=%s',(identifier,)),'report did not finish')
for language,ports in [('go',(8003,8004))]:
 if language not in os.environ.get('LANGUAGES','go,rust').split(','):continue
 env=env_for(language);uri=env['DATABASE_URL'];origin=env['APP_ORIGIN']
 conn=psycopg.connect(uri,autocommit=True)
 web_a=start(language,'web-a','web',ports[0]);web_b=start(language,'web-b','web',ports[1])
 a=f'http://127.0.0.1:{ports[0]}';b=f'http://127.0.0.1:{ports[1]}'
 wait(lambda:status(a+'/healthz')==503,'health before migration')
 event(language,'health_before_migrations',http_status=503)
 command(language,'migrate');command(language,'migrate')
 assert scalar(conn,'select count(*) from schema_migrations')==2
 wait(lambda:status(a+'/healthz')==200 and status(b+'/healthz')==200,'healthy after migrations')
 event(language,'migration_idempotence')
 command(language,'seed-test-data',app_env='development')
 fixture={table:conn.execute('select * from '+table+' order by id').fetchall() for table in ('accounts','records','documents','report_jobs')}
 def assert_fixed_rows():
  for table,rows in fixture.items():
   assert conn.execute('select * from '+table+' where id=any(%s) order by id',([row[0] for row in rows],)).fetchall()==rows, table+' fixed rows remain exact'
 command(language,'seed-test-data',app_env='staging');assert_fixed_rows()
 pod('run','--rm','--network','host','--env-file',str(root/f'{language}.env'),'--env','FIXTURE_PASSWORD='+env['FIXTURE_PASSWORD']+'changed',f'localhost/portal-{language}:integration','customer_portal','seed-test-data')
 assert_fixed_rows()
 for table in ('accounts','records','documents','report_jobs'):assert scalar(conn,'select count(*) from '+table)==2
 assert scalar(conn,'select count(*) from report_jobs where finished_at is null')==2
 event(language,'seed_idempotence',accounts=2,records=2,documents=2,jobs=2)
 # Negative seeding check uses a protected env file with the safety marker removed.
 negative=root/f'{language}-no-staging.env';negative.write_text(''.join(f'{k}={v}\n' for k,v in env.items() if k!='APP_ENV'));negative.chmod(0o600)
 result=subprocess.run(['podman','run','--rm','--network','host','--env-file',str(negative),f'localhost/portal-{language}:integration','customer_portal','seed-test-data'],capture_output=True)
 assert result.returncode!=0 and scalar(conn,'select count(*) from accounts')==2
 event(language,'seed_refuses_missing_staging_marker')
 # Preserve all fixture values, including hashes, keys and queued reports.
 for app_env,args in [('production',[]),('staging',['--accounts','1']),('staging',['--accounts','2.5'])]:
  rejected=subprocess.run(['podman','run','--rm','--network','host','--env-file',str(root/f'{language}.env'),'--env','APP_ENV='+app_env,f'localhost/portal-{language}:integration','customer_portal','seed-test-data',*args],capture_output=True,text=True)
  assert rejected.returncode!=0 and ('APP_ENV must be development or staging' if app_env=='production' else '--accounts') in rejected.stderr
 for count in ('1000','1000','2'):
  command(language,'seed-test-data','--accounts',count);assert_fixed_rows()
 for table in ('accounts','records'):
  assert scalar(conn,'select count(*) from '+table)==1000
 for table in ('documents','report_jobs'):assert conn.execute('select * from '+table+' order by id').fetchall()==fixture[table]
 assert scalar(conn,"select count(*) from records r join accounts a on a.id=r.account_id where a.email like 'test-account-%%@example.com' and r.description='Generated test record' and r.title='Test record ' || substring(a.email from '[0-9]+')::bigint::text")==998
 assert scalar(conn,"select count(distinct password_hash) from accounts where email like 'test-account-%%@example.com'")==1
 event(language,'seed_test_data_environments_volume_and_exact_fixture',accounts=1000,records=1000,documents=2,jobs=2)
 worker_a=start(language,'worker-a','jobs');worker_b=start(language,'worker-b','jobs')
 os.environ['FIXTURE_PASSWORD']=env['FIXTURE_PASSWORD']
 run=subprocess.run(['python3',str(source/'check_portal.py'),'--server-a',a,'--server-b',b,'--origin',origin],capture_output=True,text=True)
 (evidence/f'{language}-http-check.log').write_text(run.stdout+run.stderr)
 assert run.returncode==0,'HTTP integration check failed; inspect saved log'
 event(language,'shared_http_check',sessions='two processes',ownership='records/documents/reports',storage='byte and SHA-256 roundtrip')
 client=check.Client(origin);client.request(a,'/login',fields={'email':'barbara@example.com','password':env['FIXTURE_PASSWORD']})
 html_client=urllib.request.Request(a+'/',headers={'Cookie':client.cookie})
 with urllib.request.urlopen(html_client,timeout=5) as response:html=response.read().decode()
 for text in ('Barbara invoice','barbara-note.txt','Request record-count report'):assert text in html
 event(language,'rendered_portal_lists_record_document_and_report_controls')
 account=scalar(conn,"select id from accounts where email='barbara@example.com'")
 job_ids=[scalar(conn,'insert into report_jobs(account_id) values(%s) returning id',(account,)) for _ in range(20)]
 wait(lambda:scalar(conn,'select count(*) from report_jobs where id=any(%s) and finished_at is not null',(job_ids,))==20,'concurrent workers incomplete')
 assert scalar(conn,"select count(*) from report_jobs where id=any(%s) and output=E'record_count=1\\n'",(job_ids,))==20
 event(language,'two_concurrent_workers',completed=20)
 pod('stop','--time','15',worker_a,worker_b)
 # Hold records so the worker claims a job but cannot finish the report count.
 lock=psycopg.connect(uri);lock.execute('lock table records in access exclusive mode')
 identifier=scalar(conn,'insert into report_jobs(account_id) values(%s) returning id',(account,))
 pod('start',worker_a)
 wait(lambda:scalar(conn,"select count(*) from pg_stat_activity where application_name=%s and wait_event_type='Lock' and query like 'select count(*) from records%%'",(worker_a,))==1,'worker did not reach locked report count')
 pod('kill','--signal','KILL',worker_a)
 assert scalar(conn,'select finished_at is null from report_jobs where id=%s',(identifier,))
 lock.rollback();lock.close();pod('start',worker_b);until_job(conn,identifier)
 assert scalar(conn,'select output from report_jobs where id=%s',(identifier,))=='record_count=1\n'
 event(language,'interrupted_worker_transaction_recovered',job_id=identifier,killed_container=worker_a)
 # Health DB query must time out even when its target table is locked.
 lock=psycopg.connect(uri);lock.execute('lock table schema_migrations in access exclusive mode')
 started=time.monotonic();code=status(a+'/healthz');elapsed=time.monotonic()-started
 lock.rollback();lock.close();assert code==503 and 1.5<=elapsed<3.5,(code,elapsed)
 event(language,'health_database_deadline',http_status=code,elapsed_seconds=round(elapsed,3))
 lock=psycopg.connect(uri);lock.execute('lock table records in access exclusive mode')
 started=time.monotonic()
 try:
  client.request(a,'/records',expected=503)
 finally:
  elapsed=time.monotonic()-started;lock.rollback();lock.close()
 assert 10.5<=elapsed<14,(language,elapsed)
 event(language,'request_database_deadline',http_status=503,elapsed_seconds=round(elapsed,3))
 # Graceful shutdown must wait for a real in-flight request, then drain successfully.
 lock=psycopg.connect(uri);lock.execute('lock table records in access exclusive mode')
 pool=concurrent.futures.ThreadPoolExecutor()
 request=pool.submit(client.request,a,'/records')
 wait(lambda:scalar(conn,"select count(*) from pg_stat_activity where application_name=%s and wait_event_type='Lock' and query like 'select id,title,description from records%%'",(web_a,))==1,'web request not waiting on lock')
 stop=pool.submit(pod,'stop','--time','30',web_a)
 time.sleep(.5);assert not stop.done(),'web exited before draining request'
 lock.rollback();lock.close();assert request.result(timeout=5);stop.result(timeout=5);pool.shutdown()
 assert pod('inspect',web_a,'--format','{{.State.ExitCode}}')=='0'
 event(language,'graceful_web_shutdown_drains_inflight_request',exit_code=0)
 pod('stop','--time','15',worker_b,web_b)
 conn.close()
print('CORE_INTEGRATION_PASS',flush=True)

from botocore.config import Config
import boto3
for language in ('go',):
 env=dict(line.split('=',1) for line in (root/f'{language}.env').read_text().splitlines());uri=env['DATABASE_URL']
 conn=psycopg.connect(uri,autocommit=True);worker='portal-'+language+'-worker-a'
 account=scalar(conn,"select id from accounts where email='barbara@example.com'")
 lock=psycopg.connect(uri);lock.execute('lock table records in access exclusive mode')
 identifier=scalar(conn,'insert into report_jobs(account_id) values(%s) returning id',(account,))
 pod('start',worker)
 wait(lambda:scalar(conn,"select count(*) from pg_stat_activity where application_name=%s and wait_event_type='Lock' and query like 'select count(*) from records%%'",(worker,))==1,'worker not holding active report')
 pool=concurrent.futures.ThreadPoolExecutor();stop=pool.submit(pod,'stop','--time','20',worker)
 time.sleep(.5);assert not stop.done(),'worker stopped before finishing transaction'
 lock.rollback();lock.close();stop.result(timeout=5);pool.shutdown()
 assert scalar(conn,'select output from report_jobs where id=%s',(identifier,))=='record_count=1\n'
 assert pod('inspect',worker,'--format','{{.State.ExitCode}}')=='0'
 event(language,'graceful_job_shutdown')
 # Verify the SQL state and object references survive a local logical restore.
 database='portal_'+language+'_restored_v2'
 if not scalar(conn,'select exists(select 1 from pg_database where datname=%s)',(database,)):
  subprocess.run(['runuser','-u','postgres','--','createdb','--owner=portal_'+language,database],check=True)
 dump=root/f'{language}.dump'
 login=psycopg.conninfo.conninfo_to_dict(uri)
 process_env={**os.environ,'PGHOST':'127.0.0.1','PGPORT':'5432','PGUSER':login['user'],'PGPASSWORD':login['password']}
 subprocess.run(['pg_dump','--format=custom','--file',str(dump),'--dbname','portal_'+language],env=process_env,check=True,capture_output=True)
 restored_uri=uri.replace('/portal_'+language+'?','/'+database+'?')
 login=psycopg.conninfo.conninfo_to_dict(uri)
 subprocess.run(['pg_restore','--exit-on-error','--dbname',database],env={**os.environ,'PGHOST':'127.0.0.1','PGPORT':'5432','PGUSER':login['user'],'PGPASSWORD':login['password']},stdin=dump.open('rb'),check=True,capture_output=True)
 restored=psycopg.connect(restored_uri,autocommit=True)
 tables=['accounts','sessions','records','documents','report_jobs','schema_migrations']
 for table in tables:
  order='token_hash' if table=='sessions' else 'version' if table=='schema_migrations' else 'id'
  assert conn.execute('select * from '+table+' order by '+order).fetchall()==restored.execute('select * from '+table+' order by '+order).fetchall(),table
 client=boto3.client('s3',endpoint_url=env['R2_ENDPOINT'],aws_access_key_id=env['R2_ACCESS_KEY_ID'],aws_secret_access_key=env['R2_SECRET_ACCESS_KEY'],region_name='us-east-1',config=Config(request_checksum_calculation='when_required',response_checksum_validation='when_required'))
 recovered_bucket=env['R2_BUCKET']+'-restored-v2';client.create_bucket(Bucket=recovered_bucket)
 import hashlib
 documents=restored.execute('select object_key,sha256 from documents').fetchall()
 for key,sha in documents:
  data=client.get_object(Bucket=env['R2_BUCKET'],Key=key)['Body'].read();assert hashlib.sha256(data).hexdigest()==sha
  client.copy_object(Bucket=recovered_bucket,Key=key,CopySource={'Bucket':env['R2_BUCKET'],'Key':key})
  assert client.get_object(Bucket=recovered_bucket,Key=key)['Body'].read()==data
 newenv={**env,'DATABASE_URL':restored_uri,'R2_BUCKET':recovered_bucket,'PORT':'8012' if language=='go' else '8013'}
 file=root/f'{language}-restored.env';file.write_text(''.join(f'{k}={v}\n' for k,v in newenv.items()))
 name='portal-'+language+'-restored-v2'
 identifier=pod('run','-d','--name',name,'--network','host','--env-file',str(file),f'localhost/portal-{language}:integration','customer_portal','web')
 base='http://127.0.0.1:'+newenv['PORT']
 def healthy():
  try:
   with urllib.request.urlopen(base+'/healthz',timeout=2) as response:return response.status==200
  except Exception:return False
 wait(healthy,'restored app not healthy')
 browser=check.Client(env['APP_ORIGIN']);browser.request(base,'/login',fields={'email':'barbara@example.com','password':env['FIXTURE_PASSWORD']})
 for document in browser.request(base,'/documents'):
  assert browser.request(base,f"/documents/{document['id']}")==b'Barbara synthetic document\n'
 pod('stop','--time','15',name);conn.close();restored.close()
 results.append(dict(language=language,graceful_jobs='pass',logical_restore_tables=tables,recovered_objects=len(documents),restored_login_and_download='pass',restored_container_id=identifier))
 (evidence/'additional-checks.json').write_text(json.dumps(results,indent=2))
 print('PASS',language,'logical restore exact table equality and restored login/document bytes',flush=True)
