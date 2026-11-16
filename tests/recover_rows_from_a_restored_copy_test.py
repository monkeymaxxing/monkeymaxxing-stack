#!/usr/bin/env python3
"""Run the row recovery's program against stand-ins and two real PostgreSQL clusters.

Run: MMX_BINARY=/path/to/mmx python3 tests/recover_rows_from_a_restored_copy_test.py

The program is the shell task of playbooks/recover_rows_from_a_restored_copy.yml,
with its env from `mmx explain`, so MMX also checks the playbook and its
templates. Stand-ins play the provider scripts, wg, git's clone, the inner
`mmx run restore_database` and ssh. ssh to restore01 and to the primary runs
the remote psql command against two local PostgreSQL clusters, one holding the
restored copy and one the primary, so the SQL that copies the rows runs for
real. Those tests need PostgreSQL's server programs on PATH (initdb, pg_ctl,
psql) and are skipped without them; the refusals run either way.
"""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'skills/monkeymaxxing-stack/systems_repository_template'
SOURCE = TEMPLATE / 'playbooks/recover_rows_from_a_restored_copy.yml'
HAS_POSTGRESQL = all(shutil.which(name) for name in ('initdb', 'pg_ctl', 'psql'))
# The failover monitor's view, as pg_autoctl show state --json prints it.
MONITOR = [{'nodename': 'db01', 'assigned_group_state': 'primary', 'health': 1}]

FAKE = r'''import json, os, pathlib, shlex, shutil, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as file:
    file.write(json.dumps([name, *args]) + '\n')
if name == 'list_the_servers_at_the_provider':
    names = ['util01'] + (['restore01'] if os.environ.get('LEFTOVER') else [])
    print(json.dumps({'servers': [{'name': n, 'id': 'id-' + n, 'power_state': 'running',
                                   'public_ipv4_address': '203.0.113.1' if n == 'util01' else '203.0.113.90'} for n in names]}))
elif name == 'create_a_server_at_the_provider':
    receipt = {'id': 'owned-123', 'name': 'restore01', 'public_ipv4_address': '203.0.113.90'}
    pathlib.Path(args[args.index('--ownership-file') + 1]).write_text(json.dumps(receipt))
    print(json.dumps(receipt))
elif name == 'destroy_a_server_at_the_provider':
    assert args == ['--server-id', 'owned-123'], args
    sys.exit(int(os.environ.get('DESTROY_EXIT', '0')))
elif name == 'wg':
    print('QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' if args == ['genkey'] else 'PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=')
elif name == 'git':
    assert args[:4] == ['clone', '--quiet', '--no-hardlinks', '--local'], args
    shutil.copytree('.', args[-1], ignore=shutil.ignore_patterns('.mmx'))
elif name == 'mmx':
    if args == ['nodes', '--json']:
        inventory = pathlib.Path('inventories/servers.yml').read_text()
        print(json.dumps({'nodes': [{'name': n} for n in ('util01', 'db01') + (('restore01',) if 'restore01:' in inventory else ())],
                          'groups': {'database_restore_servers': []}}))
    elif args[:2] == ['run', 'restore_database']:
        # The inner run sees restore01 only in the throwaway clone.
        assert pathlib.Path.cwd().resolve() != pathlib.Path(os.environ['REPOSITORY']).resolve()
        assert '  restore01:\n    address: 10.20.8.1' in pathlib.Path('inventories/servers.yml').read_text()
        assert 'nodes: [restore01]' in pathlib.Path('inventories/servers.yml').read_text()
        assert '10.20.8.1 ssh-ed25519 restore01-key' in pathlib.Path('ssh/known_hosts').read_text()
        pathlib.Path(os.environ['STATE'], 'inner_run').write_text(json.dumps(args))
        sys.exit(int(os.environ.get('RESTORE_EXIT', '0')))
    else:
        sys.exit('unexpected mmx arguments')
elif name == 'ssh':
    target = next(a for a in args if a.startswith('root@'))[5:]
    remote = args[-1]
    if args[-3:-1] == ['wg', 'set'] or args[args.index('root@' + target) + 1:][:1] == ['wg']:
        sys.exit(int(os.environ.get('PEER_ADD_EXIT', '0')) if 'allowed-ips' in args else 0)
    if remote == 'true':
        with open('ssh/known_hosts', 'a') as file:
            file.write(target + ' ssh-ed25519 restore01-key\n')
        sys.exit(0)
    if 'pg_autoctl show state' in remote:
        assert target == '10.20.0.1', target
        print(os.environ['MONITOR'])
        sys.exit(0)
    words = shlex.split(remote)
    assert words[:4] == ['runuser', '-u', 'postgres', '--'] and words[4] == 'psql', words
    script = sys.stdin.buffer.read()
    side = {'10.20.8.1': 'restored_copy', '10.20.2.1': 'primary'}[target]
    with open(os.path.join(os.environ['STATE'], side + '.sql'), 'ab') as file:
        file.write(script)
    if side == 'restored_copy' and os.environ.get('DUMP_FAILS'):
        # A connection lost after the first row.
        result = subprocess.run(words[4:], input=script, capture_output=True, env={**os.environ, 'PGPORT': os.environ['COPY_PORT']})
        sys.stdout.buffer.write(result.stdout.splitlines(keepends=True)[0])
        sys.exit(255)
    port = os.environ['COPY_PORT' if side == 'restored_copy' else 'PRIMARY_PORT']
    result = subprocess.run(words[4:], input=script, capture_output=True, env={**os.environ, 'PGPORT': port})
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    sys.exit(result.returncode)
else:
    sys.exit('unexpected command ' + name)
'''


