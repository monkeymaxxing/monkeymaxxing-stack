#!/usr/bin/env python3
"""Create a synthetic Coolify source; secrets go only to SOURCE_SETTINGS_FILE."""
import os,json,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from coolify_inventory import api
os.umask(0o077)
settings_file=Path(os.environ['SOURCE_SETTINGS_FILE'])
if settings_file.exists():raise RuntimeError('SOURCE_SETTINGS_FILE already exists; keep the existing resource inventory')
state={}
def save():settings_file.write_text(json.dumps(state,indent=2))
state['server_uuid']=os.environ['COOLIFY_SERVER_UUID']
api('/servers/'+state['server_uuid']+'/validate','POST',{})
project=api('/projects','POST',{'name':'migration-portal'});state['project_uuid']=project['uuid'];save()
state['database_password']=secrets.token_hex(24)
db=api('/databases/postgresql','POST',{'name':'portal-postgresql','project_uuid':state['project_uuid'],'environment_name':'production','server_uuid':state['server_uuid'],'postgres_user':'portal','postgres_password':state['database_password'],'postgres_db':'portal','image':'postgres:17','is_public':False,'instant_deploy':True});state['database_uuid']=db['uuid'];save()
shared=api('/projects/'+state['project_uuid']+'/envs','POST',{'key':'PORTAL_NOTICE','value':'Recovered production setting '+secrets.token_hex(12)});state['shared']=shared
state['signing_key']=secrets.token_hex(32);state['fixture_password']=secrets.token_hex(16);state['webhook_secret']=secrets.token_hex(32)
app=api('/applications/dockerimage','POST',{'name':'migration-portal-web','project_uuid':state['project_uuid'],'environment_name':'production','server_uuid':state['server_uuid'],'docker_registry_image_name':os.environ['SOURCE_IMAGE_NAME'],'docker_registry_image_tag':os.environ['SOURCE_IMAGE_TAG'],'ports_exposes':'8080','ports_mappings':'18080:8080','health_check_enabled':True,'health_check_path':'/healthz','health_check_port':'8080','is_auto_deploy_enabled':True,'manual_webhook_secret_github':state['webhook_secret'],'instant_deploy':False});state['application_uuid']=app['uuid'];save()
prefix='/applications/'+state['application_uuid']
api(prefix,'PATCH',{'git_repository':'https://github.com/example/migration-portal','git_branch':'main'})
values={'DATABASE_URL':'postgresql://portal:'+state['database_password']+'@'+state['database_uuid']+':5432/portal','PORT':'8080','NODE_ENV':'production','COOKIE_SECURE':'false','WEB_CONCURRENCY':'1','FILE_STORAGE':'disk','UPLOADS_DIR':'/uploads','SESSION_SIGNING_KEY':state['signing_key'],'PORTAL_NOTICE':'{{project.PORTAL_NOTICE}}'}
for key,value in values.items():api(prefix+'/envs','POST',{'key':key,'value':value,'is_buildtime':False,'is_runtime':True,'is_preview':False,'is_literal':key!='PORTAL_NOTICE'})
state['storage']=api(prefix+'/storages','POST',{'type':'persistent','name':'private-uploads','mount_path':'/uploads'})
state['task']=api(prefix+'/scheduled-tasks','POST',{'name':'hourly-session-cleanup','command':'node /app/schedule.mjs','frequency':'* * * * *','timeout':60,'enabled':True})
save();print('Created native project, PostgreSQL, shared variable, runtime variables, upload mount, and Scheduled Task')
