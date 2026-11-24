#!/usr/bin/env python3
"""The automatic weekly maintenance: hands-off updates and reboots that never take the site down.

  MMX_BINARY=/path/to/mmx python3 tests/weekly_maintenance_test.py

The maintenance runs on util01 at the start of maintenance_window
(mmx_project_settings.yml) while automatic_weekly_maintenance is true:
update_database_servers only with two or more database servers and only
when one waits, reboot_servers_after_updates for the pools of two or more
and staging01, then util01's own reboot; each systems desk reboots itself
in the same hour. The test runs each program with stand-ins:

- check-whether-a-reboot-may-run-now (roles/every_server/files/): the
  weekly window's arithmetic in UTC, a person's rule, and the automatic
  maintenance's rule, which never reboots a production pool's only server.
- reboot_servers_after_updates' first program, from `mmx explain`, for app001
  alone and with app002.
- weekly-maintenance-goes-on: it gives way to a waiting MMHotline and ends
  at the window's end, writing the reason the job reads.
- update_database_servers' check of what waits on a database server, and
  its decision: a clean pair runs nothing, db01 alone is refused.
- the weekly job's own script: the order, the lock, db01 alone skipped, an
  early end that exits 0.
- reboot_servers_after_updates' check right before each automatic reboot:
  another server of the pool must do its work.
- util01's and a desk's own reboot: each guard defers, the reboot pauses
  the alerts first, root never opens a path in /var/lib/mmhotline, and a
  desk whose state cannot be read waits.
- the reminders of mmwatchdog_checks/every_server.yml and
  database_servers.yml: 30 days on a production pool's only server, 15 days
  on every server that the maintenance restarts.
It needs Python 3, bash, git and jq.
"""
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

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
RULE = T/'roles/every_server/files/check-whether-a-reboot-may-run-now'
GATE = T/'roles/util_server/files/weekly-maintenance-goes-on'
UTIL01_REBOOT = T/'roles/util_server/files/reboot-util01-after-the-weekly-maintenance'
DESK_REBOOT = T/'roles/systems_desk/files/reboot-this-desk-after-updates'
ROLE = T/'roles/util_server/main.yml'
WINDOW = ['--weekday', 'tuesday', '--starts-at', '21:00', '--length-minutes', '60']
MMX = os.environ.get('MMX_BINARY') or shutil.which('mmx')


def rule(*arguments, pool='app_servers', servers=1, live='true', window=WINDOW):
    result = subprocess.run([sys.executable, str(RULE), '--pool', pool, '--servers-in-the-pool', str(servers),
                             '--public-site-checks-run', live, *window, *arguments],
                            text=True, capture_output=True, stdin=subprocess.DEVNULL)
    return result.returncode, result.stdout.strip()


