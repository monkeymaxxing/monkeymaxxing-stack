#!/usr/bin/env python3
"""The rule that adds and removes app servers with the load, and its checks.

  MMX_BINARY=/path/to/mmx python3 tests/app_pool_with_the_load_test.py

roles/util_server/files/check-whether-the-load-changes-the-app-pool decides,
from the fleet hub's CPU readings of the app servers, whether the load calls
for one more or one fewer app server now. The test runs it with a stand-in
for `mmwatchdog fleet readings` and checks: an add when the pool's CPU
stayed above its headroom limit for the window, none when a reading dipped
below it, the largest number as a bound; a removal of the newest server when
the smaller pool would carry the week's peak with a server to spare, none
at the smallest number, none when the peak is too high, a mixed pool as a
bound; and the pause: no change while the readings of the present pool size
do not cover the window (a new server before its security updates
were installed, the load of installing it, a limit that
changed within the window, a hub that still lists a removed server).

It also renders mmwatchdog_checks/util_server.yml with MMX for the three
answers: util01's two checks exist only with routine_fixes_and_server_work,
and pass the program the settings and every app server with its type.
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
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
PROGRAM = T/'roles/util_server/files/check-whether-the-load-changes-the-app-pool'
NOW = datetime.datetime(2026, 11, 12, 14, 0, tzinfo=datetime.timezone.utc)


def stamp(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%S.123456789Z')


def series(span, value, limit, every=datetime.timedelta(minutes=5), start_offset=datetime.timedelta(minutes=1)):
    """Readings every 5 minutes over the span before NOW: value is a number or a function of the reading's time."""
    readings, at = [], NOW - span + start_offset
    while at <= NOW:
        readings.append({'at': stamp(at), 'value': value(at) if callable(value) else value, 'unit': 'percent',
                         'fail_when_measurement_above': limit, 'limit_status': 'within the limits'})
        at += every
    return readings


def answer(span, nodes):
    return {'since': stamp(NOW - span), 'until': stamp(NOW), 'check_group': 'app_server_capacity',
            'check': 'cpu_is_below_the_app_pool_headroom_limit', 'node_group': 'app_servers',
            'nodes': [{'node': name, 'readings_are_healthy': True,
                       'measurements': [{'check_group': 'app_server_capacity', 'check': 'cpu_is_below_the_app_pool_headroom_limit',
                                         'measurement': 'cpu_used_percent', 'readings': readings}]}
                      for name, readings in nodes.items()]}


FIFTEEN_MINUTES = datetime.timedelta(minutes=15)
SEVEN_DAYS = datetime.timedelta(days=7)


