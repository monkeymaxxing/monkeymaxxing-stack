#!/usr/bin/env python3
"""Render the real migration templates and check cutover failure behavior."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
MOVING = dict(wireguard_address='10.20.11.1', wireguard_public_key='W4MVmeNMv9vw3FJUc9fGBUxhKPQrS17V6L96pYaVUUM=',
              public_ipv4_address='203.0.113.50', postgres_port=5544, copy_onto='db01', apps=['shop'], through_relay=False)


def embedded_script(path):
    text = path.read_text()
    return textwrap.dedent(re.search(r"python3 -I - <<'PYTHON'\n(.*?)\s+PYTHON", text, re.S)[1])


class Inventory(unittest.TestCase):
    def validate(self, apps_connect_through_pgbouncer='false', **changes):
        moving = {k: v for k, v in dict(MOVING, **changes).items() if v is not None}
        env = dict(os.environ, DATABASE_MOVING_IN=json.dumps(moving), PRIVATE_IP_RANGES='{"database_moving_in":"10.20.11.0/24","systems_desks":"10.20.9.0/24"}',
                   WIREGUARD_NETWORK='10.20.0.0/16', DATABASE_SERVERS='["db02","db01"]',
                   INVENTORY_NODES='{}', APPS='{"shop":{"database_name":"shop"}}',
                   APPS_CONNECT_THROUGH_PGBOUNCER=apps_connect_through_pgbouncer)
        return subprocess.run([sys.executable, '-I', '-c', embedded_script(TEMPLATE/'roles/validate_database_moving_in/main.yml')],
                              env=env, text=True, capture_output=True)

    def test_valid_settings(self):
        self.assertEqual(self.validate().returncode, 0)
        self.assertEqual(self.validate(through_relay=True).returncode, 0)
        self.assertEqual(self.validate(through_relay=False).returncode, 0)

    def test_apps_through_the_stacks_pgbouncer_are_refused(self):
        result = self.validate(apps_connect_through_pgbouncer='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('add_pgbouncer.md', result.stdout + result.stderr)

    def test_relay_switch_requires_a_boolean(self):
        self.assertNotEqual(self.validate(through_relay='false').returncode, 0)

    def test_through_relay_is_required(self):
        # The switch playbook's when reads through_relay; MMX fails on a missing key.
        self.assertNotEqual(self.validate(through_relay=None).returncode, 0)

    def test_relay_copy_entry_cannot_collide_with_a_moving_database(self):
        import hashlib
        alias = 'database_moving_in_' + hashlib.sha256(b'shop').hexdigest()[:32]
        env = dict(os.environ, DATABASE_MOVING_IN=json.dumps(dict(MOVING, through_relay=True, apps=['shop', 'copy_name'])),
                   PRIVATE_IP_RANGES='{"database_moving_in":"10.20.11.0/24"}', WIREGUARD_NETWORK='10.20.0.0/16',
                   DATABASE_SERVERS='["db01"]', INVENTORY_NODES='{}', APPS_CONNECT_THROUGH_PGBOUNCER='false',
                   APPS=json.dumps({'shop': {'database_name': 'shop'}, 'copy_name': {'database_name': alias}}))
        result = subprocess.run([sys.executable, '-I', '-c', embedded_script(TEMPLATE/'roles/validate_database_moving_in/main.yml')],
                                env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('conflicts with a derived relay copy entry', result.stderr)

    def test_unknown_app_wrong_primary_and_address_outside_range_are_refused(self):
        for changes in [dict(apps=['unknown']), dict(copy_onto='db02'), dict(copy_onto='old'),
                        dict(wireguard_address='10.20.2.1'), dict(wireguard_address='10.20.11.255')]:
            with self.subTest(changes=changes):
                result = self.validate(**changes)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Refused database_moving_in:', result.stderr)


class RenderedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise unittest.SkipTest('Set MMX_BINARY or put mmx on PATH to render templates.')

    def render(self, filename, **changes):
        values = dict(database_moving_in=MOVING, database_servers=['db01','db02'], apps_connect_through_pgbouncer=False,
                      app_secrets={'shop_database_password':'invented123'}, app={'key':'shop','value':{'database_name':'shop','secrets_from_vault':[]}},
                      inventory_groups={}, inventory_nodes={'app001':{'vars':{'private_ip':'10.20.1.1'}}},
                      allowed_laptops=[], is_systems_desk=False, is_app_server=True, is_database_server=False, is_jobs_server=False,
                      is_util_server=False,is_staging_server=False,is_load_balancer_server=False,
                      tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers=False)
        values.update(changes)
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test',default_inventory='servers',vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001':{'address':'127.0.0.1'}})))
            # MMX explain defers role .inputs until execution. Use the same
            # template with the resolved role inputs in project vars.
            (root/'rendered.template').write_text((TEMPLATE/filename).read_text().replace('.inputs','.vars').replace('.app.','.vars.app.'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render',nodes='all',node_tasks=[dict(id='render',file=dict(path='/tmp/rendered',template='rendered.template',permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx,'explain','render','--json'],cwd=root,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            task=json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]
            self.assertIn('text',task['rendered_templates'][0],task)
            return task['rendered_templates'][0]['text']

    def test_old_database_is_first_in_both_files_and_has_its_own_port(self):
        for filename,port in [('app_secrets.env',6432),('app_database_direct_to_postgres.env',5432)]:
            with self.subTest(filename=filename):
                text=self.render('files_used_by_several_roles/'+filename,apps_connect_through_pgbouncer=True)
                self.assertIn(f'@10.20.11.1:5544,db01:{port},db02:{port}/shop?target_session_attrs=read-write&connect_timeout=3',text)
                self.assertIn('DATABASE_READ_URL=',text)
                self.assertNotIn('prefer-standby',text)

    def test_unlisted_app_keeps_stack_urls_and_replica_reads(self):
        for moving in ({},dict(MOVING,apps=['another_app'])):
            text=self.render('files_used_by_several_roles/app_secrets.env',database_moving_in=moving)
            self.assertIn('@db01:5432,db02:5432/shop?target_session_attrs=read-write&connect_timeout=3',text)
            self.assertIn('target_session_attrs=prefer-standby',text)
            self.assertNotIn('10.20.11.1',text)


class SwitchPlaybook(unittest.TestCase):
    """One switch playbook for both kinds of source; only a relay move needs the relay password."""
    RELAY_KEY = 'database_moving_in_relay_admin_password'

    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise unittest.SkipTest('Set MMX_BINARY or put mmx on PATH to read secrets usage.')

    def secrets_usage(self, moving):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns('.mmx'))
            settings = root/'mmx_project_settings.yml'
            text = settings.read_text()
            self.assertEqual(text.count('\n  database_moving_in: {}\n'), 1)
            settings.write_text(text.replace('\n  database_moving_in: {}\n', '\n  database_moving_in: '+json.dumps(moving)+'\n'))
            result = subprocess.run([self.mmx, 'secrets', 'usage', '--json'], cwd=root, text=True, capture_output=True)
            self.assertIn(result.returncode, (0, 1), result.stderr)  # 1: the template's vault defines no key
            return json.loads(result.stdout)

    def needed(self, usage):
        return {entry['key'] for entry in usage['keys'] if entry.get('source') is None
                and not entry.get('only_read_by_fleet_stages_left_out_before_the_run')}

    def test_a_self_hosted_move_needs_no_relay_password(self):
        needed = self.needed(self.secrets_usage(dict(MOVING, through_relay=False)))
        self.assertIn('database_moving_in_replication_password', needed)
        self.assertNotIn(self.RELAY_KEY, needed)

    def test_a_relay_move_needs_the_relay_password(self):
        self.assertIn(self.RELAY_KEY, self.needed(self.secrets_usage(dict(MOVING, through_relay=True))))


class AppRole(unittest.TestCase):
    def test_the_real_role_script_sets_read_only_for_the_listed_role(self):
        text=(TEMPLATE/'roles/database_server/main.yml').read_text().split('- id: keep_the_apps_read_only_on_the_database_copy',1)[1]
        script=textwrap.dedent(re.search(r"python3 -I - <<'PYTHON'\n(.*?)\s+PYTHON",text,re.S)[1])
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root=Path(temporary)
            psql=root/'psql'
            psql.write_text('#!'+sys.executable+'\nimport os,sys\nsql=sys.stdin.read()\nwith open(os.environ["SQL_LOG"],"a") as log: log.write(sql+"\\n")\nprint("[]" if "json_agg" in sql else "f" if sql.startswith("SELECT") else "")\n')
            psql.chmod(0o755)
            log=root/'sql.log'
            result=subprocess.run([sys.executable,'-I','-c',script],env=dict(os.environ,PATH=str(root)+':'+os.environ['PATH'],SQL_LOG=str(log),APPS='{"shop":{"database_name":"store"},"another_app":{"database_name":"other"}}',DATABASE_MOVING_IN=json.dumps(MOVING)),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('ALTER ROLE "store" SET default_transaction_read_only = on',log.read_text())
            self.assertNotIn('"other"',log.read_text())


class AppRoleOnRealPostgres(unittest.TestCase):
    """The role's read-only step runs only while the copy is unfinished."""

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix='ro')
        data = os.path.join(self.directory, 'stack')
        subprocess.run(['initdb', '-D', data, '-U', 'postgres', '-A', 'trust'], check=True, capture_output=True)
        subprocess.run(['pg_ctl', '-D', data, '-w', '-l', data + '.log', '-o', f"-p 54393 -k {self.directory} -c listen_addresses=''", 'start'], check=True, capture_output=True)
        self.run_sql('postgres', 'CREATE ROLE store LOGIN; CREATE DATABASE store OWNER store')
        text = (TEMPLATE/'roles/database_server/main.yml').read_text().split('- id: keep_the_apps_read_only_on_the_database_copy', 1)[1]
        self.script = textwrap.dedent(re.search(r"python3 -I - <<'PYTHON'\n(.*?)\s+PYTHON", text, re.S)[1])

    def tearDown(self):
        subprocess.run(['pg_ctl', '-D', os.path.join(self.directory, 'stack'), '-m', 'immediate', 'stop'], capture_output=True)
        shutil.rmtree(self.directory, ignore_errors=True)

    def run_sql(self, database, text):
        return subprocess.run(['psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-h', self.directory, '-p', '54393', '-U', 'postgres', '-d', database],
                              input=text, text=True, capture_output=True, check=True).stdout.strip()

    def run_role_step(self):
        env = dict(os.environ, PGHOST=self.directory, PGPORT='54393', PGUSER='postgres',
                   APPS='{"shop":{"database_name":"store"}}', DATABASE_MOVING_IN=json.dumps(MOVING))
        result = subprocess.run([sys.executable, '-I', '-c', self.script], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.run_sql('postgres', "SELECT coalesce('default_transaction_read_only=on'=ANY(rolconfig),false) FROM pg_roles WHERE rolname='store'")

    def test_empty_database_is_kept_read_only(self):
        self.assertEqual(self.run_role_step(), 't')

    def test_database_still_subscribed_is_kept_read_only(self):
        self.run_sql('store', "CREATE TABLE t (id int); CREATE SUBSCRIPTION database_moving_in CONNECTION 'host=127.0.0.1 port=1 dbname=x' PUBLICATION database_moving_in WITH (connect=false)")
        self.assertEqual(self.run_role_step(), 't')

    def test_finished_move_is_left_writable(self):
        self.run_sql('store', 'CREATE TABLE t (id int)')
        self.assertEqual(self.run_role_step(), 'f')


class SwitchFailure(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('database_move',TEMPLATE/'files_used_by_several_roles/move_database_into_the_stack.py')
        self.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.module.databases=['shop']
        self.module.moving=dict(MOVING)

    def test_fence_sets_only_moving_database_defaults_and_undo_resets_them(self):
        self.module.databases = ['shop', 'quoted"database']
        statements = []
        def sql(database, text, source=False, **options):
            self.assertTrue(source)
            self.assertEqual(database, 'postgres')
            statements.append(text)
            if 'ALTER SYSTEM' in text or 'pg_reload_conf' in text:
                raise RuntimeError('Managed databases refuse cluster changes')
        with patch.object(self.module, 'sql', side_effect=sql):
            self.module.fence('on')
            self.module.fence('off')
        self.assertEqual(statements, [
            'ALTER DATABASE "shop" SET default_transaction_read_only = on',
            'ALTER DATABASE "quoted""database" SET default_transaction_read_only = on',
            'ALTER DATABASE "shop" RESET default_transaction_read_only',
            'ALTER DATABASE "quoted""database" RESET default_transaction_read_only',
        ])

    def test_ready_distinguishes_same_named_subscriptions_in_separate_databases(self):
        self.module.moving=MOVING
        self.module.passfile=Path('/private/test.pgpass')
        statements=[]
        def sql(database,text,source=False,**options):
            statements.append(text)
            if 'pg_subscription' in text:
                self.assertIn('subdbid=(SELECT oid FROM pg_database WHERE datname=current_database())',text)
            if 'pg_subscription_rel' in text:
                return '0'
            if 'pg_stat_subscription' in text:
                self.assertIn('WHERE subid=(',text)
                return '1'
            if 'pg_subscription WHERE oid=' in text:
                return 't'
            return '1'
        with patch.object(self.module,'sql',side_effect=sql):
            self.module.ready('shop')
            self.module.ready('another_database')
        self.assertEqual(len(statements),8)

    def test_termination_waits_for_captured_backends_to_exit(self):
        statements=[]
        def sql(database,text,source=False,**options):
            statements.append(text)
            return '[123,456]' if 'json_agg' in text else '' if 'pg_terminate_backend' in text else '2' if len(statements)==3 else '0'
        with patch.object(self.module,'sql',side_effect=sql),patch.object(self.module.time,'sleep'):
            self.module.end_app_sessions(source=True)
        self.assertIn('pg_terminate_backend(pid)',statements[1])
        self.assertIn('pid IN (123,456)',statements[2])
        self.assertEqual(len(statements),4)

    def test_unlogged_or_other_uncopied_relations_are_refused_before_dump(self):
        with patch.object(self.module,'sql',return_value='public.unlogged_table'),patch.object(self.module,'execute') as execute:
            with self.assertRaisesRegex(RuntimeError,'does not copy the stored rows'):
                self.module.copy_database('shop')
            execute.assert_not_called()

    def test_copy_checks_replication_permission_and_prevents_row_security_filtering(self):
        self.module.moving = MOVING
        self.module.connection_env = {}
        self.module.passfile = Path('/private/test.pgpass')
        def sql(database, text, source=False, **options):
            if 'c.relpersistence' in text:
                return ''
            if 'pg_publication' in text or 'pg_roles' in text:
                return '1'
            return '0'
        for complete_rows in ['t', 'f']:
            with self.subTest(complete_rows=complete_rows):
                def execute(arguments, **options):
                    if options.get('input', '').startswith('SELECT rolbypassrls'):
                        return complete_rows
                    return ''
                with patch.object(self.module, 'sql', side_effect=sql) as queries, patch.object(self.module, 'execute', side_effect=execute) as commands:
                    if complete_rows == 't':
                        self.module.copy_database('shop')
                        self.assertTrue(any('CREATE SUBSCRIPTION' in call.args[1] for call in queries.call_args_list))
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'needs BYPASSRLS when source tables use row security'):
                            self.module.copy_database('shop')
                        self.assertFalse(any('CREATE SUBSCRIPTION' in call.args[1] for call in queries.call_args_list))
                    self.assertEqual(commands.call_args_list[0].kwargs['input'], 'IDENTIFY_SYSTEM')
                    self.assertIn('replication=database', commands.call_args_list[0].args[0][-1])

    def test_rerun_after_a_failed_cleanup_says_the_old_database_is_already_read_only(self):
        with patch.object(self.module,'ready') as ready,patch.object(self.module,'source_setting',return_value='on'),patch.object(self.module,'sql',return_value='1'):
            with self.assertRaisesRegex(RuntimeError,'already read-only'):
                self.module.switch()
            ready.assert_not_called()

    def test_source_role_override_is_refused_before_fencing(self):
        with patch.object(self.module,'ready'),patch.object(self.module,'source_setting',return_value='off'),patch.object(self.module,'sql',return_value='1'),patch.object(self.module,'fence') as fence:
            with self.assertRaisesRegex(RuntimeError,'override default_transaction_read_only'):
                self.module.switch()
            fence.assert_not_called()

    def test_undo_fence_failure_reports_that_source_can_still_be_read_only(self):
        def fence(setting):
            if setting=='off':
                raise RuntimeError('source unavailable')
        def sql(database,text,source=False,**options):
            return '0' if 'pg_db_role_setting' in text else '0/1234'
        with patch.object(self.module,'ready'),patch.object(self.module,'end_app_sessions'),patch.object(self.module,'source_setting',return_value='off'),patch.object(self.module,'sql',side_effect=sql),patch.object(self.module,'fence',side_effect=fence),patch.object(self.module.time,'monotonic',side_effect=[0,1,2,30]):
            with self.assertRaisesRegex(RuntimeError,'old fence could not be undone'):
                self.module.switch()

    def test_catchup_timeout_undoes_fence_without_removing_subscription(self):
        statements=[]
        def sql(database,text,source=False,**options):
            statements.append(text)
            return '0' if 'pg_db_role_setting' in text else 't' if 'pg_terminate_backend' in text else '0/1234' if 'pg_current_wal_' in text else 'f'
        with patch.object(self.module,'ready'),patch.object(self.module,'end_app_sessions'),patch.object(self.module,'source_setting',return_value='off'),patch.object(self.module,'fence') as fence,patch.object(self.module,'sql',side_effect=sql),patch.object(self.module.time,'monotonic',side_effect=[0,1,2,3,30]):
            with self.assertRaisesRegex(RuntimeError,'within 15 seconds'):
                self.module.switch()
            self.assertEqual([call.args[0] for call in fence.call_args_list],['on','off'])
            self.assertFalse(any('DROP SUBSCRIPTION' in text for text in statements))

    def test_cleanup_failure_keeps_source_fenced(self):
        def sql(database,text,source=False,**options):
            if text.startswith('DROP SUBSCRIPTION'):
                raise RuntimeError('source slot unavailable')
            return '0' if 'pg_db_role_setting' in text else '0/1234' if 'pg_current_wal_' in text else 't'
        with patch.object(self.module,'ready'),patch.object(self.module,'end_app_sessions'),patch.object(self.module,'source_setting',return_value='off'),patch.object(self.module,'fence') as fence,patch.object(self.module,'sql',side_effect=sql),patch.object(self.module,'sequence_values'),patch.object(self.module,'large_objects'):
            with self.assertRaisesRegex(RuntimeError,'source slot unavailable'):
                self.module.switch()
            self.assertEqual([call.args[0] for call in fence.call_args_list],['on'])


class RelaySwitch(unittest.TestCase):
    def setUp(self):
        SwitchFailure.setUp(self)
        self.module.moving['through_relay'] = True
        self.events = []

    def queries(self, database, text, source=False, **options):
        self.events.append(text)
        if 'pg_db_role_setting' in text:
            return '0'
        if 'pg_current_wal_' in text:
            return '0/1234'
        return 't'

    def run_switch(self, queries=None, relay=None):
        with patch.object(self.module, 'ready'), patch.object(self.module, 'source_setting', return_value='off'), \
             patch.object(self.module, 'end_app_sessions'), patch.object(self.module, 'sequence_values'), \
             patch.object(self.module, 'large_objects'), patch.object(self.module, 'sql', side_effect=queries or self.queries), \
             patch.object(self.module, 'relay_admin', side_effect=relay or self.events.append), \
             patch.object(self.module, 'reopen_relay') as reopen:
            self.module.switch()
            return reopen

    def test_relay_fences_all_app_entries_before_dropping_connections(self):
        self.module.databases = ['shop', 'quoted"database']
        with patch.object(self.module, 'relay_admin') as admin:
            self.module.relay_fence()
        self.assertEqual([call.args[0] for call in admin.call_args_list], [
            'DISABLE "shop"', 'DISABLE "quoted""database"', 'KILL "shop"', 'KILL "quoted""database"'])

    def test_success_keeps_relay_disabled_and_replication_entry_unfenced(self):
        reopen = self.run_switch()
        disable = self.events.index('DISABLE "shop"')
        kill = self.events.index('KILL "shop"')
        fence = self.events.index('ALTER DATABASE "shop" SET default_transaction_read_only = on')
        suspend = self.events.index('ALTER SUBSCRIPTION database_moving_in DISABLE')
        opening = next(i for i, text in enumerate(self.events) if text.startswith('BEGIN;'))
        drop = self.events.index('DROP SUBSCRIPTION database_moving_in')
        self.assertLess(disable, kill)
        self.assertLess(kill, fence)
        self.assertLess(fence, suspend)
        self.assertLess(suspend, opening)
        self.assertLess(opening, drop)
        self.assertEqual([text for text in self.events if text.startswith(('DISABLE ', 'KILL '))], ['DISABLE "shop"', 'KILL "shop"'])
        reopen.assert_not_called()

    def test_self_hosted_switch_keeps_its_sequence_and_never_calls_relay(self):
        self.module.moving.pop('through_relay')
        self.run_switch()
        self.assertFalse(any(text.startswith(('DISABLE ', 'KILL ', 'ALTER SUBSCRIPTION')) for text in self.events))
        self.assertLess(self.events.index('DROP SUBSCRIPTION database_moving_in'),
                        next(i for i, text in enumerate(self.events) if text.startswith('BEGIN;')))

    def test_partial_relay_fence_is_undone(self):
        def relay(command):
            self.events.append(command)
            if command.startswith('KILL '):
                raise RuntimeError('relay kill failed')
        with patch.object(self.module, 'reopen_relay') as reopen:
            with patch.object(self.module, 'ready'), patch.object(self.module, 'source_setting', return_value='off'), \
                 patch.object(self.module, 'sql', side_effect=self.queries), patch.object(self.module, 'relay_admin', side_effect=relay):
                with self.assertRaisesRegex(RuntimeError, 'relay kill failed'):
                    self.module.switch()
            reopen.assert_called_once()
        self.assertIn('ALTER DATABASE "shop" RESET default_transaction_read_only', self.events)
        self.assertNotIn('DROP SUBSCRIPTION database_moving_in', self.events)

    def test_failure_before_opening_restores_subscriptions_and_old_writer(self):
        def queries(database, text, source=False, **options):
            if text.startswith('BEGIN;'):
                raise RuntimeError('opening transaction failed')
            return self.queries(database, text, source, **options)
        with patch.object(self.module, 'ready'), patch.object(self.module, 'source_setting', return_value='off'), \
             patch.object(self.module, 'end_app_sessions'), patch.object(self.module, 'sequence_values'), \
             patch.object(self.module, 'large_objects'), patch.object(self.module, 'sql', side_effect=queries), \
             patch.object(self.module, 'relay_admin', side_effect=self.events.append), patch.object(self.module, 'reopen_relay') as reopen:
            with self.assertRaisesRegex(RuntimeError, 'opening transaction failed'):
                self.module.switch()
            reopen.assert_called_once()
        self.assertIn('ALTER SUBSCRIPTION database_moving_in ENABLE', self.events)
        self.assertIn('ALTER DATABASE "shop" RESET default_transaction_read_only', self.events)
        self.assertNotIn('DROP SUBSCRIPTION database_moving_in', self.events)

    def test_catchup_timeout_reopens_relay_and_keeps_subscription(self):
        with patch.object(self.module, 'ready'), patch.object(self.module, 'source_setting', return_value='off'), \
             patch.object(self.module, 'end_app_sessions'), patch.object(self.module, 'sql', side_effect=self.queries), \
             patch.object(self.module, 'relay_admin', side_effect=self.events.append), patch.object(self.module, 'reopen_relay') as reopen, \
             patch.object(self.module.time, 'monotonic', side_effect=[0, 1, 2, 30]):
            with self.assertRaisesRegex(RuntimeError, 'within 15 seconds'):
                self.module.switch()
            reopen.assert_called_once()
        self.assertIn('ALTER DATABASE "shop" RESET default_transaction_read_only', self.events)
        self.assertNotIn('DROP SUBSCRIPTION database_moving_in', self.events)

    def test_cleanup_failure_after_opening_keeps_relay_fenced(self):
        def queries(database, text, source=False, **options):
            if text.startswith('DROP SUBSCRIPTION'):
                raise RuntimeError('cleanup failed')
            return self.queries(database, text, source, **options)
        with patch.object(self.module, 'ready'), patch.object(self.module, 'source_setting', return_value='off'), \
             patch.object(self.module, 'end_app_sessions'), patch.object(self.module, 'sequence_values'), \
             patch.object(self.module, 'large_objects'), patch.object(self.module, 'sql', side_effect=queries), \
             patch.object(self.module, 'relay_admin', side_effect=self.events.append), patch.object(self.module, 'reopen_relay') as reopen:
            with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
                self.module.switch()
            reopen.assert_not_called()
        self.assertNotIn('ALTER DATABASE "shop" RESET default_transaction_read_only', self.events)

    def test_lost_opening_reply_does_not_reopen_source_when_stack_roles_opened(self):
        def queries(database, text, source=False, **options):
            if text.startswith('BEGIN;'):
                raise RuntimeError('COMMIT reply lost')
            if "bool_and('default_transaction_read_only=on'" in text:
                return 'f'
            return self.queries(database, text, source, **options)
        with patch.object(self.module, 'ready'), patch.object(self.module, 'source_setting', return_value='off'), \
             patch.object(self.module, 'end_app_sessions'), patch.object(self.module, 'sequence_values'), \
             patch.object(self.module, 'large_objects'), patch.object(self.module, 'sql', side_effect=queries), \
             patch.object(self.module, 'relay_admin', side_effect=self.events.append), patch.object(self.module, 'reopen_relay') as reopen:
            with self.assertRaisesRegex(RuntimeError, 'COMMIT reply lost'):
                self.module.switch()
            reopen.assert_not_called()
        self.assertNotIn('ALTER DATABASE "shop" RESET default_transaction_read_only', self.events)

    def test_undo_enables_entries_and_resumes_only_paused_entries(self):
        self.module.databases = ['shop', 'other']
        commands = []
        def admin(command, **options):
            commands.append(command)
            return 'name,paused,disabled\nshop,1,1\nother,0,1' if command == 'SHOW DATABASES' else ''
        with patch.object(self.module, 'relay_admin', side_effect=admin):
            self.module.reopen_relay()
        self.assertEqual(commands, ['SHOW DATABASES', 'ENABLE "shop"', 'RESUME "shop"', 'ENABLE "other"'])

    def test_admin_uses_wireguard_console_and_private_password_file(self):
        self.module.connection_env = {'PGPASSFILE': '/private/test.pgpass'}
        with patch.object(self.module, 'execute') as execute:
            self.module.relay_admin('DISABLE "shop"')
        arguments = execute.call_args.args[0]
        self.assertEqual(arguments[arguments.index('-h')+1], MOVING['wireguard_address'])
        self.assertEqual(arguments[arguments.index('-d')+1], 'pgbouncer')
        self.assertEqual(arguments[arguments.index('-U')+1], 'database_moving_in_relay_admin')
        self.assertEqual(execute.call_args.kwargs['env']['PGPASSFILE'], '/var/lib/postgresql/database_moving_in_relay_admin.pgpass')

    def test_replication_and_admin_reads_use_unfenced_copy_entry(self):
        self.module.passfile = Path('/private/test.pgpass')
        self.module.connection_env = {}
        expected = 'database_moving_in_8d9001d32c6a703d95921a77115050f3'
        self.assertIn("dbname='"+expected+"'", self.module.subscription_connection('shop'))
        with patch.object(self.module, 'execute') as execute:
            self.module.sql('shop', 'SELECT last_value FROM numbers', source=True)
        self.assertIn("dbname='"+expected+"'", execute.call_args.args[0])
        self.assertEqual(self.module.source_database('postgres'), 'postgres')


if __name__=='__main__':
    unittest.main()


@unittest.skipUnless(shutil.which('initdb') and shutil.which('pg_dump'), "needs PostgreSQL's server programs on PATH")
class LargeObjectsOnly(unittest.TestCase):
    """The switch's large-object step copies large objects and no table rows,
    also in a schema outside the search path (found on a real k3s move)."""

    def run_sql(self, port, database, text):
        return subprocess.run(['psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-h', self.directory, '-p', str(port), '-U', 'postgres', '-d', database],
                              input=text, text=True, capture_output=True, check=True).stdout.strip()

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix='lo')
        self.ports = {'old': 54391, 'stack': 54392}
        for name, port in self.ports.items():
            data = os.path.join(self.directory, name)
            subprocess.run(['initdb', '-D', data, '-U', 'postgres', '-A', 'trust'], check=True, capture_output=True)
            subprocess.run(['pg_ctl', '-D', data, '-w', '-l', data + '.log', '-o', f"-p {port} -k {self.directory} -c listen_addresses=''", 'start'], check=True, capture_output=True)
            self.run_sql(port, 'postgres', 'CREATE DATABASE shop')
            # The schema copy and the subscription already put these rows on the Stack's side.
            self.run_sql(port, 'shop', 'CREATE SCHEMA migration_probe; CREATE TABLE migration_probe.values (id int PRIMARY KEY); INSERT INTO migration_probe.values VALUES (1),(2); CREATE SEQUENCE migration_probe.numbers;')
        self.run_sql(self.ports['old'], 'shop', "SELECT nextval('migration_probe.numbers'); SELECT lo_from_bytea(0, 'old bytes');")

    def tearDown(self):
        for name in self.ports:
            subprocess.run(['pg_ctl', '-D', os.path.join(self.directory, name), '-m', 'immediate', 'stop'], capture_output=True)
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_large_objects_arrive_and_no_row_is_reloaded(self):
        spec = importlib.util.spec_from_file_location('database_move', TEMPLATE/'files_used_by_several_roles/move_database_into_the_stack.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.moving = dict(MOVING, wireguard_address=self.directory, postgres_port=self.ports['old'])
        module.working = Path(self.directory)
        module.ERROR_FILE = Path(self.directory) / 'error.txt'
        module.connection_env = dict(os.environ, PGHOST=self.directory, PGPORT=str(self.ports['stack']), PGUSER='postgres')
        module.large_objects('shop')
        stack = self.ports['stack']
        self.assertEqual(self.run_sql(stack, 'shop', "SELECT convert_from(lo_get(oid), 'UTF8') FROM pg_largeobject_metadata"), 'old bytes')
        self.assertEqual(self.run_sql(stack, 'shop', 'SELECT count(*) FROM migration_probe.values'), '2')
