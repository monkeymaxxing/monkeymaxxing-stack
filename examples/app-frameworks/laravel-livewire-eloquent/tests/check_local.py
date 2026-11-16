#!/usr/bin/env python3
"""Disposable Linux integration proof. Requires Podman, PHP 8.4+, dev Composer deps and boto3."""
import base64,concurrent.futures,json,os,re,secrets,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error
from pathlib import Path
import boto3
from check_http import Browser

POSTGRES='docker.io/library/postgres:17.11-bookworm@sha256:839fbb5a4942a7758dd93e18b42ea5649807491a0545b5eeeb8f0b8bb11857a5'
STORAGE='docker.io/adobe/s3mock@sha256:ab01a6946750f451ca215a47e91030695b260e4003b8a5a6201d25029b8fca92'
IMAGE=sys.argv[1]
ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(tempfile.mkdtemp(prefix='laravel-proof-'))
os.chmod(EVIDENCE,0o700)
PREFIX='laravel-check-'+secrets.token_hex(4)
containers=[]
results={}
def command(args,**kwargs):
 return subprocess.run(args,check=True,capture_output=True,**kwargs).stdout

def podman(*args,**kwargs):return command(['podman',*args],**kwargs)
def free_port():
 with socket.socket() as listener:
  listener.bind(('127.0.0.1',0));return listener.getsockname()[1]
def env_file(name,values):
 p=EVIDENCE/name;p.write_text(''.join(f'{k}={v}\n' for k,v in values.items()));p.chmod(0o600);return p

def start(name,image,*args,environment=None):
 name=PREFIX+'-'+name;containers.append(name)
 options=['run','-d','--name',name,'--network','host']
 if environment:options+=['--env-file',str(environment)]
 podman(*options,image,*args);return name

def app_command(*args,environment=None,expected=0,unset_app_env=False):
 response=subprocess.run(['podman','run','--rm','--network','host','--env-file',str(environment or app_env),*(['--unsetenv','APP_ENV'] if unset_app_env else []),IMAGE,'php','artisan',*args,'--no-ansi'],capture_output=True)
 assert response.returncode==expected,(args,response.returncode,response.stdout.decode()[-300:],response.stderr.decode()[-300:])
 return response.stdout.decode()