class TheRule(unittest.TestCase):
    def decide(self, direction, hub_answer, servers, smallest=1, largest=4, hub_exit=0, security_updates_installed_at=None):
        """security_updates_installed_at: server name -> when its waiting security updates were installed; a server left out has no file yet.
        By default every server finished its first run long ago."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ended_directory = root/'security_updates_installed'
            ended_directory.mkdir()
            for name in servers:
                moment = (security_updates_installed_at if security_updates_installed_at is not None else {name: NOW - datetime.timedelta(days=30)}).get(name)
                if moment is not None:
                    (ended_directory/name).write_text(moment.strftime('%Y-%m-%dT%H:%M:%SZ') + '\n')
            (root/'answer.json').write_text(json.dumps(hub_answer))
            fake = root/'mmwatchdog'
            fake.write_text(f'#!/bin/bash\nprintf "%s\\n" "$*" > {root}/arguments\ncat {root}/answer.json\nexit {hub_exit}\n')
            fake.chmod(0o755)
            program = root/'program'
            program.write_text(PROGRAM.read_text().replace('/usr/local/bin/mmwatchdog', str(fake))
                               .replace('/var/lib/app_pool_for_the_load/security_updates_installed', str(ended_directory)))
            arguments = [sys.executable, str(program), f'--{direction}', '--json',
                         '--smallest-number-of-servers', str(smallest), '--largest-number-of-servers', str(largest),
                         '--minutes-of-high-load', '15', '--days-of-low-load', '7',
                         '--cpu-percent-below-which-the-app-pool-can-spare-a-server', '50']
            for name, server_type in servers.items():
                arguments += ['--app-server', f'{name}:{server_type}']
            result = subprocess.run(arguments, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=30)
            asked = (root/'arguments').read_text().split() if (root/'arguments').exists() else []
        decision = json.loads(result.stdout) if result.stdout.strip() else None
        return result.returncode, decision, asked, result.stderr

    # Adding.
    def test_two_servers_above_35_percent_for_15_minutes_add_a_third(self):
        code, decision, asked, _ = self.decide('add', answer(FIFTEEN_MINUTES, {
            'app001': series(FIFTEEN_MINUTES, 41, 35), 'app002': series(FIFTEEN_MINUTES, 39, 35)}), {'app001': 'cx33', 'app002': 'cx33'})
        self.assertEqual((code, decision['decision']), (0, 'add'), decision)
        self.assertIn('above its limit of 35%', decision['why'])
        self.assertEqual(asked, ['fleet', 'readings', '--node-group', 'app_servers', 'app_server_capacity',
                                 'cpu_is_below_the_app_pool_headroom_limit', '--last', '15m', '--json'])

    def test_one_reading_below_the_limit_adds_nothing(self):
        dip = lambda at: 20 if at > NOW - datetime.timedelta(minutes=6) else 60
        code, decision, _, _ = self.decide('add', answer(FIFTEEN_MINUTES, {
            'app001': series(FIFTEEN_MINUTES, dip, 35), 'app002': series(FIFTEEN_MINUTES, dip, 35)}), {'app001': 'cx33', 'app002': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)

    def test_the_one_server_adds_a_second_above_70_percent(self):
        code, decision, _, _ = self.decide('add', answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 75, 70)}), {'app001': 'cx33'})
        self.assertEqual((code, decision['decision']), (0, 'add'), decision)
        code, decision, _, _ = self.decide('add', answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 69, 70)}), {'app001': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)

    def test_the_largest_number_stops_an_add(self):
        code, decision, _, _ = self.decide('add', answer(FIFTEEN_MINUTES, {
            'app001': series(FIFTEEN_MINUTES, 50, 35), 'app002': series(FIFTEEN_MINUTES, 50, 35)}),
            {'app001': 'cx33', 'app002': 'cx33'}, largest=2)
        self.assertEqual((code, decision['decision']), (2, 'stopped_by_a_bound'), decision)
        self.assertIn('holds its largest number of servers, 2', decision['why'])

    # Removing.
    def week(self, peaks, limit):
        return answer(SEVEN_DAYS, {name: series(SEVEN_DAYS, lambda at, peak=peak: peak if at.hour == 13 else 5, limit)
                                   for name, peak in peaks.items()})

    def test_a_quiet_pool_of_three_gives_up_its_newest_server(self):
        # Peaks 15 + 15 + 15 = 45, over one server (three fewer two): 45%, below 50%.
        code, decision, asked, _ = self.decide('remove', self.week({'app001': 15, 'app002': 15, 'app004': 15}, 47),
                                               {'app001': 'cx33', 'app002': 'cx33', 'app004': 'cx33'})
        self.assertEqual((code, decision['decision'], decision['server_to_remove']), (0, 'remove', 'app004'), decision)
        self.assertEqual(asked[asked.index('--last') + 1], '7d')

    def test_a_week_with_a_busy_peak_keeps_the_server(self):
        code, decision, _, _ = self.decide('remove', self.week({'app001': 20, 'app002': 20, 'app003': 20}, 47),
                                           {'app001': 'cx33', 'app002': 'cx33', 'app003': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn('not below 50%', decision['why'])

    def test_two_servers_go_down_to_one_only_when_both_peaks_fit_one_server_under_50_percent(self):
        servers = {'app001': 'cx33', 'app002': 'cx33'}
        code, decision, _, _ = self.decide('remove', self.week({'app001': 24, 'app002': 24}, 35), servers)
        self.assertEqual((code, decision['server_to_remove']), (0, 'app002'), decision)
        code, decision, _, _ = self.decide('remove', self.week({'app001': 26, 'app002': 26}, 35), servers)
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)

    def test_the_smallest_number_is_never_passed(self):
        code, decision, _, _ = self.decide('remove', self.week({'app001': 1, 'app002': 1}, 35),
                                           {'app001': 'cx33', 'app002': 'cx33'}, smallest=2)
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        code, decision, _, _ = self.decide('remove', self.week({'app001': 1}, 70), {'app001': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn('its smallest number', decision['why'])

    def test_a_pool_of_mixed_types_waits_for_a_person(self):
        code, decision, _, _ = self.decide('remove', self.week({'app001': 5, 'app002': 5, 'app003': 5}, 47),
                                           {'app001': 'cx43', 'app002': 'cx33', 'app003': 'cx33'})
        self.assertEqual((code, decision['decision']), (2, 'stopped_by_a_bound'), decision)
        self.assertIn('mixes server types', decision['why'])

    # The pause: only the readings of the present pool size count.
    def test_a_new_server_without_readings_stops_both_directions(self):
        hub = answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 60, 35), 'app002': []})
        code, decision, _, _ = self.decide('add', hub, {'app001': 'cx33', 'app002': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn('app002 has no CPU readings', decision['why'])

    def test_a_new_server_whose_readings_do_not_cover_the_window_adds_nothing(self):
        late = series(datetime.timedelta(minutes=5), 60, 47)
        hub = answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 60, 47), 'app002': series(FIFTEEN_MINUTES, 60, 47),
                                       'app003': late})
        code, decision, _, _ = self.decide('add', hub, {'app001': 'cx33', 'app002': 'cx33', 'app003': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn("app003's CPU readings cover only", decision['why'])

    def test_a_limit_that_changed_within_the_window_waits_a_whole_window(self):
        # Three days ago the pool shrank from four servers (limit 53) to three (47).
        changed = NOW - datetime.timedelta(days=3)
        readings = lambda: [dict(r, fail_when_measurement_above=53 if r['at'] < stamp(changed) else 47)
                            for r in series(SEVEN_DAYS, 5, 0)]
        hub = answer(SEVEN_DAYS, {'app001': readings(), 'app002': readings(), 'app003': readings()})
        code, decision, _, _ = self.decide('remove', hub, {'app001': 'cx33', 'app002': 'cx33', 'app003': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn('the app pool changed size at about', decision['why'])
        self.assertIn('2026-11-16', decision['why'])

    def test_a_hub_that_still_lists_a_removed_server_changes_nothing(self):
        hub = self.week({'app001': 5, 'app002': 5, 'app003': 5}, 47)
        code, decision, _, _ = self.decide('remove', hub, {'app001': 'cx33', 'app002': 'cx33'})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn('every_server has not run since the pool last changed', decision['why'])

    def test_a_server_that_has_not_installed_its_waiting_security_updates_is_not_asked_about_and_raises_nothing(self):
        """On a real server, the hub could not read a new server with no readings (exit 4), and the check warned."""
        hub = answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 60, 35), 'app002': []})
        for direction in ('add', 'remove'):
            with self.subTest(direction=direction):
                code, decision, asked, _ = self.decide(direction, hub, {'app001': 'cx33', 'app002': 'cx33'}, hub_exit=4,
                                                       security_updates_installed_at={'app001': NOW - SEVEN_DAYS})
                self.assertEqual((code, decision['decision']), (1, 'none'), decision)
                self.assertIn('app002 has not finished installing its waiting security updates', decision['why'])
                self.assertEqual(asked, [])

    def test_the_load_of_installing_a_new_server_does_not_count(self):
        """Measured: the new server's first reading was 86% CPU, ten minutes after the replacement, and the add check warned."""
        install = lambda at: 86 if at < NOW - datetime.timedelta(minutes=6) else 10
        hub = answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 60, 35), 'app002': series(FIFTEEN_MINUTES, install, 35)})
        code, decision, _, _ = self.decide('add', hub, {'app001': 'cx33', 'app002': 'cx33'},
                                           security_updates_installed_at={'app001': NOW - SEVEN_DAYS, 'app002': NOW - datetime.timedelta(minutes=7)})
        self.assertEqual((code, decision['decision']), (1, 'none'), decision)
        self.assertIn("app002's CPU readings cover only", decision['why'])

    def test_readings_after_the_security_updates_installed_at_count_over_the_whole_window(self):
        hub = answer(FIFTEEN_MINUTES, {'app001': series(FIFTEEN_MINUTES, 60, 35), 'app002': series(FIFTEEN_MINUTES, 60, 35)})
        code, decision, _, _ = self.decide('add', hub, {'app001': 'cx33', 'app002': 'cx33'},
                                           security_updates_installed_at={'app001': NOW - SEVEN_DAYS, 'app002': NOW - FIFTEEN_MINUTES})
        self.assertEqual((code, decision['decision']), (0, 'add'), decision)

    def test_a_hub_that_does_not_answer_is_an_error(self):
        code, decision, _, stderr = self.decide('add', {}, {'app001': 'cx33'}, hub_exit=4)
        self.assertEqual(code, 4)
        self.assertIn("the fleet hub's readings of the app servers could not be read", stderr)


