#!/usr/bin/env python3
"""Each alert pause lasts no longer than its run waits for that server.

  MMX_BINARY=/path/to/mmx python3 tests/alert_pauses_test.py

An alert pause is an MMWatchdog maintenance window that a playbook or role
opens on a server around its planned work. Its --for is the longest time the
run waits for that server, plus a small margin, so a run that fails or dies
never leaves alerts paused longer than it would have waited. The test adds
up each playbook's own waits, read from the playbook and role files, and
checks the pause against the sum, so a changed wait without a changed pause
fails here.

Where MMX offers it cheaply, a failure ends the pause at once too. The test
reads `mmx explain` of each playbook and checks that every `maintenance on`
sits in a node task block whose on_failure ends the pause (exit 1 of
`maintenance on` leaves a window on the server that the hub does not know),
and that the waits for the server's work, and the database servers'
updates, sit in a block whose cleanup or on_failure ends it.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
OFF = '/usr/local/bin/mmwatchdog maintenance off --every-check-group'


def minutes(duration):
    number, unit = re.fullmatch(r'(\d+)([smh])', duration).groups()
    return int(number) * {'s': 1 / 60, 'm': 1, 'h': 60}[unit]


def text(path):
    return (T/path).read_text()


def one(pattern, source):
    found = re.findall(pattern, source)
    assert len(found) == 1, (pattern, found)
    return found[0]


class EachPauseIsTheSumOfItsWaits(unittest.TestCase):
    SETTING = 'come_back_wait_after_a_reboot'

    def come_back_wait(self, playbook):
        """The come-back wait: one setting in mmx_project_settings.yml, which both reboot playbooks read."""
        self.assertEqual(one(r'run_only_if_this_path_exists: /var/run/reboot-required\n\s+wait_at_most: (.+)', playbook),
                         '"{{ .vars.%s }}"' % self.SETTING)
        default = one(r'(?m)^  %s: (\S+)$' % self.SETTING, text('mmx_project_settings.yml'))
        self.assertEqual(default, '3m')
        return default

    def pause_for(self, playbook, program, wait):
        """Runs the playbook's pause command with a stand-in program and the given come-back wait; returns its arguments."""
        script = one(r'script: \'?(/usr/local/bin/' + re.escape(program) + r' (?:maintenance on|start) .+?)\'?\n', playbook)
        self.assertIn('COME_BACK_WAIT: "{{ .vars.%s }}"' % self.SETTING, playbook)
        result = subprocess.run(['bash', '-c', script.replace('/usr/local/bin/' + program, 'printf "%s\\n"')],
                                env=dict(os.environ, COME_BACK_WAIT=wait), text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def the_settings_check_refuses_other_values(self, playbook):
        pattern = one(r'matches: \["\{\{ \.vars\.' + self.SETTING + r' \}\}", \'(.+?)\'\]', playbook)
        for value in ('1m', '3m', '15m', '45m'):
            self.assertRegex(value, pattern)
        for value in ('0m', '46m', '90s', '1h', '3', ' 3m'):
            self.assertNotRegex(value, pattern)

    def test_reboot_servers_after_updates(self):
        playbook = text('playbooks/reboot_servers_after_updates.yml')
        default = self.come_back_wait(playbook)
        self.the_settings_check_refuses_other_values(playbook)
        work = minutes(one(r'command_succeeds: /usr/local/bin/check-that-this-server-does-its-work\n\s+wait_at_most: (\S+)', playbook))
        # The default, and a dedicated server's own value from the inventory.
        for wait in (default, '15m'):
            with self.subTest(wait=wait):
                arguments = self.pause_for(playbook, 'mmwatchdog', wait)
                self.assertEqual(minutes(arguments[arguments.index('--for') + 1]), minutes(wait) + work + 2)
                # replace_failed_servers reads the server's own wait from the window's reason.
                reason = arguments[arguments.index('--reason') + 1]
                self.assertEqual(reason, f'reboot_servers_after_updates: waits {wait} for the server to come back')
                self.assertRegex(reason, r'^reboot_servers_after_updates: waits (?P<minutes>[0-9]+)m for the server to come back$')
        self.assertIn('capture("^reboot_servers_after_updates: waits (?<minutes>[0-9]+)m for the server to come back$")',
                      text('server_management_scripts/steps_for_replacing_failed_servers.bash'))

    def test_reboot_util01_after_updates(self):
        playbook = text('playbooks/reboot_util01_after_updates.yml')
        default = self.come_back_wait(playbook)
        self.the_settings_check_refuses_other_values(playbook)
        work = minutes(one(r'systemctl is-active --quiet mmwatchdog.service\n\s+wait_at_most: (\S+)', playbook))
        for wait in (default, '15m'):
            with self.subTest(wait=wait):
                arguments = self.pause_for(playbook, 'util01-alert-pause', wait)
                self.assertEqual(minutes(arguments[arguments.index('--for') + 1]), minutes(wait) + work + 2)

    def test_a_server_may_have_its_own_come_back_wait(self):
        """A dedicated server's own value in the inventory loads; a value that is no duration is refused by name.

        MMX checks the value of util01's reboot when the project loads. It
        does not check the reboot inside reboot_servers_after_updates'
        for_each_node stage then, so that playbook's own
        check, the_come_back_wait_is_whole_minutes_from_1_to_45, refuses an
        app server's wrong value on the server before its reboot.
        """
        mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not mmx:
            raise RuntimeError('Set MMX_BINARY to validate the template.')
        import tempfile
        for node, value, valid in (('app001', '15m', True), ('util01', '15m', True), ('util01', 'soon', False)):
            with self.subTest(node=node, value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)/'systems'
                shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
                inventory = (root/'inventories/servers.yml').read_text()
                inventory = re.sub(r'(?m)^(  %s:\n(?:    .*\n)*?    vars:\n)' % node, r'\1      %s: %s\n' % (self.SETTING, value), inventory, count=1)
                self.assertIn('      %s: %s\n' % (self.SETTING, value), inventory)
                (root/'inventories/servers.yml').write_text(inventory)
                result = subprocess.run([mmx, 'validate'], cwd=root, text=True, capture_output=True, stdin=subprocess.DEVNULL)
                if valid:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(self.SETTING, result.stdout + result.stderr)

    def switchover(self, playbook, primary_task):
        switch = minutes(one(rf'id: {primary_task}\n(?:.*\n)*?\s+time_limit: (\S+)', playbook))
        per_app = minutes(one(r'expected_http_status_codes: \[200\]\n\s+wait_at_most: (\S+)', playbook))
        return switch, per_app

    def test_switch_database_primary(self):
        playbook = text('playbooks/switch_database_primary.yml')
        switch, per_app = self.switchover(playbook, 'make_the_server_the_primary')
        self.assertEqual(per_app, 1)
        self.assertEqual(one(r'pause_minutes=\$\(\((\d+) \+ \$\(jq -n --argjson apps "\$APPS" \'\$apps \| length\'\)\)\)', playbook),
                         str(int(switch + 2)))

    def test_update_database_servers(self):
        playbook = text('playbooks/update_database_servers.yml')
        role = text('roles/database_server/main.yml')
        switch, per_app = self.switchover(playbook, 'make_the_updated_replica_the_primary')
        self.assertEqual(per_app, 1)
        self.assertEqual(one(r'pause_minutes=\$\(\((\d+) \+ \$\(jq', playbook), str(int(switch + 2)))
        # One server's turn: the role twice, the updates and restarts as measured, the reboot, and the margin.
        node_task = minutes(one(r'restart_postgresql_for_new_settings: "\{\{ \.inputs\.restart_postgresql_for_new_settings \}\}"\n\s+time_limit: (\S+)', role))
        monitor = minutes(one(r'wait_until_the_failover_monitor_on_util01_answers_over_wireguard\n(?:.*\n)*?\s+wait_at_most: (\S+)', role))
        reboots = re.findall(r'run_only_if_this_path_exists: /var/run/reboot-required\n\s+wait_at_most: (\S+)', playbook)
        self.assertEqual(len(reboots), 2)
        updates, restarts = 15, 5     # measured, stated beside the pause: apt is never stopped halfway
        self.assertIn('the updates, about 15m on a small server', playbook)
        self.assertIn('the restarts of the\n          # services that use a replaced file, about 5m', playbook)
        turn = 2 * (node_task + monitor) + updates + restarts + minutes(reboots[0]) + 4
        for pause in re.findall(r'maintenance on --every-check-group --for (\d+m) --reason "update_database_servers"', playbook):
            self.assertEqual(minutes(pause), turn)
        self.assertEqual(len(re.findall(r'--for 75m --reason "update_database_servers"', playbook)), 2)

    def test_mmwatchdogs_own_restart(self):
        for role, pause in (('roles/mmwatchdog_joined_node/main.yml', 'maintenance on --every-check-group'),
                            ('roles/util_server/main.yml', 'util01-alert-pause start')):
            with self.subTest(role=role):
                source = text(role)
                self.assertEqual(one(re.escape(pause) + r' --for (\S+) --reason "mmwatchdog deploy"', source), '3m')
                self.assertEqual(one(r'path_exists: /run/mmwatchdog/mmwatchdog.sock\n\s+wait_at_most: (\S+)', source), '10s')

    def test_every_pause_is_listed_here(self):
        """A new pause gets its own sum in this test before it ships."""
        known = {'playbooks/reboot_servers_after_updates.yml': 1, 'playbooks/reboot_util01_after_updates.yml': 1,
                 'playbooks/switch_database_primary.yml': 1, 'playbooks/update_database_servers.yml': 3,
                 'playbooks/remove_server.yml': 1, 'roles/mmwatchdog_joined_node/main.yml': 1, 'roles/util_server/main.yml': 1}
        found = {}
        for path in sorted(T.rglob('*')):
            if path.is_file() and path.suffix in ('.yml', ''):
                relative = str(path.relative_to(T))
                count = len(re.findall(r'maintenance on --every-check-group|util01-alert-pause start --for',
                                       path.read_text(errors='ignore')))
                if count and relative.startswith(('playbooks/', 'roles/')) and relative != 'roles/util_server/files/util01-alert-pause':
                    found[relative] = count
        self.assertEqual(found, known)


class Util01sPublicSiteChecksAreNeverPaused(unittest.TestCase):
    """util01's own pauses name every check group but public_sites."""

    def test_util01_never_opens_a_window_on_every_check_group(self):
        for path in ('playbooks/reboot_util01_after_updates.yml', 'roles/util_server/main.yml'):
            with self.subTest(path=path):
                self.assertNotIn('--every-check-group', text(path))

    def run_pause(self, *arguments, status_exit=1):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root/'log'
            status = {'checks': {'public_sites/shop_answers_at_its_public_host_name': {}, 'restore_drill/passed': {},
                                 'util_server_capacity/cpu_is_below_70_percent': {}, 'node_reports/app001': {},
                                 'clock/synchronized': {}}}
            (root/'mmwatchdog').write_text(f'#!/bin/bash\necho "$*" >> {log}\n'
                                           f'[ "$1" = status ] && {{ echo \'{json.dumps(status)}\'; exit {status_exit}; }}\nexit 0\n')
            (root/'mmwatchdog').chmod(0o755)
            program = (T/'roles/util_server/files/util01-alert-pause').read_text().replace('/usr/local/bin/mmwatchdog', str(root/'mmwatchdog'))
            result = subprocess.run(['bash', '-c', program, 'util01-alert-pause', *arguments], text=True,
                                    capture_output=True, stdin=subprocess.DEVNULL)
            return result, log.read_text().splitlines()

    def test_start_names_every_check_group_but_public_sites(self):
        result, log = self.run_pause('start', '--for', '10m', '--reason', 'reboot_util01_after_updates')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log[1], 'maintenance on clock node_reports restore_drill util_server_capacity --for 10m --reason reboot_util01_after_updates')

    def test_end_ends_the_same_check_groups(self):
        result, log = self.run_pause('end', status_exit=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log[1], 'maintenance off clock node_reports restore_drill util_server_capacity')

    def test_an_mmwatchdog_that_does_not_answer_changes_nothing(self):
        result, log = self.run_pause('start', '--for', '3m', status_exit=4)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(log, ['status --json'])