def stand_ins(directory, programs):
    """Writes each program as an executable Python or shell stand-in and returns the directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, source in programs.items():
        path = directory/name
        path.write_text(source if source.startswith('#!') else '#!' + sys.executable + '\n' + source)
        path.chmod(0o755)
    return directory


LOGGING = '''import json, os, sys
with open(os.environ['COMMAND_LOG'], 'a') as log: log.write(json.dumps([os.path.basename(sys.argv[0]), *sys.argv[1:]]) + '\\n')
'''


class TheWeeklyWindowInUTC(unittest.TestCase):
    def test_the_first_minute_is_inside_and_the_end_is_outside(self):
        # 2026-11-17 is a tuesday.
        self.assertEqual(rule('--at', '2026-11-17T21:00:00Z'),
                         (0, 'may reboot now: inside the maintenance window, which ends tuesday 2026-11-17 22:00 UTC'))
        self.assertEqual(rule('--at', '2026-11-17T21:59:59Z')[0], 0)
        self.assertEqual(rule('--at', '2026-11-17T22:00:00Z'),
                         (1, 'waits for the maintenance window: tuesday 2026-11-24 21:00 UTC, for 60 minutes; '
                             'the only server of app_servers serves the users'))

    def test_another_time_zone_in_the_time_given_counts_in_utc(self):
        self.assertEqual(rule('--at', '2026-11-17T22:30:00+01:00')[0], 0)

    def test_a_window_across_midnight_and_the_end_of_the_week(self):
        window = ['--weekday', 'sunday', '--starts-at', '23:30', '--length-minutes', '60']
        self.assertEqual(rule('--at', '2026-11-22T23:45:00Z', window=window)[0], 0)
        self.assertEqual(rule('--at', '2026-11-23T00:15:00Z', window=window),
                         (0, 'may reboot now: inside the maintenance window, which ends monday 2026-11-23 00:30 UTC'))
        self.assertEqual(rule('--at', '2026-11-23T00:30:00Z', window=window)[0], 1)

    def test_a_persons_reboot_that_users_do_not_see_may_run_at_any_time(self):
        outside = ('--at', '2026-11-18T12:00:00Z')
        self.assertEqual(rule(*outside, servers=2), (0, 'may reboot now: another server of app_servers carries the work'))
        self.assertEqual(rule(*outside, pool='jobs_servers')[0], 0)
        self.assertEqual(rule(*outside, pool='staging_server')[0], 0)
        self.assertEqual(rule(*outside, live='false')[0], 0)
        self.assertEqual(rule(*outside, '--a-person-allows-it')[0], 0)
        self.assertEqual(rule(*outside, pool='load_balancer_servers')[0], 1)

    def test_the_automatic_maintenance_never_reboots_a_production_pools_only_server(self):
        inside = ('--at', '2026-11-17T21:10:00Z', '--automatic-weekly-maintenance')
        self.assertEqual(rule(*inside, servers=2), (0, 'may reboot now: another server of app_servers carries the work'))
        self.assertEqual(rule(*inside, pool='staging_server'), (0, 'may reboot now: staging01 serves no users'))
        for pool, live in (('app_servers', 'true'), ('jobs_servers', 'true'), ('load_balancer_servers', 'true'),
                           ('app_servers', 'false'), ('cache_servers', 'true')):
            with self.subTest(pool=pool, live=live):
                self.assertEqual(rule(*inside, pool=pool, live=live),
                                 (1, f'waits for a person: the automatic weekly maintenance never reboots the only server of '
                                     f'{pool}; a person reboots it in the maintenance window'))

    def test_a_wrong_time_is_refused(self):
        self.assertEqual(rule('--at', '2026-11-18T12:00:00Z', window=['--weekday', 'tuesday', '--starts-at', '9:00',
                                                                       '--length-minutes', '60'])[0], 2)


class TheSettings(unittest.TestCase):
    def setting(self, pattern):
        return re.search(pattern, (T/'mmx_project_settings.yml').read_text(), re.M)[1]

    def test_the_window_is_a_quiet_night_hour_clear_of_the_nightly_work(self):
        weekday = self.setting(r'^    weekday: (\S+)$')
        starts_at = self.setting(r'^    starts_at: "(\S+)"$')
        length = int(self.setting(r'^    length_minutes: (\d+)$'))
        nightly = self.setting(r'^  nightly_work_starts_at: "(\S+)"$')
        self.assertEqual((weekday, starts_at, length), ('wednesday', '03:00', 120))
        # Not the restore drill's day, and after the night's backups and the uploads' copy an hour later.
        self.assertNotEqual(weekday, self.setting(r'^  weekly_work_day: (\S+)$'))
        minutes = lambda hhmm: int(hhmm[:2]) * 60 + int(hhmm[3:])
        self.assertGreaterEqual(minutes(starts_at), minutes(nightly) + 120)
        self.assertEqual(self.setting(r'^  automatic_weekly_maintenance: (\S+)$'), 'true')

    def test_no_warning_wait_for_a_reboot_is_left(self):
        for path in ('mmx_project_settings.yml', 'mmhotline_settings.yml', 'playbooks/every_server.yml', 'triage_agent_rules.md'):
            with self.subTest(path=path):
                self.assertNotIn('minutes_between_the_warning_and_a_reboot', (T/path).read_text())
        self.assertNotIn('reboot_servers_after_updates:', (T/'mmhotline_settings.yml').read_text())
        self.assertNotIn('reboots_that_may_run_now', (T/'mmwatchdog_checks/every_server.yml').read_text())


class TemplateCopies:
    """A filled copy of the template, and the environment of one node task from `mmx explain`."""

    def copy_of_the_template(self, temporary, settings_changes=(), inventory_changes=()):
        root = Path(temporary)/'systems'
        shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
        template_values.fill_the_values_the_setup_fills(root)
        for name, changes in (('mmx_project_settings.yml', settings_changes), ('inventories/servers.yml', inventory_changes)):
            text = (root/name).read_text()
            for old, new in changes:
                self.assertEqual(text.count(old), 1, old)
                text = text.replace(old, new)
            (root/name).write_text(text)
        return root

    def task_environment(self, root, playbook, path_end, node, *extra):
        explained = subprocess.run([MMX, 'explain', playbook, '--json', *extra], cwd=root, text=True, capture_output=True)
        self.assertEqual(explained.returncode, 0, explained.stderr)
        task = next(task for stage in json.loads(explained.stdout)['fleet_stages'] for task in stage.get('node_tasks') or []
                    if task['path'].endswith(path_end) and task['node'] == node)
        env = {}
        for item in task['arguments']:
            if item['field'].startswith('shell.env.'):
                value = item['value']
                env[item['field'][len('shell.env.'):]] = value if isinstance(value, str) else json.dumps(value)
        return env


@unittest.skipUnless(MMX, 'Set MMX_BINARY to explain the actual playbooks.')
class ThePlaybooksDecide(TemplateCopies, unittest.TestCase):
    LIVE = [('public_site_checks_run: false', 'public_site_checks_run: true')]
    APP002 = [('    nodes: [app001]\n', '    nodes: [app001, app002]\n'),
              ('\n  db01:\n', '\n  app002:\n    address: 10.20.1.2\n    vars:\n      private_ip: 10.20.1.2\n'
               '      public_ipv4_address: 203.0.113.12\n      server_type: cx33\n      location: fsn1\n'
               '      wireguard_public_key: "xntON0r+ip4v53R2PDYOEKeq0RH91Y9x307uPnUQOTE="\n\n  db01:\n')]

    def decide(self, at, *extra, settings_changes=(), inventory_changes=()):
        """Runs reboot_servers_after_updates' first program for app001, as at the time given, and returns its JSON."""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_of_the_template(temporary, settings_changes, inventory_changes)
            env = {**os.environ, **self.task_environment(root, 'reboot_servers_after_updates', '/whether_a_reboot_waits_and_may_run_now', 'app001', *extra)}
            marker = Path(temporary)/'reboot-required'
            marker.touch()
            stand_in = Path(temporary)/'rule'
            stand_in.write_text(f'#!/bin/sh\nexec {sys.executable} {RULE} "$@" --at {at}\n')
            stand_in.chmod(0o755)
            program = env['PROGRAM'].replace('/var/run/reboot-required', str(marker)).replace(
                '/usr/local/bin/check-whether-a-reboot-may-run-now', str(stand_in))
            result = subprocess.run(['bash', '-c', program], env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_a_persons_run_skips_the_only_app_server_outside_the_window_and_says_until_when(self):
        self.assertEqual(self.decide('2026-11-18T12:00:00Z', settings_changes=self.LIVE), {
            'a_reboot_waits': True, 'the_reboot_may_run_now': False, 'the_only_server_of_a_pool_that_serves_users': True,
            'why': 'waits for the maintenance window: wednesday 2026-11-25 03:00 UTC, for 120 minutes; '
                   'the only server of app_servers serves the users', 'pool': 'app_servers', 'servers_in_the_pool': 1})

    def test_a_persons_run_reboots_the_only_app_server_inside_the_window_with_the_public_site_pause(self):
        decision = self.decide('2026-11-25T03:10:00Z', settings_changes=self.LIVE)
        self.assertTrue(decision['the_reboot_may_run_now'], decision)
        self.assertTrue(decision['the_only_server_of_a_pool_that_serves_users'], decision)

    def test_the_automatic_maintenance_never_reboots_app001_alone(self):
        decision = self.decide('2026-11-25T03:10:00Z', '--var', 'run_as_the_automatic_weekly_maintenance=true', settings_changes=self.LIVE)
        self.assertFalse(decision['the_reboot_may_run_now'], decision)
        self.assertIn('the automatic weekly maintenance never reboots the only server of app_servers', decision['why'])
        # Not before go-live either.
        decision = self.decide('2026-11-25T03:10:00Z', '--var', 'run_as_the_automatic_weekly_maintenance=true')
        self.assertFalse(decision['the_reboot_may_run_now'], decision)

    def test_the_automatic_maintenance_reboots_an_app_server_of_two_without_the_public_site_pause(self):
        decision = self.decide('2026-11-18T12:00:00Z', '--var', 'run_as_the_automatic_weekly_maintenance=true',
                               settings_changes=self.LIVE, inventory_changes=self.APP002)
        self.assertEqual(decision['why'], 'may reboot now: another server of app_servers carries the work')
        self.assertFalse(decision['the_only_server_of_a_pool_that_serves_users'])
        self.assertEqual((decision['pool'], decision['servers_in_the_pool']), ('app_servers', 2))

    def the_reboot_goes_on(self, automatic, servers_in_the_pool, others):
        """Runs util01's decision right before a reboot, from `mmx explain`, with the other servers' checks given."""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_of_the_template(temporary, self.LIVE, self.APP002)
            explained = subprocess.run([MMX, 'explain', 'reboot_servers_after_updates', '--json', '--var',
                                        'run_as_the_automatic_weekly_maintenance=true'], cwd=root, text=True, capture_output=True)
        self.assertEqual(explained.returncode, 0, explained.stderr)
        def tasks(stages):
            for stage in stages:
                yield from stage.get('node_tasks') or []
                yield from tasks(stage.get('fleet_stages') or [])
        task = next(task for task in tasks(json.loads(explained.stdout)['fleet_stages']) if task['path'].endswith('/whether_the_reboot_goes_on'))
        program = next(item['reference'] for item in task['arguments'] if item['field'] == 'shell.env.PROGRAM')
        result = subprocess.run(['bash', '-c', program], text=True, capture_output=True, stdin=subprocess.DEVNULL,
                                env={**os.environ, 'AUTOMATIC': automatic, 'SERVERS_IN_THE_POOL': str(servers_in_the_pool),
                                     'OTHER_SERVERS': json.dumps(others)})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_automatic_maintenance_reboots_only_while_another_server_of_the_pool_does_its_work(self):
        # app001 and app002 in app_servers, and app002's web container is unhealthy: app001 waits.
        self.assertFalse(self.the_reboot_goes_on('true', 2, {'app002': {'does_its_work': False}}))
        self.assertFalse(self.the_reboot_goes_on('true', 2, {}))
        self.assertTrue(self.the_reboot_goes_on('true', 2, {'app002': {'does_its_work': True}}))
        self.assertTrue(self.the_reboot_goes_on('true', 3, {'app002': {'does_its_work': False}, 'app003': {'does_its_work': True}}))
        # staging01, a pool of one that the automatic maintenance reboots, and a person's run, need no other server.
        self.assertTrue(self.the_reboot_goes_on('true', 1, {}))
        self.assertTrue(self.the_reboot_goes_on('false', 2, {'app002': {'does_its_work': False}}))

    def test_the_other_servers_are_checked_right_before_the_reboot_and_a_waiting_server_is_skipped(self):
        source = (T/'playbooks/reboot_servers_after_updates.yml').read_text()
        loop = source.split('  - id: reboot_each_server_whose_updates_wait_for_a_reboot\n', 1)[1]
        stages = re.findall(r'(?m)^      - id: (\S+)$', loop)
        self.assertEqual(stages, ['the_weekly_maintenance_goes_on', 'check_that_the_other_servers_of_the_pool_do_their_work',
                                  'another_server_of_the_pool_carries_the_work', 'pause_the_public_site_checks_for_the_only_server_of_a_pool',
                                  'reboot_the_server', 'wait_until_the_server_does_its_work_again',
                                  'end_the_pause_of_the_public_site_checks', 'the_server_does_its_work_again'])
        check = loop.split('      - id: check_that_the_other_servers_of_the_pool_do_their_work\n', 1)[1].split('\n      - id: ', 1)[0]
        self.assertIn('except_nodes: [util_server, database_servers, database_restore_servers, systems_desks, "{{ .server }}"]', check)
        self.assertIn('- "{{ .vars.run_as_the_automatic_weekly_maintenance }}"', check)
        self.assertIn('- equals: ["{{ .outputs.find_the_servers_whose_updates_wait_for_a_reboot[.node.name].pool }}", '
                      '"{{ .outputs.find_the_servers_whose_updates_wait_for_a_reboot[.server].pool }}"]', check)
        self.assertIn('script: if /usr/local/bin/check-that-this-server-does-its-work >&2; then echo true; else echo false; fi', check)
        for stage in stages[3:]:
            with self.subTest(stage=stage):
                block = loop.split(f'      - id: {stage}\n', 1)[1].split('\n      - id: ', 1)[0]
                self.assertIn('"{{ .outputs.another_server_of_the_pool_carries_the_work.util01.the_reboot_goes_on }}"', block)

    def test_each_turn_starts_with_the_check_that_the_maintenance_goes_on(self):
        for playbook, stages in (('reboot_servers_after_updates', ['the_weekly_maintenance_goes_on']),
                                 ('update_database_servers', ['the_weekly_maintenance_goes_on_with_the_replica'])):
            source = (T/f'playbooks/{playbook}.yml').read_text()
            for stage in stages:
                with self.subTest(playbook=playbook, stage=stage):
                    block = source.split(f'- id: {stage}\n', 1)[1][:900]
                    self.assertIn('nodes: util_server', block)
                    self.assertIn('when: "{{ .vars.run_as_the_automatic_weekly_maintenance }}"', block)
                    self.assertIn('/usr/local/bin/weekly-maintenance-goes-on --weekday', block)
            self.assertIn('run_as_the_automatic_weekly_maintenance: {type: boolean, default: false}', source)
        database = (T/'playbooks/update_database_servers.yml').read_text()
        self.assertIn('- id: the_weekly_maintenance_goes_on_with_the_switchover', database)
        # The switchover is confirmed before the old primary's turn.
        self.assertLess(database.index('- id: the_updated_replica_is_the_primary'), database.index('- id: update_the_old_primary'))


class TheCheckBeforeEachTurn(unittest.TestCase):
    def run_gate(self, at, touch_the_marker=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker, ended = root/'systems_repository.lock.waiting', root/'ended_early_because'
            if touch_the_marker == 'stale':
                marker.write_text('mmhotline: an old wait\n')
                os.utime(marker, (time.time() - 60, time.time() - 60))
            process = subprocess.Popen([sys.executable, str(GATE), '--weekday', 'wednesday', '--starts-at', '03:00',
                                        '--length-minutes', '120', '--at', at, '--waiting-marker', str(marker),
                                        '--ended-early-because', str(ended), '--seconds-to-watch', '1'],
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if touch_the_marker == 'fresh':
                time.sleep(0.3)
                marker.write_text('mmhotline: mmx run every_server --inventory servers for the triage agent; waiting since 2026-11-25T03:20:00Z\n')
            stdout, stderr = process.communicate(timeout=30)
            return process.returncode, stdout.strip(), ended.read_text() if ended.exists() else None

    def test_inside_the_window_with_no_waiting_mmhotline_the_turn_starts(self):
        status, said, ended = self.run_gate('2026-11-25T03:20:00Z')
        self.assertEqual(status, 0, said)
        self.assertIn('ends wednesday 2026-11-25 05:00 UTC', said)
        self.assertIsNone(ended)

    def test_a_marker_mmhotline_no_longer_rewrites_is_ignored(self):
        self.assertEqual(self.run_gate('2026-11-25T03:20:00Z', 'stale')[0], 0)

    def test_it_gives_way_to_a_waiting_mmhotline(self):
        status, said, ended = self.run_gate('2026-11-25T03:20:00Z', 'fresh')
        self.assertEqual(status, 1)
        self.assertIn('gives way to MMHotline', said)
        self.assertEqual(ended, "gives way to MMHotline, which waits for util01's lock: mmhotline: mmx run every_server "
                                '--inventory servers for the triage agent; waiting since 2026-11-25T03:20:00Z\n')

    def test_it_ends_with_the_window(self):
        status, said, ended = self.run_gate('2026-11-25T05:00:00Z')
        self.assertEqual(status, 1)
        self.assertEqual(ended, 'the maintenance window (wednesday 03:00 UTC, for 120 minutes) has ended\n')


@unittest.skipUnless(MMX, 'Set MMX_BINARY to explain the actual playbooks.')
class TheDatabaseServersRunOnlyWhenSomethingWaits(TemplateCopies, unittest.TestCase):
    DB02 = [('    nodes: [db01]\n', '    nodes: [db01, db02]\n'),
            ('\n  util01:\n', '\n  db02:\n    address: 10.20.2.2\n    vars:\n      private_ip: 10.20.2.2\n'
             '      public_ipv4_address: 203.0.113.22\n      server_type: cx33\n      location: fsn1\n'
             '      wireguard_public_key: "xntON0r+ip4v53R2PDYOEKeq0RH91Y9x307uPnUQOTE="\n\n  util01:\n')]

    def run_what_waits(self, apt='', services='', settings='', psql_fails=False, reboot=False, apt_fails=False, needrestart_fails=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_of_the_template(temporary)
            env = self.task_environment(root, 'update_database_servers', '/what_waits', 'db01',
                                        '--var', 'run_as_the_automatic_weekly_maintenance=true')
            binary = stand_ins(Path(temporary)/'bin', {
                # The simulation is a dist-upgrade, so a kernel update that needs a new package counts.
                'apt-get': f'import sys\nif "dist-upgrade" not in sys.argv or {apt_fails!r}: sys.exit(100)\nsys.stdout.write({apt!r})\n',
                'needrestart': f'import sys\nif {needrestart_fails!r}: sys.exit(1)\nsys.stdout.write("NEEDRESTART-VER: 3.6\\n" + {services!r})\n',
                'runuser': 'import sys\nsys.exit(2)\n' if psql_fails else f'print({settings!r})\n',
            })
            marker = Path(temporary)/'reboot-required'
            if reboot:
                marker.touch()
            program = env['PROGRAM'].replace('/var/run/reboot-required', str(marker))
            return subprocess.run(['bash', '-c', program], text=True, capture_output=True, stdin=subprocess.DEVNULL,
                                  env={**os.environ, **env, 'PATH': f'{binary}:{os.environ["PATH"]}'})

    def what_waits(self, **arguments):
        result = self.run_what_waits(**arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_a_failing_apt_get_or_needrestart_fails_the_check_instead_of_saying_nothing_waits(self):
        for name, arguments, said in (('apt-get', dict(apt_fails=True), 'apt-get --simulate dist-upgrade failed (exit 100)'),
                                      ('needrestart', dict(needrestart_fails=True), 'needrestart failed (exit 1)')):
            with self.subTest(name=name):
                result = self.run_what_waits(**arguments)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(said, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_a_clean_server_waits_for_nothing(self):
        self.assertEqual(self.what_waits(apt='Inst libfoo1 [1.0] (1.1 Debian:13.2/stable [amd64])\n'),
                         {'waits': False, 'why': 'nothing waits'})

    def test_each_kind_of_waiting_work_is_named(self):
        self.assertEqual(self.what_waits(apt='Inst postgresql-17 [17.5-1] (17.6-0+deb13u1 Debian-Security:13/stable-security [amd64])\n'
                                             'Inst linux-image-amd64 [6.12.1] (6.12.2 Debian-Security:13/stable-security [amd64])\n'),
                         {'waits': True, 'why': 'waits for security updates: postgresql-17 linux-image-amd64'})
        self.assertEqual(self.what_waits(services='NEEDRESTART-SVC: pgautofailover.service\nNEEDRESTART-SVC: pgbouncer.service\n'),
                         {'waits': True, 'why': 'waits for a restart of services that use a replaced library: pgautofailover.service pgbouncer.service'})
        self.assertEqual(self.what_waits(settings='shared_buffers'),
                         {'waits': True, 'why': 'waits for a Postgres restart for the settings shared_buffers'})
        self.assertEqual(self.what_waits(reboot=True), {'waits': True, 'why': 'waits for a reboot'})
        self.assertEqual(self.what_waits(psql_fails=True), {'waits': True, 'why': 'waits for an answer from Postgres'})
        self.assertEqual(self.what_waits(reboot=True, settings='archive_mode'),
                         {'waits': True, 'why': 'waits for a reboot; a Postgres restart for the settings archive_mode'})

    def decision(self, found, inventory_changes=()):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_of_the_template(temporary, inventory_changes=inventory_changes)
            env = self.task_environment(root, 'update_database_servers', '/whether_this_run_updates_the_database_servers', 'util01',
                                        '--var', 'run_as_the_automatic_weekly_maintenance=true')
        env['FOUND'] = json.dumps(found)
        return subprocess.run(['bash', '-c', env['PROGRAM']], text=True, capture_output=True, stdin=subprocess.DEVNULL,
                              env={**os.environ, **env})

    def test_a_clean_pair_gets_no_switchover_and_a_waiting_one_does(self):
        clean = self.decision({'db01': {'waits': False}, 'db02': {'waits': False}}, self.DB02)
        self.assertEqual((clean.returncode, clean.stdout.strip()), (0, 'false'), clean.stderr)
        waiting = self.decision({'db01': {'waits': False}, 'db02': {'waits': True}}, self.DB02)
        self.assertEqual((waiting.returncode, waiting.stdout.strip()), (0, 'true'), waiting.stderr)

    def test_the_automatic_maintenance_refuses_db01_alone(self):
        alone = self.decision({'db01': {'waits': True}})
        self.assertEqual(alone.returncode, 1)
        self.assertIn('never restarts a database server alone', alone.stderr)

    def test_a_persons_run_always_updates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_of_the_template(temporary)
            env = self.task_environment(root, 'update_database_servers', '/whether_this_run_updates_the_database_servers', 'util01')
        result = subprocess.run(['bash', '-c', env['PROGRAM']], text=True, capture_output=True, env={**os.environ, **env})
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'true'), result.stderr)

    def test_every_later_stage_waits_for_the_decision(self):
        source = (T/'playbooks/update_database_servers.yml').read_text()
        for stage in ('update_each_replica', 'read_the_production_formation', 'pause_the_alerts_of_the_database_servers_for_the_switchover',
                      'switch_the_primary_to_an_updated_replica', 'end_the_alert_pause_of_the_switchover', 'update_the_old_primary'):
            with self.subTest(stage=stage):
                block = source.split(f'\n  - id: {stage}\n', 1)[1].split('\n  - id: ', 1)[0]
                self.assertIn('"{{ .outputs.read_which_database_server_is_the_primary.util01.the_run_updates }}"', block)
        # The automatic maintenance never falls back to restarting a primary in place.
        self.assertIn('- id: a_healthy_replica_can_take_over_before_the_automatic_weekly_maintenance', source)
        self.assertIn('- id: an_updated_replica_can_take_over_in_the_automatic_weekly_maintenance', source)


class TheWeeklyJob(unittest.TestCase):
    def job_script(self):
        text = ROLE.read_text().split('      name: weekly_maintenance\n', 1)[1]
        body = re.search(r'      script: \|\n(.*?)      env:', text, re.S)[1]
        return '\n'.join(line[8:] for line in body.splitlines())

    def run_job(self, database_servers=('db01',), ended_early_in=None, failing=None, locked_out=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git = lambda *arguments: subprocess.run(['git', '-C', str(root/'systems_repository'), *arguments], check=True,
                                                    capture_output=True, text=True,
                                                    env={**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_AUTHOR_NAME': 'a',
                                                         'GIT_AUTHOR_EMAIL': 'a@example.invalid', 'GIT_COMMITTER_NAME': 'a',
                                                         'GIT_COMMITTER_EMAIL': 'a@example.invalid'}).stdout.strip()
            (root/'systems_repository').mkdir()
            git('init', '-q', '-b', 'main')
            git('commit', '-q', '--allow-empty', '-m', 'first')
            head = git('rev-parse', 'HEAD')
            (root/'weekly_maintenance').mkdir()
            (root/'systems_repository.lock').write_text('')
            log = root/'commands'
            binary = stand_ins(root/'bin', {
                'flock': LOGGING,
                'find_the_trusted_commit_of_the_systems_repository': LOGGING + f'print({head!r})\n',
                'mmx': LOGGING + f'''
args = sys.argv[1:]
if args[:2] == ['nodes', '--json']:
    print(json.dumps({{'groups': {{'database_servers': {list(database_servers)!r}}}}}))
elif args[:1] == ['run']:
    if args[1] == {ended_early_in!r}:
        open({str(root/'weekly_maintenance/ended_early_because')!r}, 'w').write('gives way to MMHotline, which waits\\n')
        sys.exit(1)
    if args[1] == {failing!r}:
        sys.exit(1)
''',
            })
            script = self.job_script().replace('/var/lib/mmhotline', str(root)).replace('/var/lib/weekly_maintenance', str(root/'weekly_maintenance'))
            if locked_out:
                (root/'everyone-locked-out').write_text('')
            script = script.replace('/etc/mmhotline/everyone-locked-out', str(root/'everyone-locked-out'))
            result = subprocess.run(['bash', '-c', script], cwd=root, text=True, capture_output=True, timeout=60,
                                    env={**os.environ, 'PATH': f'{binary}:{os.environ["PATH"]}', 'COMMAND_LOG': str(log), 'JOB_NAME': 'weekly_maintenance'})
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, commands

    def runs(self, commands):
        return [command[2] for command in commands if command[:2] == ['mmx', 'run']]

    def test_db01_alone_is_never_restarted_and_the_reboots_still_run(self):
        result, commands = self.run_job()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runs(commands), ['reboot_servers_after_updates'])
        self.assertIn('one database server: the weekly maintenance never restarts it', result.stdout)
        self.assertIn(['mmx', 'run', 'reboot_servers_after_updates', '--var', 'run_as_the_automatic_weekly_maintenance=true',
                       '--non-interactive'], commands)

    def test_two_database_servers_come_first(self):
        result, commands = self.run_job(database_servers=('db01', 'db02'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runs(commands), ['update_database_servers', 'reboot_servers_after_updates'])

    def test_it_asks_mmhotline_before_it_takes_the_lock(self):
        result, commands = self.run_job()
        names = [command[0] for command in commands]
        self.assertLess(names.index('find_the_trusted_commit_of_the_systems_repository'), names.index('mmx'))
        script = self.job_script()
        self.assertLess(script.index('trusted=$(find_the_trusted_commit_of_the_systems_repository)'), script.index('exec 9>>'))

    def test_an_early_end_exits_0_and_runs_nothing_more(self):
        result, commands = self.run_job(database_servers=('db01', 'db02'), ended_early_in='update_database_servers')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runs(commands), ['update_database_servers'])
        self.assertIn('the weekly maintenance ended early in update_database_servers: gives way to MMHotline', result.stdout)

    def test_a_failed_run_fails_the_job_and_util01_does_not_reboot(self):
        result, commands = self.run_job(database_servers=('db01', 'db02'), failing='update_database_servers')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.runs(commands), ['update_database_servers'])
        # util01's reboot follows only a job that ended with success.
        self.assertIn('OnSuccess=reboot_util01_after_the_weekly_maintenance.service', ROLE.read_text())

    def test_during_a_lock_out_it_runs_nothing(self):
        result, commands = self.run_job(locked_out=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, [])

    def test_root_owns_the_early_end_and_removes_it_before_each_start(self):
        role = ROLE.read_text()
        directory = role.split('- id: create_the_directory_of_the_weekly_maintenance\n', 1)[1][:200]
        self.assertIn('path: /var/lib/weekly_maintenance\n      owner: root\n      group: root\n      permissions_mode: "0755"', directory)
        self.assertIn('ExecStartPre=+/bin/rm -f /var/lib/weekly_maintenance/ended_early_because', role)
        self.assertIn('10-forget-the-last-early-end.conf', role.split('- id: remove_the_drop_ins_of_the_weekly_maintenance_while_it_is_turned_off\n', 1)[1][:300])
        # The job runs as mmhotline and only reads the file; weekly-maintenance-goes-on writes it as root.
        self.assertNotIn('rm -f "$ended_early"', self.job_script())
        for playbook in ('reboot_servers_after_updates', 'update_database_servers'):
            source = (T/f'playbooks/{playbook}.yml').read_text()
            for block in source.split('script: /usr/local/bin/weekly-maintenance-goes-on')[1:]:
                self.assertNotIn('run_as_user_account', block.split('changed_when', 1)[0])

    def test_the_job_never_catches_up_a_missed_window_and_upgrades_never_kill_it(self):
        text = ROLE.read_text().split('      name: weekly_maintenance\n', 1)[1][:400]
        self.assertIn('systemd_calendar_schedule: "{{ .inputs.maintenance_window.weekday }} *-*-* {{ .inputs.maintenance_window.starts_at }}:00 UTC"', text)
        self.assertIn('run_missed_job_after_downtime: false', text)
        self.assertIn('when: "{{ .inputs.automatic_weekly_maintenance }}"', ROLE.read_text().split('- id: run_the_weekly_maintenance\n', 1)[1][:80])
        self.assertIn(r'$nrconf{override_rc}{qr(^weekly_maintenance\.service$)} = 0;', (T/'roles/every_server/files/needrestart.conf').read_text())
        desk = (T/'roles/systems_desk/main.yml').read_text().split('      name: reboot_systems_desk_after_updates\n', 1)[1][:400]
        self.assertIn('run_missed_job_after_downtime: false', desk)


class TheSelfReboots(unittest.TestCase):
    """util01's and a desk's own reboot: every guard defers with exit 0, and a reboot pauses the alerts first."""

    def run_util01(self, reboot_waits=True, locked_out=False, lock_busy=False, incidents='{"incidents": []}', pause_exit=0,
                   ended_early='', goes_on=(0, 'the next server\'s turn may start')):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root/'commands'
            (root/'lock').write_text('mmhotline: mmx run every_server for the triage agent\n' if lock_busy else '')
            binary = stand_ins(root/'bin', {
                'flock': LOGGING + f"sys.exit(1 if {lock_busy!r} else 0)\n",
                # runuser -u mmhotline -- COMMAND...: the stand-in runs the command as the test's user.
                'runuser': LOGGING + "os.execvp(sys.argv[4], sys.argv[4:])\n",
                'weekly-maintenance-goes-on': LOGGING + f"print({goes_on[1]!r})\nsys.exit({goes_on[0]})\n",
                'mmhotline': LOGGING + f"print({incidents!r})\n",
                'util01-alert-pause': LOGGING + f"sys.exit({pause_exit} if sys.argv[1] == 'start' else 0)\n",
                'systemctl': LOGGING,
            })
            program = UTIL01_REBOOT.read_text()
            for old, new in (('/var/run/reboot-required', root/'reboot-required'), ('/etc/mmhotline/everyone-locked-out', root/'locked-out'),
                             ('/var/lib/mmhotline/systems_repository.lock', root/'lock'),
                             ('/var/lib/weekly_maintenance/ended_early_because', root/'ended_early_because'),
                             ('/var/lib/util01_weekly_reboot/the_alert_pause_waits_for_the_boot', root/'marker/waits'),
                             ('/usr/local/bin/', f'{binary}/')):
                program = program.replace(old, str(new))
            if reboot_waits:
                (root/'reboot-required').touch()
            if locked_out:
                (root/'locked-out').touch()
            (root/'ended_early_because').write_text(ended_early)
            result = subprocess.run(['bash', '-c', program, 'reboot-util01-after-the-weekly-maintenance'], text=True, capture_output=True,
                                    timeout=30, env={**os.environ, 'PATH': f'{binary}:{os.environ["PATH"]}', 'COMMAND_LOG': str(log),
                                                     'WINDOW_WEEKDAY': 'wednesday', 'WINDOW_STARTS_AT': '03:00', 'WINDOW_LENGTH_MINUTES': '120'})
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            self.lock_line = (root/'lock').read_text()
            return result, commands, (root/'marker/waits').exists()

    def test_util01_reboots_after_a_silent_pause(self):
        result, commands, marker = self.run_util01()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c for c in commands if c[0] not in ('flock', 'runuser')], [
            ['weekly-maintenance-goes-on', '--weekday', 'wednesday', '--starts-at', '03:00', '--length-minutes', '120',
             '--ended-early-because', '/dev/null'],
            ['mmhotline', 'incidents', 'list', '--json'],
            ['util01-alert-pause', 'start', '--for', '5m', '--reason', 'weekly_maintenance', '--without-maintenance-on-and-off-alerts'],
            ['systemctl', '--no-block', 'reboot']])
        self.assertTrue(marker)
        self.assertTrue(self.lock_line.startswith('reboot of util01 after the weekly maintenance; user root; process '), self.lock_line)

    def test_root_takes_util01s_lock_only_through_the_mmhotline_user(self):
        # The mmhotline user owns /var/lib/mmhotline and could put a link there, so root never opens a path inside it.
        result, commands, _ = self.run_util01()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands[0][:4], ['runuser', '-u', 'mmhotline', '--'])
        self.assertLess(commands.index(next(c for c in commands if c[0] == 'flock')), commands.index(next(c for c in commands if c[0] == 'mmhotline')))
        program = UTIL01_REBOOT.read_text()
        helper = program.split("exec runuser -u mmhotline -- bash -c '", 1)[1].split("' reboot-util01-lock-holder", 1)[0]
        outside = program.replace(helper, '')
        self.assertNotIn('/var/lib/mmhotline', outside.split('set -euo pipefail', 1)[1])
        self.assertNotIn('exec 9>>', outside)
        # The helper holds the lock while the root process lives, which exec hands to the reboot command.
        self.assertIn('while state=$(awk "/^State:/{print \\$2}" "/proc/$1/status" 2> /dev/null) && [ -n "$state" ] && [ "$state" != Z ]; do', program)
        self.assertTrue(program.rstrip().endswith('exec systemctl --no-block reboot'))
        unit = ROLE.read_text().split('name: reboot_util01_after_the_weekly_maintenance.service\n', 1)[1][:600]
        self.assertIn('Environment=WINDOW_WEEKDAY={{ .inputs.maintenance_window.weekday }} WINDOW_STARTS_AT={{ .inputs.maintenance_window.starts_at }} '
                      'WINDOW_LENGTH_MINUTES={{ .inputs.maintenance_window.length_minutes }}', unit)

    def test_util01_defers_for_each_guard(self):
        for name, arguments, said in (
                ('no reboot waits', dict(reboot_waits=False), 'no reboot waits'),
                ('a lock-out', dict(locked_out=True), 'everyone is locked out'),
                ('an early end', dict(ended_early='gives way to MMHotline, which waits for util01\'s lock: mmhotline: a run\n'),
                 'the weekly maintenance ended early (gives way to MMHotline'),
                ('a busy lock', dict(lock_busy=True), "a run holds util01's lock (mmhotline: mmx run every_server for the triage agent)"),
                ('a closed window', dict(goes_on=(1, 'the weekly maintenance ends here: the maintenance window (wednesday 03:00 UTC, for 120 minutes) has ended'
                                                     '; the servers it did not reach wait for next week')),
                 'the maintenance window (wednesday 03:00 UTC, for 120 minutes) has ended'),
                ('a waiting MMHotline', dict(goes_on=(1, "the weekly maintenance ends here: gives way to MMHotline, which waits for util01's lock: a run")),
                 'gives way to MMHotline'),
                ('an open SOS', dict(incidents='{"incidents": [{"incident_id": "a"}]}'), '1 SOS incident(s) not resolved'),
                ('an MMHotline that does not answer', dict(incidents='not json'), 'did not list its incidents')):
            with self.subTest(name=name):
                result, commands, marker = self.run_util01(**arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(said, result.stdout)
                self.assertFalse([c for c in commands if c[0] in ('util01-alert-pause', 'systemctl')])
                self.assertFalse(marker)

    def test_util01_does_not_reboot_without_its_alert_pause(self):
        result, commands, marker = self.run_util01(pause_exit=1)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(['systemctl', '--no-block', 'reboot'], commands)
        self.assertIn(['util01-alert-pause', 'end'], commands)

    def test_after_the_boot_the_pause_ends(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root/'commands'
            binary = stand_ins(root/'bin', {'mmwatchdog': LOGGING, 'util01-alert-pause': LOGGING})
            (root/'waits').write_text('2026-11-25T04:00:00Z\n')
            program = UTIL01_REBOOT.read_text().replace('/var/lib/util01_weekly_reboot/the_alert_pause_waits_for_the_boot', str(root/'waits')).replace('/usr/local/bin/', f'{binary}/')
            result = subprocess.run(['bash', '-c', program, 'reboot', '--end-the-alert-pause-after-the-boot'], text=True, capture_output=True,
                                    env={**os.environ, 'COMMAND_LOG': str(log)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(['util01-alert-pause', 'end'], [json.loads(line) for line in log.read_text().splitlines()])
            self.assertFalse((root/'waits').exists())
        unit = ROLE.read_text().split('name: end_the_alert_pause_after_the_weekly_util01_reboot.service\n', 1)[1][:700]
        self.assertIn('After=mmwatchdog.service', unit)
        self.assertIn('ConditionPathExists=/var/lib/util01_weekly_reboot/the_alert_pause_waits_for_the_boot', unit)

    def run_desk(self, reboot_waits=True, locked_out=False, sessions='', transient='no', mmx_runs=False, joined=True,
                 list_fails=False, show_fails=False, unit_show_fails=False, pgrep_status=None, busy_after_the_pause=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root/'commands'
            (root/'sessions').write_text(sessions)
            binary = stand_ins(root/'bin', {
                'loginctl': LOGGING + f'''
args = sys.argv[1:]
if args[0] == 'list-sessions':
    if {list_fails!r}: sys.exit(1)
    print(open({str(root/'sessions')!r}).read(), end='')
elif args[0] == 'show-session':
    if {show_fails!r}: sys.exit(1)
    print('sshd' if args[2] == '--property=Service' else 'active')
''',
                'systemctl': LOGGING + f'''
args = sys.argv[1:]
if 'list-units' in args:
    print('user-runtime-dir.service loaded active exited\\nevery-server-2026-11-25.service loaded active running')
elif 'show' in args:
    if {unit_show_fails!r}: sys.exit(1)
    print({transient!r} if 'every-server-2026-11-25.service' in args else 'no')
''',
                'pgrep': LOGGING + f"sys.exit({pgrep_status!r} if {pgrep_status!r} is not None else 0 if {mmx_runs!r} else 1)\n",
                # While the fleet hub accepts the pause, someone logs in or presses the lock-out button.
                'mmwatchdog': LOGGING + f'''
if sys.argv[1:3] == ['maintenance', 'on']:
    if {busy_after_the_pause!r} == 'login': open({str(root/'sessions')!r}, 'w').write('7 1001 alex - pts/0\\n')
    if {busy_after_the_pause!r} == 'lock-out': open({str(root/'locked-out')!r}, 'w').write('')
''',
            })
            program = DESK_REBOOT.read_text()
            for old, new in (('/var/run/reboot-required', root/'reboot-required'), ('/etc/systems-desk/everyone-locked-out', root/'locked-out'),
                             ('/etc/mmwatchdog/secrets/fleet-hub-join-code', root/'join-code'), ('/usr/local/bin/', f'{binary}/')):
                program = program.replace(old, str(new))
            for path, wanted in ((root/'reboot-required', reboot_waits), (root/'locked-out', locked_out), (root/'join-code', joined)):
                if wanted:
                    path.touch()
            result = subprocess.run(['bash', '-c', program], text=True, capture_output=True,
                                    env={**os.environ, 'PATH': f'{binary}:{os.environ["PATH"]}', 'COMMAND_LOG': str(log)})
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return result, commands

    def test_an_idle_desk_reboots_after_a_silent_pause_the_hub_accepted(self):
        result, commands = self.run_desk()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c for c in commands if c[0] == 'mmwatchdog' or c[1:] == ['--no-block', 'reboot']], [
            ['mmwatchdog', 'maintenance', 'on', '--every-check-group', '--for', '5m', '--reason', 'weekly_maintenance',
             '--without-maintenance-on-and-off-alerts'],
            ['systemctl', '--no-block', 'reboot']])

    def test_a_desk_in_use_waits(self):
        for name, arguments, said in (
                ('no reboot waits', dict(reboot_waits=False), 'no reboot waits'),
                ('a lock-out on this desk', dict(locked_out=True), 'lock-out button ran on this systems desk'),
                ('an SSH login', dict(sessions='3 1001 alex - pts/0\n'), 'an SSH login is open'),
                ('a desk job', dict(transient='yes'), "job every-server-2026-11-25.service runs on this systems desk"),
                ('an mmx run', dict(mmx_runs=True), 'an mmx run is going'),
                ('before util01 exists', dict(joined=False), 'does not report to MMWatchdog yet')):
            with self.subTest(name=name):
                result, commands = self.run_desk(**arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(said, result.stdout)
                self.assertNotIn(['systemctl', '--no-block', 'reboot'], commands)
                self.assertFalse([c for c in commands if c[0] == 'mmwatchdog'])

    def test_a_desk_whose_state_cannot_be_read_waits(self):
        for name, arguments, said in (
                ('loginctl list-sessions fails', dict(list_fails=True), 'loginctl did not list the login sessions'),
                ('loginctl show-session fails', dict(sessions='3 1001 alex - pts/0\n', show_fails=True), 'loginctl did not show login session 3'),
                ("a unit's state cannot be read", dict(unit_show_fails=True), "did not show its unit user-runtime-dir.service"),
                ('pgrep fails', dict(pgrep_status=3), 'pgrep did not say whether an mmx run is going (exit 3)')):
            with self.subTest(name=name):
                result, commands = self.run_desk(**arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(said, result.stdout)
                self.assertNotIn(['systemctl', '--no-block', 'reboot'], commands)
                self.assertFalse([c for c in commands if c[0] == 'mmwatchdog'])

    def test_a_desk_that_becomes_busy_while_the_hub_accepts_the_pause_ends_the_pause_and_waits(self):
        for busy, said in (('login', 'an SSH login is open'), ('lock-out', 'lock-out button ran on this systems desk')):
            with self.subTest(busy=busy):
                result, commands = self.run_desk(busy_after_the_pause=busy)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(said, result.stdout)
                self.assertIn('the alert pause of this systems desk ended again', result.stdout)
                self.assertNotIn(['systemctl', '--no-block', 'reboot'], commands)
                self.assertEqual([c[:3] for c in commands if c[0] == 'mmwatchdog'],
                                 [['mmwatchdog', 'maintenance', 'on'], ['mmwatchdog', 'maintenance', 'off']])


@unittest.skipUnless(MMX, 'Set MMX_BINARY to render the check files.')
class TheRemindersFollowWhoRestartsTheServer(unittest.TestCase):
    """30 days on a production pool's only server, 15 days where the automatic maintenance restarts it."""

    def rendered(self, path, node, groups, **inputs):
        template = (T/path).read_text()
        inputs = dict(is_database_server=False, is_staging_server=False, inventory_groups=groups, pgbouncer_runs_in_front_of_postgres=False) | inputs
        declared = {name: {'type': 'mapping' if isinstance(value, dict) else 'boolean', 'required': True} for name, value in inputs.items()}
        declared['block_devices'] = {'type': 'list', 'default': []}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'roles/render').mkdir(parents=True)
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars={})))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={node: {'address': '127.0.0.1'}})))
            (root/'roles/render/source.template').write_text(template.replace('.node.storage.block_devices', '.inputs.block_devices'))
            (root/'roles/render/main.yml').write_text(json.dumps(dict(inputs=declared, node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(role='render', inputs=inputs)])])))
            result = subprocess.run([MMX, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = next(task for task in json.loads(result.stdout)['fleet_stages'][0]['node_tasks'] if task.get('rendered_templates'))
        rendered = task['rendered_templates'][0]
        self.assertIn('text', rendered, rendered.get('not_rendered_because'))
        return rendered['text']

    def reminders(self, node, groups, is_database_server=False, is_staging_server=False):
        text = self.rendered('mmwatchdog_checks/every_server.yml', node, groups, is_database_server=is_database_server, is_staging_server=is_staging_server)
        security = text.split('\n  security_updates:\n', 1)[1]
        return (re.search(r'(?m)^    alert_after_failing_for: (\S+)$', security)[1],
                re.search(r'no_reboot_waits:\n(?:.*\n)*?        alert_after_failing_for: (\S+)', security)[1])

    ONE_EACH = {'app_servers': ['app001'], 'database_servers': ['db01'], 'util_server': ['util01'], 'systems_desks': ['desk01'],
                'jobs_servers': ['jobs001'], 'load_balancer_servers': [], 'staging_server': ['staging01'], 'database_restore_servers': []}
    TWO_EACH = ONE_EACH | {'app_servers': ['app001', 'app002'], 'database_servers': ['db01', 'db02'], 'jobs_servers': ['jobs001', 'jobs002']}

    def test_a_production_pools_only_server_reminds_after_30_days(self):
        self.assertEqual(self.reminders('app001', self.ONE_EACH), ('26h', '30d'))
        self.assertEqual(self.reminders('jobs001', self.ONE_EACH), ('26h', '30d'))
        self.assertEqual(self.reminders('db01', self.ONE_EACH, is_database_server=True), ('30d', '30d'))

    def test_every_server_the_maintenance_restarts_reminds_after_15_days(self):
        self.assertEqual(self.reminders('app001', self.TWO_EACH), ('26h', '15d'))
        self.assertEqual(self.reminders('db02', self.TWO_EACH, is_database_server=True), ('15d', '15d'))
        self.assertEqual(self.reminders('staging01', self.ONE_EACH, is_staging_server=True), ('26h', '15d'))
        self.assertEqual(self.reminders('desk01', {'systems_desks': ['desk01'], 'app_servers': [], 'database_servers': []}), ('26h', '15d'))
        # util01's role passes no groups.
        self.assertEqual(self.reminders('util01', {}), ('26h', '15d'))

    def library_reminder(self, groups):
        text = self.rendered('mmwatchdog_checks/database_servers.yml', 'db01', groups, is_database_server=True)
        group = text.split('\n  services_restarted_after_library_updates:\n', 1)[1]
        return re.search(r'(?m)^    alert_after_failing_for: (\S+)$', group)[1], group

    def test_a_database_server_reminds_about_a_replaced_library(self):
        days, group = self.library_reminder(self.ONE_EACH)
        self.assertEqual(days, '30d')
        self.assertIn('run_as_user_account: root', group)
        self.assertRegex(group, r'(?m)^        alert_severity: warn$')
        self.assertEqual(self.library_reminder(self.TWO_EACH)[0], '15d')
        staging = self.rendered('mmwatchdog_checks/database_servers.yml', 'staging01', self.ONE_EACH, is_staging_server=True)
        self.assertNotIn('services_restarted_after_library_updates', staging)

    def test_the_library_check_fails_only_while_a_service_uses_a_replaced_library(self):
        _, group = self.library_reminder(self.ONE_EACH)
        script = '\n'.join(line[12:] for line in re.search(r'(?ms)^          script: \|\n(.*?)^          run_as_user_account', group)[1].splitlines())
        with tempfile.TemporaryDirectory() as temporary:
            for listed, status in (('', 0), ('NEEDRESTART-SVC: pgautofailover.service\n', 1), (None, 2)):
                with self.subTest(listed=listed):
                    # None: needrestart itself fails, and the check fails with its reason instead of passing.
                    binary = stand_ins(Path(temporary)/'bin', {'needrestart': 'import sys\nsys.exit(1)\n' if listed is None else
                                                               f'import sys\nsys.stdout.write("NEEDRESTART-VER: 3.6\\nNEEDRESTART-KSTA: 1\\n" + {listed!r})\n'})
                    result = subprocess.run(['bash', '-c', script], text=True, capture_output=True,
                                            env={**os.environ, 'PATH': f'{binary}:{os.environ["PATH"]}'})
                    self.assertEqual(result.returncode, status, result.stdout + result.stderr)
                    if status == 1:
                        self.assertIn('pgautofailover.service', result.stdout)
                    if status == 2:
                        self.assertIn('needrestart failed (exit 1)', result.stdout)


if __name__ == '__main__':
    unittest.main()
