#!/usr/bin/env python3
"""replace_failed_servers replaces only what it may, and leaves a record.

  MMX_BINARY=/path/to/mmx python3 tests/replace_failed_servers_test.py

The test copies the template into a Git repository with a bare "Git host"
beside it, takes the program's env from `mmx explain replace_failed_servers
--json` of that copy, writes the fleet hub's answer, and runs
server_management_scripts/replace_failed_servers with stand-in commands for
the provider scripts, ssh and wg. Git and `mmx validate` are real, so the
pushed inventory must pass MMX's own checks. It needs Python 3, bash 4 or
later, git and jq.

It checks the target choice (a silent server; a server the hub does not
list; a planned maintenance window; the window of a failed reboot by
reboot_servers_after_updates; waiting_for_first_report), the bound of more
than half silent at 1 of 2 and 2 of 2, each refusal with nothing created or
powered off, the next name above the Git history and the provider's list,
the inventory change and the Git trailers, a one-time playbook moved, a
moved main redone, a third refused push destroying the created server by
its ID only, try 2 and its refusal, and a pool that failed again within the
hours. For jobs servers and load-balancer servers it checks the name with
the pool's digits and the address in the pool's block, the inventory edit
(real `mmx validate`), the only jobs server replaced while only the jobs
servers run the jobs, a load-balancer server replaced beside its partner, a
new load-balancer server that never joined the hub replaced as try 2, a
pool not listed, a pool above its largest number, and a database server
listed by mistake. It also runs read_the_fleet_hub_for_server_replacement,
which waits for a server whose reboot may still be under way.
"""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
T = ROOT/'skills/monkeymaxxing-stack/systems_repository_template'
NEW_KEY = 'PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0='

FAKE = r'''import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as file:
    file.write(json.dumps([name, *args]) + '\n')
if name == 'list_the_servers_at_the_provider':
    print(os.environ.get('PROVIDER_SERVERS', '{"servers": []}'))
    sys.exit(int(os.environ.get('LIST_EXIT', '0')))
elif name == 'power_off_a_server_at_the_provider':
    assert args[0] == '--server-id' and len(args) == 2, args
    print(json.dumps({'id': args[1], 'power_state': 'stopped'}))
    sys.exit(int(os.environ.get('POWER_OFF_EXIT', '0')))
elif name == 'create_a_server_at_the_provider':
    new = args[args.index('--server-name') + 1]
    first_boot = pathlib.Path(args[args.index('--first-boot-data') + 1]).read_text()
    assert '#cloud-config' in first_boot
    receipt = {'id': 'created-' + new, 'name': new, 'public_ipv4_address': '203.0.113.200',
               'server_type': args[args.index('--server-type') + 1], 'location': args[args.index('--location') + 1]}
    pathlib.Path(args[args.index('--ownership-file') + 1]).write_text(json.dumps(receipt))
    print(json.dumps(receipt))
    sys.exit(int(os.environ.get('CREATE_EXIT', '0')))
elif name == 'destroy_a_server_at_the_provider':
    sys.exit(int(os.environ.get('DESTROY_EXIT', '0')))
elif name == 'wg':
    print('QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' if args == ['genkey'] else os.environ['NEW_KEY'])
elif name == 'ssh':
    target = next(a for a in args if a.startswith('root@'))
    if 'wg' in args:
        assert args[:4] == ['-F', 'ssh/config', 'root@10.20.0.1', 'wg'], args
    elif 'StrictHostKeyChecking=accept-new' in args:
        with open('ssh/known_hosts', 'a') as file:
            file.write(target[5:] + ' ssh-ed25519 new-host-key\n')
    elif args[-1] == '/usr/local/bin/check-that-this-server-does-its-work':
        if target[5:] in os.environ.get('NOT_WORKING', '').split(','):
            print('shop does not answer its health URL'); sys.exit(1)
    else:
        sys.exit('unexpected ssh ' + repr(args))
elif name == 'mmx' and args[:1] == ['mark-node-work-failed']:
    # mmx mark-node-work-failed exits: 0 recorded or nothing unconfirmed, 2 the server answered, 3 could not tell, 4 an error.
    assert args[1] == '--node' and args[3:] == ['--json', '--non-interactive'], args
    assert os.environ['MMX_VAULT_PASSWORD_FILE']
    code = int(os.environ.get('MARK_EXIT', '0'))
    print(json.dumps({'schema_version': 1, 'node': args[2], 'reason': 'the team says this server is gone', 'runs': []}) if code == 0
          else 'MMX said something went wrong with ' + args[2])
    sys.exit(code)
elif name == 'mmx':
    assert args == ['validate'], args
    if os.environ.get('DESK_PUSHES_ONCE') and not pathlib.Path(os.environ['DESK_PUSHES_ONCE']).exists():
        pathlib.Path(os.environ['DESK_PUSHES_ONCE']).write_text('')
        desk = os.environ['DESK_CLONE']
        subprocess.run(['git', '-C', desk, 'pull', '--quiet'], check=True)
        with open(desk + '/README.md', 'a') as file: file.write('\nA desk change.\n')
        subprocess.run(['git', '-C', desk, 'commit', '--quiet', '-am', 'A desk change'], check=True)
        subprocess.run(['git', '-C', desk, 'push', '--quiet'], check=True)
    os.execv(os.environ['REAL_MMX'], ['mmx', 'validate'])
else:
    sys.exit('unexpected command ' + name)
'''


