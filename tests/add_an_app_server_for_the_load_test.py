#!/usr/bin/env python3
"""add_an_app_server_for_the_load adds one app server only when it may.

  MMX_BINARY=/path/to/mmx python3 tests/add_an_app_server_for_the_load_test.py

The test uses the stand-ins and the Git host of
tests/replace_failed_servers_test.py: it copies the template into a Git
repository with a bare "Git host" beside it, takes the program's env from
`mmx explain add_an_app_server_for_the_load --json`, writes the fleet hub's
answer and the load's decision, and runs
server_management_scripts/add_an_app_server_for_the_load with stand-ins for
the provider scripts, ssh and wg. Git and `mmx validate` are real.

It checks the add itself (the type and location of the pool's newest
server, the next name, the inventory change, the trailers, the price line,
the next request), "nothing to add", each refusal with nothing created (the
lock-out, a bound the load decision names, the largest number, a server
that does not report, an unfinished replacement, a type outside the pool's
types, the Postgres connection budget), and a third refused push that
destroys the created server by its ID only. It also runs
read_the_app_pool_load, which hands the decision program the inventory's
app servers and the settings.
"""
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replace_failed_servers_test as replacement  # noqa: E402

T = replacement.T
NEW_KEY = replacement.NEW_KEY
node = replacement.node
git = replacement.git

FAKE = replacement.FAKE.replace(
    "    elif args[-1] == '/usr/local/bin/check-that-this-server-does-its-work':",
    "    elif args[-1] == 'nproc':\n        print(os.environ.get('NPROC', '2'))\n"
    "    elif args[-1] == '/usr/local/bin/check-that-this-server-does-its-work':").replace(
    "else:\n    sys.exit('unexpected command ' + name)",
    "elif name == 'read_the_monthly_price_at_the_provider':\n"
    "    assert args[0] == '--server-type' and args[2] == '--location', args\n"
    "    print(json.dumps({'server_type': args[1], 'location': args[3], 'monthly_price': '7.49', 'currency': 'EUR'}))\n"
    "    sys.exit(int(os.environ.get('PRICE_EXIT', '0')))\n"
    "else:\n    sys.exit('unexpected command ' + name)")
assert "args[-1] == 'nproc'" in FAKE and 'read_the_monthly_price_at_the_provider' in FAKE

ADD = {'decision': 'add', 'why': "the app pool's CPU stayed above its limit of 70% for 15 minutes (app001 82%): add an app server",
       'app_servers': 1, 'cpu_limit_percent': 70}


class AddAnAppServerForTheLoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to validate the changed inventory with MMX.')

    tearDown = replacement.ReplaceFailedServers.tearDown
    commit_all = replacement.ReplaceFailedServers.commit_all
    edit_inventory = replacement.ReplaceFailedServers.edit_inventory
    add_app_server = replacement.ReplaceFailedServers.add_app_server
    add_server = replacement.ReplaceFailedServers.add_server
    replacement_commit = replacement.ReplaceFailedServers.replacement_commit
    main_at_the_git_host = replacement.ReplaceFailedServers.main_at_the_git_host

    def setUp(self):
        replacement.ReplaceFailedServers.setUp(self)
        for name in ('wg', 'ssh', 'mmx'):
            self.fake(self.binary/name)
        for name in ('list_the_servers_at_the_provider', 'create_a_server_at_the_provider', 'power_off_a_server_at_the_provider',
                     'destroy_a_server_at_the_provider', 'read_the_monthly_price_at_the_provider'):
            self.fake(self.repository/'server_management_scripts'/name)
        self.commit_all('The provider scripts')

    def fake(self, path):
        path.write_text('#!' + sys.executable + '\n' + FAKE)
        path.chmod(0o755)

    def env(self, **settings):
        result = subprocess.run([self.mmx, 'explain', 'add_an_app_server_for_the_load', '--json'], cwd=self.repository,
                                text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][2]
        env = {}
        for item in task['arguments']:
            if item['field'].startswith('shell.env.'):
                value = item['value']
                env[item['field'][10:]] = value if isinstance(value, str) else json.dumps(value) if value is not None else 'stand-in token'
        env['SYSTEMS_REPOSITORY_SSH_URL'] = str(self.origin)
        for key, value in settings.items():
            if key in ('GROWTH_LIMITS', 'APPS', 'APPS_CONNECT_THROUGH_PGBOUNCER'):
                merged = json.loads(env[key]); merged.update(value); value = json.dumps(merged)
            env[key] = value
        return env

    def run_program(self, fleet, load=ADD, provider=(), util01_listed=True, **settings):
        (self.state/'fleet.json').write_text(json.dumps({'nodes': fleet}))
        (self.state/'app_pool_for_the_load.json').write_text(json.dumps(load))
        env = {**os.environ, **self.env(**settings),
               'PATH': f'{self.binary}:{os.environ["PATH"]}', 'COMMAND_LOG': str(self.log), 'NEW_KEY': NEW_KEY,
               'REAL_MMX': self.mmx, 'PROVIDER_SERVERS': json.dumps({'servers': list(provider) + ([replacement.UTIL01_AT_THE_PROVIDER] if util01_listed else [])})}
        result = subprocess.run(['bash', str(self.repository/'server_management_scripts/add_an_app_server_for_the_load')],
                                cwd=self.repository, env=env, text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=120)
        commands = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        self.log.unlink(missing_ok=True)
        return result, commands

    def assert_refused(self, result, commands, text):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('add_an_app_server_for_the_load refuses: ' + text, result.stdout)
        self.assertIn('nothing created or committed', result.stdout)
        self.assertFalse([c for c in commands if c[0] in ('create_a_server_at_the_provider', 'destroy_a_server_at_the_provider')], commands)
        self.assertEqual(git(self.origin, 'log', '-1', '--format=%s', 'main').strip(), 'The provider scripts')

    def test_the_load_adds_one_server_like_the_newest(self):
        self.add_app_server('app003', 3)
        self.edit_inventory('  app003:\n    address: 10.20.1.3\n    https_address: https://10.20.1.3:7443\n    ssh_user: root\n'
                            '    ssh_known_hosts: ssh/known_hosts\n    ssh_config: ssh/config\n    vars:\n'
                            '      public_ipv4_address: 203.0.113.113\n      server_type: cx33\n      location: fsn1\n',
                            '  app003:\n    address: 10.20.1.3\n    https_address: https://10.20.1.3:7443\n    ssh_user: root\n'
                            '    ssh_known_hosts: ssh/known_hosts\n    ssh_config: ssh/config\n    vars:\n'
                            '      public_ipv4_address: 203.0.113.113\n      server_type: cx33\n      location: nbg1\n')
        self.commit_all('app003 in another location')
        result, commands = self.run_program([node('app001'), node('app003'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        create = next(c for c in commands if c[0] == 'create_a_server_at_the_provider')
        for flag, value in (('--server-name', 'app004'), ('--server-type', 'cx33'), ('--location', 'nbg1'),
                            ('--image', 'debian-13'), ('--wireguard-private-ip', '10.20.1.4'), ('--wireguard-public-key', NEW_KEY)):
            self.assertEqual(create[create.index(flag) + 1], value, flag)
        self.assertNotIn('power_off_a_server_at_the_provider', [c[0] for c in commands])
        inventory = self.main_at_the_git_host()
        self.assertIn('  app_servers:\n    nodes: [app001, app003, app004]\n', inventory)
        # The new block follows the pool's last server, and the rest of the inventory is unchanged.
        self.assertIn('      location: nbg1\n      private_ip: 10.20.1.3\n', inventory)
        self.assertRegex(inventory, r'(?s)  app003:\n.*?\n\n  app004:\n    address: 10.20.1.4\n.*?\n\n  db01:\n')
        self.assertIn('      server_type: cx33\n      location: nbg1\n      private_ip: 10.20.1.4\n', inventory)
        self.assertIn('10.20.1.4 ssh-ed25519 new-host-key', self.main_at_the_git_host('ssh/known_hosts'))
        self.assertEqual(git(self.origin, 'log', '-1', '--format=%s', 'main').strip(), 'Add app004 to app_servers for the load')
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main')
        self.assertEqual(trailers.strip().splitlines(), ['Server-pool: app_servers', 'Added-server: app004',
                                                         'Added-server-provider-id: created-app004'])
        self.assertIn('app004, cx33 in nbg1, costs 7.49 EUR a month with its public address', result.stdout)
        self.assertIn('app_servers holds 3 of at most 4 servers', result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith('which installs app004 and sends it requests'), result.stdout)
        self.assertEqual(git(self.repository, 'status', '--porcelain'), '')
        self.assertEqual(list(self.state.glob('attempt.*')), [])

    def test_the_inventory_after_an_add_passes_mmx_validate_and_the_one_server_pool_grows(self):
        result, commands = self.run_program([node('app001'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('  app_servers:\n    nodes: [app001, app002]\n', self.main_at_the_git_host())
        self.assertIn(['read_the_monthly_price_at_the_provider', '--server-type', 'cx23', '--location', 'fsn1'], commands)

    def test_a_price_that_cannot_be_read_does_not_stop_the_add(self):
        result, _ = self.run_program([node('app001'), node('db01')], PRICE_EXIT='1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('app002 is cx23 in fsn1; its monthly price could not be read', result.stdout)

    def test_no_load_adds_nothing(self):
        result, commands = self.run_program([node('app001'), node('db01')], load={
            'decision': 'none', 'why': "the app pool's CPU ... not above its limit of 70%: no app server to add"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('nothing to add: ', result.stdout)
        self.assertEqual(commands, [])

    def test_a_bound_the_load_decision_names_is_refused(self):
        result, commands = self.run_program([node('app001'), node('db01')], load={
            'decision': 'stopped_by_a_bound', 'why': 'the pool holds its largest number of servers, 1'})
        self.assert_refused(result, commands, 'the pool holds its largest number of servers, 1')

    def test_the_largest_number_is_refused(self):
        result, commands = self.run_program([node('app001'), node('db01')],
                                            GROWTH_LIMITS={'app_servers': {'smallest_number_of_servers': 1, 'largest_number_of_servers': 1,
                                                                           'server_types': ['cx23']}})
        self.assert_refused(result, commands, 'app_servers holds 1 servers, its largest number, 1')

    def test_the_lock_out_is_refused(self):
        result, commands = self.run_program([node('app001'), node('db01')], EVERYONE_LOCKED_OUT_EXCEPT_DESK='desk01')
        self.assert_refused(result, commands, 'the lock-out is on')

    def test_a_server_that_does_not_report_is_refused(self):
        for fleet, text in (([node('app001', 'silent', 300), node('db01')], 'app001 is silent'),
                            ([node('db01')], 'app001 is not in the fleet hub')):
            with self.subTest(text=text):
                result, commands = self.run_program(fleet)
                self.assert_refused(result, commands, text)

    def test_an_unfinished_replacement_is_refused(self):
        self.replacement_commit('app001', 'id-app001', 'app002', 2, 1)
        result, commands = self.run_program([node('app002'), node('db01')])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('the replacement of app001 by app002 in app_servers is unfinished', result.stdout)
        self.assertNotIn('create_a_server_at_the_provider', [c[0] for c in commands])

    def test_a_type_outside_the_pools_types_is_refused(self):
        result, commands = self.run_program([node('app001'), node('db01')],
                                            GROWTH_LIMITS={'app_servers': {'smallest_number_of_servers': 1, 'largest_number_of_servers': 4,
                                                                           'server_types': ['cx43']}})
        self.assert_refused(result, commands, 'the newest app server, app001, has the server type cx23, which is not in growth_limits.app_servers.server_types')

    def test_the_postgres_connection_budget(self):
        # The template's shop: 2 CPUs x 3 connections on two servers is 12, 24 during a deploy; jobs 3 x 2; 15: 45.
        result, _ = self.run_program([node('app001'), node('db01')])
        self.assertIn('Postgres connections with one more app server: 12 for the web containers, 24 during a deploy, '
                      '6 for the job containers and 15 for the system: 45, within 70', result.stdout)
        # 8 CPUs and 10 threads: 2 x 8 x 10 = 160, 320 during a deploy; jobs 10 x 2: 355. Refused, with the numbers.
        self.setUp_again()
        result, commands = self.run_program([node('app001'), node('db01')], NPROC='8',
                                            APPS={'shop': self.shop(env={'RAILS_ENV': 'production', 'RAILS_MAX_THREADS': '10'})})
        self.assert_refused(result, commands, 'with one more app server, the apps would open 160 for the web containers, 320 during a deploy, '
                                              '20 for the job containers and 15 for the system: 355: more than 70')
        self.assertIn('Add PgBouncer first (operating_procedures/add_pgbouncer.md)', result.stdout)
        # Through PgBouncer the apps share 54: 54 + 15 = 69, within the limit.
        result, _ = self.run_program([node('app001'), node('db01')], NPROC='8',
                                     APPS={'shop': self.shop(env={'RAILS_ENV': 'production', 'RAILS_MAX_THREADS': '10'})},
                                     PGBOUNCER_RUNS_IN_FRONT_OF_POSTGRES='true', APPS_CONNECT_THROUGH_PGBOUNCER={'production': True})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('54 through PgBouncer, 0 for the job containers and 15 for the system: 69, within 70', result.stdout)

    def test_an_apps_own_connections_per_worker_process_come_before_the_rails_rule(self):
        # A Node.js app's pool of 10, beside RAILS_MAX_THREADS 3: the setting counts.
        # 2 CPUs x 10 on two servers is 40, 80 during a deploy; jobs 10 x 2 is 20; 15: 115. Refused.
        result, commands = self.run_program([node('app001'), node('db01')], APPS={'shop': self.shop(
            database_connections_per_worker_process=10, env={'RAILS_ENV': 'production', 'RAILS_MAX_THREADS': '3'})})
        self.assert_refused(result, commands, 'with one more app server, the apps would open 40 for the web containers, 80 during a deploy, '
                                              '20 for the job containers and 15 for the system: 115: more than 70')

    def setUp_again(self):
        """A fresh copy, so that the next run starts from a main without the earlier add."""
        self.tearDown()
        self.setUp()

    def shop(self, **changes):
        apps = json.loads(self.env()['APPS'])
        return {**apps['shop'], **changes}

    def test_a_third_refused_push_destroys_the_created_server_by_its_id_only(self):
        hook = self.origin/'hooks/pre-receive'
        hook.write_text('#!/bin/sh\necho "refused by the test" >&2\nexit 1\n'); hook.chmod(0o755)
        result, commands = self.run_program([node('app001'), node('db01')])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([c for c in commands if c[0] == 'destroy_a_server_at_the_provider'],
                         [['destroy_a_server_at_the_provider', '--server-id', 'created-app002']])
        self.assertIn(['ssh', '-F', 'ssh/config', 'root@10.20.0.1', 'wg', 'set', 'wg0', 'peer', NEW_KEY, 'remove'], commands)
        self.assertIn('app002: created, then destroyed again, because its commit was not pushed', result.stdout)

    def test_the_name_is_above_the_providers_list(self):
        result, _ = self.run_program([node('app001'), node('db01')], provider=(
            {'id': 'a-desk-server', 'name': 'app020', 'public_ipv4_address': '203.0.113.120', 'power_state': 'running'},))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('  app021:\n    address: 10.20.1.21\n', self.main_at_the_git_host())


    def test_a_provider_list_without_util01_is_refused(self):
        """A partial list could hide a name in use; it is not this system's whole list."""
        result, commands = self.run_program([node('app001'), node('db01')], util01_listed=False)
        self.assert_refused(result, commands, "the provider's list does not hold util01")


class DatabaseConnectionsPerWorkerProcessIsChecked(unittest.TestCase):
    """every_server refuses an app's database_connections_per_worker_process that is not a whole number from 1."""

    TASK = 'database_connections_per_worker_process_is_a_whole_number_from_1'

    def run_the_check(self, line=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            if line is not None:
                settings = root/'mmx_project_settings.yml'
                text = settings.read_text()
                old = '      # database_connections_per_worker_process: 10\n'
                self.assertEqual(text.count(old), 1)
                settings.write_text(text.replace(old, line))
            explained = subprocess.run([os.environ['MMX_BINARY'], 'explain', 'every_server', '--json', '--limit', 'util01'],
                                       cwd=root, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(explained.returncode, 0, explained.stderr)
        task = next(task for stage in json.loads(explained.stdout)['fleet_stages']
                    for task in stage.get('node_tasks') or [] if task['path'].endswith('/' + self.TASK))
        env = dict(os.environ)
        for item in task['arguments']:
            if item['field'].startswith('shell.env.'):
                value = item['value']
                env[item['field'][10:]] = value if isinstance(value, str) else json.dumps(value)
        return subprocess.run(['bash', '-c', env['PROGRAM']], env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL)

    def test_left_out_or_a_whole_number_passes(self):
        for line in (None, '      database_connections_per_worker_process: 10\n'):
            with self.subTest(line=line):
                result = self.run_the_check(line)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_zero_a_fraction_or_text_is_refused(self):
        for value in ('0', '2.5', '"10"'):
            with self.subTest(value=value):
                result = self.run_the_check(f'      database_connections_per_worker_process: {value}\n')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('apps.shop.database_connections_per_worker_process in mmx_project_settings.yml is', result.stderr)
                self.assertIn('Use a whole number from 1', result.stderr)

class ReadTheAppPoolLoad(unittest.TestCase):
    """The root step hands the decision program the inventory's app servers and the settings."""

    def test_the_arguments_and_the_written_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root/'state'; state.mkdir()
            repository = root/'repository'; (repository/'server_management_scripts').mkdir(parents=True)
            for name in ('read_the_app_pool_load', 'steps_for_replacing_failed_servers.bash'):
                text = (T/'server_management_scripts'/name).read_text().replace('/var/lib/replace_failed_servers', str(state))
                text = text.replace('/usr/local/bin/check-whether-the-load-changes-the-app-pool', str(root/'bin/decide'))
                (repository/'server_management_scripts'/name).write_text(text)
            binary = root/'bin'; binary.mkdir()
            (binary/'decide').write_text(f'#!/bin/bash\nprintf "%s\\n" "$@" > {root}/arguments\n'
                                         'echo \'{"decision": "remove", "why": "remove app002", "server_to_remove": "app002"}\'\nexit 0\n')
            (binary/'chgrp').write_text('#!/bin/bash\n')
            for path in binary.iterdir():
                path.chmod(0o755)
            env = {**os.environ, 'PATH': f'{binary}:{os.environ["PATH"]}',
                   'GROWTH_LIMITS': json.dumps({'app_servers': {'smallest_number_of_servers': 2, 'largest_number_of_servers': 5}}),
                   'SERVER_WORK': json.dumps({'minutes_of_high_load_before_an_app_server_is_added': 15,
                                              'days_of_low_load_before_an_app_server_is_removed': 7,
                                              'cpu_percent_below_which_the_app_pool_can_spare_a_server': 50}),
                   'INVENTORY_GROUPS': json.dumps({'app_servers': ['app001', 'app002']}),
                   'INVENTORY_NODES': json.dumps({'app001': {'vars': {'server_type': 'cx33'}}, 'app002': {'vars': {'server_type': 'cx43'}}})}
            result = subprocess.run(['bash', 'server_management_scripts/read_the_app_pool_load', '--remove'], cwd=repository,
                                    env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), 'remove app002')
            self.assertEqual((root/'arguments').read_text().split(), [
                '--remove', '--json', '--smallest-number-of-servers', '2', '--largest-number-of-servers', '5',
                '--minutes-of-high-load', '15', '--days-of-low-load', '7',
                '--cpu-percent-below-which-the-app-pool-can-spare-a-server', '50',
                '--app-server', 'app001:cx33', '--app-server', 'app002:cx43'])
            self.assertEqual(json.loads((state/'app_pool_for_the_load.json').read_text())['server_to_remove'], 'app002')


if __name__ == '__main__':
    unittest.main()