class AFailureEndsThePauseWhereMMXOffersIt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to explain the actual playbooks.')

    def tasks(self, playbook, *arguments):
        result = subprocess.run([self.mmx, 'explain', playbook, *arguments, '--json'], cwd=T, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = text(f'playbooks/{playbook}.yml')
        tasks = []

        def walk(stage):
            for task in stage.get('node_tasks') or []:
                script = next((item.get('value') for item in task.get('arguments') or [] if item['field'] == 'shell.script'), None)
                if not isinstance(script, str):
                    # explain lists no arguments for the tasks of on_failure and
                    # cleanup, and none for a loop's unevaluated values: read the
                    # task's one-line script from the playbook by its id.
                    found = re.findall(r'- id: ' + re.escape(task['path'].rsplit('/', 1)[-1]) + r'\n\s+shell:\n\s+script: (.+)', source)
                    script = found[0] if len(set(found)) == 1 else ''
                tasks.append((task['path'], task['action'], script))
            for inner in stage.get('fleet_stages') or []:
                walk(inner)
        for stage in json.loads(result.stdout)['fleet_stages']:
            walk(stage)
        return tasks

    def check(self, tasks, ended_by_phase, start='maintenance on', end=OFF):
        """Every pause ends again in its block's on_failure; each named block ends the pause in the named phase."""
        pauses = [path for path, _, script in tasks if start in script]
        self.assertTrue(pauses)
        for path in pauses:
            block = path.rsplit('/changes/', 1)[0]
            self.assertNotEqual(block, path, f'{path} is not in a node task block')
            self.assertTrue(any(other.startswith(block + '/on_failure/') and script == end for other, _, script in tasks), block)
        for block_name, phase in ended_by_phase:
            ends = [other for other, _, script in tasks if f'/{block_name}/{phase}/' in other and script == end]
            self.assertTrue(ends, (block_name, phase))

    def test_reboot_servers_after_updates(self):
        self.check(self.tasks('reboot_servers_after_updates'),
                   [('wait_until_the_server_does_its_work_then_end_its_alert_pause', 'cleanup')])

    def test_reboot_util01_after_updates(self):
        self.check(self.tasks('reboot_util01_after_updates'),
                   [('wait_until_mmhotline_and_mmwatchdog_run_then_end_the_alert_pause', 'cleanup')],
                   start='util01-alert-pause start', end='/usr/local/bin/util01-alert-pause end')

    def test_switch_database_primary(self):
        self.check(self.tasks('switch_database_primary', '--var', 'server_name=db01'), [])

    def test_update_database_servers(self):
        tasks = self.tasks('update_database_servers')
        self.check(tasks, [('install_the_updates_and_restart_what_uses_them', 'on_failure')])
        # Each turn ends its own pause once the server has caught up.
        for stage in ('end_the_maintenance_of_the_replica', 'end_the_maintenance_of_the_old_primary'):
            self.assertTrue(any(f'/{stage}/end_the_alert_pause_of_' in path and script == OFF for path, _, script in tasks), stage)


if __name__ == '__main__':
    unittest.main()