def git(directory, *arguments, **settings):
    return subprocess.run(['git', '-C', str(directory), *arguments], check=True, text=True,
                          capture_output=True, stdin=subprocess.DEVNULL, **settings).stdout


def stamp(seconds_ago):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds_ago)).strftime('%Y-%m-%dT%H:%M:%S.123456789Z')


def node(name, state='reporting', seconds_since_report=5, window=None):
    entry = {'name': name, 'state': state, 'exit_code': 1 if state == 'silent' else 0,
             'last_report_received_at': stamp(seconds_since_report), 'report': {}}
    if window:
        entry['report']['maintenance'] = {'every_check_group': window}
    return entry


def window(reason, minutes_left=10):
    return {'until': stamp(-60 * minutes_left), 'reason': reason, 'user': 'root', 'without_maintenance_on_and_off_alerts': False}


# The third number of each pool's address block in the template's inventory.
POOL_BLOCKS = {'app_servers': 1, 'jobs_servers': 3, 'load_balancer_servers': 4}
REBOOT_REASON = 'reboot_servers_after_updates: waits 10m for the server to come back'
APP001_AT_THE_PROVIDER = {'id': 'id-app001', 'name': 'app001', 'public_ipv4_address': '203.0.113.11', 'power_state': 'running'}
# util01, the machine the programs run on, at its inventory address: in every list of this system's servers.
UTIL01_AT_THE_PROVIDER = {'id': 'id-util01', 'name': 'util01', 'public_ipv4_address': '203.0.113.1', 'power_state': 'running'}


