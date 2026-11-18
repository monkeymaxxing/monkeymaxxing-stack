#!/usr/bin/env python3
"""Check the two shapes of a system: without staging01, as the template
ships, and with staging01, as operating_procedures/add_staging01.md adds it.

  MMX_BINARY=/path/to/mmx python3 tests/staging_server_test.py

Without staging01, `mmx validate` passes and every fleet stage of
every_server that serves staging01 skips itself, so the run asks for no
staging secret. With staging01 added by the procedure's inventory edits,
those stages select staging01, and staging01 gets Postgres without
pgBackRest, backups, or backup checks: staging holds only seed data.
"""
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(os.environ.get('STACK_TEMPLATE_DIR') or Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template')

STAGING_STAGES = ['database_server_on_staging01', 'pgbouncer_on_staging01', 'find_the_live_and_new_web_ports_on_staging01',
                  'app_server_on_staging01', 'tunnel_connector_and_caddy_on_staging01']


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise AssertionError(f'expected one {old!r} in the inventory')
    return text.replace(old, new)


def add_staging01(root):
    """The inventory edits of add_staging01.md, steps 1 and 2."""
    path = root/'inventories/servers.yml'
    text = path.read_text()
    tag = '      shop: "3f2a1c97d4e85b60a1c2d3e4f5061728394a5b6c"\n'
    text = replace_once(text, tag + '    staging: {}\n', tag + '    staging:\n' + tag)
    text = replace_once(text, '      shop: shop.example.com\n    staging: {}\n',
                        '      shop: shop.example.com\n    staging:\n      shop: staging.shop.example.com\n')
    text = replace_once(text, '  app001:\n', '''  staging01:
    address: 10.20.0.2
    https_address: https://10.20.0.2:7443
    ssh_user: root
    ssh_known_hosts: ssh/known_hosts
    ssh_config: ssh/config
    vars:
      public_ipv4_address: 203.0.113.2
      private_ip: 10.20.0.2
      wireguard_public_key: "xntON0r+ip4v53R2PDYOEKeq0RH91Y9x307uPnUQOTE="

  app001:
''')
    text = replace_once(text, '  staging_server:\n    nodes: []\n', '  staging_server:\n    nodes: [staging01]\n')
    path.write_text(text)


class TwoShapes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def mmx_in(self, root, *arguments):
        result = subprocess.run([self.mmx, *arguments], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def system(self, directory, with_staging01):
        root = Path(directory)/'systems'
        shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
        template_values.fill_the_values_the_setup_fills(root)
        if with_staging01:
            add_staging01(root)
        self.mmx_in(root, 'validate')
        return root

    def stages(self, root):
        explained = json.loads(self.mmx_in(root, 'explain', 'every_server', '--json'))
        return {stage['path']: stage for stage in explained['fleet_stages']}

    def test_the_template_ships_without_staging01(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.system(directory, with_staging01=False)
            stages = self.stages(root)
            for name in STAGING_STAGES:
                self.assertFalse(stages[name].get('nodes'), f'{name} selects a server without staging01')
            text = self.mmx_in(root, 'explain', 'every_server')
            self.assertNotIn('secrets.staging_', text)

    def test_the_other_playbooks_explain_in_both_shapes(self):
        for with_staging01 in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                root = self.system(directory, with_staging01)
                environments = ['production', 'staging'] if with_staging01 else ['production']
                for environment in environments:
                    self.mmx_in(root, 'explain', 'deploy', '--var', f'environment_name={environment}')
                    self.mmx_in(root, 'explain', 'end_connections_that_use_an_old_database_password',
                                '--var', 'database_name=shop', '--var', f'environment_name={environment}')
                self.mmx_in(root, 'explain', 'reboot_servers_after_updates')
                self.mmx_in(root, 'explain', 'lock_everyone_out', '--var', 'desk_name=desk01')

    def test_staging01_runs_postgres_without_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.system(directory, with_staging01=True)
            stages = self.stages(root)
            for name in STAGING_STAGES:
                selected = {task['node'] for task in stages[name].get('node_tasks') or []}
                if name != 'pgbouncer_on_staging01':     # PgBouncer waits for pgbouncer_runs_in_front_of_postgres
                    self.assertEqual(selected, {'staging01'}, name)
            statuses = {task['path'].rsplit('/', 1)[-1]: task['status'] for task in stages['database_server_on_staging01']['node_tasks']}
            self.assertEqual(statuses['run_debians_cluster_main'], 'ready')
            self.assertEqual(statuses['listen_addresses_of_debians_cluster'], 'ready')
            backup_tasks = [task for task in statuses if 'pgbackrest' in task or 'backup' in task]
            self.assertTrue(backup_tasks)
            for task in backup_tasks:
                self.assertEqual(statuses[task], 'skipped', f'{task} runs on staging01, which keeps no backups')
            text = self.mmx_in(root, 'explain', 'every_server')
            self.assertNotIn('staging_pgbackrest', text)
            self.assertNotIn('staging_bucket', text)

    def test_staging01s_checks_have_no_backup_checks(self):
        """database_servers.yml, rendered for staging01. (A database server's
        rendering needs its facts, which explain cannot read.)"""
        def check_groups(is_staging_server):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'inventories').mkdir()
                (root/'playbooks').mkdir()
                (root/'mmx_project_settings.yml').write_text(json.dumps(dict(
                    project_name='render_test', default_inventory='servers',
                    vars=dict(is_staging_server=is_staging_server, pgbouncer_runs_in_front_of_postgres=False))))
                (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'db01': {'address': '127.0.0.1'}})))
                (root/'source.template').write_text((T/'mmwatchdog_checks/database_servers.yml').read_text().replace('.inputs', '.vars'))
                (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                    dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
                explained = json.loads(self.mmx_in(root, 'explain', 'render', '--json'))
                text = explained['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0].get('text', '')
                return {line.strip().rstrip(':') for line in text.splitlines() if line.startswith('  ') and not line.startswith('   ') and line.strip().endswith(':')}
        staging = check_groups(True)
        self.assertIn('postgres', staging)
        self.assertNotIn('backups', staging)
        self.assertNotIn('write_ahead_log_archiving', staging)



class StagingSettingsStayOffProduction(unittest.TestCase):
    """staging01 gets each app's env with staging_env laid over it, and
    every_server refuses to configure staging01 when that would reach
    production's bucket or address."""

    SHOP = {'env': {'RAILS_ENV': 'production', 'APP_ORIGIN': 'https://shop.example.com'},
            'staging_env': {'APP_ORIGIN': 'https://staging.shop.example.com'},
            'production_uploads_r2_bucket': 'shop-uploads', 'staging_uploads_r2_bucket': 'shop-staging-uploads'}

    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')
        text = (T/'playbooks/every_server.yml').read_text()
        match = re.search(r"- id: refuse_staging_settings_that_reach_production\n.*?<<'PYTHON'\n(.*?)\n\s+PYTHON\n", text, re.S)
        cls.script = textwrap.dedent(match[1]) if match else None

    def render_settings_file(self, is_staging_server, app):
        values = {'app': {'key': 'shop', 'value': app}, 'is_staging_server': is_staging_server}
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001': {'address': '127.0.0.1'}})))
            # MMX explain defers role .inputs until execution; resolve them in project vars.
            text = (T/'files_used_by_several_roles/app_settings.env').read_text().replace('.inputs', '.vars').replace('.app.', '.vars.app.')
            (root/'rendered.template').write_text(text)
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[dict(
                id='render', file=dict(path='/tmp/rendered', template='rendered.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    def lines(self, text):
        return {line for line in text.splitlines() if '=' in line and not line.startswith('#')}

    def test_staging01_gets_its_own_origin_and_bucket_and_production_keeps_its_own(self):
        staging = self.lines(self.render_settings_file(True, self.SHOP))
        self.assertIn('R2_BUCKET=shop-staging-uploads', staging)
        self.assertIn('APP_ORIGIN=https://staging.shop.example.com', staging)
        self.assertIn('RAILS_ENV=production', staging)
        self.assertNotIn('R2_BUCKET=shop-uploads', staging)
        production = self.lines(self.render_settings_file(False, self.SHOP))
        self.assertIn('R2_BUCKET=shop-uploads', production)
        self.assertIn('APP_ORIGIN=https://shop.example.com', production)
        self.assertNotIn('R2_BUCKET=shop-staging-uploads', production)

    def test_an_app_without_staging_env_gets_its_env_on_staging01(self):
        app = {'env': {'RAILS_ENV': 'production'}, 'production_uploads_r2_bucket': ''}
        self.assertEqual(self.lines(self.render_settings_file(True, app)), {'RAILS_ENV=production'})

    def test_an_app_without_uploads_gets_no_bucket_on_staging01_or_production(self):
        app = dict(self.SHOP, production_uploads_r2_bucket='', staging_uploads_r2_bucket='')
        for is_staging_server in (True, False):
            self.assertFalse([line for line in self.lines(self.render_settings_file(is_staging_server, app)) if line.startswith('R2_BUCKET')])

    def refusal(self, **changes):
        self.assertIsNotNone(self.script, 'every_server has no refuse_staging_settings_that_reach_production task')
        app = json.loads(json.dumps(self.SHOP))
        for name, value in changes.items():
            if '__' not in name:
                app[name] = value
                continue
            part, key = name.split('__')
            if value is None:
                app[part].pop(key, None)
            else:
                app[part][key] = value
        return subprocess.run([sys.executable, '-I', '-c', self.script], env=dict(os.environ, APPS=json.dumps({'shop': app})),
                              text=True, capture_output=True)

    def test_the_example_app_is_accepted(self):
        self.assertEqual(self.refusal().returncode, 0)

    def test_staging_uploads_without_their_own_bucket_are_refused_naming_the_app_and_the_line(self):
        result = self.refusal(staging_uploads_r2_bucket='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('apps.shop', result.stderr)
        self.assertIn('staging_uploads_r2_bucket: <', result.stderr)

    def test_production_bucket_as_the_staging_bucket_is_refused(self):
        self.assertNotEqual(self.refusal(staging_uploads_r2_bucket='shop-uploads').returncode, 0)

    def test_an_app_naming_r2_bucket_itself_is_refused_with_the_setting_to_use(self):
        for where in ('env', 'staging_env'):
            with self.subTest(where=where):
                result = self.refusal(**{where+'__R2_BUCKET': 'shop-uploads'})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'apps.shop.{where} names R2_BUCKET', result.stderr)
                self.assertIn('production_uploads_r2_bucket', result.stderr)

    def test_an_app_without_uploads_needs_no_bucket(self):
        self.assertEqual(self.refusal(production_uploads_r2_bucket='', staging_uploads_r2_bucket='').returncode, 0)

    def test_production_origin_on_staging_is_refused(self):
        for origin in (None, 'https://shop.example.com'):
            with self.subTest(origin=origin):
                result = self.refusal(staging_env__APP_ORIGIN=origin)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('staging_env: {APP_ORIGIN:', result.stderr)


if __name__ == '__main__':
    unittest.main()