def shell_script():
    text = SOURCE.read_text()
    body = re.search(r'          script: \|\n(.*?)          dryrun:', text, re.S)[1]
    return '\n'.join(line[12:] for line in body.splitlines())


def explain_env(mmx, **values):
    arguments = [mmx, 'explain', 'recover_rows_from_a_restored_copy', '--json']
    for key, value in values.items():
        arguments += ['--var', f'{key}={value}']
    result = subprocess.run(arguments, cwd=TEMPLATE, text=True, capture_output=True, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    task = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]
    env = {}
    for item in task['arguments']:
        if item['field'].startswith('shell.env.'):
            value = item['value']
            env[item['field'][10:]] = value if isinstance(value, str) else json.dumps(value) if value is not None else 'stand-in token'
    return env


VALUES = {'recover_to': '2026-11-03 14:01:00+00', 'read_backup_bucket_as_of': '2026-11-03 15:30:00+00',
          'database_name': 'shop', 'table': 'orders', 'rows_where': 'id <= 5',
          'when_a_primary_key_exists': 'skip_the_row'}


class RowRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY so MMX checks the playbook and gives the program its env.')
        cls.root = Path(tempfile.mkdtemp())
        cls.ports = {}
        if HAS_POSTGRESQL:
            subprocess.run(['initdb', '-D', str(cls.root / 'copy'), '-A', 'trust', '-U', 'postgres'],
                           check=True, capture_output=True)
            shutil.copytree(cls.root / 'copy', cls.root / 'primary')
            for side, port in (('copy', '55431'), ('primary', '55432')):
                subprocess.run(['pg_ctl', '-D', str(cls.root / side), '-l', str(cls.root / f'{side}.log'), '-w',
                                '-o', f"-k {cls.root} -p {port} -c listen_addresses=''", 'start'],
                               check=True, capture_output=True)
                cls.ports[side] = port

    @classmethod
    def tearDownClass(cls):
        for side in cls.ports:
            subprocess.run(['pg_ctl', '-D', str(cls.root / side), '-m', 'immediate', 'stop'], capture_output=True)
        shutil.rmtree(cls.root)

    def psql(self, side, sql, database='shop'):
        return subprocess.run(['psql', '-X', '-q', '-At', '-v', 'ON_ERROR_STOP=1', '-h', str(self.root), '-p', self.ports[side],
                               '-U', 'postgres', '-d', database, '-c', sql], check=True, text=True, capture_output=True).stdout.strip()

    def make_databases(self):
        """The copy holds rows 1 to 5, as before the bad change. Since then the
        primary lost 3, 4 and 5, changed row 2, and got row 6."""
        for side in ('copy', 'primary'):
            self.psql(side, 'DROP DATABASE IF EXISTS shop', 'postgres')
            self.psql(side, 'CREATE DATABASE shop', 'postgres')
            self.psql(side, 'CREATE TABLE orders (id int PRIMARY KEY, note text, details json, email text UNIQUE)')
        self.psql('copy', "INSERT INTO orders SELECT n, 'secret-note-' || n, '{\"n\": 1}', 'customer' || n || '@example.com' FROM generate_series(1, 5) n")
        self.psql('primary', "INSERT INTO orders VALUES (1, 'secret-note-1', '{\"n\": 1}', 'customer1@example.com'), "
                             "(2, 'changed later', null, 'customer2@example.com'), (6, 'new', null, 'customer6@example.com')")

    def primary_rows(self):
        return self.psql('primary', 'SELECT id, note FROM orders ORDER BY id')

    def run_recovery(self, **settings):
        values = {**VALUES, **{k: v for k, v in settings.items() if k.islower()}}
        env_settings = {k: v for k, v in settings.items() if not k.islower()}
        root = Path(tempfile.mkdtemp(dir=self.root))
        state = root / 'state'; state.mkdir()
        drill_dir = root / 'restore_drill'; drill_dir.mkdir()
        repo = root / 'repository'
        (repo / 'inventories').mkdir(parents=True); (repo / 'ssh').mkdir(); (repo / '.mmx').mkdir()
        inventory = (TEMPLATE / 'inventories/servers.yml').read_text()
        (repo / 'inventories/servers.yml').write_text(inventory)
        (repo / 'ssh/known_hosts').write_text('10.20.0.1 ssh-ed25519 util01-key\n')
        scripts = repo / 'server_management_scripts'; scripts.mkdir()
        binary = root / 'bin'; binary.mkdir()
        for name in ('git', 'mmx', 'wg', 'ssh', 'list_the_servers_at_the_provider',
                     'create_a_server_at_the_provider', 'destroy_a_server_at_the_provider'):
            path = (scripts if name.endswith('_at_the_provider') else binary) / name
            path.write_text('#!' + sys.executable + '\n' + FAKE); path.chmod(0o755)
        for name in ('render_server_first_boot', 'server_first_boot.cloud-config.yml',
                     'steps_for_a_server_this_run_creates.bash', 'steps_for_reading_the_providers_list.bash'):
            shutil.copy2(TEMPLATE / 'server_management_scripts' / name, scripts / name)
        log = root / 'commands'
        script = shell_script().replace('/var/lib/mmhotline/systems_repository', str(repo)).replace('/var/lib/restore_drill', str(drill_dir))
        env = {**os.environ, **explain_env(self.mmx, **values), 'PATH': f'{binary}:{os.environ["PATH"]}',
               'COMMAND_LOG': str(log), 'STATE': str(state), 'REPOSITORY': str(repo), 'MONITOR': json.dumps(MONITOR),
               'PGHOST': str(self.root), 'PGUSER': 'postgres',
               'COPY_PORT': self.ports.get('copy', ''), 'PRIMARY_PORT': self.ports.get('primary', ''), **env_settings}
        result = subprocess.run(['bash', '-c', script], cwd=repo, env=env, text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=120)
        commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        sent = {path.stem: path.read_text() for path in state.glob('*.sql')}
        # util01's own copy stays clean: restore01 and its host key lived only in the clone.
        self.assertEqual((repo / 'inventories/servers.yml').read_text(), inventory)
        self.assertEqual((repo / 'ssh/known_hosts').read_text(), '10.20.0.1 ssh-ed25519 util01-key\n')
        return result, commands, sent, list(drill_dir.iterdir())

    def assert_cleaned_up(self, result, commands, leftovers):
        self.assertIn(['destroy_a_server_at_the_provider', '--server-id', 'owned-123'], commands, result.stderr)
        peers = [c for c in commands if c[0] == 'ssh' and 'wg' in c]
        self.assertEqual([p[-1] for p in peers], ['10.20.8.1/32', 'remove'], result.stderr)
        self.assertEqual(leftovers, [], result.stderr)

    # The refusals: nothing is created.
    def test_values_that_do_not_fit_are_refused_before_anything_is_created(self):
        for values, message in (({'rows_where': ' '}, 'rows_where is empty'),
                                ({'recover_to': 'latest'}, 'not latest'),
                                ({'database_name': 'someone_elses'}, "no app's database_name"),
                                ({'when_a_primary_key_exists': 'overwrite'}, 'give skip_the_row or change_nothing')):
            with self.subTest(values=values):
                result, commands, sent, leftovers = self.run_recovery(**values)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertIn('nothing created', result.stderr)
                self.assertEqual(commands, [])
                self.assertEqual(result.stdout, '')

    def test_a_restore01_that_exists_is_refused(self):
        result, commands, sent, leftovers = self.run_recovery(LEFTOVER='yes')
        self.assertEqual(result.returncode, 1)
        self.assertIn('restore01 already exists at the provider; nothing created', result.stderr)
        self.assertFalse(any(c[0] == 'create_a_server_at_the_provider' for c in commands))

    def test_mmx_refuses_a_run_without_the_values(self):
        result = subprocess.run([self.mmx, 'explain', 'recover_rows_from_a_restored_copy', '--json'], cwd=TEMPLATE,
                                text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('rows_where', result.stderr)
        # An empty value for a variable with no default is refused by MMX itself, naming the variable.
        result = subprocess.run([self.mmx, 'explain', 'recover_rows_from_a_restored_copy', '--json', '--var', 'table='],
                                cwd=TEMPLATE, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--var table= gives an empty value', result.stderr)

    def test_a_failed_restore_still_destroys_restore01(self):
        result, commands, sent, leftovers = self.run_recovery(RESTORE_EXIT='1')
        self.assertEqual(result.returncode, 1)
        self.assert_cleaned_up(result, commands, leftovers)
        self.assertEqual(sent, {})

    def test_a_failed_destroy_fails_the_run_and_keeps_the_receipt(self):
        result, commands, sent, leftovers = self.run_recovery(RESTORE_EXIT='1', DESTROY_EXIT='1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('destroying restore01 FAILED', result.stderr)
        self.assertIn('--server-id owned-123', result.stderr)
        self.assertEqual(len(leftovers), 1)
        self.assertTrue((leftovers[0] / 'created_server.json').exists())

    def test_no_single_primary_changes_nothing(self):
        result, commands, sent, leftovers = self.run_recovery(MONITOR=json.dumps([
            {'nodename': 'db01', 'assigned_group_state': 'demoted'}, {'nodename': 'db02', 'assigned_group_state': 'secondary'}]))
        self.assertEqual(result.returncode, 1)
        self.assertIn('names no single primary', result.stderr)
        self.assertEqual(sent, {})
        self.assert_cleaned_up(result, commands, leftovers)

    # The row copy, against real PostgreSQL.
    @unittest.skipUnless(HAS_POSTGRESQL, "needs PostgreSQL's server programs on PATH")
    def test_the_preview_reports_the_counts_and_changes_nothing(self):
        self.make_databases()
        before = self.primary_rows()
        result, commands, sent, leftovers = self.run_recovery()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.primary_rows(), before)
        report = json.loads(result.stdout)
        self.assertEqual(report, {'primary': 'db01', 'database_name': 'shop', 'table': 'orders',
                                  'rows_from_the_restored_copy': 5, 'rows_whose_primary_key_exists': 2,
                                  'rows_whose_primary_key_exists_with_other_values': 1,
                                  'rows_on_the_primary_before': 2, 'rows_added': 3, 'rows_on_the_primary_after': 5,
                                  'added_to_the_primary': False})
        self.assertIn('preview, nothing changed: the real run would add 3 rows to orders on db01', result.stderr)
        self.assertTrue(sent['primary'].rstrip().endswith('false);'))
        self.assertEqual(re.findall(r'^(BEGIN|COMMIT|ROLLBACK);$', sent['primary'], re.M), ['BEGIN', 'ROLLBACK'])
        self.assertIn('BEGIN TRANSACTION READ ONLY;', sent['restored_copy'])
        self.assert_cleaned_up(result, commands, leftovers)
        inner = [c for c in commands if c[:3] == ['mmx', 'run', 'restore_database']]
        self.assertEqual(inner, [['mmx', 'run', 'restore_database', '--non-interactive', '--var', 'restore_mode=copy_on_restore01',
                                  '--var', 'server_name=restore01', '--var', 'recover_to=2026-11-03 14:01:00+00',
                                  '--var', 'read_backup_bucket_as_of=2026-11-03 15:30:00+00']])

    @unittest.skipUnless(HAS_POSTGRESQL, "needs PostgreSQL's server programs on PATH")
    def test_the_real_run_adds_the_missing_rows_in_one_transaction(self):
        self.make_databases()
        result, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.primary_rows(), '1|secret-note-1\n2|changed later\n3|secret-note-3\n4|secret-note-4\n5|secret-note-5\n6|new')
        report = json.loads(result.stdout)
        self.assertEqual((report['rows_added'], report['rows_on_the_primary_before'], report['rows_on_the_primary_after'],
                          report['added_to_the_primary']), (3, 2, 5, True))
        self.assertEqual(re.findall(r'^(BEGIN|COMMIT|ROLLBACK);$', sent['primary'], re.M), ['BEGIN', 'COMMIT'])
        self.assertIn('added 3 rows to orders on db01; rows where rows_where: 2 before, 5 after', result.stderr)
        # The rows travel only in the pipe: no row value in the run's output.
        self.assertNotIn('secret-note', result.stdout + result.stderr)
        self.assert_cleaned_up(result, commands, leftovers)
        # A second real run adds nothing twice.
        again, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)['rows_added'], 0)

    @unittest.skipUnless(HAS_POSTGRESQL, "needs PostgreSQL's server programs on PATH")
    def test_change_nothing_stops_on_an_existing_primary_key(self):
        self.make_databases()
        before = self.primary_rows()
        result, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true', when_a_primary_key_exists='change_nothing')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.primary_rows(), before)
        self.assertIn('duplicate key value violates unique constraint "orders_pkey"', result.stderr)
        self.assertIn('the primary already holds the primary key of 2', result.stderr)
        self.assertIn('an SQL error ended the transaction on the primary; nothing changed on the primary', result.stderr)
        self.assertNotIn('secret-note', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assert_cleaned_up(result, commands, leftovers)
        # Without existing keys, change_nothing adds the rows.
        result, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true', when_a_primary_key_exists='change_nothing',
                                                              rows_where='id BETWEEN 3 AND 5')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['rows_added'], 3)

    @unittest.skipUnless(HAS_POSTGRESQL, "needs PostgreSQL's server programs on PATH")
    def test_another_unique_constraint_ends_the_whole_transaction(self):
        self.make_databases()
        self.psql('primary', "UPDATE orders SET email = 'customer4@example.com' WHERE id = 6")
        before = self.primary_rows()
        result, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.primary_rows(), before)
        self.assertIn('orders_email_key', result.stderr)
        self.assertNotIn('customer4@example.com', result.stderr)

    @unittest.skipUnless(HAS_POSTGRESQL, "needs PostgreSQL's server programs on PATH")
    def test_a_failed_copy_on_restore01_sends_no_commit(self):
        self.make_databases()
        before = self.primary_rows()
        result, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true', DUMP_FAILS='yes')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.primary_rows(), before)
        self.assertNotIn('COMMIT;', sent['primary'])
        self.assertNotIn('\\.', sent['primary'])
        self.assertIn('BEGIN;', sent['primary'])
        self.assert_cleaned_up(result, commands, leftovers)

    @unittest.skipUnless(HAS_POSTGRESQL, "needs PostgreSQL's server programs on PATH")
    def test_a_table_without_a_primary_key_is_refused(self):
        self.make_databases()
        for side in ('copy', 'primary'):
            self.psql(side, 'CREATE TABLE notes (body text)')
        result, commands, sent, leftovers = self.run_recovery(add_the_rows_to_the_primary='true', table='notes', rows_where='true')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('the table notes has no primary key', result.stderr)


if __name__ == '__main__':
    unittest.main()