class TheChecksOnUtil01(unittest.TestCase):
    """util01's two checks exist only with the third answer, with the program's arguments from the settings."""

    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to render the actual MMX template.')

    def rendered_checks(self, answer):
        """The part of mmwatchdog_checks/util_server.yml that holds the two checks, rendered with MMX from the template's settings."""
        source = (T/'mmwatchdog_checks/util_server.yml').read_text()
        part = source[source.index('{{- $load := .inputs.app_pool_load_settings }}'):].replace('.inputs.', '.vars.')
        settings = (T/'mmx_project_settings.yml').read_text()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            values = dict(app_pool_load_settings=dict(
                what_the_triage_agent_may_do_without_a_person=answer, app_servers=['app001'],
                growth_limits=dict(smallest_number_of_servers=1, largest_number_of_servers=4, server_types=['cx33', 'cx43']),
                triage_agent_server_work={key: int(value) for key, value in re.findall(
                    r'(?m)^    (minutes_of_high_load_before_an_app_server_is_added|days_of_low_load_before_an_app_server_is_removed|'
                    r'cpu_percent_below_which_the_app_pool_can_spare_a_server): (\d+)$', settings)}),
                inventory_nodes={'app001': {'vars': {'server_type': 'cx33'}}})
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'util01': {'address': '127.0.0.1'}})))
            (root/'source.template').write_text('check_groups:\n' + part)
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True,
                                    stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    def test_every_server_passes_the_settings_to_util01(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        self.assertIn('''          app_pool_load_settings:
            what_the_triage_agent_may_do_without_a_person: "{{ .vars.what_the_triage_agent_may_do_without_a_person }}"
            app_servers: "{{ .inventory.groups.app_servers }}"
            growth_limits: "{{ .vars.growth_limits.app_servers }}"
            triage_agent_server_work: "{{ .vars.triage_agent_server_work }}"
''', playbook)

    def test_every_server_records_when_each_app_server_installed_its_security_updates_after_the_stages_that_install_them(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        stages = re.findall(r'(?m)^  - id: (\S+)', playbook)
        stage = 'record_when_each_app_server_installed_its_waiting_security_updates'
        self.assertGreater(stages.index(stage), stages.index('tunnel_connector_and_caddy'))
        self.assertGreater(stages.index(stage), stages.index('mmwatchdog_joins_the_fleet_hub_after_the_roles_on_the_load_balancer_servers'))
        self.assertGreater(stages.index(stage), stages.index('install_the_waiting_security_updates_on_new_servers'))
        self.assertIn('for_each_node: app_servers', playbook[playbook.index(f'  - id: {stage}'):])
        self.assertIn('directory=/var/lib/app_pool_for_the_load/security_updates_installed', playbook)
        self.assertIn('marker=/var/lib/mmx/commands_run_once/security_updates_installed_on_a_new_server', playbook)
        roles = (T/'roles/every_server/main.yml').read_text()
        self.assertIn('run_only_once_marker_file: /var/lib/mmx/commands_run_once/security_updates_installed_on_a_new_server', roles)
        self.assertIn("SECURITY_UPDATES_INSTALLED_DIRECTORY = '/var/lib/app_pool_for_the_load/security_updates_installed'", PROGRAM.read_text())

    def test_app_jobs_and_load_balancer_servers_serve_first_and_install_their_updates_in_the_last_stage(self):
        """Serve first: the role's task skips the pools whose new server carries requests; the last fleet stage installs for them."""
        roles = (T/'roles/every_server/main.yml').read_text()
        task = roles[roles.index('  - id: install_the_waiting_security_updates_on_a_new_server'):]
        task = task[:task.index('\n  - id:', 10)]
        self.assertIn('    when:\n      not:\n        any:\n          - "{{ .inputs.is_app_server }}"\n          - "{{ .inputs.is_jobs_server }}"\n          - "{{ .inputs.is_load_balancer_server }}"', task)
        self.assertIn('unattended-upgrade --no-minimal-upgrade-steps', task)
        playbook = (T/'playbooks/every_server.yml').read_text()
        stages = re.findall(r'(?m)^  - id: (\S+)', playbook)
        new_stage = 'install_the_waiting_security_updates_on_new_servers'
        # Only the first restore drill's start comes after them.
        self.assertEqual(stages[-3:], [new_stage, 'record_when_each_app_server_installed_its_waiting_security_updates',
                                       'start_the_restore_drill_until_one_has_passed'])
        text = playbook[playbook.index(f'  - id: {new_stage}'):playbook.index("  # util01's rule for the load")]
        self.assertIn('nodes: [app_servers, jobs_servers, load_balancer_servers]', text)
        self.assertIn('unattended-upgrade --no-minimal-upgrade-steps', text)
        self.assertIn('run_only_once_marker_file: /var/lib/mmx/commands_run_once/security_updates_installed_on_a_new_server', text)

    def test_only_the_third_answer_renders_the_checks(self):
        for answer in ('every_fix_waits_for_a_person', 'routine_fixes'):
            with self.subTest(answer=answer):
                text = self.rendered_checks(answer)
                self.assertNotIn('app_servers_to_add_for_the_load', text)
                self.assertNotIn('app_servers_to_remove_for_the_load', text)
        text = self.rendered_checks('routine_fixes_and_server_work')
        arguments = ('--smallest-number-of-servers 1 --largest-number-of-servers 4 --minutes-of-high-load 15 '
                     '--days-of-low-load 7 --cpu-percent-below-which-the-app-pool-can-spare-a-server 50 --app-server app001:cx33')
        self.assertIn(f'/usr/local/bin/check-whether-the-load-changes-the-app-pool --add {arguments})', text)
        self.assertIn(f'/usr/local/bin/check-whether-the-load-changes-the-app-pool --remove {arguments})', text)
        for group, every in (('app_servers_to_add_for_the_load', '1m'), ('app_servers_to_remove_for_the_load', '1h')):
            block = text.split(f'  {group}:\n')[1]
            self.assertTrue(block.startswith(f'    check_every: {every}\n'), block[:80])
            self.assertIn('alert_after_failing_for: 0s', block[:200])
            self.assertIn('alert_severity: warn', block)


    def run_the_check(self, text, group, program_exit_code):
        """Runs the rendered check's script, with a stand-in for the rule that exits PROGRAM_EXIT_CODE."""
        block = text.split(f'  {group}:\n')[1]
        script = re.search(r'(?s)script: \|\n(.*?)\n        alert_severity', block)[1]
        with tempfile.TemporaryDirectory() as temporary:
            stand_in = Path(temporary)/'rule'
            stand_in.write_text(f'#!/bin/sh\necho "the rule\'s reason"\nexit {program_exit_code}\n')
            stand_in.chmod(0o755)
            script = script.replace('/usr/local/bin/check-whether-the-load-changes-the-app-pool', str(stand_in))
            return subprocess.run(['bash', '-c', script], text=True, capture_output=True, stdin=subprocess.DEVNULL).returncode

    def test_the_add_check_also_warns_when_the_largest_number_stops_an_add(self):
        """With the third answer the app servers' CPU warning is info, so util01's add check is the one alert, bound or not."""
        text = self.rendered_checks('routine_fixes_and_server_work')
        # The rule: 0 change now, 1 no change, 2 a change a bound stops, 4 the hub does not answer.
        for program_exit_code, add_fails, remove_fails in ((0, True, True), (1, False, False), (2, True, False), (4, True, True)):
            with self.subTest(program_exit_code=program_exit_code):
                self.assertEqual(self.run_the_check(text, 'app_servers_to_add_for_the_load', program_exit_code) != 0, add_fails)
                self.assertEqual(self.run_the_check(text, 'app_servers_to_remove_for_the_load', program_exit_code) != 0, remove_fails)


class TheAppServersCPUWarning(unittest.TestCase):
    """With the third answer the app servers' own CPU check is info: util01's check starts the triage agent, one sound."""

    def rendered_severity(self, answer):
        source = (T/'mmwatchdog_checks/app_servers.yml').read_text()
        block = source.split('      cpu_is_below_the_app_pool_headroom_limit:\n')[1]
        line = re.search(r'(?m)^        alert_severity: (.*)$', block)[1].replace('.inputs.', '.vars.')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=dict(
                reboot_check_settings=dict(what_the_triage_agent_may_do_without_a_person=answer)))))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'util01': {'address': '127.0.0.1'}})))
            (root/'source.template').write_text(line)
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
            result = subprocess.run([mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True,
                                    stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text'].strip()

    def test_info_only_with_the_third_answer(self):
        for answer, severity in (('every_fix_waits_for_a_person', 'warn'), ('routine_fixes', 'warn'),
                                 ('routine_fixes_and_server_work', 'info')):
            with self.subTest(answer=answer):
                self.assertEqual(self.rendered_severity(answer), severity)


if __name__ == '__main__':
    unittest.main()