class ReplaceFailedServers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to validate the changed inventory with MMX.')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = self.root = Path(self.temporary.name)
        self.state = root/'state'; self.state.mkdir()
        self.origin = root/'origin.git'
        git(root, 'init', '--quiet', '--bare', '--initial-branch=main', str(self.origin))
        self.gitconfig = root/'gitconfig'
        self.gitconfig.write_text('[user]\n\tname = util01, the mmhotline user\n\temail = mmhotline@util01.invalid\n[commit]\n\tgpgsign = false\n')
        os.environ['GIT_CONFIG_GLOBAL'] = str(self.gitconfig)
        self.repository = root/'repository'
        shutil.copytree(T, self.repository)
        template_values.fill_the_values_the_setup_fills(self.repository)
        steps = self.repository/'server_management_scripts/steps_for_replacing_failed_servers.bash'
        steps.write_text(steps.read_text().replace('/var/lib/replace_failed_servers', str(self.state)))
        (self.repository/'one_time_playbooks/completed').mkdir(parents=True)
        (self.repository/'one_time_playbooks/completed/.keep').write_text('')
        self.binary = root/'bin'; self.binary.mkdir()
        for name in ('wg', 'ssh', 'mmx'):
            self.fake(self.binary/name)
        for name in ('list_the_servers_at_the_provider', 'create_a_server_at_the_provider',
                     'power_off_a_server_at_the_provider', 'destroy_a_server_at_the_provider'):
            self.fake(self.repository/'server_management_scripts'/name)
        git(self.repository, 'init', '--quiet', '--initial-branch=main')
        git(self.repository, 'remote', 'add', 'origin', str(self.origin))
        self.commit_all('The systems repository')
        self.log = root/'commands'

    def tearDown(self):
        os.environ.pop('GIT_CONFIG_GLOBAL', None)
        self.temporary.cleanup()

    def fake(self, path):
        path.write_text('#!' + sys.executable + '\n' + FAKE)
        path.chmod(0o755)

    def commit_all(self, message):
        git(self.repository, 'add', '-A')
        git(self.repository, 'commit', '--quiet', '--allow-empty', '-m', message)
        git(self.repository, 'push', '--quiet', 'origin', 'main')

    def edit_inventory(self, old, new):
        path = self.repository/'inventories/servers.yml'
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def add_app_server(self, name, number):
        self.add_server('app_servers', name, number)

    def add_server(self, pool, name, number):
        """A server added by hand, as "Add a server" adds it, at its pool's address block."""
        block = POOL_BLOCKS[pool]
        self.edit_inventory('  db01:\n', f'''  {name}:
    address: 10.20.{block}.{number}
    https_address: https://10.20.{block}.{number}:7443
    ssh_user: root
    ssh_known_hosts: ssh/known_hosts
    ssh_config: ssh/config
    vars:
      public_ipv4_address: 203.0.113.{100 + 10 * block + number}
      server_type: cx33
      location: fsn1
      private_ip: 10.20.{block}.{number}
      wireguard_public_key: "{'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm'}{block}{number:02d}0="

  db01:
''')
        groups = re.search(rf'  {pool}:\n    nodes: \[(.*)\]', (self.repository/'inventories/servers.yml').read_text())[1]
        self.edit_inventory(f'  {pool}:\n    nodes: [{groups}]', f'  {pool}:\n    nodes: [{groups + ", " if groups else ""}{name}]')

    def replacement_commit(self, replaced, replaced_id, replacement, number, try_number, pool='app_servers'):
        """A pushed replacement, as replace_failed_servers makes it."""
        block = POOL_BLOCKS[pool]
        text = (self.repository/'inventories/servers.yml').read_text()
        old_block = re.search(rf'(?ms)^  {replaced}:\n.*?\n\n', text)[0]
        new_block = re.sub(rf'\b{replaced}\b', replacement, old_block)
        new_block = re.sub(rf'10\.20\.{block}\.\d+', f'10.20.{block}.{number}', new_block)
        text = text.replace(old_block, new_block)
        text = re.sub(rf'(nodes: \[[^]]*)\b{replaced}\b', rf'\g<1>{replacement}', text)
        (self.repository/'inventories/servers.yml').write_text(text)
        self.commit_all(f'Replace {replaced} with {replacement}\n\n'
                        f'Server-pool: {pool}\nReplaced-server: {replaced}\nReplaced-server-provider-id: {replaced_id}\n'
                        f'Replacement-server: {replacement}\nReplacement-server-provider-id: created-{replacement}\n'
                        f'Replacement-try: {try_number}')

    def env(self, **settings):
        result = subprocess.run([self.mmx, 'explain', 'replace_failed_servers', '--json'], cwd=self.repository,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][1]
        env = {}
        for item in task['arguments']:
            if item['field'].startswith('shell.env.'):
                value = item['value']
                env[item['field'][10:]] = value if isinstance(value, str) else json.dumps(value) if value is not None else 'stand-in token'
        env['SYSTEMS_REPOSITORY_SSH_URL'] = str(self.origin)
        for key, value in settings.items():
            if key in ('SERVER_WORK', 'GROWTH_LIMITS'):
                merged = json.loads(env[key]); merged.update(value); value = json.dumps(merged)
            env[key] = value
        return env

    def run_program(self, fleet, provider=(APP001_AT_THE_PROVIDER,), util01_listed=True, **settings):
        (self.state/'fleet.json').write_text(json.dumps({'nodes': fleet}))
        env = {**os.environ, **self.env(**settings),
               'PATH': f'{self.binary}:{os.environ["PATH"]}', 'COMMAND_LOG': str(self.log), 'NEW_KEY': NEW_KEY,
               'REAL_MMX': self.mmx,
               'PROVIDER_SERVERS': json.dumps({'servers': [UTIL01_AT_THE_PROVIDER] * util01_listed + list(provider)})}
        result = subprocess.run(['bash', str(self.repository/'server_management_scripts/replace_failed_servers')],
                                cwd=self.repository, env=env, text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=120)
        commands = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, commands

    def main_at_the_git_host(self, path='inventories/servers.yml'):
        return git(self.origin, 'show', f'main:{path}')

    def assert_nothing_happened(self, result, commands, text):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(text, result.stdout)
        self.assertIn('nothing created, powered off or committed', result.stdout)
        self.assertFalse([c for c in commands if c[0] in ('create_a_server_at_the_provider', 'power_off_a_server_at_the_provider',
                                                          'destroy_a_server_at_the_provider')], commands)
        self.assertEqual(git(self.origin, 'rev-list', '--count', 'main').strip(), '1')

    # The target choice.
    def test_a_silent_app_server_is_replaced_with_its_type_and_location(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(['power_off_a_server_at_the_provider', '--server-id', 'id-app001'], commands)
        create = next(c for c in commands if c[0] == 'create_a_server_at_the_provider')
        for flag, value in (('--server-name', 'app002'), ('--server-type', 'cx23'), ('--location', 'fsn1'),
                            ('--image', 'debian-13'), ('--ssh-key-name', 'util01-mmhotline-user'),
                            ('--wireguard-private-ip', '10.20.1.2'), ('--wireguard-public-key', NEW_KEY)):
            self.assertEqual(create[create.index(flag) + 1], value, flag)
        # The runtime peer comes before the create; the power-off before both.
        names = [c[0] if c[0] != 'ssh' else ' '.join(c[4:6]) for c in commands]
        self.assertLess(names.index('power_off_a_server_at_the_provider'), names.index('wg set'))
        self.assertLess(names.index('wg set'), names.index('create_a_server_at_the_provider'))
        self.assertNotIn('destroy_a_server_at_the_provider', names)
        inventory = self.main_at_the_git_host()
        self.assertIn('  app002:\n    address: 10.20.1.2\n    https_address: https://10.20.1.2:7443\n', inventory)
        for line in ('public_ipv4_address: 203.0.113.200', 'server_type: cx23', 'location: fsn1',
                     'private_ip: 10.20.1.2', f'wireguard_public_key: "{NEW_KEY}"'):
            self.assertIn(line, inventory)
        self.assertNotIn('app001', inventory)
        self.assertIn('  app_servers:\n    nodes: [app002]\n', inventory)
        self.assertIn('10.20.1.2 ssh-ed25519 new-host-key', self.main_at_the_git_host('ssh/known_hosts'))
        message = git(self.origin, 'log', '-1', '--format=%B', 'main')
        self.assertTrue(message.startswith('Replace app001 with app002\n'), message)
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main')
        self.assertEqual(trailers.strip().splitlines(), [
            'Server-pool: app_servers', 'Replaced-server: app001', 'Replaced-server-provider-id: id-app001',
            'Replacement-server: app002', 'Replacement-server-provider-id: created-app002', 'Replacement-try: 1'])
        self.assertEqual(git(self.origin, 'log', '-1', '--format=%an', 'main').strip(), 'util01, the mmhotline user')
        # The shared copy, at the judged commit, is never changed.
        self.assertIn('  app001:\n', (self.repository/'inventories/servers.yml').read_text())
        self.assertEqual(git(self.repository, 'status', '--porcelain'), '')
        # The last lines say what exists.
        self.assertIn('app002: at the provider (ID created-app002), and in the inventory in place of app001', result.stdout)
        self.assertIn('app001: still at the provider, powered off, until destroy_replaced_servers', result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith('then playbooks/destroy_replaced_servers.yml'), result.stdout)
        self.assertEqual(list(self.state.glob('attempt.*')), [])

    def test_the_last_lines_give_the_new_servers_monthly_price_or_say_it_is_missing(self):
        """The triage agent's last report names the new server's cost from these lines; a missing price never stops the run."""
        result, _ = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("app002 is cx23 in fsn1; its monthly price could not be read", result.stdout)
        self.setUp_again()
        price = self.repository/'server_management_scripts/read_the_monthly_price_at_the_provider'
        price.write_text('#!/bin/sh\necho \'{"server_type": "cx23", "location": "fsn1", "monthly_price": "7.49", "currency": "EUR"}\'\n')
        price.chmod(0o755)
        result, _ = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("app002, cx23 in fsn1, costs 7.49 EUR a month with its public address, at the provider's price now", result.stdout)

    def setUp_again(self):
        """A fresh copy, so that the next run starts from a main without the earlier replacement."""
        self.tearDown()
        self.setUp()

    def test_the_new_server_peers_with_util01_and_every_desk(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wireguard_peer = next(c for c in commands if c[0] == 'ssh' and 'allowed-ips' in c)
        self.assertEqual(wireguard_peer[-4:], ['peer', NEW_KEY, 'allowed-ips', '10.20.1.2/32'])

    def test_a_server_the_hub_does_not_list_is_never_a_target(self):
        result, commands = self.run_program([node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('app001 is not in the fleet hub yet', result.stdout)
        self.assertIn('nothing to replace: every server of app_servers, jobs_servers, load_balancer_servers reports', result.stdout)
        self.assertEqual(commands, [])

    def test_a_server_waiting_for_its_first_report_is_never_a_target(self):
        result, commands = self.run_program([node('app001', 'waiting_for_first_report', 600), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('nothing to replace', result.stdout)
        self.assertEqual(commands, [])

    def test_a_server_in_a_whole_server_maintenance_window_is_never_a_target(self):
        for reason in ('moving the disk by hand', 'reboot_servers_after_updates: waits for the server'):
            with self.subTest(reason=reason):
                result, commands = self.run_program([node('app001', 'silent', 3600, window(reason)), node('db01')])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f'app001 is silent in planned maintenance ({reason}): not a target', result.stdout)
                self.assertEqual(commands, [])

    def test_an_ended_window_no_longer_protects_a_silent_server(self):
        result, commands = self.run_program([node('app001', 'silent', 3600, window('moving the disk by hand', -1)), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('create_a_server_at_the_provider', [c[0] for c in commands])

    def test_a_server_silent_during_its_reboot_is_not_a_target_yet(self):
        # The reboot run waits 10 minutes, plus 2: silent for 11 minutes is not yet a failed reboot.
        result, commands = self.run_program([node('app001', 'silent', 11 * 60, window(REBOOT_REASON, 6)), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('app001 is silent during its reboot by reboot_servers_after_updates; its reboot counts as failed at', result.stdout)
        self.assertEqual(commands, [])

    def test_a_server_that_did_not_come_back_from_its_reboot_is_replaced(self):
        result, commands = self.run_program([node('app001', 'silent', 12 * 60 + 5, window(REBOOT_REASON, 5)), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(['power_off_a_server_at_the_provider', '--server-id', 'id-app001'], commands)
        self.assertIn('  app002:\n', self.main_at_the_git_host())

    # The bound and the refusals.
    def test_more_than_half_silent_is_refused(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01', 'silent', 120)])
        self.assert_nothing_happened(result, commands, '2 of 2 servers are silent at once, more than half')

    def test_two_of_three_silent_is_refused_and_one_of_three_is_replaced(self):
        self.add_app_server('app002', 2)
        self.commit_all('A second app server')
        result, commands = self.run_program([node('app001', 'silent', 120), node('app002', 'silent', 120), node('db01')])
        self.assert_nothing_happened_since(result, commands, '2 of 3 servers are silent at once', 2)
        result, commands = self.run_program([node('app001', 'silent', 120), node('app002'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('  app_servers:\n    nodes: [app003, app002]\n', self.main_at_the_git_host())

    def assert_nothing_happened_since(self, result, commands, text, commits):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(text, result.stdout)
        self.assertFalse([c for c in commands if c[0] in ('create_a_server_at_the_provider', 'power_off_a_server_at_the_provider')], commands)
        self.assertEqual(git(self.origin, 'rev-list', '--count', 'main').strip(), str(commits))
        self.log.unlink(missing_ok=True)

    def test_the_lock_out_is_refused(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')], EVERYONE_LOCKED_OUT_EXCEPT_DESK='desk01')
        self.assert_nothing_happened(result, commands, 'the lock-out is on (everyone_locked_out_except_desk: desk01)')

    def test_a_silent_database_server_is_left_to_a_person(self):
        result, commands = self.run_program([node('app001'), node('db01', 'silent', 120)])
        self.assert_nothing_happened(result, commands, 'db01 of database_servers stopped reporting')
        self.assertIn('a person replaces db01', result.stdout)

    def test_no_listed_pool_replaces_nothing(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')],
                                            SERVER_WORK={'pools_whose_failed_servers_the_triage_agent_replaces': []})
        self.assert_nothing_happened(result, commands, 'app001 of app_servers stopped reporting')

    def test_a_pool_above_its_largest_number_is_refused(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')],
                                            GROWTH_LIMITS={'app_servers': {'largest_number_of_servers': 0, 'server_types': ['cx33']}})
        self.assert_nothing_happened(result, commands, 'app_servers holds 1 servers, more than its largest number, 0')

    def test_a_server_type_outside_the_pools_types_is_refused(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')],
                                            GROWTH_LIMITS={'app_servers': {'largest_number_of_servers': 4, 'server_types': ['cx43']}})
        self.assert_nothing_happened(result, commands, 'app001 has the server type cx23, which is not in growth_limits.app_servers.server_types')

    def test_a_failed_provider_list_is_refused(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')], LIST_EXIT='1')
        self.assert_nothing_happened(result, commands, "the provider's list failed")

    def test_a_list_without_util01_is_refused(self):
        # 2026-11-12 at a real provider: a list script's filter matched no
        # server, and the program went on as if app001 were gone, without
        # powering it off.
        for provider, address in (((), '203.0.113.1'), ((APP001_AT_THE_PROVIDER,), '203.0.113.1'),
                                  ((APP001_AT_THE_PROVIDER, dict(UTIL01_AT_THE_PROVIDER, public_ipv4_address='198.51.100.7')), None)):
            with self.subTest(provider=provider):
                result, commands = self.run_program([node('app001', 'silent', 120), node('db01')], provider=provider, util01_listed=False)
                self.assert_nothing_happened(result, commands, "the provider's list does not hold util01, the server this program runs on")
                self.assertIn('list_the_servers_at_the_provider leaves servers out, or the provider API token belongs to another project',
                              result.stdout)

    def test_a_pool_that_failed_again_within_the_hours_is_refused(self):
        self.replacement_commit('app001', 'id-app001', 'app002', 2, 1)
        self.commit_all('Destroy app001 at the provider: app002 does its work\n\nServer-pool: app_servers\n'
                        'Destroyed-server: app001\nDestroyed-server-provider-id: id-app001')
        result, commands = self.run_program([node('app002', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('app_servers failed again: a replacement in app_servers finished within the last 24 hours', result.stdout)
        self.assertFalse([c for c in commands if c[0] != 'list_the_servers_at_the_provider'], commands)
        # With 0 hours, the same failure is replaced.
        result, commands = self.run_program([node('app002', 'silent', 120), node('db01')],
                                            SERVER_WORK={'hours_after_a_replacement_in_which_another_failure_of_the_pool_needs_a_person': 0})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Replacement-try: 1', git(self.origin, 'log', '-1', '--format=%B', 'main'))

    # Names.
    def test_the_name_is_above_the_git_history_and_the_providers_list(self):
        self.add_app_server('app012', 12)
        self.commit_all('Add app012')
        self.edit_inventory('  app012:\n', '  app012_gone:\n')
        text = (self.repository/'inventories/servers.yml').read_text()
        text = re.sub(r'(?ms)^  app012_gone:\n.*?\n\n', '', text).replace(', app012]', ']')
        (self.repository/'inventories/servers.yml').write_text(text)
        self.commit_all('Remove app012')
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('  app013:\n    address: 10.20.1.13\n', self.main_at_the_git_host())

    def test_a_desks_server_at_the_provider_not_yet_committed_counts_for_the_name(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')], provider=(
            APP001_AT_THE_PROVIDER, {'id': 'a-desk-server', 'name': 'app020', 'public_ipv4_address': '203.0.113.120', 'power_state': 'running'}))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('  app021:\n    address: 10.20.1.21\n', self.main_at_the_git_host())

    def test_a_one_time_playbook_that_names_the_failed_server_is_moved(self):
        (self.repository/'one_time_playbooks/2026-11-12_free_disk_space_on_app001.yml').write_text(
            'fleet_stages:\n  - id: free_disk_space\n    nodes: app001\n    node_tasks:\n      - id: clean\n        shell:\n          script: "true"\n          dryrun: "true"\n')
        self.commit_all('A one-time playbook for app001')
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        files = git(self.origin, 'ls-tree', '-r', '--name-only', 'main', 'one_time_playbooks')
        self.assertIn('one_time_playbooks/completed/2026-11-12_free_disk_space_on_app001.yml', files)
        self.assertNotIn('one_time_playbooks/2026-11-12_free_disk_space_on_app001.yml\n', files)

    # Pushes.
    def test_a_moved_main_is_redone_on_the_new_main(self):
        desk = self.root/'desk'
        git(self.root, 'clone', '--quiet', str(self.origin), str(desk))
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')],
                                            DESK_PUSHES_ONCE=str(self.root/'desk_pushed'), DESK_CLONE=str(desk))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('the main copy refused push 1 of 3 to main', result.stdout)
        subjects = git(self.origin, 'log', '--format=%s', 'main').splitlines()
        self.assertEqual(subjects[:2], ['Replace app001 with app002', 'A desk change'])
        self.assertIn('A desk change.', self.main_at_the_git_host('README.md'))
        self.assertEqual(len([c for c in commands if c[0] == 'create_a_server_at_the_provider']), 1)

    def test_a_third_refused_push_destroys_the_created_server_by_its_id_only(self):
        hook = self.origin/'hooks/pre-receive'
        hook.write_text('#!/bin/sh\necho "refused by the test" >&2\nexit 1\n'); hook.chmod(0o755)
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout.count('the main copy refused push'), 3, result.stdout)
        self.assertEqual([c for c in commands if c[0] == 'destroy_a_server_at_the_provider'],
                         [['destroy_a_server_at_the_provider', '--server-id', 'created-app002']])
        self.assertIn(['ssh', '-F', 'ssh/config', 'root@10.20.0.1', 'wg', 'set', 'wg0', 'peer', NEW_KEY, 'remove'], commands)
        self.assertIn('app002: created, then destroyed again, because its commit was not pushed', result.stdout)
        self.assertEqual(git(self.origin, 'rev-list', '--count', 'main').strip(), '1')

    def test_a_failed_create_leaves_nothing(self):
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')], CREATE_EXIT='1')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([c for c in commands if c[0] == 'destroy_a_server_at_the_provider'],
                         [['destroy_a_server_at_the_provider', '--server-id', 'created-app002']])
        self.assertEqual(git(self.origin, 'rev-list', '--count', 'main').strip(), '1')

    def test_a_failed_destroy_says_which_id_to_destroy(self):
        hook = self.origin/'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n'); hook.chmod(0o755)
        result, commands = self.run_program([node('app001', 'silent', 120), node('db01')], DESTROY_EXIT='1')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('app002: created and NOT destroyed: a person destroys it by the ID in', result.stdout)
        self.assertEqual(len(list(self.state.glob('attempt.*'))), 1)

    # Tries.
    def test_a_bad_new_server_is_replaced_as_try_2_and_try_3_is_refused(self):
        self.replacement_commit('app001', 'id-app001', 'app002', 2, 1)
        app002 = {'id': 'created-app002', 'name': 'app002', 'public_ipv4_address': '203.0.113.200', 'power_state': 'running'}
        result, commands = self.run_program([node('app002'), node('db01')], provider=(app002,), NOT_WORKING='10.20.1.2')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('app002, the new server of an unfinished replacement, does not do its work', result.stdout)
        # Powered off by the ID the trailer recorded, never by its name.
        self.assertIn(['power_off_a_server_at_the_provider', '--server-id', 'created-app002'], commands)
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main')
        self.assertIn('Replaced-server: app002\nReplaced-server-provider-id: created-app002\nReplacement-server: app003', trailers)
        self.assertIn('Replacement-try: 2', trailers)
        git(self.repository, 'pull', '--quiet', 'origin', 'main')
        self.log.unlink()
        result, commands = self.run_program([node('app003', 'silent', 120), node('db01')])
        self.assert_nothing_happened_since(result, commands, 'replacing app003 would be try 3, and tries_to_replace_a_failed_server is 2', 3)

    def test_a_new_server_that_does_its_work_is_no_target(self):
        self.replacement_commit('app001', 'id-app001', 'app002', 2, 1)
        result, commands = self.run_program([node('app002'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('nothing to replace', result.stdout)
        self.assertEqual([c[0] for c in commands], ['ssh'])

    def test_a_new_server_that_never_joined_the_hub_is_a_bad_new_server(self):
        self.replacement_commit('app001', 'id-app001', 'app002', 2, 1)
        result, commands = self.run_program([node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('app002, the new server of an unfinished replacement, has not joined the fleet hub', result.stdout)
        self.assertIn('Replacement-try: 2', git(self.origin, 'log', '-1', '--format=%B', 'main'))

    # Jobs servers and load-balancer servers.
    def assert_replaced(self, result, commands, pool, old, new, address, nodes):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(['power_off_a_server_at_the_provider', '--server-id', f'id-{old}'], commands)
        create = next(c for c in commands if c[0] == 'create_a_server_at_the_provider')
        for flag, value in (('--server-name', new), ('--server-type', 'cx33'), ('--location', 'fsn1'),
                            ('--wireguard-private-ip', address)):
            self.assertEqual(create[create.index(flag) + 1], value, flag)
        wireguard_peer = next(c for c in commands if c[0] == 'ssh' and 'allowed-ips' in c)
        self.assertEqual(wireguard_peer[-2:], ['allowed-ips', f'{address}/32'])
        inventory = self.main_at_the_git_host()
        self.assertIn(f'  {new}:\n    address: {address}\n    https_address: https://{address}:7443\n', inventory)
        for line in ('server_type: cx33', 'location: fsn1', f'private_ip: {address}', f'wireguard_public_key: "{NEW_KEY}"'):
            self.assertIn(line, inventory.split(f'  {new}:\n')[1].split('\n\n')[0])
        self.assertNotIn(f'  {old}:\n', inventory)
        self.assertIn(f'  {pool}:\n    nodes: [{nodes}]\n', inventory)
        self.assertIn(f'{address} ssh-ed25519 new-host-key', self.main_at_the_git_host('ssh/known_hosts'))
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main')
        self.assertEqual(trailers.strip().splitlines(), [
            f'Server-pool: {pool}', f'Replaced-server: {old}', f'Replaced-server-provider-id: id-{old}',
            f'Replacement-server: {new}', f'Replacement-server-provider-id: created-{new}', 'Replacement-try: 1'])
        self.assertIn(f'replaced {old} with {new}', result.stdout)

    def at_the_provider(self, name, address):
        return {'id': f'id-{name}', 'name': name, 'public_ipv4_address': address, 'power_state': 'running'}

    def test_the_only_jobs_server_is_replaced_while_only_the_jobs_servers_run_the_jobs(self):
        # remove_server refuses the last jobs server; a replacement never
        # removes a server, it puts the new one in its place in one commit.
        self.add_server('jobs_servers', 'jobs001', 1)
        settings = self.repository/'mmx_project_settings.yml'
        text = settings.read_text()
        self.assertIn('job_containers_run_only_on_the_jobs_servers: false\n', text)
        settings.write_text(text.replace('job_containers_run_only_on_the_jobs_servers: false\n',
                                         'job_containers_run_only_on_the_jobs_servers: true\n'))
        self.commit_all('jobs001, and only the jobs servers run the jobs')
        result, commands = self.run_program([node('app001'), node('db01'), node('jobs001', 'silent', 120)],
                                            provider=(APP001_AT_THE_PROVIDER, self.at_the_provider('jobs001', '203.0.113.131')))
        self.assert_replaced(result, commands, 'jobs_servers', 'jobs001', 'jobs002', '10.20.3.2', 'jobs002')

    def test_a_load_balancer_server_is_replaced_beside_its_partner(self):
        self.add_server('load_balancer_servers', 'lb01', 1)
        self.add_server('load_balancer_servers', 'lb02', 2)
        self.commit_all('lb01 and lb02')
        result, commands = self.run_program([node('app001'), node('db01'), node('lb01', 'silent', 120), node('lb02')],
                                            provider=(APP001_AT_THE_PROVIDER, self.at_the_provider('lb01', '203.0.113.141'),
                                                      self.at_the_provider('lb02', '203.0.113.142')))
        # Two digits, as the pool's names have, and one above lb02.
        self.assert_replaced(result, commands, 'load_balancer_servers', 'lb01', 'lb03', '10.20.4.3', 'lb03, lb02')
        self.assertIn('  lb02:\n    address: 10.20.4.2\n', self.main_at_the_git_host())
        self.assertNotIn(['power_off_a_server_at_the_provider', '--server-id', 'id-lb02'], commands)

    def test_a_new_load_balancer_server_that_never_joined_the_hub_is_replaced_as_try_2(self):
        # A load-balancer server joins the hub only once its tunnel connector runs.
        self.add_server('load_balancer_servers', 'lb01', 1)
        self.add_server('load_balancer_servers', 'lb02', 2)
        self.commit_all('lb01 and lb02')
        self.replacement_commit('lb01', 'id-lb01', 'lb03', 3, 1, pool='load_balancer_servers')
        lb03 = {'id': 'created-lb03', 'name': 'lb03', 'public_ipv4_address': '203.0.113.200', 'power_state': 'running'}
        result, commands = self.run_program([node('app001'), node('db01'), node('lb02')], provider=(lb03,))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('lb03, the new server of an unfinished replacement, has not joined the fleet hub', result.stdout)
        self.assertIn(['power_off_a_server_at_the_provider', '--server-id', 'created-lb03'], commands)
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main')
        self.assertIn('Server-pool: load_balancer_servers\nReplaced-server: lb03\nReplaced-server-provider-id: created-lb03\n'
                      'Replacement-server: lb04', trailers)
        self.assertIn('Replacement-try: 2', trailers)
        self.assertIn('  load_balancer_servers:\n    nodes: [lb04, lb02]\n', self.main_at_the_git_host())

    def test_a_jobs_server_of_a_pool_not_listed_is_refused(self):
        self.add_server('jobs_servers', 'jobs001', 1)
        self.commit_all('jobs001')
        result, commands = self.run_program([node('app001'), node('db01'), node('jobs001', 'silent', 120)],
                                            SERVER_WORK={'pools_whose_failed_servers_the_triage_agent_replaces': ['app_servers']})
        self.assert_nothing_happened_since(result, commands, 'jobs001 of jobs_servers stopped reporting, and the triage agent replaces failed servers only in app_servers', 2)

    def test_a_load_balancer_pool_above_its_largest_number_is_refused(self):
        self.add_server('load_balancer_servers', 'lb01', 1)
        self.add_server('load_balancer_servers', 'lb02', 2)
        self.commit_all('lb01 and lb02')
        result, commands = self.run_program([node('app001'), node('db01'), node('lb01', 'silent', 120), node('lb02')],
                                            GROWTH_LIMITS={'load_balancer_servers': {'largest_number_of_servers': 1, 'server_types': ['cx33']}})
        self.assert_nothing_happened_since(result, commands, 'load_balancer_servers holds 2 servers, more than its largest number, 1', 2)

    def test_a_database_server_listed_by_mistake_is_still_refused(self):
        # every_server refuses the setting; the program refuses too, for a
        # setting pushed and not yet applied.
        result, commands = self.run_program([node('app001'), node('db01', 'silent', 120)],
                                            SERVER_WORK={'pools_whose_failed_servers_the_triage_agent_replaces': ['app_servers', 'database_servers']})
        self.assert_nothing_happened(result, commands, 'replace_failed_servers replaces only app servers, jobs servers and load-balancer servers')


class ReadTheFleetHub(unittest.TestCase):
    """The root step waits for a server whose reboot may still be under way."""

    def run_reader(self, fleet):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root/'state'; state.mkdir()
            repository = root/'repository'; (repository/'server_management_scripts').mkdir(parents=True)
            for name in ('read_the_fleet_hub_for_server_replacement', 'steps_for_replacing_failed_servers.bash'):
                text = (T/'server_management_scripts'/name).read_text().replace('/var/lib/replace_failed_servers', str(state))
                text = text.replace('/usr/local/bin/mmwatchdog', 'mmwatchdog')
                (repository/'server_management_scripts'/name).write_text(text)
            binary = root/'bin'; binary.mkdir()
            log = root/'log'
            for name, body in (('mmwatchdog', f'echo mmwatchdog >> {log}\ncat {root}/fleet\nexit 1\n'),
                               ('sleep', f'echo "sleep $1" >> {log}\n'), ('chgrp', f'echo "chgrp $*" >> {log}\n')):
                (binary/name).write_text('#!/bin/bash\n' + body); (binary/name).chmod(0o755)
            (root/'fleet').write_text(json.dumps({'nodes': fleet}))
            result = subprocess.run(['bash', 'server_management_scripts/read_the_fleet_hub_for_server_replacement'],
                                    cwd=repository, env={**os.environ, 'PATH': f'{binary}:{os.environ["PATH"]}'},
                                    text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
            written = json.loads((state/'fleet.json').read_text()) if (state/'fleet.json').exists() else None
            return result, log.read_text().splitlines(), written

    def test_a_silent_server_without_a_reboot_window_is_read_once(self):
        result, log, written = self.run_reader([node('app001', 'silent', 120)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log[0], 'mmwatchdog')
        self.assertEqual([line for line in log if line.startswith(('mmwatchdog', 'sleep'))], ['mmwatchdog'])
        self.assertEqual(written['nodes'][0]['name'], 'app001')

    def test_a_server_silent_during_its_reboot_is_waited_for_then_read_again(self):
        result, log, written = self.run_reader([node('app001', 'silent', 10 * 60, window(REBOOT_REASON, 7))])
        self.assertEqual(result.returncode, 0, result.stderr)
        waits = [int(line.split()[1]) for line in log if line.startswith('sleep')]
        self.assertEqual(len(waits), 1)
        self.assertTrue(115 <= waits[0] <= 125, waits)   # 10 + 2 minutes after the last report, which was 10 minutes ago
        self.assertEqual(log.count('mmwatchdog'), 2)

    def test_a_hub_that_does_not_answer_writes_nothing(self):
        result, log, written = self.run_reader('not a list')
        self.assertEqual(result.returncode, 1)
        self.assertIn('the fleet hub did not answer', result.stdout)
        self.assertIsNone(written)


if __name__ == '__main__':
    unittest.main()
