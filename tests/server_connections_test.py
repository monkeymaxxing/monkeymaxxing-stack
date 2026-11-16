#!/usr/bin/env python3
"""Each server's WireGuard peers and firewall rules, from connections_between_server_pools.

  MMX_BINARY=/path/to/mmx python3 tests/server_connections_test.py

roles/work_out_who_this_server_talks_to reads the table in
inventories/servers.yml and gives each server its peers and incoming
firewall rules. These tests take each server's inputs from `mmx explain` of
the real playbooks, run the role's own program with them, and render the
real WireGuard template with its outputs. So they prove the playbook wiring,
the program, and the template together, without a server. A systems desk's
peers for the servers come from update-this-desks-wireguard-peers instead,
which tests/desk_wireguard_peers_test.py tests; the desk rows below record
what a desk had before the table, and that test checks the same peers.

PEERS_BEFORE_THE_TABLE and FIREWALL_BEFORE_THE_TABLE are what each test
server had before the table: its six firewall tasks and
its WireGuard peer logic, read with `mmx explain` in four states. The table
must give every server the same peers and the same rules. The only change
allowed is the order of the rules on the database servers and util01,
which the program sorts by port and then address; every rule is `allow`,
so the order changes nothing that is admitted.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
SERVERS = {  # name: (pool, private address)
    'util01': ('util_server', '10.20.0.1'), 'staging01': ('staging_server', '10.20.0.2'),
    'app001': ('app_servers', '10.20.1.1'), 'app002': ('app_servers', '10.20.1.2'),
    'db01': ('database_servers', '10.20.2.1'), 'db02': ('database_servers', '10.20.2.2'),
    'jobs001': ('jobs_servers', '10.20.3.1'), 'lb01': ('load_balancer_servers', '10.20.4.1'),
    'desk01': ('systems_desks', '10.20.9.1'), 'desk02': ('systems_desks', '10.20.9.2'),
}
MOVING = {'wireguard_public_key': 'OLDDATABASEKEY', 'public_ipv4_address': '203.0.113.50',
          'wireguard_address': '10.20.11.1', 'postgres_port': 5544, 'apps': ['shop'], 'copy_onto': 'db01',
          'through_relay': False}
STATES = {
    'default': {},
    'tunnel_setting_true': {'tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers': True},
    'locked_out_except_desk01': {'everyone_locked_out_except_desk': 'desk01'},
    'database_moving_in': {'database_moving_in': MOVING},
}
# The rule order may change once on these servers (see the module text).
RULES_MAY_BE_REORDERED = {'db01', 'db02', 'util01'}

PEERS_BEFORE_THE_TABLE = {
    'database_moving_in': {
        'app001': 'app002 db01 db02 desk01 desk02 lb01 util01 the old database',
        'app002': 'app001 db01 db02 desk01 desk02 lb01 util01 the old database',
        'db01': 'app001 app002 db02 desk01 desk02 jobs001 util01 the old database',
        'db02': 'app001 app002 db01 desk01 desk02 jobs001 util01 the old database',
        'desk01': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk01-laptop',
        'desk02': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk02-laptop',
        'jobs001': 'db01 db02 desk01 desk02 util01 the old database',
        'lb01': 'app001 app002 desk01 desk02 util01',
        'staging01': 'desk01 desk02 util01',
        'util01': 'app001 app002 db01 db02 desk01 desk02 jobs001 lb01 staging01',
    },
    'default': {
        'app001': 'app002 db01 db02 desk01 desk02 lb01 util01',
        'app002': 'app001 db01 db02 desk01 desk02 lb01 util01',
        'db01': 'app001 app002 db02 desk01 desk02 jobs001 util01',
        'db02': 'app001 app002 db01 desk01 desk02 jobs001 util01',
        'desk01': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk01-laptop',
        'desk02': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk02-laptop',
        'jobs001': 'db01 db02 desk01 desk02 util01',
        'lb01': 'app001 app002 desk01 desk02 util01',
        'staging01': 'desk01 desk02 util01',
        'util01': 'app001 app002 db01 db02 desk01 desk02 jobs001 lb01 staging01',
    },
    'locked_out_except_desk01': {
        'app001': 'app002 db01 db02 desk01 lb01 util01',
        'app002': 'app001 db01 db02 desk01 lb01 util01',
        'db01': 'app001 app002 db02 desk01 jobs001 util01',
        'db02': 'app001 app002 db01 desk01 jobs001 util01',
        'desk01': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk01-laptop',
        'desk02': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk02-laptop',
        'jobs001': 'db01 db02 desk01 util01',
        'lb01': 'app001 app002 desk01 util01',
        'staging01': 'desk01 util01',
        'util01': 'app001 app002 db01 db02 desk01 jobs001 lb01 staging01',
    },
    'tunnel_setting_true': {
        'app001': 'db01 db02 desk01 desk02 lb01 util01',
        'app002': 'db01 db02 desk01 desk02 lb01 util01',
        'db01': 'app001 app002 db02 desk01 desk02 jobs001 util01',
        'db02': 'app001 app002 db01 desk01 desk02 jobs001 util01',
        'desk01': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk01-laptop',
        'desk02': 'app001 app002 db01 db02 jobs001 lb01 staging01 util01 desk02-laptop',
        'jobs001': 'db01 db02 desk01 desk02 util01',
        'lb01': 'app001 app002 desk01 desk02 util01',
        'staging01': 'desk01 desk02 util01',
        'util01': 'app001 app002 db01 db02 desk01 desk02 jobs001 lb01 staging01',
    },
}
FIREWALL_BEFORE_THE_TABLE = {
    'database_moving_in': {
        'app001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.1.1, 8001:8099/tcp from 10.20.1.2, 8001:8099/tcp from 10.20.4.1',
        'app002': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.1.1, 8001:8099/tcp from 10.20.1.2, 8001:8099/tcp from 10.20.4.1',
        'db01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'db02': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'jobs001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'lb01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'staging01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'util01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 8445/tcp from 10.20.9.1, 8445/tcp from 10.20.9.2, 8445/tcp from 10.20.0.2, 8445/tcp from 10.20.1.1, 8445/tcp from 10.20.1.2, 8445/tcp from 10.20.2.1, 8445/tcp from 10.20.2.2, 8445/tcp from 10.20.3.1, 8445/tcp from 10.20.4.1, 8484/tcp from 10.20.9.1, 8484/tcp from 10.20.9.2, 8484/tcp from 10.20.0.2, 8484/tcp from 10.20.1.1, 8484/tcp from 10.20.1.2, 8484/tcp from 10.20.2.1, 8484/tcp from 10.20.2.2, 8484/tcp from 10.20.3.1, 8484/tcp from 10.20.4.1',
    },
    'default': {
        'app001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.1.1, 8001:8099/tcp from 10.20.1.2, 8001:8099/tcp from 10.20.4.1',
        'app002': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.1.1, 8001:8099/tcp from 10.20.1.2, 8001:8099/tcp from 10.20.4.1',
        'db01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'db02': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'jobs001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'lb01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'staging01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'util01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 8445/tcp from 10.20.9.1, 8445/tcp from 10.20.9.2, 8445/tcp from 10.20.0.2, 8445/tcp from 10.20.1.1, 8445/tcp from 10.20.1.2, 8445/tcp from 10.20.2.1, 8445/tcp from 10.20.2.2, 8445/tcp from 10.20.3.1, 8445/tcp from 10.20.4.1, 8484/tcp from 10.20.9.1, 8484/tcp from 10.20.9.2, 8484/tcp from 10.20.0.2, 8484/tcp from 10.20.1.1, 8484/tcp from 10.20.1.2, 8484/tcp from 10.20.2.1, 8484/tcp from 10.20.2.2, 8484/tcp from 10.20.3.1, 8484/tcp from 10.20.4.1',
    },
    'locked_out_except_desk01': {
        'app001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.1.1, 8001:8099/tcp from 10.20.1.2, 8001:8099/tcp from 10.20.4.1',
        'app002': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.1.1, 8001:8099/tcp from 10.20.1.2, 8001:8099/tcp from 10.20.4.1',
        'db01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'db02': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'jobs001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'lb01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'staging01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'util01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 8445/tcp from 10.20.9.1, 8445/tcp from 10.20.9.2, 8445/tcp from 10.20.0.2, 8445/tcp from 10.20.1.1, 8445/tcp from 10.20.1.2, 8445/tcp from 10.20.2.1, 8445/tcp from 10.20.2.2, 8445/tcp from 10.20.3.1, 8445/tcp from 10.20.4.1, 8484/tcp from 10.20.9.1, 8484/tcp from 10.20.9.2, 8484/tcp from 10.20.0.2, 8484/tcp from 10.20.1.1, 8484/tcp from 10.20.1.2, 8484/tcp from 10.20.2.1, 8484/tcp from 10.20.2.2, 8484/tcp from 10.20.3.1, 8484/tcp from 10.20.4.1',
    },
    'tunnel_setting_true': {
        'app001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.4.1',
        'app002': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 8001:8099/tcp from 10.20.4.1',
        'db01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'db02': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1, 5432/tcp from 10.20.1.1, 5432/tcp from 10.20.1.2, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 5432/tcp from 10.20.0.1, 5432/tcp from 10.20.3.1, 6432/tcp from 10.20.1.1, 6432/tcp from 10.20.1.2, 6432/tcp from 10.20.3.1',
        'jobs001': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'lb01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'staging01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 7443/tcp from 10.20.0.1',
        'util01': '22/tcp from 10.20.9.0/24, 22/tcp from 10.20.0.1, 51820/udp, 5432/tcp from 10.20.2.1, 5432/tcp from 10.20.2.2, 8445/tcp from 10.20.9.1, 8445/tcp from 10.20.9.2, 8445/tcp from 10.20.0.2, 8445/tcp from 10.20.1.1, 8445/tcp from 10.20.1.2, 8445/tcp from 10.20.2.1, 8445/tcp from 10.20.2.2, 8445/tcp from 10.20.3.1, 8445/tcp from 10.20.4.1, 8484/tcp from 10.20.9.1, 8484/tcp from 10.20.9.2, 8484/tcp from 10.20.0.2, 8484/tcp from 10.20.1.1, 8484/tcp from 10.20.1.2, 8484/tcp from 10.20.2.1, 8484/tcp from 10.20.2.2, 8484/tcp from 10.20.3.1, 8484/tcp from 10.20.4.1',
    },
}


def server_block(name, address):
    third, last = address.split('.')[2:]
    variables = {'public_ipv4_address': '203.0.113.%d' % (int(third) * 10 + int(last)),
                 'private_ip': address, 'wireguard_public_key': name.upper() + 'KEY'}
    if name.startswith('desk'):
        variables.update(person_unix_username=name.replace('desk', 'person'), production_ssh_public_key='ssh-ed25519 AAAA%s %s' % (name, name),
                         allowed_laptops=[{'laptop_name': name + '-laptop', 'wireguard_public_key': name.upper() + 'LAPTOP',
                                           'private_ip': '10.20.10.' + last, 'ssh_public_key': 'ssh-ed25519 AAAAlaptop ' + name}])
    return {'address': address, 'ssh_user': 'root', 'ssh_known_hosts': 'ssh/known_hosts', 'ssh_config': 'ssh/config', 'vars': variables}


def group_vars_of_the_template():
    """Each group's vars lines in the template's inventory, such as is_app_server: true."""
    text = (T/'inventories/servers.yml').read_text()
    result, name, in_vars = {}, None, False
    for line in text[text.index('\ngroups:\n'):].splitlines():
        if re.match(r'^  (\w+):\s*$', line):
            name, in_vars = line.strip()[:-1], False
        elif re.match(r'^    vars:\s*$', line):
            in_vars = True
        elif re.match(r'^    \w', line):
            in_vars = False
        elif in_vars and line.startswith('      '):
            result.setdefault(name, []).append(line)
    return result


def make_project(root, state='default', extra_vars='', extra_servers=None, extra_groups=None):
    """The template with the ten test servers. extra_groups: name -> (servers, vars lines)."""
    shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
    inventory = (root/'inventories/servers.yml').read_text()
    head = inventory[:inventory.index('\nnodes:\n')]
    overrides = ''.join('  %s: %s\n' % (k, json.dumps(v)) for k, v in STATES[state].items())
    head = head.replace('\nvars:\n', '\nvars:\n' + overrides, 1)
    head = head.replace('\n  connections_between_server_pools:\n', '\n  connections_between_server_pools:\n' + extra_vars, 1)
    servers = {n: server_block(n, ip) for n, (_, ip) in SERVERS.items()}
    servers.update(extra_servers or {})
    members = {}
    for n, (pool, _) in SERVERS.items():
        members.setdefault(pool, []).append(n)
    members['database_restore_servers'] = []
    group_vars = group_vars_of_the_template()
    for name, (names, lines) in (extra_groups or {}).items():
        members[name] = names
        group_vars[name] = lines.splitlines()
    text = head + '\nnodes:\n' + ''.join('  %s: %s\n' % (n, json.dumps(b)) for n, b in servers.items()) + '\ngroups:\n'
    for name, names in members.items():
        text += '  %s:\n    nodes: %s\n' % (name, json.dumps(names))
        if group_vars.get(name):
            text += '    vars:\n' + '\n'.join(group_vars[name]) + '\n'
    (root/'inventories/servers.yml').write_text(text)


class ServerConnections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX playbooks and templates.')

    def explain(self, root, *arguments):
        result = subprocess.run([self.mmx, 'explain', *arguments, '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def program_environments(self, root, *arguments):
        """Each server's environment for the role's program, as the playbook resolves it."""
        environments = {}
        for stage in self.explain(root, *arguments)['fleet_stages']:
            for task in stage.get('node_tasks') or []:
                if task['path'].endswith('/work_out_the_peers_and_the_firewall_rules') and stage['path'] in (
                        'every_server', 'systems_desk', 'cut_off_untrusted_server_access'):
                    environment = {}
                    for argument in task['arguments']:
                        if argument['field'].startswith('shell.env.'):
                            value = argument['value']
                            environment[argument['field'][len('shell.env.'):]] = value if isinstance(value, str) else json.dumps(value)
                    environments[task['node']] = environment
        return environments

    def run_program(self, environment):
        result = subprocess.run(['python3', '-I', '-c', environment['PROGRAM']], env=dict(environment, PATH=os.environ['PATH']),
                                text=True, capture_output=True)
        return result

    def outputs(self, environment):
        result = self.run_program(environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def outputs_of_every_server(self, state='default', **changes):
        """Each server's program outputs, from every_server."""
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)/'systems'
            make_project(root, state, **changes)
            environments = self.program_environments(root, 'every_server')
        return {name: (self.outputs(environment), environment) for name, environment in environments.items()}

    def rendered_peers(self, outputs, state):
        """The peer comments of wg0 as the real template renders it, for every server at once."""
        nodes = {n: {'vars': server_block(n, ip)['vars']} for n, (_, ip) in SERVERS.items()}
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            project_vars = dict(inventory_nodes=nodes, wireguard_listen_port=51820, database_moving_in=STATES[state].get('database_moving_in', {}))
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=project_vars)))
            servers = {}
            for name, (output, _) in outputs.items():
                server_vars = dict(wireguard_peer_names=output['wireguard_peer_names'],
                                   peers_with_the_database_moving_in=output['peers_with_the_database_moving_in'])
                servers[name] = {'address': '127.0.0.1', 'vars': server_vars}
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes=servers)))
            (root/'source.template').write_text((T/'roles/every_server/files/wireguard_wg0.conf').read_text().replace('.inputs', '.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            tasks = self.explain(root, 'render')['fleet_stages'][0]['node_tasks']
        peers = {}
        for task in tasks:
            text = task['rendered_templates'][0]['text']
            self.assertIn('\nListenPort = 51820\n', text)
            names = re.findall(r'^# (\S+)$', text, re.M)
            if '# The old database, only while its data moves into the Stack.' in text:
                names.append('the old database')
            peers[task['node']] = ' '.join(names)
        return peers

    @staticmethod
    def rule_texts(rules):
        texts = []
        for rule in rules:
            assert rule['action'] == 'allow' and rule.get('incoming_interface') in (None, 'wg0'), rule
            texts.append('%s/%s' % (rule['port'], rule['protocol']) + (' from ' + rule['from'] if 'from' in rule else ''))
        return texts

    def test_every_server_keeps_the_peers_and_firewall_rules_it_had_before_the_table(self):
        for state in STATES:
            with self.subTest(state=state):
                outputs = self.outputs_of_every_server(state)
                servers = {n for n, (pool, _) in SERVERS.items() if pool != 'systems_desks'}
                self.assertEqual(set(outputs), servers)
                self.assertEqual(self.rendered_peers(outputs, state),
                                 {n: peers for n, peers in PEERS_BEFORE_THE_TABLE[state].items() if n in servers})
                for name, before in FIREWALL_BEFORE_THE_TABLE[state].items():
                    with self.subTest(server=name):
                        after = self.rule_texts(outputs[name][0]['incoming_firewall_rules'])
                        if name in RULES_MAY_BE_REORDERED:
                            self.assertEqual(sorted(after), sorted(before.split(', ')))
                        else:
                            self.assertEqual(after, before.split(', '))

    def test_the_lock_out_button_gives_each_server_the_peers_every_server_gives(self):
        state = 'locked_out_except_desk01'
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)/'systems'
            make_project(root, state)
            environments = self.program_environments(root, 'lock_everyone_out', '--var', 'desk_name=desk01')
        servers = {n for n, (pool, _) in SERVERS.items() if pool != 'systems_desks'}
        self.assertEqual(set(environments), servers)
        every_server = self.outputs_of_every_server(state)
        for name in servers:
            with self.subTest(server=name):
                peers = self.outputs(environments[name])['wireguard_peer_names']
                self.assertEqual(peers, every_server[name][0]['wireguard_peer_names'])
                self.assertNotIn('desk02', peers)
                self.assertIn('desk01', peers)

    def test_a_new_pool_needs_only_its_group_block_lines_and_check_file(self):
        # The two pools of the design's example: cache servers that the app
        # servers connect to, and report workers that connect to Postgres.
        # Each pool's group names its own MMWatchdog check file; no role or
        # playbook changes.
        lines = ('    - {from_pool: app_servers, to_pool: cache_servers, tcp_ports: [11211], why: The apps cache pages in memcached.}\n'
                 '    - {from_pool: report_workers, to_pool: database_servers, tcp_ports: [5432], why: The report workers read Postgres.}\n')
        new_servers = {'cache001': server_block('cache001', '10.20.5.1'), 'report001': server_block('report001', '10.20.6.1')}
        groups = {'cache_servers': (['cache001'], '      mmwatchdog_check_file: cache_servers.yml'),
                  'report_workers': (['report001'], '      mmwatchdog_check_file: report_workers.yml')}
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)/'systems'
            make_project(root, extra_vars=lines, extra_servers=new_servers, extra_groups=groups)
            inventory = (root/'inventories/servers.yml').read_text().replace(
                '    load_balancer_servers: 10.20.4.0/24\n',
                '    load_balancer_servers: 10.20.4.0/24\n    cache_servers: 10.20.5.0/24\n    report_workers: 10.20.6.0/24\n', 1)
            (root/'inventories/servers.yml').write_text(inventory)
            for pool in ('cache_servers', 'report_workers'):
                (root/'mmwatchdog_checks'/(pool + '.yml')).write_text((T/'mmwatchdog_checks/jobs_servers.yml').read_text())
            installed = self.installed_check_files(root)
            environments = self.program_environments(root, 'every_server')
        after = {name: self.outputs(environment) for name, environment in environments.items()}
        before = {name: output for name, (output, _) in self.outputs_of_every_server().items()}
        desks, apps, databases = {'desk01', 'desk02'}, {'app001', 'app002'}, {'db01', 'db02'}

        def new_peers(name):
            return set(after[name]['wireguard_peer_names']) - set(before[name]['wireguard_peer_names'])

        def new_rules(name):
            return [r for r in self.rule_texts(after[name]['incoming_firewall_rules'])
                    if r not in self.rule_texts(before[name]['incoming_firewall_rules'])]

        self.assertEqual(set(after['cache001']['wireguard_peer_names']), desks | apps | {'util01'})
        self.assertEqual(self.rule_texts(after['cache001']['incoming_firewall_rules']),
                         ['22/tcp from 10.20.9.0/24', '22/tcp from 10.20.0.1', '51820/udp', '7443/tcp from 10.20.0.1',
                          '11211/tcp from 10.20.1.1', '11211/tcp from 10.20.1.2'])
        self.assertEqual(set(after['report001']['wireguard_peer_names']), desks | databases | {'util01'})
        self.assertEqual(self.rule_texts(after['report001']['incoming_firewall_rules']),
                         ['22/tcp from 10.20.9.0/24', '22/tcp from 10.20.0.1', '51820/udp', '7443/tcp from 10.20.0.1'])
        expected = {
            'app001': ({'cache001'}, []), 'app002': ({'cache001'}, []),
            'db01': ({'report001'}, ['5432/tcp from 10.20.6.1']), 'db02': ({'report001'}, ['5432/tcp from 10.20.6.1']),
            'util01': ({'cache001', 'report001'}, ['8445/tcp from 10.20.5.1', '8445/tcp from 10.20.6.1',
                                                   '8484/tcp from 10.20.5.1', '8484/tcp from 10.20.6.1']),
            'staging01': (set(), []), 'jobs001': (set(), []), 'lb01': (set(), []),
        }
        for name, (peers, rules) in expected.items():
            with self.subTest(server=name):
                self.assertEqual(new_peers(name), peers)
                self.assertEqual(new_rules(name), rules)
                self.assertEqual(set(before[name]['wireguard_peer_names']) - set(after[name]['wireguard_peer_names']), set())
        self.assertEqual(installed['cache001'], {'every_server.yml', 'cache_servers.yml'})
        self.assertEqual(installed['report001'], {'every_server.yml', 'report_workers.yml'})
        self.assertEqual(installed['app001'], {'every_server.yml', 'app_servers.yml'})
        self.assertEqual(installed['staging01'], {'every_server.yml', 'database_servers.yml'})

    def installed_check_files(self, root):
        """The check files mmwatchdog_joined_node installs on each server in
        every_server's last MMWatchdog stage on that server."""
        installed = {}
        for stage in self.explain(root, 'every_server')['fleet_stages']:
            if not stage['path'].startswith('mmwatchdog_joins_the_fleet_hub_after_the_roles'):
                continue
            for task in stage.get('node_tasks') or []:
                if '/install_the_check_groups_of_' in task['path']:
                    path = next(a['value'] for a in task['arguments'] if a['field'] == 'file.path')
                    installed.setdefault(task['node'], set()).add(path.rsplit('/', 1)[1])
        return installed

    def refusal(self, change):
        """Run app001's program with one inventory mistake; return its error text."""
        environment = dict(self.outputs_of_every_server()['app001'][1])
        values = {k: json.loads(environment[k]) for k in ('INVENTORY_NODES', 'INVENTORY_GROUPS', 'PRIVATE_IP_RANGES',
                                                            'CONNECTIONS_BETWEEN_SERVER_POOLS', 'SETTINGS_NAMED_IN_THE_CONNECTIONS')}
        change(values)
        environment.update({k: json.dumps(v) for k, v in values.items()})
        result = self.run_program(environment)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout, '')
        self.assertTrue(result.stderr.endswith('Nothing changed.\n'), result.stderr)
        return result.stderr

    def test_mistakes_in_the_pools_or_the_table_are_refused_before_any_change(self):
        def add_cache_server(v, block=True, private_ip='10.20.5.1'):
            v['INVENTORY_NODES']['cache001'] = {'vars': {'private_ip': private_ip, 'wireguard_public_key': 'CACHEKEY'}}
            v['INVENTORY_GROUPS']['cache_servers'] = ['cache001']
            if block:
                v['PRIVATE_IP_RANGES']['cache_servers'] = '10.20.5.0/24'

        def line(**changes):
            entry = dict(from_pool='app_servers', to_pool='database_servers', tcp_ports=[5432], why='Postgres.')
            entry.update(changes)
            return lambda v: v['CONNECTIONS_BETWEEN_SERVER_POOLS'].append({k: x for k, x in entry.items() if x is not None})

        cases = {
            'a line naming a pool with a typo': (lambda v: (add_cache_server(v), line(to_pool='cache_server')(v)),
                                                 "to_pool is 'cache_server', which is not a server pool"),
            'a server outside its pool\'s block': (lambda v: add_cache_server(v, private_ip='10.20.1.9'),
                                                   'cache001 has private_ip 10.20.1.9, outside its pool cache_servers'),
            'a group with no address block': (lambda v: add_cache_server(v, block=False), 'cache001 is in no server pool'),
            'a server in two pools': (lambda v: v['INVENTORY_GROUPS']['jobs_servers'].append('app002'),
                                      'app002 is in two server pools'),
            'a line with no why': (line(why=' '), 'has no why'),
            'a port that is neither a number nor a range': (line(tcp_ports=['8001-8099']), 'tcp_ports is'),
            'a misspelt key': (line(tcp_port=[5432]), 'has the key tcp_port'),
            'a setting the playbooks do not pass': (line(only_while_this_setting_is_false='a_setting_nobody_passes'),
                                                    'which the playbooks do not pass in settings_named_in_the_connections'),
            'a line into a systems desk': (line(to_pool='systems_desks'), 'to_pool cannot be systems_desks'),
        }
        for case, (change, message) in cases.items():
            with self.subTest(case=case):
                self.assertIn(message, self.refusal(change))

    def test_the_validation_stage_runs_the_same_role_on_util01_before_any_server_changes(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        stages = re.findall(r'(?m)^  - id: (\w+)', playbook)
        self.assertLess(stages.index('validate_the_connections_between_server_pools'), stages.index('every_server'))
        stage = playbook[playbook.index('  - id: validate_the_connections_between_server_pools'):]
        stage = stage[:stage.index('\n  - id: ', 1)]
        self.assertIn('nodes: util_server', stage)
        self.assertIn('on_node_failure: stop_run', stage)
        self.assertIn('role: work_out_who_this_server_talks_to', stage)


if __name__ == '__main__':
    unittest.main()
