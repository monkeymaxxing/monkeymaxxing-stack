#!/usr/bin/env python3
"""Render the protections that setup used to check by hand, for every server group.

  MMX_BINARY=/path/to/mmx python3 tests/setup_protections_test.py

The Stack's tests prove how the Stack behaves; setup checks only what is
specific to the team's system. This file proves, from the rendered files:
  - automatic updates: database servers exclude the packages whose update
    restarts Postgres, no group reboots by itself, needrestart lists but never
    restarts on a database server and never restarts a desk's Rex sessions,
  - journald's size limits and the restart that applies them.
Real-system checks of the same settings are recorded in docs/testing.md.
Each server group's WireGuard peers are in tests/server_connections_test.py.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
FLAGS = ['is_systems_desk', 'is_app_server', 'is_database_server', 'is_util_server',
         'is_staging_server', 'is_jobs_server', 'is_load_balancer_server']
NODES = {  # name: (flag, private address)
    'util01': ('is_util_server', '10.20.0.1'), 'staging01': ('is_staging_server', '10.20.0.2'),
    'app001': ('is_app_server', '10.20.1.1'), 'app002': ('is_app_server', '10.20.1.2'),
    'db01': ('is_database_server', '10.20.2.1'), 'db02': ('is_database_server', '10.20.2.2'),
    'jobs001': ('is_jobs_server', '10.20.3.1'), 'lb01': ('is_load_balancer_server', '10.20.4.1'),
    'desk01': ('is_systems_desk', '10.20.9.1'), 'desk02': ('is_systems_desk', '10.20.9.2'),
}
GROUPS = {'util_server': ['util01'], 'staging_server': ['staging01'], 'app_servers': ['app001', 'app002'],
          'database_servers': ['db01', 'db02'], 'jobs_servers': ['jobs001'], 'load_balancer_servers': ['lb01'],
          'systems_desks': ['desk01', 'desk02']}


class Rendered(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def render(self, filename, node='app001', **changes):
        nodes = {n: {'vars': {'private_ip': ip, 'wireguard_public_key': n.upper(), 'public_ipv4_address': '203.0.113.' + ip.split('.')[-1]}}
                 for n, (_, ip) in NODES.items()}
        values = dict(inventory_nodes=nodes, inventory_groups=GROUPS, everyone_locked_out_except_desk='', database_moving_in={},
                      allowed_laptops=[dict(laptop_name='laptop1', wireguard_public_key='LAPTOP1', private_ip='10.20.10.1')],
                      tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers=False, **{f: False for f in FLAGS})
        values.update(changes)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={node: {'address': '127.0.0.1'}})))
            (root/'source.template').write_text((T/filename).read_text().replace('.inputs', '.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]
        self.assertIn('text', rendered, rendered)
        return rendered['text']

    def update_policy(self, **flags):
        return self.render('roles/every_server/files/unattended_upgrades.conf', **flags)

    def test_automatic_updates_never_reboot_and_a_database_server_excludes_what_restarts_postgres(self):
        for flags in ({}, {'is_app_server': True}, {'is_util_server': True}, {'is_staging_server': True},
                      {'is_systems_desk': True}, {'is_database_server': True}):
            with self.subTest(flags=flags):
                self.assertRegex(self.update_policy(**flags), r'(?m)^Unattended-Upgrade::Automatic-Reboot "false";$')
        database = self.update_policy(is_database_server=True)
        for package in ('postgresql', 'pg-auto-failover', 'linux-', 'pgbouncer'):
            self.assertIn(f'"{package}";', database)
        self.assertNotIn('Origins-Pattern', database)
        ordinary = self.update_policy(is_app_server=True)
        self.assertNotIn('Package-Blacklist', ordinary)
        self.assertIn('origin=cloudflared,codename=any', ordinary)
        self.assertNotIn('Superlogical', ordinary)
        self.assertIn('Superlogical', self.update_policy(is_systems_desk=True))

    def test_needrestart_lists_on_a_database_server_and_restarts_elsewhere(self):
        policy = 'roles/every_server/files/needrestart.conf'
        self.assertIn("$nrconf{restart} = 'l';", self.render(policy, is_database_server=True))
        for flags in ({}, {'is_app_server': True}, {'is_systems_desk': True}, {'is_util_server': True}):
            self.assertIn("$nrconf{restart} = 'a';", self.render(policy, **flags))
        self.assertIn('weekly_database_restore_drill', self.render(policy, is_util_server=True))
        self.assertNotIn('weekly_database_restore_drill', self.render(policy, is_app_server=True))

    def test_needrestart_never_restarts_the_web_containers_caddy_or_cloudflared(self):
        # 2026-11-13: needrestart restarted shop-web-8001.service on the only, serving app server: a failed request.
        policy = 'roles/every_server/files/needrestart.conf'
        for flags in ({}, {'is_app_server': True}, {'is_util_server': True}):
            text = self.render(policy, **flags)
            held_back = [re.compile(found) for found in re.findall(r'\$nrconf\{override_rc\}\{qr\((.+?)\)\} = 0;', text)]
            def is_held_back(unit):
                return any(pattern.search(unit) for pattern in held_back)
            for unit in ('shop-web-8001.service', 'my-shop-web-8002.service', 'caddy.service', 'cloudflared.service'):
                self.assertTrue(is_held_back(unit), unit)
            for unit in ('shop-jobs.service', 'postgresql.service', 'mmwatchdog.service'):
                self.assertFalse(is_held_back(unit), unit)
        self.assertNotIn('shop-jobs', self.render(policy, is_app_server=True))
        self.assertIn("$nrconf{restart} = 'a';", self.render(policy, is_app_server=True))

    def test_journald_limits_are_written_and_applied_by_a_restart(self):
        main = (T/'roles/every_server/main.yml').read_text()
        block = main[main.index('id: journal_size_limits'):]
        block = block[:block.index('name: systemd-journald')]
        self.assertIn('/etc/systemd/journald.conf.d/50-monkeymaxxing-stack.conf', block)
        self.assertRegex(block, r'(?m)^\s+SystemMaxUse=2G$')
        self.assertRegex(block, r'(?m)^\s+SystemKeepFree=4G$')
        self.assertIn('refresh: restart', main[main.index('id: restart_journald'):][:200])

    def test_every_server_and_the_desk_resolve_their_own_name(self):
        # 2026-11-12: every sudo on a real desk printed "sudo: unable to
        # resolve host desk01": the desk role set the host name and wrote no
        # /etc/hosts line for it.
        for node in ('util01', 'app001', 'db01'):
            with self.subTest(node=node):
                self.assertRegex(self.render('roles/every_server/files/hosts', node=node), rf'(?m)^\S+ {node}$')
        result = subprocess.run([self.mmx, 'explain', 'systems_desk', '--json', '--var', 'desk_name=desk01'],
                                cwd=template_values.filled_copy(), text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        tasks = [task for stage in json.loads(result.stdout)['fleet_stages'] for task in stage.get('node_tasks') or []]
        self.assertTrue(any(task['path'].endswith('/set_the_desk_name') for task in tasks))
        hosts = [item['value'] for task in tasks for item in task.get('arguments') or []
                 if item['field'] == 'file.content' and task['path'].endswith('/write_the_desk_name_into_the_hosts_file')]
        self.assertEqual(len(hosts), 1)
        self.assertRegex(hosts[0], r'(?m)^127\.0\.1\.1 desk01$')
        self.assertRegex(hosts[0], r'(?m)^127\.0\.0\.1 localhost$')


if __name__ == '__main__':
    unittest.main()
