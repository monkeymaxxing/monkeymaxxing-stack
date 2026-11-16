#!/usr/bin/env python3
"""A recovery refuses while a database server the inventory still lists runs Postgres.

After a rebuild of util01 the failover monitor knows no database server, so the
monitor's table alone would let a recovery make a second primary beside a live one.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
PLAYBOOK = TEMPLATE / 'playbooks/restore_database.yml'

# Stand-ins: psql prints the monitor's table from MONITOR_NODES; pg_isready
# answers for each address from PG_ISREADY_EXIT_CODES, as JSON, and logs its arguments.
PSQL = '#!/bin/sh\nprintf "%s" "$MONITOR_NODES"\n'
PG_ISREADY = '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['PG_ISREADY_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
sys.exit(json.loads(os.environ['PG_ISREADY_EXIT_CODES']).get(args[args.index('-h') + 1], 2))
'''


def task_script():
    text = PLAYBOOK.read_text().split('      - id: read_the_formation_from_the_failover_monitor\n', 1)[1]
    body = re.search(r'          script: \|\n(.*?)          dryrun:', text, re.S)[1]
    return '\n'.join(line[12:] for line in body.splitlines())


INVENTORY_NODES = {
    'util01': {'name': 'util01', 'vars': {'private_ip': '10.20.0.1'}},
    'db01': {'name': 'db01', 'vars': {'private_ip': '10.20.2.1'}},
    'db02': {'name': 'db02', 'vars': {'private_ip': '10.20.2.2'}},
    'db03': {'name': 'db03', 'vars': {'private_ip': '10.20.2.3'}},
}


class RecoveryRefusesARunningDatabaseServer(unittest.TestCase):
    def run_check(self, answers, monitor_nodes=''):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temporary:
            root = Path(temporary)
            binary = root / 'bin'
            binary.mkdir()
            for name, text in (('psql', PSQL), ('pg_isready', PG_ISREADY)):
                (binary / name).write_text(text)
                (binary / name).chmod(0o755)
            log = root / 'pg_isready.log'
            log.write_text('')
            result = subprocess.run(['bash', '-c', task_script()], text=True, capture_output=True, timeout=30, env={
                **os.environ, 'PATH': str(binary) + ':' + os.environ['PATH'],
                'SERVER_NAME': 'db03', 'MONITOR_NODES': monitor_nodes,
                'DATABASE_SERVERS': json.dumps(['db01', 'db02']), 'INVENTORY_NODES': json.dumps(INVENTORY_NODES),
                'SECONDS_TO_WAIT_FOR_AN_ANSWER': '5',
                'PG_ISREADY_EXIT_CODES': json.dumps(answers), 'PG_ISREADY_LOG': str(log)})
            return result, [json.loads(line) for line in log.read_text().splitlines()]

    def test_an_empty_monitor_and_a_running_old_primary_refuse_naming_it(self):
        for code in (0, 1):  # accepting connections, or answering while it starts
            with self.subTest(code=code):
                result, asked = self.run_check({'10.20.2.2': code})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('refused: db02 (10.20.2.2) answers as a running Postgres', result.stderr)
                self.assertIn('two primaries', result.stderr)
                self.assertIn('operating_procedures/recover_when_every_database_server_is_lost.md', result.stderr)
                self.assertIn(['-q', '-h', '10.20.2.2', '-p', '5432', '-t', '5'], asked)

    def test_servers_that_do_not_answer_count_as_lost(self):
        result, asked = self.run_check({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('db01 (10.20.2.1) does not answer on port 5432; counted as lost', result.stdout)
        self.assertIn('db02 (10.20.2.2) does not answer on port 5432; counted as lost', result.stdout)
        # Only the servers in database_servers are asked: not the new server, not util01.
        self.assertEqual(sorted(a[2] for a in asked), ['10.20.2.1', '10.20.2.2'])

    def test_a_check_that_could_not_ask_refuses(self):
        result, asked = self.run_check({'10.20.2.1': 3})
        self.assertEqual(result.returncode, 1)
        self.assertIn('refused: pg_isready could not ask db01 (10.20.2.1), exit 3', result.stderr)

    def test_a_healthy_node_on_the_monitor_still_refuses_first(self):
        result, asked = self.run_check({}, monitor_nodes='db01 1\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn('the monitor reaches the Postgres of db01', result.stderr)
        self.assertEqual(asked, [])

    def test_the_task_reads_the_servers_from_the_inventory(self):
        text = PLAYBOOK.read_text()
        self.assertIn('DATABASE_SERVERS: "{{ .inventory.groups.database_servers }}"', text)
        self.assertIn('INVENTORY_NODES: "{{ .inventory.nodes }}"', text)


class TheDeskThatKeepsAccessCanRunARecovery(unittest.TestCase):
    """During a lock-out util01 has lost admission, so the desk runs the recovery.

    MMX's ufw module refuses a rule set that blocks the controller's own SSH, so
    the recovery server's firewall must admit the systems desks' block.
    """

    def test_the_recovery_servers_firewall_admits_ssh_from_the_desks(self):
        mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not mmx:
            self.skipTest('Set MMX_BINARY to render the playbook with MMX.')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary) / 'systems'
            shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns('.mmx'))
            inventory = (root / 'inventories/servers.yml').read_text()
            db03 = ('  db03:\n    address: 10.20.2.3\n    ssh_user: root\n    connection: ssh_only\n'
                    '    ssh_known_hosts: ssh/known_hosts\n    ssh_config: ssh/config\n    vars:\n'
                    '      private_ip: 10.20.2.3\n      public_ipv4_address: 203.0.113.23\n'
                    '      wireguard_public_key: PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=\n\ngroups:\n')
            self.assertIn('\ngroups:\n', inventory)
            inventory = inventory.replace('\ngroups:\n', '\n' + db03, 1)
            self.assertIn('  database_restore_servers:\n    nodes: []', inventory)
            inventory = inventory.replace('  database_restore_servers:\n    nodes: []', '  database_restore_servers:\n    nodes: [db03]')
            (root / 'inventories/servers.yml').write_text(inventory)
            result = subprocess.run([mmx, 'explain', 'restore_database', '--json',
                                     '--var', 'restore_mode=recovery', '--var', 'server_name=db03',
                                     '--var', 'recover_to=2026-11-03 14:01:00+00',
                                     '--var', 'read_backup_bucket_as_of=2026-11-03 15:30:00+00'],
                                    cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"from": "10.20.9.0/24"', json.dumps(json.loads(result.stdout)))


if __name__ == '__main__':
    unittest.main()
