#!/usr/bin/env python3
"""Check MMWatchdog's pinned_program_releases checks on util01.

  MMX_BINARY=/path/to/mmx python3 tests/pinned_program_releases_test.py

The checks are written in mmwatchdog_checks/util_server.yml from
stack_software in mmx_project_settings.yml. This file proves:
  - the real every_server playbook passes the inputs, and util01 gets one
    check per downloaded program that the settings install: every
    downloaded_binary entry of software_outside_the_distribution.yml, codex
    only while a coding agent setting is codex, rclone only while the
    uploads' copy runs on util01; a pin that is not a GitHub release gets
    no check;
  - each generated script against a stand-in GitHub API: a newer release
    fails and names the program, both versions and the update procedure;
    the same, an older, or no stable release (GitHub's 404 when only
    pre-releases exist) passes; a source that does not answer, refuses
    with 403, or answers malformed JSON passes the program's check after
    3 tries and fails release_sources_answer, which names the program.
It needs Python 3, bash, curl, jq, and sort with -V, as on util01.
"""
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
CHECK_SUFFIX = '_pin_is_the_newest_release'


def downloaded_programs():
    """The entries of software_outside_the_distribution.yml installed from a downloaded binary."""
    names, current = [], None
    for line in (T/'software_outside_the_distribution.yml').read_text().splitlines():
        entry = re.match(r'^  ([a-z0-9_]+):\s*$', line)
        if entry:
            current = entry.group(1)
        elif current and re.match(r'^\s+installed_from:\s*downloaded_binary\b', line):
            names.append(current)
    return names


def checks_of_group(text, group):
    """{check name: script text} of one check group in a rendered check file."""
    lines = text.splitlines()
    start = lines.index(f'  {group}:')
    checks, name, script, in_script = {}, None, [], False
    for line in lines[start + 1:]:
        if re.match(r'^  \S', line):
            break
        check = re.match(r'^      ([a-z0-9_]+):$', line)
        if check:
            if name:
                checks[name] = '\n'.join(script)
            name, script, in_script = check.group(1), [], False
        elif line.strip() == 'script: |':
            in_script = True
        elif in_script and (line.startswith('            ') or not line.strip()):
            script.append(line[12:])
        elif in_script:
            in_script = False
    if name:
        checks[name] = '\n'.join(script)
    return checks


class StandInGitHub(http.server.BaseHTTPRequestHandler):
    answers = {}       # repository: list of (status, body); the last one repeats
    requests = {}

    def do_GET(self):
        match = re.match(r'^/repos/([^/]+/[^/]+)/releases/latest$', self.path)
        repository = match.group(1) if match else ''
        StandInGitHub.requests[repository] = StandInGitHub.requests.get(repository, 0) + 1
        queue = StandInGitHub.answers.get(repository, [(404, '{"message": "Not Found"}')])
        status, body = queue.pop(0) if len(queue) > 1 else queue[0]
        data = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *arguments):
        pass


def release(tag, repository):
    return (200, json.dumps({'tag_name': tag, 'prerelease': False,
                             'html_url': f'https://github.com/{repository}/releases/tag/{tag}'}))


