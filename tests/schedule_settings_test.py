#!/usr/bin/env python3
"""Check that the schedule settings of the systems repository template reach the jobs.

  MMX_BINARY=/path/to/mmx python3 tests/schedule_settings_test.py

It copies the template, changes nightly_work_starts_at, weekly_work_day, and
the job-container stop time, and reads what `mmx explain every_server` says
each job gets.
"""
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


class ScheduleSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def explain(self, **changes):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            settings = (root/'mmx_project_settings.yml').read_text()
            for old, new in changes.items():
                self.assertIn(old, settings, old)
                settings = settings.replace(old, new, 1)
            (root/'mmx_project_settings.yml').write_text(settings)
            result = subprocess.run([self.mmx, 'explain', 'every_server'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_the_template_keeps_todays_times(self):
        text = self.explain()
        self.assertIn('systemd_scheduled_job.systemd_calendar_schedule = "sunday *-*-* 01:00:00"', text)
        self.assertIn('OnCalendar=sunday 04:00:00 UTC', text)

    def test_the_settings_reach_the_full_backup_and_the_image_cleanup(self):
        text = self.explain(**{'\n  nightly_work_starts_at: "01:00"': '\n  nightly_work_starts_at: "19:30"',
                               '\n  weekly_work_day: sunday': '\n  weekly_work_day: wednesday'})
        self.assertIn('systemd_calendar_schedule = "wednesday *-*-* 19:30:00"', text)
        # The differential backups run on the other six days, at the same time.
        self.assertIn('systemd_calendar_schedule = "monday,tuesday,thursday,friday,saturday,sunday *-*-* 19:30:00"', text)
        self.assertNotIn('"sunday *-*-*', text)
        # Three hours after the nightly work starts: 22:30 UTC, computed by the image cleanup's timer template.
        self.assertIn('OnCalendar=wednesday 22:30:00 UTC', text)

    def test_the_other_jobs_wait_for_the_times_worked_out_on_the_server(self):
        text = self.explain()
        for task in ('work_out_the_time_of_the_uploads_copy', 'work_out_the_time_of_the_restore_drill',
                     'work_out_the_time_of_the_server_settings_comparison', 'work_out_the_time_of_the_leftover_restore01_check'):
            self.assertIn(task, text)

    def test_the_nightly_start_leaves_room_for_the_last_job_before_midnight(self):
        # The last nightly job, the leftover-restore01 check, starts 225 minutes
        # (3 hours 45 minutes) after nightly_work_starts_at, so 20:14 is the latest start.
        playbook = (T/'playbooks/every_server.yml').read_text()
        pattern = re.search(r'matches: \["\{\{ \.vars\.nightly_work_starts_at \}\}", \'(.*?)\'\]', playbook)[1]
        self.assertIn('225 minutes', (T/'roles/util_server/main.yml').read_text())
        for value, accepted in (('00:00', True), ('01:00', True), ('19:59', True), ('20:00', True), ('20:14', True),
                                ('20:15', False), ('20:59', False), ('21:00', False), ('1:00', False), ('24:00', False)):
            with self.subTest(value=value):
                self.assertEqual(bool(re.search(pattern, value)), accepted)
        self.assertIn('from 00:00 to 20:14', playbook)
        self.assertIn('20:14', (T/'mmx_project_settings.yml').read_text())

    def test_the_interval_of_the_check_of_new_commits_is_a_setting(self):
        self.assertIn('systemd_calendar_schedule = "*-*-* *:00/5:00 UTC"', self.explain())
        self.assertIn('systemd_calendar_schedule = "*-*-* *:00/15:00 UTC"', self.explain(**{
            '\n  check_new_commits_on_main_every_minutes: 5': '\n  check_new_commits_on_main_every_minutes: 15'}))

    def uploads_copy_schedule(self, nightly_work_starts_at, every_hours):
        """Runs the role's schedule script with a stand-in for GNU date's arithmetic."""
        role = (T/'roles/uploads_backup/main.yml').read_text()
        task = role.split('  - id: work_out_the_time_of_the_uploads_copy\n', 1)[1]
        script = re.search(r'      script: (.*)\n      dryrun: (.*)\n      env:\n        PROGRAM: \|\n(.*?)\n        [A-Z_]+:', task, re.S)
        self.assertEqual(script[1], script[2], 'the dryrun must work out the same time')
        program = '\n'.join(line[10:] for line in script[3].splitlines())
        with tempfile.TemporaryDirectory() as temporary:
            date = Path(temporary)/'date'
            # Only the call the script makes: date -u -d "2000-01-01 HH:MM UTC + 60 minutes" +%H:%M
            date.write_text('#!/usr/bin/env python3\nimport re, sys\n'
                            'h, m = map(int, re.search(r"(\\d\\d):(\\d\\d) UTC \\+ 60 minutes", sys.argv[3]).groups())\n'
                            'assert sys.argv[1:3] == ["-u", "-d"] and sys.argv[4] == "+%H:%M", sys.argv\n'
                            'print("%02d:%02d" % ((h + 1) % 24, m))\n')
            date.chmod(0o755)
            result = subprocess.run(['bash', '-c', script[1]], text=True, capture_output=True, env={
                **os.environ, 'PATH': f"{temporary}:{os.environ['PATH']}", 'PROGRAM': program,
                'NIGHTLY_WORK_STARTS_AT': nightly_work_starts_at, 'EVERY_HOURS': str(every_hours)})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_the_uploads_copy_runs_at_the_hours_its_interval_gives(self):
        # Expected hours: the start (nightly_work_starts_at plus one hour), then every interval, all day.
        for start, every, expected in (('01:00', 24, '02:00:00'),   # the template: one copy at 02:00, as before
                                       ('19:30', 24, '20:30:00'),
                                       ('01:00', 6, '02/6:00:00'),  # 02:00, 08:00, 14:00, 20:00
                                       ('22:30', 6, '05/6:30:00'),  # 05:30, 11:30, 17:30, 23:30
                                       ('20:14', 1, '00/1:14:00'),  # every hour at 14 past
                                       ('03:00', 8, '04/8:00:00')):
            with self.subTest(start=start, every=every):
                self.assertEqual(self.uploads_copy_schedule(start, every), expected)
        self.assertIn('systemd_calendar_schedule: "*-*-* {{ .node_tasks.work_out_the_time_of_the_uploads_copy.stdout }} UTC"',
                      (T/'roles/uploads_backup/main.yml').read_text())

    def test_the_uploads_copy_interval_divides_a_day(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        stage = playbook.split('      - id: uploads_copy_every_hours_divides_a_day\n', 1)[1].split('      - id: ', 1)[0]
        accepted = [int(n) for n in re.findall(r'number_equals: \["\{\{ \.vars\.backups\.uploads_copy_every_hours \}\}", (\d+)\]', stage)]
        self.assertEqual(accepted, [n for n in range(1, 25) if 24 % n == 0])
        self.assertIn('Use one of 1, 2, 3, 4, 6, 8, 12 or 24', stage)
        self.assertIn('\n    uploads_copy_every_hours: 24\n', (T/'mmx_project_settings.yml').read_text())

    def test_the_copy_age_warning_follows_the_interval(self):
        self.assertIn('file_age_hours: 26', self.explain())
        text = self.explain(**{'\n    uploads_copy_every_hours: 24\n': '\n    uploads_copy_every_hours: 6\n'})
        self.assertIn('file_age_hours: 8', text)
        self.assertNotIn('file_age_hours: 26', text)

    def test_no_uploads_means_no_uploads_checks(self):
        text = self.explain(**{'\n    uploads_backup_runs_on: [util_server]\n': '\n    uploads_backup_runs_on: []\n'})
        self.assertNotIn('apps_whose_latest_copy_hid_an_unusual_share', text)
        self.assertNotIn('WARN_WHEN_ONE_COPY_HIDES_MORE_THAN_PERCENT', text)
        with_uploads = self.explain()
        self.assertIn('apps_whose_latest_copy_hid_an_unusual_share', with_uploads)
        self.assertIn('WARN_WHEN_ONE_COPY_HIDES_MORE_THAN_PERCENT = 10', with_uploads)

    def render_job_container(self, **app):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            apps = {'shop': dict(jobs_command='bin/jobs', jobs_connect_directly_to_postgres=False, **app)}
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=dict(apps=apps))))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001': {'address': '127.0.0.1'}})))
            (root/'source.template').write_text((T/'files_used_by_several_roles/jobs_container.container').read_text().replace('.inputs', '.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', loop={'shop': dict(image='registry/shop:1')}, **{'as': 'job_container'},
                     file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]

    def test_the_job_containers_stop_time_is_a_setting(self):
        self.assertIn('StopTimeout=30\n', self.render_job_container()['text'])
        self.assertIn('StopTimeout=300\n', self.render_job_container(seconds_a_job_gets_to_finish_when_stopped=300)['text'])
        for bad in (9, 3601, 'long'):
            with self.subTest(bad=bad):
                rendered = self.render_job_container(seconds_a_job_gets_to_finish_when_stopped=bad)
                self.assertNotIn('text', rendered)
                self.assertIn('seconds_a_job_gets_to_finish_when_stopped', rendered['not_rendered_because'])


if __name__ == '__main__':
    unittest.main()
