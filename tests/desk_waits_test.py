#!/usr/bin/env python3
"""wait-for-a-desk-job and wait-for-the-setup: the coding agent's two waits on
the systems desk, which replace its loops of sleeps.

  python3 tests/desk_waits_test.py

Runs each command with a stand-in clock: `sleep` moves the clock forward,
prints a `@clock N` marker, and carries out the events the test planned for
that time, such as a job writing its exit file. The markers show when each
progress line was printed.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
FILES = T/'roles/systems_desk/files'
CLOCK_START = 1_794_909_600  # 2026-11-17T10:00:00Z

FAKE_DATE = '''#!/usr/bin/env python3
import sys
assert sys.argv[1:] == ['+%s'], sys.argv
print(open(sys.argv[0] + '.clock').read().strip())
'''
FAKE_SLEEP = '''#!/usr/bin/env python3
import json, os, sys
here = os.path.dirname(sys.argv[0])
clock_file = os.path.join(here, 'date.clock')
now = int(open(clock_file).read()) + int(sys.argv[1])
open(clock_file, 'w').write(str(now))
print('@clock %d' % now, flush=True)
events = json.load(open(os.path.join(here, 'events.json')))
for event in events:
    if not event.get('done') and now >= event['at']:
        mode = 'a' if event['how'] == 'append' else 'w'
        open(event['path'], mode).write(event['text'])
        event['done'] = True
json.dump(events, open(os.path.join(here, 'events.json'), 'w'))
'''


class StandInClock:
    def __init__(self, test, command_path, replacements):
        temporary = tempfile.TemporaryDirectory()
        test.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.binary = self.root/'bin'
        self.binary.mkdir()
        (self.binary/'date').write_text(FAKE_DATE)
        (self.binary/'date.clock').write_text(str(CLOCK_START))
        (self.binary/'sleep').write_text(FAKE_SLEEP)
        for name in ('date', 'sleep'):
            (self.binary/name).chmod(0o755)
        self.events = []
        text = command_path.read_text()
        for old, new in [('export PATH=/usr/local/bin:/usr/bin:/bin', f'export PATH="{self.binary}:{os.environ["PATH"]}"'),
                         *replacements(self.root)]:
            test.assertIn(old, text)
            text = text.replace(old, new)
        self.command = self.root/command_path.name
        self.command.write_text(text)

    def at(self, seconds, how, path, text):
        self.events.append({'at': CLOCK_START + seconds, 'how': how, 'path': str(path), 'text': text})

    def run(self, *arguments):
        (self.binary/'events.json').write_text(json.dumps(self.events))
        (self.binary/'date.clock').write_text(str(CLOCK_START))
        return subprocess.run(['bash', str(self.command), *arguments], text=True, capture_output=True, timeout=120)


def seconds_between_lines(output):
    """The stand-in seconds between the lines the command printed, from the
    start to its end."""
    clock, last_line_at, gaps = CLOCK_START, CLOCK_START, []
    for line in output.splitlines():
        marker = re.fullmatch(r'@clock (\d+)', line)
        if marker:
            clock = int(marker.group(1))
        else:
            gaps.append(clock - last_line_at)
            last_line_at = clock
    gaps.append(clock - last_line_at)
    return gaps


def printed_lines(output):
    return [line for line in output.splitlines() if not line.startswith('@clock ')]


class WaitForADeskJob(unittest.TestCase):
    def setUp(self):
        self.clock = StandInClock(self, FILES/'wait-for-a-desk-job',
                                  lambda root: [('runs=/home/coding-agent/runs', f'runs={root}/runs')])
        self.runs = self.clock.root/'runs'
        self.runs.mkdir()

    def test_names_that_start_a_desk_job_refuses_are_refused(self):
        for arguments in (['../job'], ['a/b'], ['-job'], ['Job'], ['job.service'], ['..'], [''], ['x' * 65],
                          [], ['job', 'extra'], ['job', '--at-most-minutes'], ['job', '--at-most-minutes', '0'],
                          ['job', '--at-most-minutes', '1.5'], ['job', '--at-most', '5']):
            with self.subTest(arguments=arguments):
                result = self.clock.run(*arguments)
                self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
                self.assertIn('Nothing was waited for.', result.stderr)

    def test_a_finished_job_returns_its_exit_code_at_once_with_a_plain_last_line(self):
        for code in ('0', '3', '130'):
            with self.subTest(code=code):
                (self.runs/f'job-{code}.log').write_text('line one\nline two\n')
                (self.runs/f'job-{code}.exit').write_text(code + '\n')
                result = self.clock.run(f'job-{code}')
                self.assertEqual(result.returncode, int(code))
                lines = printed_lines(result.stdout)
                self.assertIn('line two', lines)
                self.assertIn(f'The systems desk job job-{code} ended with exit code {code}.', lines[-1])
                self.assertNotIn('@clock', result.stdout)

    def test_a_job_that_ended_without_an_exit_code_returns_its_own_code_and_shows_why(self):
        (self.runs/'long.log').write_text('working\n')
        (self.runs/'long.exit').write_text('stopped: the systems desk ended the job (timeout, killed TERM). A job runs 10 hours at most.\n')
        result = self.clock.run('long')
        self.assertEqual(result.returncode, 125)
        last = printed_lines(result.stdout)[-1]
        self.assertIn('The systems desk job long ended without an exit code', last)
        self.assertIn('stopped: the systems desk ended the job', last)

    def test_the_wait_ends_with_the_job_and_prints_at_least_once_a_minute(self):
        log = self.runs/'every-server-1.log'
        log.write_text('starting\n')
        for second in range(10, 400, 10):
            self.clock.at(second, 'append', log, f'task at {second}\n')
        self.clock.at(400, 'write', self.runs/'every-server-1.exit', '1\n')
        result = self.clock.run('every-server-1')
        self.assertEqual(result.returncode, 1)
        gaps = seconds_between_lines(result.stdout)
        self.assertLessEqual(max(gaps), 60, gaps)
        self.assertIn('ended with exit code 1', printed_lines(result.stdout)[-1])

    def test_log_lines_come_at_most_every_30_seconds_and_a_quiet_log_still_gets_a_line(self):
        log = self.runs/'busy.log'
        log.write_text('starting\n')
        for second in range(5, 300, 5):
            self.clock.at(second, 'append', log, f'task at {second}\n')
        self.clock.at(300, 'write', self.runs/'busy.exit', '0\n')
        result = self.clock.run('busy')
        progress = [gap for gap, line in zip(seconds_between_lines(result.stdout), printed_lines(result.stdout))
                    if line.startswith('--- busy runs')]
        self.assertTrue(progress)
        self.assertGreaterEqual(min(progress), 30, progress)

        quiet = self.runs/'quiet.log'
        quiet.write_text('starting\n')
        self.clock.events = []
        self.clock.at(200, 'write', self.runs/'quiet.exit', '0\n')
        result = self.clock.run('quiet')
        self.assertEqual(result.returncode, 0)
        self.assertIn('its log has not changed', result.stdout)
        self.assertLessEqual(max(seconds_between_lines(result.stdout)), 60)

    def test_at_the_bound_it_says_the_job_still_runs_and_how_to_wait_again(self):
        (self.runs/'slow.log').write_text('starting\n')
        result = self.clock.run('slow', '--at-most-minutes', '3')
        self.assertEqual(result.returncode, 124)
        last = printed_lines(result.stdout)[-1]
        self.assertIn('still runs after 3 minutes', last)
        self.assertIn('wait-for-a-desk-job slow', last)
        self.assertLessEqual(max(seconds_between_lines(result.stdout)), 60)
        self.assertFalse((self.runs/'slow.exit').exists())

    def test_the_default_bound_ends_before_a_ten_minute_command_limit(self):
        (self.runs/'slow.log').write_text('starting\n')
        result = self.clock.run('slow')
        self.assertEqual(result.returncode, 124)
        ended_at = max(int(n) for n in re.findall(r'@clock (\d+)', result.stdout))
        self.assertLess(ended_at - CLOCK_START, 10 * 60)

    def test_a_job_that_never_started_is_named(self):
        result = self.clock.run('never-started')
        self.assertEqual(result.returncode, 66)
        self.assertIn('No systems desk job named never-started', result.stdout)

    def test_a_job_whose_log_appears_late_is_waited_for(self):
        self.clock.at(10, 'write', self.runs/'new.log', 'starting\n')
        self.clock.at(120, 'write', self.runs/'new.exit', '0\n')
        self.assertEqual(self.clock.run('new').returncode, 0)


def results(steps, finished=False, stopped_with=None, updated_at='2026-11-17T09:00:00Z'):
    content = {'command': 'set-up-outside-services go-live', 'version': '0.1.0', 'updated_at': updated_at,
               'steps': [{'name': name, 'state': state} for name, state in steps],
               'finished': finished, 'for_the_coding_agent': {'cloudflare_account_id': 'abc'}}
    if stopped_with:
        content['stopped_with'] = stopped_with
    return json.dumps(content, indent=2)


class WaitForTheSetup(unittest.TestCase):
    def setUp(self):
        self.clock = StandInClock(self, FILES/'wait-for-the-setup', lambda root: [
            ('results_file=/var/lib/monkeymaxxing-stack/setup_results.json', f'results_file={root}/setup_results.json')])
        self.file = self.clock.root/'setup_results.json'

    def test_wrong_arguments_are_refused(self):
        for arguments in (['now'], ['--at-most-minutes'], ['--at-most-minutes', '0'], ['--at-most-minutes', 'x'],
                          ['--at-most-minutes', '5', 'more']):
            with self.subTest(arguments=arguments):
                result = self.clock.run(*arguments)
                self.assertEqual(result.returncode, 64)
                self.assertIn('Nothing was waited for.', result.stderr)

    def test_a_finished_setup_ends_the_wait_at_once_with_the_summary(self):
        self.file.write_text(results([('cloudflare', 'done'), ('registrar', 'not_needed')], finished=True))
        result = self.clock.run()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('@clock', result.stdout)
        self.assertIn('"cloudflare=done"', result.stdout)
        self.assertIn('cloudflare_account_id', result.stdout)
        self.assertEqual(printed_lines(result.stdout)[-1], 'go-live finished.')

    def test_an_earlier_runs_stop_does_not_end_the_wait_but_the_new_runs_stop_does(self):
        self.file.write_text(results([('cloudflare', 'in_progress')], stopped_with='Cloudflare refused the token'))
        self.clock.at(100, 'write', self.file, results([('cloudflare', 'in_progress')], updated_at='2026-11-17T10:01:40Z'))
        self.clock.at(250, 'write', self.file, results([('cloudflare', 'done'), ('registrar', 'in_progress')],
                                                       stopped_with='the registrar still lists the old nameservers',
                                                       updated_at='2026-11-17T10:04:10Z'))
        result = self.clock.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('the registrar still lists the old nameservers', result.stdout)
        self.assertNotIn('Cloudflare refused the token', result.stdout)
        self.assertTrue(printed_lines(result.stdout)[-1].startswith('go-live stopped.'))
        ended_at = max(int(n) for n in re.findall(r'@clock (\d+)', result.stdout))
        self.assertLess(ended_at - CLOCK_START, 300)

    def test_progress_comes_at_least_once_a_minute_and_names_the_steps(self):
        self.clock.at(130, 'write', self.file, results([('cloudflare', 'in_progress')], updated_at='2026-11-17T10:02:10Z'))
        self.clock.at(400, 'write', self.file, results([('cloudflare', 'done')], finished=True,
                                                       updated_at='2026-11-17T10:06:40Z'))
        result = self.clock.run()
        self.assertEqual(result.returncode, 0)
        self.assertLessEqual(max(seconds_between_lines(result.stdout)), 60)
        self.assertIn('the person has not started it yet', result.stdout)
        self.assertIn('cloudflare in_progress', result.stdout)

    def test_at_the_bound_it_says_the_setup_still_runs_and_how_to_wait_again(self):
        self.file.write_text(results([('cloudflare', 'in_progress')], updated_at='2026-11-17T10:00:00Z'))
        result = self.clock.run('--at-most-minutes', '2')
        self.assertEqual(result.returncode, 124)
        self.assertIn('Wait again with: wait-for-the-setup', printed_lines(result.stdout)[-1])
        self.assertLessEqual(max(seconds_between_lines(result.stdout)), 60)


class TheDeskInstallsTheWaits(unittest.TestCase):
    def test_the_desk_role_installs_both_waits_for_the_coding_agent(self):
        role = (T/'roles/systems_desk/main.yml').read_text()
        for name in ('wait-for-a-desk-job', 'wait-for-the-setup'):
            self.assertIn(f'file: {{path: /usr/local/bin/{name}, source: files/{name}, owner: root, group: root, '
                          'permissions_mode: "0755"}', role)


if __name__ == '__main__':
    unittest.main()
