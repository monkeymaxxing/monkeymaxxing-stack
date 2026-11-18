#!/usr/bin/env python3
"""Reboots for installed updates: when one may run now, and who starts it.

  MMX_BINARY=/path/to/mmx python3 tests/reboots_that_may_run_now_test.py

check-whether-a-reboot-may-run-now (roles/every_server/files/) holds the one
rule, which both reboot_servers_after_updates and MMWatchdog's check
no_reboot_waits_that_may_run_now run. The test runs the program directly for
the weekly window's arithmetic in UTC: the window's first minute is inside
and its end is outside, a window across midnight and across the end of the
week (sunday into monday), and the next window's date. It runs the
playbook's own program, taken from `mmx explain`, with the real rule program
and a reboot marker in a temporary directory: one app server outside the
window is skipped with the line that says until when, inside the window or
before go-live or with a second app server it reboots, and the person's
override reboots it. It renders mmwatchdog_checks/every_server.yml: the
check exists only with routine_fixes_and_server_work, never on a database
server, util01 or a desk, and alerts at warn. It needs Python 3, bash and jq.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
RULE = T/'roles/every_server/files/check-whether-a-reboot-may-run-now'
WINDOW = ['--weekday', 'tuesday', '--starts-at', '21:00', '--length-minutes', '60']


def rule(*arguments, pool='app_servers', servers=1, live='true', window=WINDOW):
    result = subprocess.run([sys.executable, str(RULE), '--pool', pool, '--servers-in-the-pool', str(servers),
                             '--public-site-checks-run', live, *window, *arguments],
                            text=True, capture_output=True, stdin=subprocess.DEVNULL)
    return result.returncode, result.stdout.strip()


def argument(task, field):
    for item in task.get('arguments') or []:
        if item['field'] == field:
            return item['value']
    raise AssertionError(f'{task["path"]} has no argument {field}')


class TheWeeklyWindowInUTC(unittest.TestCase):
    def test_the_first_minute_is_inside_and_the_end_is_outside(self):
        # 2026-11-17 is a tuesday.
        self.assertEqual(rule('--at', '2026-11-17T21:00:00Z'),
                         (0, 'may reboot now: inside the maintenance window, which ends tuesday 2026-11-17 22:00 UTC'))
        self.assertEqual(rule('--at', '2026-11-17T21:59:59Z')[0], 0)
        self.assertEqual(rule('--at', '2026-11-17T22:00:00Z'),
                         (1, 'waits for the maintenance window: tuesday 2026-11-24 21:00 UTC, for 60 minutes; '
                             'the only server of app_servers serves the users'))
        self.assertEqual(rule('--at', '2026-11-17T20:59:00Z'),
                         (1, 'waits for the maintenance window: tuesday 2026-11-17 21:00 UTC, for 60 minutes; '
                             'the only server of app_servers serves the users'))

    def test_another_time_zone_in_the_time_given_counts_in_utc(self):
        # 22:30 in UTC+1 is 21:30 UTC, inside the window.
        self.assertEqual(rule('--at', '2026-11-17T22:30:00+01:00')[0], 0)

    def test_a_window_across_midnight(self):
        window = ['--weekday', 'tuesday', '--starts-at', '23:30', '--length-minutes', '90']
        self.assertEqual(rule('--at', '2026-11-17T23:30:00Z', window=window)[0], 0)
        self.assertEqual(rule('--at', '2026-11-18T00:59:00Z', window=window),
                         (0, 'may reboot now: inside the maintenance window, which ends wednesday 2026-11-18 01:00 UTC'))
        self.assertEqual(rule('--at', '2026-11-18T01:00:00Z', window=window)[0], 1)
        # The same hour a day earlier is outside: the window is weekly.
        self.assertEqual(rule('--at', '2026-11-17T00:30:00Z', window=window)[0], 1)

    def test_a_window_across_the_end_of_the_week(self):
        window = ['--weekday', 'sunday', '--starts-at', '23:30', '--length-minutes', '60']
        self.assertEqual(rule('--at', '2026-11-22T23:45:00Z', window=window)[0], 0)
        self.assertEqual(rule('--at', '2026-11-23T00:15:00Z', window=window),
                         (0, 'may reboot now: inside the maintenance window, which ends monday 2026-11-23 00:30 UTC'))
        self.assertEqual(rule('--at', '2026-11-23T00:30:00Z', window=window),
                         (1, 'waits for the maintenance window: sunday 2026-11-29 23:30 UTC, for 60 minutes; '
                             'the only server of app_servers serves the users'))

    def test_the_longest_window_of_one_day(self):
        window = ['--weekday', 'friday', '--starts-at', '00:00', '--length-minutes', '1440']
        self.assertEqual(rule('--at', '2026-11-20T23:59:00Z', window=window)[0], 0)
        self.assertEqual(rule('--at', '2026-11-21T00:00:00Z', window=window)[0], 1)

    def test_a_reboot_that_users_do_not_see_may_run_at_any_time(self):
        outside = ('--at', '2026-11-18T12:00:00Z')
        self.assertEqual(rule(*outside, servers=2), (0, 'may reboot now: another server of app_servers carries the work'))
        self.assertEqual(rule(*outside, pool='jobs_servers')[0], 0)
        self.assertEqual(rule(*outside, pool='staging_server')[0], 0)
        self.assertEqual(rule(*outside, live='false'),
                         (0, 'may reboot now: the site is not live yet (public_site_checks_run is false)'))
        self.assertEqual(rule(*outside, '--a-person-allows-it')[0], 0)
        self.assertEqual(rule(*outside, pool='load_balancer_servers')[0], 1)

    def test_a_wrong_time_is_refused(self):
        self.assertEqual(rule('--at', '2026-11-18T12:00:00Z', window=['--weekday', 'tuesday', '--starts-at', '9:00',
                                                                       '--length-minutes', '60'])[0], 2)


class ThePlaybookAndTheCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to explain the actual playbooks.')

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

    def decide(self, at, *extra, settings_changes=(), inventory_changes=()):
        """Runs the playbook's first program for app001, as at the time given, and returns its JSON."""
        with tempfile.TemporaryDirectory() as temporary:
            root = self.copy_of_the_template(temporary, settings_changes, inventory_changes)
            explained = subprocess.run([self.mmx, 'explain', 'reboot_servers_after_updates', '--json', *extra],
                                       cwd=root, text=True, capture_output=True)
            self.assertEqual(explained.returncode, 0, explained.stderr)
            task = next(task for stage in json.loads(explained.stdout)['fleet_stages'] for task in stage.get('node_tasks') or []
                        if task['path'].endswith('/whether_a_reboot_waits_and_may_run_now') and task['node'] == 'app001')
            env = dict(os.environ)
            for item in task['arguments']:
                if item['field'].startswith('shell.env.'):
                    value = item['value']
                    env[item['field'][len('shell.env.'):]] = value if isinstance(value, str) else json.dumps(value)
            marker = Path(temporary)/'reboot-required'
            marker.touch()
            stand_in = Path(temporary)/'rule'
            stand_in.write_text(f'#!/bin/sh\nexec {sys.executable} {RULE} "$@" --at {at}\n')
            stand_in.chmod(0o755)
            program = env['PROGRAM'].replace('/var/run/reboot-required', str(marker)).replace(
                '/usr/local/bin/check-whether-a-reboot-may-run-now', str(stand_in))
            self.assertNotEqual(program, env['PROGRAM'])
            result = subprocess.run(['bash', '-c', program], env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_only_app_server_outside_the_window_is_skipped_with_until_when(self):
        decision = self.decide('2026-11-18T12:00:00Z', settings_changes=[('public_site_checks_run: false', 'public_site_checks_run: true')])
        self.assertEqual(decision, {'a_reboot_waits': True, 'the_reboot_may_run_now': False, 'why':
                                    'waits for the maintenance window: tuesday 2026-11-24 21:00 UTC, for 60 minutes; '
                                    'the only server of app_servers serves the users'})
        playbook = (T/'playbooks/reboot_servers_after_updates.yml').read_text()
        self.assertIn('show: "{{ .node.name }} {{ .node_tasks.whether_a_reboot_waits_and_may_run_now.stdout_json.why }}"', playbook)
        self.assertIn('when: "{{ .outputs.find_the_servers_whose_updates_wait_for_a_reboot[.server].a_reboot_waits_and_may_run_now }}"', playbook)

    def test_inside_the_window_it_reboots(self):
        decision = self.decide('2026-11-24T21:10:00Z', settings_changes=[('public_site_checks_run: false', 'public_site_checks_run: true')])
        self.assertTrue(decision['the_reboot_may_run_now'], decision)

    def test_before_go_live_it_reboots(self):
        self.assertTrue(self.decide('2026-11-18T12:00:00Z')['the_reboot_may_run_now'])

    def test_a_second_app_server_carries_the_work(self):
        decision = self.decide('2026-11-18T12:00:00Z', settings_changes=[('public_site_checks_run: false', 'public_site_checks_run: true')],
                               inventory_changes=[('    nodes: [app001]\n', '    nodes: [app001, app002]\n'),
                                                  ('\n  db01:\n', '\n  app002:\n    address: 10.20.1.2\n    vars:\n      private_ip: 10.20.1.2\n'
                                                   '      public_ipv4_address: 203.0.113.12\n      server_type: cx33\n      location: fsn1\n'
                                                   '      wireguard_public_key: "xntON0r+ip4v53R2PDYOEKeq0RH91Y9x307uPnUQOTE="\n\n  db01:\n')])
        self.assertEqual(decision['why'], 'may reboot now: another server of app_servers carries the work')

    def test_the_persons_override_reboots_outside_the_window(self):
        decision = self.decide('2026-11-18T12:00:00Z', '--var', 'reboot_the_only_server_of_a_pool_outside_the_maintenance_window=true',
                               settings_changes=[('public_site_checks_run: false', 'public_site_checks_run: true')])
        self.assertEqual(decision['why'], 'may reboot now: a person allowed the reboot outside the maintenance window for this run')

    def rendered_check_groups(self, node, groups, answer):
        """mmwatchdog_checks/every_server.yml, rendered for one server through a role, as the real roles render it.

        answer None renders it as util01's role and the desk playbook do: they
        pass no reboot settings. The template reads role inputs, whose
        missing keys stop the rendering, so the inputs stay inputs.
        """
        inputs = dict(is_database_server=False, is_staging_server=False, inventory_groups=groups)
        if answer is not None:
            inputs['reboot_check_settings'] = {
                'what_the_triage_agent_may_do_without_a_person': answer, 'public_site_checks_run': True,
                'maintenance_window': {'weekday': 'tuesday', 'starts_at': '21:00', 'length_minutes': 60}}
        template = (T/'mmwatchdog_checks/every_server.yml').read_text()
        self.assertEqual(set(re.findall(r'\.inputs\.(\w+)', template)), set(inputs) | {'reboot_check_settings'})
        declared = {'is_database_server': {'type': 'boolean', 'required': True}, 'is_staging_server': {'type': 'boolean', 'required': True},
                    'inventory_groups': {'type': 'mapping', 'default': {}}, 'reboot_check_settings': {'type': 'mapping', 'default': {}},
                    'block_devices': {'type': 'list', 'default': []}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'roles/render').mkdir(parents=True)
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars={})))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={node: {'address': '127.0.0.1'}})))
            # explain cannot read a server's facts, so the disks become an empty list.
            (root/'roles/render/source.template').write_text(template.replace('.node.storage.block_devices', '.inputs.block_devices'))
            (root/'roles/render/main.yml').write_text(json.dumps(dict(inputs=declared, node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(role='render', inputs=inputs)])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True,
                                    stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = next(task for task in json.loads(result.stdout)['fleet_stages'][0]['node_tasks'] if task.get('rendered_templates'))
        rendered = task['rendered_templates'][0]
        self.assertIn('text', rendered, rendered.get('not_rendered_because'))
        return rendered['text']

    GROUPS = {'app_servers': ['app001'], 'database_servers': ['db01'], 'util_server': ['util01'], 'systems_desks': ['desk01'],
              'jobs_servers': [], 'load_balancer_servers': [], 'staging_server': [], 'database_restore_servers': []}

    def test_the_check_exists_only_with_server_work_and_only_where_the_playbook_reboots(self):
        text = self.rendered_check_groups('app001', self.GROUPS, 'routine_fixes_and_server_work')
        group = text.split('\n  reboots_that_may_run_now:\n')[1]
        self.assertIn('alert_after_failing_for: 10m', group)
        self.assertIn('check_every: 1m', group)
        self.assertRegex(group, r'(?m)^        alert_severity: warn$')
        self.assertIn('--pool app_servers --servers-in-the-pool 1', group)
        self.assertIn('--public-site-checks-run true --weekday tuesday', group)
        self.assertIn('--starts-at 21:00 --length-minutes 60', group)
        for answer in ('routine_fixes', 'every_fix_waits_for_a_person'):
            with self.subTest(answer=answer):
                self.assertNotIn('reboots_that_may_run_now', self.rendered_check_groups('app001', self.GROUPS, answer))
        for node in ('db01', 'util01', 'desk01'):
            with self.subTest(node=node):
                self.assertNotIn('reboots_that_may_run_now', self.rendered_check_groups(node, self.GROUPS, 'routine_fixes_and_server_work'))
        # As the callers render it: util01's own role passes no groups and no
        # reboot settings, and the desk playbook passes {}. On 2026-11-12 the
        # template read the empty settings and failed on a real util01.
        self.assertNotIn('reboots_that_may_run_now', self.rendered_check_groups('util01', {}, None))
        self.assertNotIn('reboots_that_may_run_now', self.rendered_check_groups('desk01', self.GROUPS, None))

    def test_the_rendered_check_fails_only_when_a_reboot_waits_and_may_run_now(self):
        text = self.rendered_check_groups('app001', self.GROUPS, 'routine_fixes_and_server_work')
        script = re.search(r'(?ms)^          script: \|\n(.*?)^        alert_severity', text).group(1)
        script = '\n'.join(line[12:] for line in script.splitlines())
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary)/'reboot-required'

            def run(at):
                stand_in = Path(temporary)/'rule'
                stand_in.write_text(f'#!/bin/sh\nexec {sys.executable} {RULE} "$@" --at {at}\n')
                stand_in.chmod(0o755)
                program = script.replace('/var/run/reboot-required', str(marker)).replace(
                    '/usr/local/bin/check-whether-a-reboot-may-run-now', str(stand_in))
                return subprocess.run(['bash', '-c', program], text=True, capture_output=True, stdin=subprocess.DEVNULL)
            self.assertEqual(run('2026-11-24T21:10:00Z').returncode, 0, 'no reboot waits: healthy')
            marker.touch()
            outside = run('2026-11-18T12:00:00Z')
            self.assertEqual(outside.returncode, 0, outside.stdout)
            inside = run('2026-11-24T21:10:00Z')
            self.assertEqual(inside.returncode, 1)
            self.assertIn('a reboot for installed updates waits: may reboot now: inside the maintenance window', inside.stdout)

    def test_the_triage_user_may_confirm_the_new_check_group(self):
        self.assertIn('/usr/local/bin/mmwatchdog check-now reboots_that_may_run_now --count-as-scheduled-run',
                      (T/'roles/every_server/files/sudoers_triage').read_text())

    def test_every_server_accepts_windows_from_30_to_1440_minutes(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        self.assertIn('number_at_least: ["{{ .vars.maintenance_window.length_minutes }}", 30]', playbook)
        self.assertIn('number_at_most: ["{{ .vars.maintenance_window.length_minutes }}", 1440]', playbook)
        self.assertRegex((T/'mmx_project_settings.yml').read_text(), r'(?m)^    length_minutes: 60$')


if __name__ == '__main__':
    unittest.main()