class PinnedProgramReleases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), StandInGitHub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.stand_in_url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.default_checks = cls.util01_checks()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    @classmethod
    def util01_checks(cls, settings_changes=()):
        """The pinned_program_releases checks that the real every_server playbook renders for util01."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            settings = (root/'mmx_project_settings.yml').read_text()
            for old, new in settings_changes:
                assert settings.count(old) == 1, old
                settings = settings.replace(old, new)
            (root/'mmx_project_settings.yml').write_text(settings)
            result = subprocess.run([cls.mmx, 'explain', 'every_server', '--json'], cwd=root, text=True, capture_output=True)
            assert result.returncode == 0, result.stderr
        texts = []

        def walk(value):
            if isinstance(value, dict):
                if value.get('field') == 'file.template' and '\n  pinned_program_releases:' in value.get('text', ''):
                    texts.append(value['text'])
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(json.loads(result.stdout))
        assert len(texts) == 1, f'{len(texts)} rendered files hold pinned_program_releases'
        return checks_of_group(texts[0], 'pinned_program_releases'), texts[0]

    def programs(self, checks):
        return sorted(name[:-len(CHECK_SUFFIX)] for name in checks if name.endswith(CHECK_SUFFIX))

    # Which checks util01 gets.

    def test_util01_gets_one_check_per_downloaded_program_that_its_settings_install(self):
        checks, _ = self.util01_checks([('  triage_agent_coding_agent: claude_code', '  triage_agent_coding_agent: codex')])
        self.assertEqual(self.programs(checks), sorted(downloaded_programs()))
        self.assertIn('release_sources_answer', checks)

    def test_codex_is_checked_only_while_a_coding_agent_setting_is_codex(self):
        checks, _ = self.default_checks
        self.assertEqual(self.programs(checks), sorted(set(downloaded_programs()) - {'codex'}))
        checks, _ = self.util01_checks([('  systems_desk_coding_agent: claude_code', '  systems_desk_coding_agent: codex')])
        self.assertIn('codex' + CHECK_SUFFIX, checks)

    def test_rclone_is_checked_only_while_the_uploads_copy_runs_on_util01(self):
        checks, _ = self.util01_checks([('    uploads_backup_runs_on: [util_server]', '    uploads_backup_runs_on: []')])
        self.assertNotIn('rclone' + CHECK_SUFFIX, checks)
        self.assertNotIn("'rclone/rclone'", checks['release_sources_answer'])

    def test_a_pin_that_is_not_a_github_release_gets_no_check_and_a_comment(self):
        checks, text = self.util01_checks([(
            '      download_url: https://github.com/rclone/rclone/releases/download/v1.75.2/rclone-v1.75.2-linux-amd64.zip',
            '      download_url: https://downloads.example.com/rclone-v1.75.2-linux-amd64.zip')])
        self.assertNotIn('rclone' + CHECK_SUFFIX, checks)
        self.assertIn('# rclone: no check, because its download_url is not a GitHub release.', text)

    # A pin without a release stops the run before any change.

    def test_every_pin_is_checked_for_zeros_before_any_change(self):
        settings = (T/'mmx_project_settings.yml').read_text().split('\n  stack_software:\n', 1)[1]
        pins = sorted(re.findall(r'^    ([a-z0-9_]+):$', settings.split('\n\n', 1)[0], re.M))
        self.assertIn('set_up_outside_services', pins)
        for playbook, extra, first in (('every_server', [], 'util01 / refuse_programs_pinned_without_a_release/'),
                                       ('systems_desk', ['--var', 'desk_name=desk01'], 'desk01 / systems_desk/refuse_a_node_outside_systems_desks')):
            with self.subTest(playbook=playbook):
                result = subprocess.run([self.mmx, 'explain', playbook, *extra], cwd=T, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                tasks = re.findall(r'^  (\S+ / \S+): ', result.stdout, re.M)
                self.assertTrue(tasks[0].startswith(first), tasks[:3])
                zero_checks = [task for task in tasks if '/no_pin_has_a_sha256_of_zeros[' in task]
                self.assertEqual(sorted(re.search(r'\[(.*)\]', task)[1] for task in zero_checks), pins)
                # Each check comes before the first task that downloads or installs anything.
                last = max(tasks.index(task) for task in zero_checks)
                self.assertLessEqual(last, 1 + len(pins))
                self.assertIn('"' + '0' * 64 + '"', result.stdout)

    # What each generated script does.

    def run_script(self, script, answers):
        StandInGitHub.answers = {repository: list(queue) for repository, queue in answers.items()}
        StandInGitHub.requests = {}
        script = script.replace('https://api.github.com', self.stand_in_url).replace('sleep 5', 'sleep 0')
        result = subprocess.run(['bash', '--noprofile', '--norc', '-o', 'pipefail', '-c', script],
                                text=True, capture_output=True, timeout=120)
        return result.returncode, result.stdout + result.stderr

    def check(self, program):
        checks, _ = self.default_checks
        return checks[program + CHECK_SUFFIX]

    def test_a_newer_release_fails_and_names_the_program_both_versions_and_the_procedure(self):
        code, output = self.run_script(self.check('mmhotline'), {
            'monkeymaxxing/mmhotline': [release('v0.1.1', 'monkeymaxxing/mmhotline')]})
        self.assertEqual(code, 1, output)
        for text in ('mmhotline has a newer release, 0.1.1', 'pins 0.1.0',
                     'https://github.com/monkeymaxxing/mmhotline/releases/tag/v0.1.1',
                     'add_or_update_a_program_from_outside_the_distribution.md'):
            self.assertIn(text, output)

    def test_a_newer_release_by_number_fails_whatever_the_tag_prefix(self):
        code, output = self.run_script(self.check('rclone'), {'rclone/rclone': [release('v1.100.0', 'rclone/rclone')]})
        self.assertEqual(code, 1, output)
        code, output = self.run_script(self.check('litestream'), {
            'benbjohnson/litestream': [release('litestream-99.0.0', 'benbjohnson/litestream')]})
        self.assertEqual(code, 1, output)

    def test_the_same_or_an_older_release_passes(self):
        for tag in ('v0.5.16', 'v0.4.99', 'v0.0.1'):
            code, output = self.run_script(self.check('litestream'), {
                'benbjohnson/litestream': [release(tag, 'benbjohnson/litestream')]})
            self.assertEqual(code, 0, f'{tag}: {output}')

    def test_a_pre_release_pin_passes_until_its_release_and_before_any_stable_release(self):
        # releases/latest answers 404 while a project has published only pre-releases.
        code, output = self.run_script(self.check('mmhotline'), {
            'monkeymaxxing/mmhotline': [(404, '{"message": "Not Found"}')]})
        self.assertEqual(code, 0, output)
        self.assertIn('no release that is not a pre-release', output)
        code, output = self.run_script(self.check('mmhotline'), {
            'monkeymaxxing/mmhotline': [release('v0.0.9', 'monkeymaxxing/mmhotline')]})
        self.assertEqual(code, 0, output)

    def test_a_source_that_does_not_answer_passes_after_3_tries(self):
        for name, answer in (('rate-limited', (403, '{"message": "API rate limit exceeded for 203.0.113.7."}')),
                             ('malformed', (200, '{"tag_name": ')),
                             ('no tag', (200, '{"name": "x"}')),
                             ('server error', (502, 'Bad gateway'))):
            code, output = self.run_script(self.check('mmx'), {'monkeymaxxing/mmx': [answer]})
            self.assertEqual(code, 0, f'{name}: {output}')
            self.assertIn('did not answer', output, name)
            self.assertEqual(StandInGitHub.requests.get('monkeymaxxing/mmx'), 3, name)

    def test_a_failed_request_is_tried_again_in_the_same_run(self):
        code, output = self.run_script(self.check('mmx'), {'monkeymaxxing/mmx': [
            (502, 'Bad gateway'), release('v0.2.0', 'monkeymaxxing/mmx')]})
        self.assertEqual(code, 1, output)
        self.assertEqual(StandInGitHub.requests['monkeymaxxing/mmx'], 2)

    def test_release_sources_answer_fails_and_names_each_source_that_did_not_answer(self):
        checks, _ = self.default_checks
        script = checks['release_sources_answer']
        every_source = {'monkeymaxxing/mmx': [release('v0.1.0', 'monkeymaxxing/mmx')],
                        'monkeymaxxing/mmwatchdog': [release('v0.1.0', 'monkeymaxxing/mmwatchdog')],
                        'monkeymaxxing/mmhotline': [(404, '{"message": "Not Found"}')],
                        'monkeymaxxing/monkeymaxxing-stack': [release('2026-11', 'monkeymaxxing/monkeymaxxing-stack')],
                        'benbjohnson/litestream': [release('v0.5.17', 'benbjohnson/litestream')],
                        'rclone/rclone': [release('v1.75.2', 'rclone/rclone')]}
        code, output = self.run_script(script, every_source)
        self.assertEqual(code, 0, output)
        code, output = self.run_script(script, dict(every_source, **{
            'rclone/rclone': [(403, '{"message": "API rate limit exceeded"}')]}))
        self.assertEqual(code, 1, output)
        self.assertIn("rclone's release source, rclone/rclone at GitHub, did not answer: HTTP 403: API rate limit exceeded", output)
        self.assertNotIn('litestream', output)

    def test_no_connection_counts_as_no_answer(self):
        with socket.socket() as unused:
            unused.bind(('127.0.0.1', 0))
            closed_url = f'http://127.0.0.1:{unused.getsockname()[1]}'
        script = self.check('mmx').replace('https://api.github.com', closed_url).replace('sleep 5', 'sleep 0')
        result = subprocess.run(['bash', '--noprofile', '--norc', '-o', 'pipefail', '-c', script],
                                text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('no answer, curl exit code 7', result.stdout)


if __name__ == '__main__':
    unittest.main()
