#!/usr/bin/env python3
"""Check the live password and app-file gates before old sessions can end."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template/playbooks/end_connections_that_use_an_old_database_password.yml'


def shell_task(source, task):
    """The script and dryrun lines of a shell task, and the program they run from env PROGRAM."""
    import textwrap
    text = source.read_text().split('- id: '+task+'\n',1)[1]
    script = re.search(r'^ *script: (.*)$', text, re.M)[1]
    dryrun = re.search(r'^ *dryrun: (.*)$', text, re.M)[1]
    match = re.search(r'^( *)PROGRAM: \|\n((?:\1 +.*\n|\n)+)', text, re.M)
    return script, dryrun, textwrap.dedent(match[2])


class Rotation(unittest.TestCase):
    def run_gate(self, task='check_the_current_password_with_a_database_login', dryrun=False, **settings):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temporary:
            root = Path(temporary)
            binary=root/'bin';binary.mkdir()
            psql=binary/'psql'
            psql.write_text('#!'+sys.executable+'\n' + r'''import json, os, sys
args = sys.argv[1:]
assert args == ["-X", "--no-password", "-qAt", "-v", "ON_ERROR_STOP=1", "--host", "10.20.2.1", "--username", "shop", "--dbname", "shop", "--command", "select true"], args
assert os.environ["PGOPTIONS"] == "-c default_transaction_read_only=on"
assert os.environ["PGPASSFILE"] == "/dev/null"
assert os.environ["PGCONNECT_TIMEOUT"] == "3"
sys.exit(1 if os.environ.get("REFUSE_LOGIN") else 0 if os.environ["PGPASSWORD"] == "correct horse 1" else 2)
''')
            psql.chmod(0o755)
            systemctl=binary/'systemctl'
            systemctl.write_text('#!'+sys.executable+'\nimport os,sys\nprint("shop-web-8001.service" if sys.argv[1]=="list-units" else "@"+os.environ.get("STARTED","1100"))\n')
            systemctl.chmod(0o755)
            app=root/'shop';app.mkdir()
            secrets=app/'shop.env'
            secrets.write_text(settings.pop('FILE_TEXT', 'DATABASE_URL=postgresql://shop:correct horse 1@db01/shop\n'))
            os.utime(secrets,(1000,1000))
            if task == 'read_the_start_times_of_the_containers':
                script, dryrun_script, program = shell_task(SOURCE, task)
                program = program.replace('f"/etc/{app}/{app}.env"', 'f"'+str(root)+'/{app}/{app}.env"')
            else:
                script, dryrun_script, program = shell_task(SOURCE.parents[1]/'roles/verify_database_password_for_rotation/main.yml', task)
            command=['bash','-c',dryrun_script if dryrun else script]
            settings.setdefault('PROGRAM', program)
            env={**os.environ, 'PATH':str(binary)+':'+os.environ['PATH'],'DATABASE_SERVER_ADDRESS':'10.20.2.1','PGCONNECT_TIMEOUT':'3','PGPASSFILE':'/dev/null','PGOPTIONS':'-c default_transaction_read_only=on',
                 'DATABASE_NAME':'shop','ENVIRONMENT_NAME':'production',
                 'DATABASE_PASSWORDS':json.dumps({'production':{'db01':{'database_passwords':{'shop':'correct horse 1'}}},'staging':{'staging01':{'database_passwords':{'shop':'different'}}}}) if task == 'read_the_start_times_of_the_containers' else json.dumps({'shop':'correct horse 1'}),
                 'APPS':json.dumps({'shop':{'database_name':'shop'}}), **settings}
            return subprocess.run(command,text=True,capture_output=True,env=env)

    def test_current_password_logs_in_as_the_app_role(self):
        result=self.run_gate()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('matches the current vault',result.stdout)
        self.assertNotIn('correct horse 1',result.stdout+result.stderr)

    def test_wrong_password_or_refused_login_stops_rotation(self):
        for settings in ({'DATABASE_PASSWORDS':json.dumps({'shop':'different'})},{'REFUSE_LOGIN':'yes'}):
            with self.subTest(settings=settings):
                result=self.run_gate(**settings)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('does not match the current vault',result.stderr)
                self.assertNotIn('correct horse 1',result.stderr)

    def test_dryrun_proves_the_same_read_only_login(self):
        result=self.run_gate(dryrun=True)
        self.assertEqual(result.returncode,0,result.stderr)
        refused=self.run_gate(dryrun=True,REFUSE_LOGIN='yes')
        self.assertNotEqual(refused.returncode,0)
        self.assertIn('does not match the current vault',refused.stderr)

    def test_missing_password_refuses(self):
        for passwords in ('{}', '{"shop":null}', '{"shop":""}'):
            with self.subTest(passwords=passwords):
                result=self.run_gate(DATABASE_PASSWORDS=passwords)
                self.assertNotEqual(result.returncode,0)

    def test_current_app_file_and_new_container_pass(self):
        result=self.run_gate('read_the_start_times_of_the_containers')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'oldest_container_started_at':1100})

    def test_old_app_file_or_container_refuses(self):
        for settings in ({'FILE_TEXT':'DATABASE_URL=postgresql://shop:old@db01/shop\n'},{'STARTED':'900'}):
            with self.subTest(settings=settings):
                result=self.run_gate('read_the_start_times_of_the_containers',**settings)
                self.assertNotEqual(result.returncode,0)


class PgBouncerClients(unittest.TestCase):
    """end_the_pgbouncer_clients_older_than_the_oldest_container: a run ends the app's old clients, a dryrun only counts them."""

    def run_task(self, dryrun):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temporary:
            root = Path(temporary)
            binary=root/'bin';binary.mkdir()
            log=root/'psql.log'
            psql=binary/'psql'
            psql.write_text('#!'+sys.executable+'\n' + r'''import os, sys
command = sys.argv[sys.argv.index("-c")+1]
open(os.environ["PSQL_LOG"], "a").write(command+"\n")
if command == "SHOW CLIENTS":
    print("type,user,database,id,connect_time")
    print("C,shop,shop,1,2026-11-03 14:00:00 UTC")
    print("C,shop,shop,2,2026-11-03 15:00:00 UTC")
    print("C,blog,blog,3,2026-11-03 14:00:00 UTC")
''')
            psql.chmod(0o755)
            script, dryrun_script, program = shell_task(SOURCE, 'end_the_pgbouncer_clients_older_than_the_oldest_container')
            cutoff = int(__import__('calendar').timegm((2026,11,3,14,30,0)))
            env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],'TZ':'UTC','PSQL_LOG':str(log),'PROGRAM':program,
                 'DATABASE_NAME':'shop','CONTAINER_START_TIMES':json.dumps({'app001':{'oldest_container_started_at':cutoff+60},'app002':{'oldest_container_started_at':cutoff}})}
            result=subprocess.run(['bash','-c',dryrun_script if dryrun else script],text=True,capture_output=True,env=env)
            return result, log.read_text().splitlines()

    def test_a_run_ends_only_the_apps_clients_from_before_the_oldest_container(self):
        result, commands = self.run_task(dryrun=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'1')
        self.assertEqual(commands,['SHOW CLIENTS','KILL_CLIENT 1'])

    def test_a_dryrun_counts_the_same_clients_and_ends_none(self):
        result, commands = self.run_task(dryrun=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'1')
        self.assertEqual(commands,['SHOW CLIENTS'])


if __name__=='__main__':
    unittest.main()
