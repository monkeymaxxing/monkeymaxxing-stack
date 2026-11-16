#!/usr/bin/env python3
"""Export the example's Supabase source using customer-scoped APIs and pg_dump."""
import hashlib,json,os,shutil,subprocess,urllib.request,urllib.error,urllib.parse
from pathlib import Path
os.umask(0o077)
ref=os.environ['SUPABASE_PROJECT_REF'];access=os.environ['SUPABASE_ACCESS_TOKEN'];service=os.environ['SUPABASE_SERVICE_ROLE_KEY']
out=Path(os.environ['EXPORT_DIR']).resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
def request(url,method='GET',body=None,headers=None):
 h=headers or {}
 if isinstance(body,dict):body=json.dumps(body).encode();h={**h,'Content-Type':'application/json'}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,method=method,data=body,headers=h),timeout=90) as r:
   b=r.read();return json.loads(b) if b and 'json' in r.headers.get('Content-Type','') else b
 except urllib.error.HTTPError as e:raise RuntimeError('Export request failed with HTTP '+str(e.code)) from None

def management(route,method='GET',body=None):return request('https://api.supabase.com/v1/projects/'+ref+'/'+route,method,body,{'Authorization':'Bearer '+access})
def sql(q):return management('database/query','POST',{'query':q})
def save(name,value):
 p=out/name;p.write_text(json.dumps(value,indent=2)+'\n');p.chmod(0o600)
if os.environ.get('FREEZE_SOURCE_FOR_EXPORT')!='true':raise RuntimeError('Set FREEZE_SOURCE_FOR_EXPORT=true after approving the write freeze')
sql("begin; revoke insert,update,delete on public.records,public.documents from authenticated; revoke execute on function public.queue_report(),public.process_report() from authenticated; select cron.alter_job((select jobid from cron.job where jobname='portal-minute-marker'),active:=false); commit;")
queries={
'users':'select id,email,encrypted_password,email_confirmed_at,banned_until,deleted_at,is_anonymous,raw_app_meta_data,raw_user_meta_data from auth.users order by email',
'identities':'select * from auth.identities','mfa_factors':'select * from auth.mfa_factors',
'records':'select * from public.records','documents':'select * from public.documents','report_jobs':'select * from public.report_jobs',
'schedule_occurrences':'select * from public.schedule_occurrences','cron_jobs':'select * from cron.job','cron_runs':'select * from cron.job_run_details',
'migrations':'select * from supabase_migrations.schema_migrations','storage_buckets':'select * from storage.buckets','storage_objects':'select * from storage.objects'}
parts=["'"+k+"',coalesce((select jsonb_agg(row_to_json(q)) from ("+q+")q),'[]'::jsonb)" for k,q in queries.items()]
s=sql('begin isolation level repeatable read read only; select jsonb_build_object('+','.join(parts)+') as snapshot; commit;')[0]['snapshot'];save('snapshot.json',s)
manifest=[]
for d in s['documents']:
 p=(out/'objects'/d['object_key']).resolve()
 if not p.is_relative_to(out/'objects'):raise RuntimeError('Unsafe object key')
 b=request('https://'+ref+'.supabase.co/storage/v1/object/authenticated/documents/'+urllib.parse.quote(d['object_key'],safe='/'),headers={'apikey':service,'Authorization':'Bearer '+service})
 if hashlib.sha256(b).hexdigest()!=d['sha256'] or len(b)!=int(d['byte_length']):raise RuntimeError('Object integrity check failed')
 p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(b);manifest.append({k:d[k] for k in ['object_key','sha256','byte_length']})
save('objects.json',manifest)
args=['pg_dump','--format=custom','--no-owner','--no-acl','--file='+str(out/'source-database.dump')]
args+=['--schema='+n for n in ['public','auth','storage','cron','supabase_migrations']]
r=subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
if r.returncode:raise RuntimeError('pg_dump failed; verify PGHOST, PGPORT, PGUSER, PGDATABASE, PGPASSWORD, PGSSLMODE and compatible client major version')
save('function-config.json',management('functions'))
body=management('functions/report-job/body')
if not isinstance(body,bytes):raise RuntimeError('Unexpected Edge Function export format')
(out/'report-job-provider-body.bin').write_bytes(body)
auth=management('config/auth');save('auth-config.json',{k:auth.get(k) for k in ['site_url','mailer_autoconfirm','disable_signup','jwt_exp','password_min_length','external_email_enabled']})
shutil.copyfile(os.environ['SOURCE_CODE_ARCHIVE'],out/'source-code.tar.gz')
save('config-variable-names.json',['VITE_SUPABASE_URL','VITE_SUPABASE_ANON_KEY','VITE_SCHEMA_VERSION','SUPABASE_URL','SUPABASE_ANON_KEY','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_DB_URL'])
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
save('sha256.json',manifest)
print('Export complete. Source remains frozen. Verify the destination before enabling jobs or changing traffic.')
