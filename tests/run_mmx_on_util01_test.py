#!/usr/bin/env python3
"""Run the helper with fake git, ssh, mmx, flock and mmhotline; no server access.

The stand-in mmhotline answers commit-reviews check as MMHotline
does with trusted_commits: every_commit_on_origin (exit 0 with the commit as
the trusted one; an empty answer when MMHotline trusts nothing) and fails the test when it is called while the helper
holds util01's lock: MMHotline's check takes the same lock itself and waits for
it without a time limit.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template/server_management_scripts/run_mmx_on_util01'
COMMIT = 'a' * 40
OLDER = 'b' * 40
FAKE = r'''import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
remote = os.environ.get('REMOTE') == 'yes'
held = pathlib.Path(os.environ['COMMAND_LOG'] + '.lock-held')
with open(os.environ['COMMAND_LOG'], 'a') as log:
    log.write(json.dumps([remote, name, *args]) + '\n')
if name == 'git':
    if args[0] == 'status':
        print(os.environ.get('REMOTE_DIRTY' if remote else 'DIRTY', ''), end='')
        sys.exit(int(os.environ.get('STATUS_EXIT', '0')))
    if args[0] == 'fetch': sys.exit(int(os.environ.get('FETCH_EXIT', '0')))
    if args[0] == 'symbolic-ref': print(os.environ.get('BRANCH', 'main'))
    if args[0] == 'rev-parse':
        print(os.environ.get('REMOTE_COMMIT' if remote else 'PUSHED_COMMIT' if args[-1] != 'HEAD' else 'COMMIT', os.environ['THE_COMMIT']))
elif name == 'mmx':
    if args == ['nodes', '--json']:
        print(json.dumps({'nodes': [{'name': 'util01', 'address': '203.0.113.1'}]}))
    else:
        assert remote
        assert os.environ['MMX_VAULT_PASSWORD_FILE'].endswith('/mmx_vault_passphrase')
        if args[0] not in ('status', 'stop', 'results'):
            holder = pathlib.Path(os.environ['MMX_VAULT_PASSWORD_FILE']).parent / 'systems_repository.lock'
            lines = holder.read_text().splitlines()
            assert len(lines) == 1 and lines[0].startswith('run_mmx_on_util01: mmx '), lines
            assert 'daily server settings comparison' not in lines[0], lines
        print('MMX streamed output')
        sys.exit(int(os.environ.get('MMX_EXIT', '0')))
elif name == 'mmhotline':
    assert remote
    if held.exists():
        print('the helper called mmhotline while holding the lock', file=sys.stderr)
        sys.exit(99)
    if args[:2] == ['commit-reviews', 'check']:
        commit = args[args.index('--commit-id') + 1]
        answer = os.environ.get('CHECK_ANSWER', 'trusted')
        if answer == 'down':
            print('mmhotline: the command socket /run/mmhotline/command.sock is missing', file=sys.stderr)
            sys.exit(1)
        waiting = [] if answer == 'trusted' else [{'commit_id': commit, 'reason_kind': 'not_signed_by_a_trusted_key',
                   'reason': 'which no key the team trusts signed', 'author': 'Mallory \x1b[2J', 'message': 'evil \x1b]0;title\x07',
                   'review_url': 'https://ops.example.com/approvals/commits/' + commit}]
        trusted = {'trusted': commit, 'waits': os.environ['OLDER'], 'none': ''}[answer]
        print(json.dumps({'message': 'Checked.', 'web_url': 'https://ops.example.com', 'commit_check': {
            'checked_commit_id': commit, 'trusted_through_commit_id': trusted, 'commits_waiting_for_review': waiting}}))
        sys.exit(0 if trusted == commit else 1)
    print('MMHotline answered ' + ' '.join(args))
    sys.exit(int(os.environ.get('MMHOTLINE_EXIT', '0')))
elif name == 'ssh':
    script = sys.stdin.read()
    env = dict(os.environ, REMOTE='yes')
    sys.exit(subprocess.run(['bash', '-c', args[-1]], input=script, text=True, env=env).returncode)
elif name == 'sudo':
    assert args[:3] == ['-H', '-u', 'mmhotline'], args
    os.execvp(args[3], args[3:])
elif name == 'flock':
    if '--nonblock' in args:
        busy = int(os.environ.get('BUSY', '0'))
        if not busy: held.write_text('')
        sys.exit(busy)
    assert args == ['--wait', '60', '9'], args
    if os.environ.get('CHANGING_HOLDER'):
        state = pathlib.Path(os.environ['COMMAND_LOG'] + '.waits')
        count = int(state.read_text()) if state.exists() else 0
        state.write_text(str(count + 1))
        if count < 2:
            holder = pathlib.Path(os.environ['MMX_VAULT_PASSWORD_FILE']).parent / 'systems_repository.lock'
            holder.write_text(['weekly restore drill, user mmhotline\n', 'person shell, user root\n'][count])
            sys.exit(1)
    held.write_text('')
'''


class Helper(unittest.TestCase):
    def run_helper(self, arguments=('run', 'every_server'), **settings):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            (root / 'server_management_scripts').mkdir()
            (root / 'systems_repository').mkdir()
            path = root / 'server_management_scripts/run_mmx_on_util01'
            path.write_text(SOURCE.read_text().replace('/var/lib/mmhotline', str(root)))
            path.chmod(0o755)
            (root / 'systems_repository.lock').write_text(settings.pop('LOCK_HOLDER', 'daily server settings comparison, user mmhotline\n'))
            binary = root / 'bin'; binary.mkdir()
            for command in ('ssh', 'git', 'mmx', 'flock', 'sudo', 'mmhotline'):
                fake = binary / command
                fake.write_text('#!' + sys.executable + '\n' + FAKE)
                fake.chmod(0o755)
            log = root / 'commands.jsonl'
            result = subprocess.run(['bash', str(path), *arguments], text=True, capture_output=True,
                                    env={**os.environ, 'PATH': str(binary) + ':' + os.environ['PATH'],
                                         'COMMAND_LOG': str(log), 'THE_COMMIT': COMMIT, 'OLDER': OLDER, **settings})
            commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            self.assertNotIn('while holding the lock', result.stderr)
            return result, commands

    def test_runs_exact_arguments_at_the_trusted_commit_and_returns_mmx_status(self):
        for status in ('0', '1', '2', '3', '4', '130'):
            with self.subTest(status=status):
                result, commands = self.run_helper(('run', 'restore_database', '--var', 'read_backup_bucket_as_of=2026-11-03 15:30:00+00', '--var', 'literal=$(touch unwanted); *'), MMX_EXIT=status)
                self.assertEqual(result.returncode, int(status), result.stderr)
                self.assertIn('MMX streamed output', result.stdout)
                self.assertEqual([c for c in commands if c[:2] == [True, 'mmx']], [[True, 'mmx', 'run', '--non-interactive', 'restore_database', '--var', 'read_backup_bucket_as_of=2026-11-03 15:30:00+00', '--var', 'literal=$(touch unwanted); *']])
                order = [c[1] for c in commands if c[1] in ('ssh', 'mmhotline', 'flock', 'mmx') and c != [False, 'mmx', 'nodes', '--json']]
                self.assertEqual(order, ['ssh', 'mmhotline', 'flock', 'mmx'])
                self.assertIn([True, 'mmhotline', 'commit-reviews', 'check', '--commit-id', COMMIT, '--json'], commands)

    def test_the_helper_never_moves_util01s_checkout(self):
        result, commands = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        moves = [c for c in commands if c[0] and c[1] == 'git' and c[2] in ('pull', 'fetch', 'merge', 'checkout', 'reset')]
        self.assertEqual(moves, [])

    def test_mmhotline_that_does_not_answer_stops_the_run(self):
        for answer in ('down', 'none'):
            with self.subTest(answer=answer):
                result, commands = self.run_helper(CHECK_ANSWER=answer)
                self.assertEqual(result.returncode, 1)
                self.assertIn('MMHotline did not answer the commit check', result.stderr)
                self.assertFalse(any(c[:2] == [True, 'mmx'] or c[1] == 'flock' for c in commands))

    def test_laptop_refusals_never_contact_util01(self):
        for settings in ({'DIRTY': ' M vault'}, {'BRANCH': 'topic'}, {'PUSHED_COMMIT': 'other'}, {'FETCH_EXIT': '1'}, {'STATUS_EXIT': '1'}):
            with self.subTest(settings=settings):
                result, commands = self.run_helper(**settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(c[1] == 'ssh' for c in commands))
        # main moved, such as after the triage agent pushed a note: the refusal names the pull.
        result, commands = self.run_helper(PUSHED_COMMIT='other')
        self.assertIn('HEAD must equal pushed main: run git pull --rebase, and push your own commits if any, then run this again; nothing ran',
                      result.stderr)

    def test_remote_refusals_never_start_mmx(self):
        for settings in ({'REMOTE_DIRTY': ' M vault'}, {'REMOTE_COMMIT': OLDER}):
            with self.subTest(settings=settings):
                result, commands = self.run_helper(**settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(c[:2] == [True, 'mmx'] for c in commands))
        self.assertIn('pull on the systems desk and run again', result.stderr)

    def test_wait_names_lock_holder(self):
        result, commands = self.run_helper(BUSY='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Lock holder: daily server settings comparison, user mmhotline.', result.stderr)
        self.assertEqual(len([c for c in commands if c[1] == 'flock']), 2)

    def test_wait_repeats_each_minute_and_reads_the_current_holder(self):
        result, commands = self.run_helper(BUSY='1', CHANGING_HOLDER='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        hint = (". If the holder is an MMX run, "
                "./server_management_scripts/run_mmx_on_util01 status shows its run ID; "
                "if this change is urgent, ./server_management_scripts/run_mmx_on_util01 stop RUN_ID stops that run.")
        messages = [line for line in result.stderr.splitlines() if "waiting for util01's lock" in line]
        self.assertEqual(messages, [
            "run_mmx_on_util01: waiting for util01's lock" + waited + '. Lock holder: ' + holder + hint
            for holder, waited in [('daily server settings comparison, user mmhotline', ''),
                                   ('weekly restore drill, user mmhotline', ' (waited 1 minute)'),
                                   ('person shell, user root', ' (waited 2 minutes)')]])
        self.assertEqual([c[2:] for c in commands if c[1] == 'flock'],
                         [['--nonblock', '9']] + [['--wait', '60', '9']] * 3)
        self.assertIn('MMX streamed output', result.stdout)

    def test_wait_with_an_empty_holder_line(self):
        result, commands = self.run_helper(BUSY='1', LOCK_HOLDER='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Lock holder: another process on util01 (no holder line).', result.stderr)

    def test_multiline_arguments_keep_one_holder_line(self):
        result, commands = self.run_helper(('run-command', '--command', 'printf first\nprintf second'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn([True, 'mmx', 'run-command', '--non-interactive', '--command', 'printf first\nprintf second'], commands)

    def test_no_arguments(self):
        result, commands = self.run_helper(())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('give MMX arguments', result.stderr)
        self.assertEqual(commands, [])

    def test_results_does_not_get_a_run_only_option(self):
        result, commands = self.run_helper(('results', '--json'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn([True, 'mmx', 'results', '--json'], commands)

    def test_stop_and_status_reach_a_run_that_holds_the_lock(self):
        # A run in progress holds the lock, so stopping or reading it must not
        # wait for the lock, nor need a clean, pushed laptop copy.
        for command in ('stop', 'status'):
            with self.subTest(command=command):
                result, commands = self.run_helper((command, 'run-7f3a'), BUSY='1', DIRTY=' M notes.md', BRANCH='work')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn([True, 'mmx', command, '--non-interactive', 'run-7f3a'], commands)
                self.assertEqual([c for c in commands if c[1] in ('flock', 'git', 'mmhotline')], [])



if __name__ == '__main__':
    unittest.main()