def sql(query):return podman('exec','-i',database,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','portal','-p',str(db_port),'portal',input=query.encode()).decode().strip()

def wait_for(check,seconds=30):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if check():return
  time.sleep(.1)
 raise AssertionError('Condition did not become true before the deadline')

def health(url):
 try:
  with urllib.request.urlopen(url+'/healthz',timeout=4) as response:return response.status
 except urllib.error.HTTPError as error:return error.code
 except (OSError,TimeoutError):return 0

def pending():return int(sql('select count(*) from report_jobs where completed_at is null'))
def inspect(name):return json.loads(podman('inspect',name))[0]
def lock_records(table="records"):
 process=subprocess.Popen(['podman','exec','-i',database,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','portal','-p',str(db_port),'portal'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 process.stdin.write(f"BEGIN; LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE;\n\\echo LOCKED\n");process.stdin.flush()
 assert process.stdout.readline().strip()=='LOCKED';return process

def unlock(process):
 process.stdin.write('ROLLBACK;\n');process.stdin.close();assert process.wait(timeout=10)==0

def blocked():return int(sql("select count(*) from pg_stat_activity where application_name='laravel_portal' and wait_event_type='Lock'"))>0

def job(name):return start(name,IMAGE,'php','artisan','portal:jobs',environment=app_env)

def main():
 global database,app_env,db_port
 password=secrets.token_urlsafe(24);fixture=secrets.token_urlsafe(18)
 db_port=free_port();port_a=free_port();port_b=free_port()
 url_a=f'http://127.0.0.1:{port_a}';url_b=f'http://127.0.0.1:{port_b}'
 db_env=env_file('postgres.env',{'POSTGRES_USER':'portal','POSTGRES_PASSWORD':password,'POSTGRES_DB':'portal'})
 database=start('database',POSTGRES,'postgres','-p',str(db_port),'-c','listen_addresses=127.0.0.1',environment=db_env)
 def ready_database():
  return subprocess.run(['podman','exec',database,'pg_isready','-U','portal','-p',str(db_port)],capture_output=True).returncode==0
 wait_for(ready_database,60)
 storage=start('storage',STORAGE,'--server.address=127.0.0.1')
 client=boto3.client('s3',endpoint_url='http://127.0.0.1:9090',aws_access_key_id='synthetic-access',aws_secret_access_key='synthetic-secret',region_name='auto')
 def ready_storage():
  try:client.list_buckets();return True
  except Exception:return False
 wait_for(ready_storage,60);client.create_bucket(Bucket='laravel-portal-check')
 environment={'DATABASE_URL':f'postgresql://portal:{password}@127.0.0.2:{db_port},127.0.0.1:{db_port}/portal?target_session_attrs=read-write&connect_timeout=3',
  'APP_ENV':'staging','APP_KEY':'base64:'+base64.b64encode(secrets.token_bytes(32)).decode(),'APP_URL':url_a,'SESSION_SECURE_COOKIE':'false',
  'R2_ENDPOINT':'http://127.0.0.1:9090','R2_BUCKET':'laravel-portal-check','R2_ACCESS_KEY_ID':'synthetic-access','R2_SECRET_ACCESS_KEY':'synthetic-secret','FIXTURE_PASSWORD':fixture,'WEB_CONCURRENCY':'2','PORT':str(port_a)}
 app_env=env_file('app.env',environment)
 web_a=start('web-a',IMAGE,environment=app_env)
 environment_b=environment|{'PORT':str(port_b)}
 web_b=start('web-b',IMAGE,environment=env_file('app-b.env',environment_b))
 wait_for(lambda:health(url_a)==503)
 assert health(url_b)==503
 results['unmigrated_health']='PASS'
 app_command('migrate','--force','--path=database/migrations/0001_01_01_000001_create_portal.php')
 prior=Browser()
 page=prior.request('GET','/login',base=url_a)
 prior.token=re.search(rb'name="_token" value="([^"]+)"',page).group(1).decode()
 prior.request('POST','/register',{'email':'old-release@example.com','password':fixture},base=url_a,expected=201)
 page=prior.request('GET','/',base=url_a)
 prior.token=re.search(rb'name="_token" value="([^"]+)"',page).group(1).decode()
 prior.request('POST','/records',{'title':'Preserved title'},base=url_a,expected=201)
 assert json.loads(prior.request('GET','/portal',base=url_a))['records'][0]['title']=='Preserved title' 
 old_id=inspect(web_a)['Id']
 # This image's title-only API path works before and after the additive migration.
 app_command('migrate','--force');app_command('migrate','--force')
 assert sql("select description='' from records where title='Preserved title'")=='t'
 assert inspect(web_a)['Id']==old_id
 assert json.loads(prior.request('GET','/portal',base=url_a))['records'][0]['description']==''
 prior.request('POST','/records',{'title':'Title after migration'},base=url_a,expected=201)
 wait_for(lambda:health(url_a)==200 and health(url_b)==200)
 results['migrations']='PASS ordered, additive empty default, repeatable; web containers unchanged'
 # Remove only the extra synthetic migration row, before fixtures and counts are checked.
 sql("delete from sessions where user_id in (select id from users where email='old-release@example.com'); delete from users where email='old-release@example.com'")
 refusal='seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data'
 assert refusal in app_command('portal:seed-test-data',environment=env_file('production.env',environment|{'APP_ENV':'production'}),expected=1)
 assert refusal in app_command('portal:seed-test-data',environment=env_file('missing-app-env.env',{k:v for k,v in environment.items() if k!='APP_ENV'}),unset_app_env=True,expected=1)
 assert refusal in app_command('portal:seed-test-data','--env=development',environment=env_file('production-override.env',environment|{'APP_ENV':'production'}),expected=1)
 assert refusal in app_command('portal:seed-test-data','--env=development',environment=env_file('missing-override.env',{k:v for k,v in environment.items() if k!='APP_ENV'}),unset_app_env=True,expected=1)
 for count in ('1','2.5'):
  assert '--accounts' in app_command('portal:seed-test-data','--accounts',count,expected=1)
 app_command('portal:seed-test-data',environment=env_file('development.env',environment|{'APP_ENV':'development'}))
 fixed_rows={table:sql('select to_jsonb(t) from '+table+' t order by id') for table in ('users','records','documents','report_jobs')}
 def assert_fixed_rows():
  for table,rows in fixed_rows.items():
   ids=','.join(str(json.loads(row)['id']) for row in rows.splitlines())
   assert sql('select to_jsonb(t) from '+table+' t where id in ('+ids+') order by id')==rows,table+' fixed rows remain exact'
 app_command('portal:seed-test-data')
 assert_fixed_rows()
 app_command('portal:seed-test-data',environment=env_file('changed-password.env',environment|{'FIXTURE_PASSWORD':fixture+'changed'}))
 assert_fixed_rows()
 assert sql('select (select count(*) from users)=2 and (select count(*) from records)=2 and (select count(*) from documents)=2 and (select count(*) from report_jobs)=2')=='t'
 fixture_rows=[json.loads(row) for row in sql("select row_to_json(t) from (select u.email,r.title,r.description,d.file_name,d.sha256 from users u join records r on r.user_id=u.id join documents d on d.user_id=u.id order by u.email) t").splitlines()]
 import hashlib
 assert fixture_rows==[dict(email=name.lower()+'@example.com',title=name+' invoice',description=ordinal+' synthetic record',file_name=name.lower()+'-note.txt',sha256=hashlib.sha256((name+' synthetic document\n').encode()).hexdigest()) for name,ordinal in [('Barbara','First'),('Michael','Second')]]
 for count in ('1000','1000','2'):
  app_command('portal:seed-test-data','--accounts',count);assert_fixed_rows()
 assert sql('select (select count(*) from users)=1000 and (select count(*) from records)=1000 and (select count(*) from documents)=2 and (select count(*) from report_jobs)=2')=='t'
 assert sql("select count(*) from records r join users u on u.id=r.user_id where u.email like 'test-account-%@example.com' and r.description='Generated test record' and r.title='Test record ' || substring(u.email from '[0-9]+')::bigint::text")=='998'
 assert sql("select count(distinct password) from users where email like 'test-account-%@example.com'")=='1'
 results['seed']='PASS exact fixture and hashes, both environments, production/unset refusal, invalid counts, 1000 accounts twice, smaller total preserves rows'
 # Test native Livewire actions against this real PostgreSQL database.
 native_env=os.environ|environment
 completed=subprocess.run(['php','vendor/bin/phpunit','--no-progress'],cwd=ROOT,env=native_env,capture_output=True)
 (EVIDENCE/'phpunit.log').write_bytes(completed.stdout+completed.stderr)
 assert completed.returncode==0,completed.stdout.decode()[-800:]+completed.stderr.decode()[-800:]
 results['phpunit']='PASS connector URL, no replay, Livewire CRUD and ownership'
 http_env=os.environ|{'PORTAL_URL_A':url_a,'PORTAL_URL_B':url_b,'FIXTURE_PASSWORD':fixture}
 completed=subprocess.run([sys.executable,'tests/check_http.py'],cwd=ROOT,env=http_env,capture_output=True)
 (EVIDENCE/'http.log').write_bytes(completed.stdout+completed.stderr)
 assert completed.returncode==0,completed.stdout.decode()[-800:]+completed.stderr.decode()[-800:]
 results['http']='PASS registration, login, sessions across web containers, logout revocation, CSRF, ownership, CRUD, S3 exact bytes'
 # Finish fixture reports before adding concurrency work, so expected output stays exact.
 worker_a=job('worker-a');worker_b=job('worker-b');wait_for(lambda:pending()==0)
 assert sql("select bool_and(output=E'record_count=1\\n') from report_jobs where fixture_key is not null")=='t'
 sql("insert into report_jobs(user_id,created_at,updated_at) select users.id,now(),now() from users cross join generate_series(1,10) where email in ('barbara@example.com','michael@example.com')")
 wait_for(lambda:pending()==0)
 assert sql("select count(*)=22 and bool_and(output=E'record_count=1\\n') from report_jobs")=='t'
 for worker in [worker_a,worker_b]:podman('stop','--time','20',worker)
 results['concurrent_jobs']='PASS two real workers, 22 outputs, owner-only counts'
 # A blocked count proves the killed worker held a real job transaction.
 sql("insert into report_jobs(user_id,created_at,updated_at) select id,now(),now() from users where email='barbara@example.com'")
 holder=lock_records();killed=job('killed-worker');wait_for(blocked)
 podman('kill','--signal','KILL',killed);wait_for(lambda:not inspect(killed)['State']['Running'])
 assert pending()==1;unlock(holder)
 app_command('portal:jobs','--once');assert pending()==0
 results['interrupted_job']='PASS SIGKILL rolls back reservation, next worker completes'
 # Graceful job stop must finish the active transaction.
 sql("insert into report_jobs(user_id,created_at,updated_at) select id,now(),now() from users where email='barbara@example.com'")
 holder=lock_records();graceful=job('graceful-worker');wait_for(blocked)
 podman('kill','--signal','TERM',graceful);unlock(holder)
 wait_for(lambda:not inspect(graceful)['State']['Running'])
 assert inspect(graceful)['State']['ExitCode']==0 and pending()==0
 results['job_shutdown']='PASS SIGTERM commits active report then exits zero'
 # Keep a signed-in session and all app processes across database restart.
 import check_http
 check_http.PASSWORD=fixture
 browser=Browser();browser.csrf=lambda:None
 page=browser.request('GET','/login',base=url_a)
 browser.token=re.search(rb'name="_token" value="([^"]+)"',page).group(1).decode()
 browser.request('POST','/login',{'email':'barbara@example.com','password':fixture},base=url_a)
 page=browser.request('GET','/',base=url_b);browser.token=re.search(rb'name="_token" value="([^"]+)"',page).group(1).decode()
 ids={name:inspect(name)['Id'] for name in [web_a,web_b]}
 reconnect_worker=job('reconnect-worker');ids[reconnect_worker]=inspect(reconnect_worker)['Id']
 podman('stop','--time','15',database)
 failed_status=health(url_a);assert failed_status==503
 restarted=time.monotonic();podman('start',database)
 wait_for(lambda:health(url_b)==200,60)
 browser.request('POST','/records',{'title':'After database restart'},base=url_b,expected=201)
 resumed_report=json.loads(browser.request('POST','/reports',{},base=url_b,expected=202))
 wait_for(lambda:sql(f"select completed_at is not null from report_jobs where id={resumed_report['id']}")=='t')
 assert sql(f"select output=E'record_count=2\\n' from report_jobs where id={resumed_report['id']}")=='t'
 assert inspect(reconnect_worker)['State']['Running']
 assert all(inspect(name)['Id']==identity for name,identity in ids.items())
 results['database_restart']={'result':'PASS unchanged multi-host URL and web/job containers; session and fresh write survived','recovery_seconds':round(time.monotonic()-restarted,3),'outage_http_status':failed_status,'limit':'Database restart and refused-first-host fallback; not a real primary promotion or PgBouncer'}
 podman('stop','--time','20',reconnect_worker)
 # Bounded ordinary queries: hold the records table lock beyond statement_timeout.
 holder=lock_records();started=time.monotonic()
 browser.request('GET','/portal',base=url_b,expected=503)
 elapsed=time.monotonic()-started;unlock(holder)
 assert 4<=elapsed<9
 results['lock_deadline_seconds']=round(elapsed,3)
 # Sessions and authentication must enter the same bounded request transaction.
 for table,label in [('sessions','session_deadline_seconds'),('users','authentication_deadline_seconds')]:
  holder=lock_records(table);started=time.monotonic()
  browser.request('GET','/portal',base=url_b,expected=503)
  elapsed=time.monotonic()-started;unlock(holder)
  assert 4<=elapsed<9
  results[label]=round(elapsed,3)
 # A running statement, rather than a lock wait, reaches the twelve-second query deadline.
 started=time.monotonic()
 code="require '/app/vendor/autoload.php'; $app=require '/app/bootstrap/app.php'; $app->make(Illuminate\\Contracts\\Console\\Kernel::class)->bootstrap(); try { (new App\\Http\\DatabaseRequestTimeouts)->handle(Illuminate\\Http\\Request::create('/portal'), fn()=>Illuminate\\Support\\Facades\\DB::select('select pg_sleep(30)')); exit(1); } catch (Illuminate\\Database\\QueryException $error) { exit(($error->errorInfo[0]??'')==='57014'?0:2); }"
 podman('run','--rm','--network','host','--env-file',str(app_env),IMAGE,'php','-r',code)
 elapsed=time.monotonic()-started;assert 11<=elapsed<17
 results['query_deadline_seconds']=round(elapsed,3)
 holder=lock_records('migrations');started=time.monotonic()
 assert health(url_b)==503
 elapsed=time.monotonic()-started;unlock(holder)
 assert 1.5<=elapsed<4
 results['health_statement_deadline_seconds']=round(elapsed,3)
 # Dump and restore every application row. S3 references and bytes remain separately verified.
 tables=['migrations','users','sessions','records','documents','report_jobs']
 snapshot={table:sql(f'select row_to_json(t) from {table} t order by id') for table in tables}
 dump=podman('exec',database,'pg_dump','-U','portal','-p',str(db_port),'--clean','--if-exists','portal')
 podman('exec','-i',database,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','portal','-p',str(db_port),'portal',input=dump)
 assert snapshot=={table:sql(f'select row_to_json(t) from {table} t order by id') for table in tables}
 portal=json.loads(browser.request('GET','/portal',base=url_b))
 assert browser.request('GET',f"/documents/{portal['documents'][0]['id']}",base=url_b)==b'Barbara synthetic document\n'
 results['logical_restore']='PASS six tables exact, retained session and referenced object bytes; not Stack backup recovery'
 # Drain a real in-flight web request during SIGTERM.
 holder=lock_records()
 with concurrent.futures.ThreadPoolExecutor() as executor:
  request=executor.submit(browser.request,'GET','/portal',None,url_a)
  wait_for(blocked)
  stopping=executor.submit(podman,'stop','--time','25',web_a)
  time.sleep(.3);unlock(holder);request.result(timeout=20);stopping.result(timeout=25)
 assert inspect(web_a)['State']['ExitCode']==0
 results['web_shutdown']='PASS SIGTERM drains blocked authenticated request and exits zero'
 results['versions']={'database':sql('select version()'),'runtime':podman('exec',web_b,'php','--version').decode().splitlines()[0],
  'frankenphp':podman('exec',web_b,'frankenphp','version').decode().strip(),'podman':podman('--version').decode().strip(),'image_id':inspect(web_b)['Image']}
 print(json.dumps(results,indent=2))

if __name__=='__main__':
 try:main()
 finally:
  (EVIDENCE/'results.json').write_text(json.dumps(results,indent=2))
  for name in reversed(containers):
   subprocess.run(['podman','logs',name],stdout=(EVIDENCE/(name+'.log')).open('wb'),stderr=subprocess.STDOUT)
   subprocess.run(['podman','rm','--force',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  print('Evidence directory:',EVIDENCE)
