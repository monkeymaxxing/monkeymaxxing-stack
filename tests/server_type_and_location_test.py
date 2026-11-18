#!/usr/bin/env python3
"""Every production and staging server records its server type and location.

  MMX_BINARY=/path/to/mmx python3 tests/server_type_and_location_test.py

A replacement of a failed server is created with the failed server's
server type and location, read from the inventory, because the provider may
no longer list a failed server. every_server's first checks refuse a server
without vars.server_type and vars.location, before anything changes, and
name what to add. Systems desks and the servers of database_restore_servers
are left out: no playbook replaces them.

The test takes the refusal's program, with its inputs, from
`mmx explain every_server --json` of a copy of the template, and runs it
with bash and jq, as util01 does. It needs Python 3, bash and jq.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
TASK = 'every_server_records_its_server_type_and_location'


def argument(task, field):
    for item in task.get('arguments') or []:
        if item['field'] == field:
            return item['value']
    raise AssertionError(f'{task["path"]} has no argument {field}')


class ServerTypeAndLocation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to explain the actual playbook.')

    def run_the_check(self, edit=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            if edit:
                inventory = root/'inventories/servers.yml'
                inventory.write_text(edit(inventory.read_text()))
            explained = subprocess.run([self.mmx, 'explain', 'every_server', '--json', '--limit', 'util01'],
                                       cwd=root, text=True, capture_output=True)
        self.assertEqual(explained.returncode, 0, explained.stderr)
        task = next(task for stage in json.loads(explained.stdout)['fleet_stages']
                    for task in stage.get('node_tasks') or [] if task['path'].endswith('/' + TASK))
        env = dict(os.environ, **{name: argument(task, f'shell.env.{name}') for name in ('PROGRAM', 'INVENTORY_NODES', 'INVENTORY_GROUPS')})
        for name in ('INVENTORY_NODES', 'INVENTORY_GROUPS'):
            if not isinstance(env[name], str):
                env[name] = json.dumps(env[name])
        self.assertEqual(argument(task, 'shell.script'), 'bash -c "$PROGRAM"')
        return subprocess.run(['bash', '-c', env['PROGRAM']], env=env, text=True, capture_output=True,
                              stdin=subprocess.DEVNULL)

    def test_the_template_records_both_on_every_server(self):
        result = self.run_the_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')

    def test_a_server_without_them_is_refused_with_what_to_add(self):
        def remove_app001s(text):
            old = '      public_ipv4_address: 203.0.113.11\n      server_type: cx23\n      location: fsn1\n'
            self.assertEqual(text.count(old), 1)
            return text.replace(old, '      public_ipv4_address: 203.0.113.11\n')
        result = self.run_the_check(remove_app001s)
        self.assertEqual(result.returncode, 1)
        self.assertIn('app001 has no server_type and location in inventories/servers.yml.', result.stderr)
        self.assertIn('Add vars.server_type and vars.location', result.stderr)
        self.assertIn('Nothing changed.', result.stderr)
        self.assertNotIn('db01', result.stderr)

    def test_a_missing_location_alone_is_named(self):
        def remove_db01s_location(text):
            old = '      server_type: cx23\n      location: fsn1\n      private_ip: 10.20.2.1\n'
            self.assertEqual(text.count(old), 1)
            return text.replace(old, '      server_type: cx23\n      private_ip: 10.20.2.1\n')
        result = self.run_the_check(remove_db01s_location)
        self.assertEqual(result.returncode, 1)
        self.assertIn('db01 has no location in inventories/servers.yml.', result.stderr)

    def test_desks_and_restore_servers_need_neither(self):
        def add_restore01(text):
            text = text.replace('  database_restore_servers:\n    nodes: []', '  database_restore_servers:\n    nodes: [restore01]')
            return text.replace('\ngroups:\n', '\n  restore01:\n    address: 10.20.8.1\n    ssh_user: root\n    connection: ssh_only\n'
                                '    vars:\n      private_ip: 10.20.8.1\n      public_ipv4_address: 203.0.113.50\n'
                                '      wireguard_public_key: "xntON0r+ip4v53R2PDYOEKeq0RH91Y9x307uPnUQOTE="\n\ngroups:\n', 1)
        result = self.run_the_check(add_restore01)
        self.assertEqual(result.returncode, 0, result.stderr)
        # desk01 in the template has neither, and passes.
        self.assertNotIn('server_type', (T/'inventories/servers.yml').read_text().split('  util01:')[0].split('  desk01:')[1])

    def test_the_check_comes_before_any_server_changes(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        stage = playbook.split('  - id: validate_that_apps_and_servers_are_not_listed_twice\n')[1].split('\n  - id: ')[0]
        self.assertIn(f'- id: {TASK}', stage)
        self.assertIn('on_node_failure: stop_run', stage)


if __name__ == '__main__':
    unittest.main()
