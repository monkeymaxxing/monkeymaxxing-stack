#!/usr/bin/env python3
"""util01's scheduled jobs run only a commit that MMHotline trusts: a push alone changes no server.

Runs each job's script from roles/util_server/main.yml, with
roles/util_server/files/find_the_trusted_commit_of_the_systems_repository, real
Git against a local origin, and a stand-in for `sudo -n /usr/local/bin/mmhotline
commit-reviews check`. The stand-in answers as MMHotline does:
it fetches into the copy, moves the copy's checkout forward to the checked
commit (MMHotline trusts every commit on origin), prints the JSON answer, and exits 0 when the checked commit is trusted
and 1 when MMHotline trusts nothing. MMHotline's own CLI exits 4 both for a
refusal and for a command socket that does not answer, and only its words
tell them apart; the stand-in uses the CLI's words. It fails the test when it
is called while
the job holds /var/lib/mmhotline/systems_repository.lock: MMHotline's check
takes that lock itself and waits for it without a time limit.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
SCRIPT = TEMPLATE / 'roles/util_server/files/find_the_trusted_commit_of_the_systems_repository'
ROLE = TEMPLATE / 'roles/util_server/main.yml'
JOBS = ('compare_every_server_with_the_repository', 'weekly_database_restore_drill', 'check_for_a_leftover_restore01',
        'weekly_maintenance')

STAND_INS = {
    # MMHotline's commit check, reached through the one sudo line util_server installs.
    'sudo': r'''
import json, os, pathlib, re, subprocess, sys
args = sys.argv[1:]
log = pathlib.Path(os.environ['TEST_ROOT']) / 'commands'
with log.open('a') as f: f.write(json.dumps(['mmhotline', *args]) + '\n')
if (pathlib.Path(os.environ['TEST_ROOT']) / 'lock-held').exists():
    sys.exit('mmhotline commit-reviews check was called while the job held the lock')
assert args[:5] == ['-n', '/usr/local/bin/mmhotline', 'commit-reviews', 'check', '--commit-id'] and args[6:] == ['--json'], args
commit = args[5]
answer = os.environ.get('MMHOTLINE', 'trusts_everything')
if answer == 'lock_out_while_waiting':
    # The person pressed the lock-out button while the check waited, and MMHotline stopped.
    (pathlib.Path(os.environ['TEST_ROOT']) / 'everyone-locked-out').write_text('locked out\n')
    answer = 'down'
if answer == 'down':
    print('mmhotline: mmhotline serve is not running at command socket /run/mmhotline/command.sock', file=sys.stderr)
    sys.exit(4)
if answer == 'unreachable':
    print('mmhotline: cannot reach mmhotline serve at command socket /run/mmhotline/command.sock: connection refused', file=sys.stderr)
    sys.exit(4)
if answer == 'locked_out':
    # MMHotline's answer during a lock-out, when its settings hold no trusted keys.
    print('mmhotline: The operation could not be saved. Please try again.', file=sys.stderr)
    sys.exit(4)
git = lambda *a: subprocess.run(['git', *a], check=True, capture_output=True, text=True).stdout.strip()
git('fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main')
trusted = {'trusts_everything': commit, 'trusts_nothing': ''}[answer]
if trusted:
    git('merge', '--ff-only', '-q', trusted)
print(json.dumps({'message': 'Checked.', 'web_url': 'https://ops.example.com', 'commit_check': {
    'checked_commit_id': commit, 'trusted_through_commit_id': trusted, 'commits_waiting_for_review': []}}))
sys.exit(0 if trusted == commit else 1)
''',
    'flock': r'''
import json, os, pathlib, sys
args = sys.argv[1:]
root = pathlib.Path(os.environ['TEST_ROOT'])
with (root / 'commands').open('a') as f: f.write(json.dumps(['flock', *args]) + '\n')
if args[-1] == 'true':
    # flock [--nonblock] FILE true takes the lock and gives it back at once;
    # LOCK_BUSY: another holder, such as the restore drill, has it.
    sys.exit(1 if '--nonblock' in args and os.environ.get('LOCK_BUSY') else 0)
(root / 'lock-held').write_text('')
if os.environ.get('LOCK_OUT_WHILE_WAITING_FOR_THE_LOCK'):
    # The person pressed the lock-out button while the job waited for the lock.
    (root / 'everyone-locked-out').write_text('locked out\n')
''',
    'mmx': r'''
import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
head = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
with (pathlib.Path(os.environ['TEST_ROOT']) / 'commands').open('a') as f: f.write(json.dumps(['mmx', head, *args]) + '\n')
if args[:2] == ['explain', 'every_server']:
    print(json.dumps({'fleet_stages': [{'node_tasks': [{'path': 'every_server/a_lock_out_starts_only_with_the_lock_out_button', 'status': 'skipped'}]}]}))
''',
}


def job_script(name):
    text = ROLE.read_text().split('      name: ' + name + '\n', 1)[1]
    body = re.search(r'      script: \|\n(.*?)      env:', text, re.S)[1]
    return '\n'.join(line[8:] for line in body.splitlines())


class TimersRunOnlyTrustedCommits(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        root = self.root = Path(self.temporary.name)
        identity = {'GIT_AUTHOR_NAME': 'a', 'GIT_AUTHOR_EMAIL': 'a@example.invalid', 'GIT_COMMITTER_NAME': 'a',
                    'GIT_COMMITTER_EMAIL': 'a@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1', 'HOME': str(root)}
        binary = root / 'bin'
        binary.mkdir()
        for name, source in STAND_INS.items():
            (binary / name).write_text('#!' + sys.executable + '\n' + source)
            (binary / name).chmod(0o755)
        wrapper = binary / 'find_the_trusted_commit_of_the_systems_repository'
        self.settings = root / 'mmhotline_settings.yml'
        script = root / 'find_the_trusted_commit_of_the_systems_repository'
        self.locked_out = root / 'everyone-locked-out'
        script.write_text(SCRIPT.read_text().replace('/etc/mmhotline/everyone-locked-out', str(self.locked_out)))
        wrapper.write_text(f'#!/bin/bash\nexec bash {script} "$@"\n')
        wrapper.chmod(0o755)
        self.env = {**os.environ, **identity, 'PATH': f'{binary}:{os.environ["PATH"]}', 'TEST_ROOT': str(root)}
        self.origin = root / 'origin.git'
        self.git(root, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        self.desk = root / 'desk'
        self.git(root, 'clone', '-q', str(self.origin), str(self.desk))
        self.first = self.push('first')
        self.copy = root / 'systems_repository'
        self.git(root, 'clone', '-q', str(self.origin), str(self.copy))
        (root / 'systems_repository.lock').write_text('')

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, directory, *arguments):
        return subprocess.run(['git', '-C', str(directory), *arguments], check=True, text=True, capture_output=True,
                              env=self.env, timeout=30).stdout.strip()

    def push(self, message):
        self.git(self.desk, 'commit', '-q', '--allow-empty', '-m', message)
        self.git(self.desk, 'push', '-q', 'origin', 'main')
        return self.git(self.desk, 'rev-parse', 'HEAD')

    def run_job(self, name, **settings):
        (self.root / 'commands').write_text('')
        (self.root / 'lock-held').unlink(missing_ok=True)
        script = job_script(name).replace('/var/lib/mmhotline', str(self.root)).replace('/etc/mmhotline/everyone-locked-out', str(self.locked_out))
        result = subprocess.run(['bash', '-c', script], cwd=self.root, text=True, capture_output=True, timeout=60,
                                env={**self.env, 'JOB_NAME': name, **settings})
        commands = [json.loads(line) for line in (self.root / 'commands').read_text().splitlines()]
        self.assertNotIn('while the job held the lock', result.stderr)
        return result, commands

    def asked(self, commands):
        return [c for c in commands if c[0] != 'flock']

    def ran_at(self, commands):
        return {c[1] for c in commands if c[0] == 'mmx'}

    def test_a_trusted_head_runs_at_the_head(self):
        head = self.push('pushed to the main copy')
        for job in JOBS[:2]:
            with self.subTest(job=job):
                result, commands = self.run_job(job)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.ran_at(commands), {head})
                self.assertIn(['mmhotline', '-n', '/usr/local/bin/mmhotline', 'commit-reviews', 'check', '--commit-id', head, '--json'], commands)
                self.assertLess(next(i for i, c in enumerate(commands) if c[0] == 'mmhotline'), next(i for i, c in enumerate(commands) if c[0] == 'mmx'))

    def test_mmhotline_that_does_not_answer_keeps_the_commit_util01_has(self):
        self.push('pushed while MMHotline is stopped')
        for answer in ('down', 'unreachable'):
            with self.subTest(answer=answer):
                result, commands = self.run_job(JOBS[0], MMHOTLINE=answer)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.ran_at(commands), {self.first})
                self.assertIn(f'find_the_trusted_commit_of_the_systems_repository: MMHotline did not answer the commit check; '
                              f'this job runs at the commit util01 already has, {self.first[:12]}, and at nothing newer\n', result.stderr)

    def test_a_lock_out_that_starts_while_the_check_waits_never_falls_back(self):
        self.push('pushed before the lock-out')
        result, commands = self.run_job(JOBS[0], MMHOTLINE='lock_out_while_waiting')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran_at(commands), set())
        self.assertIn('everyone is locked out', result.stderr)
        self.assertNotIn('at nothing newer', result.stderr)

    def test_a_lock_out_that_starts_while_a_job_waits_for_the_lock_runs_nothing(self):
        for job in JOBS:
            with self.subTest(job=job):
                result, commands = self.run_job(job, LOCK_OUT_WHILE_WAITING_FOR_THE_LOCK='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([c for c in commands if c[0] == 'mmx'], [])
                self.assertIn('everyone is locked out (', result.stdout)
                self.locked_out.unlink()

    def test_during_a_lock_out_every_job_runs_nothing_and_says_why_in_one_line(self):
        """The lock-out button's marker on util01 comes before MMHotline's answer and the commit util01 already has."""
        self.push('pushed during the lock-out')
        self.locked_out.write_text('The incident response disabled triage runs.\n')
        for job in JOBS[:3]:
            with self.subTest(job=job):
                result, commands = self.run_job(job)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.asked(commands), [])
                self.assertEqual(result.stderr, 'find_the_trusted_commit_of_the_systems_repository: everyone is locked out '
                                 f'({self.locked_out}), so this job runs nothing until the person undoes the lock-out with the lock-out button\n')
        self.locked_out.unlink()
        # A refusal by MMHotline keeps MMHotline's own words, runs nothing, and
        # never falls back to the commit util01 already has.
        head = self.git(self.desk, 'rev-parse', 'HEAD')
        result, commands = self.run_job(JOBS[0], MMHOTLINE='locked_out')
        self.assertEqual(result.returncode, 4)
        self.assertEqual(self.ran_at(commands), set())
        self.assertEqual(result.stderr, 'mmhotline: The operation could not be saved. Please try again.\n'
                         f'find_the_trusted_commit_of_the_systems_repository: MMHotline refused the commit check of {head[:12]}; nothing ran\n')

    def test_nothing_new_runs_at_the_same_commit(self):
        result, commands = self.run_job(JOBS[0])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran_at(commands), {self.first})
        self.assertEqual(result.stderr, '')

    def test_a_check_that_trusts_nothing_runs_nothing(self):
        # MMHotline answered: an answer is never a reason to run the commit util01 already has.
        head = self.push('pushed, but MMHotline trusts nothing')
        result, commands = self.run_job(JOBS[0], MMHOTLINE='trusts_nothing')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.ran_at(commands), set())
        self.assertIn(f'MMHotline trusts no commit through {head[:12]} (exit 1); nothing ran', result.stderr)
        self.assertNotIn('at nothing newer', result.stderr)

    def test_an_unreachable_git_host_fails_the_job_and_asks_nothing(self):
        self.git(self.copy, 'remote', 'set-url', 'origin', str(self.root / 'missing.git'))
        for job in JOBS:
            with self.subTest(job=job):
                result, commands = self.run_job(job)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.asked(commands), [])
                self.assertIn('cannot read main in the main copy of the systems repository; nothing ran', result.stderr)

    def test_a_checkout_behind_the_trusted_commit_runs_nothing(self):
        # Only MMHotline moves the checkout. Here it could not, such as for a
        # local change, so the job refuses rather than run an older commit.
        head = self.push('checked, but the copy did not move')
        self.git(self.copy, 'fetch', '-q', 'origin')
        script = job_script(JOBS[0]).replace('/var/lib/mmhotline', str(self.root))
        script = script.replace('trusted=$(find_the_trusted_commit_of_the_systems_repository)', f'trusted=$(echo {head})')
        result = subprocess.run(['bash', '-c', script], cwd=self.root, text=True, capture_output=True, timeout=60,
                                env={**self.env, 'JOB_NAME': JOBS[0]})
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"util01's copy is at {self.first[:12]}, not at or past the trusted commit {head[:12]}; nothing ran", result.stderr)

    def test_every_job_asks_mmhotline_before_it_takes_the_lock(self):
        for job in JOBS:
            with self.subTest(job=job):
                script = job_script(job)
                self.assertLess(script.index('find_the_trusted_commit_of_the_systems_repository'), script.index('exec 9>>'))
                for moves in ('git pull', 'git fetch', 'git merge ', 'git checkout', 'git reset'):
                    self.assertNotIn(moves, script)

    def test_the_comparison_and_the_leftover_check_ask_only_once_the_lock_is_free(self):
        for job in (JOBS[0], JOBS[2]):
            with self.subTest(job=job):
                script = job_script(job)
                self.assertLess(script.index('flock /var/lib/mmhotline/systems_repository.lock true'),
                                script.index('trusted=$(find_the_trusted_commit_of_the_systems_repository)'))

    def test_the_sudo_line_allows_exactly_the_command_the_script_runs(self):
        line = re.search(r'content: "mmhotline ALL=\(root\) NOPASSWD: /usr/local/bin/mmhotline \^(.*)\$\\n"', ROLE.read_text())[1]
        allowed = re.compile('^' + line + '$')
        self.assertIn('sudo -n /usr/local/bin/mmhotline commit-reviews check --commit-id "$head" --json', SCRIPT.read_text())
        self.assertTrue(allowed.match('commit-reviews check --commit-id ' + 'a1' * 20 + ' --json'))
        for refused in ('commit-reviews check --commit-id ' + 'a1' * 20 + ' --json --command-socket /tmp/other',
                        'commit-reviews mark-reviewed --commit-id ' + 'a1' * 20 + ' --json',
                        'commit-reviews trust-through --commit-id ' + 'a1' * 20 + ' --json',
                        'commit-reviews check --commit-id HEAD --json'):
            self.assertIsNone(allowed.match(refused), refused)

    def rendered_mmhotline_settings(self, root_ssh_public_keys, everyone_locked_out_except_desk=''):
        """The text of mmhotline_settings.yml as MMX renders it for util01."""
        mmx = os.environ.get('MMX_BINARY', 'mmx')
        source = (TEMPLATE / 'mmhotline_settings.yml').read_text().replace('.secrets.', '.vars.secret_')
        root = Path(tempfile.mkdtemp(dir=self.root))
        (root / 'inventories').mkdir(parents=True)
        (root / 'playbooks').mkdir()
        values = {name: 'stand-in' for name in re.findall(r'\.vars\.(secret_\w+)', source)}
        values.update(everyone_locked_out_except_desk=everyone_locked_out_except_desk, triage_ssh_public_key='ssh-ed25519 AAAA triage', root_ssh_public_keys=root_ssh_public_keys,
                      triage_agent_coding_agent='claude_code', what_the_triage_agent_may_do_without_a_person='routine_fixes',
                      triage_agent_server_work={'sos_waits_for_a_server_replacement_minutes': 10, 'warn_waits_for_the_triage_agent_minutes': 3},
                      util01_private_page_host_names={'mmhotline': 'ops.example.com'},
                      private_ip='10.20.0.1', cloudflare_account_id='0' * 32, status_page_host_name='status.example.com')
        (root / 'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
        (root / 'inventories/servers.yml').write_text(json.dumps(dict(nodes={'util01': {'address': '127.0.0.1'}})))
        (root / 'settings.template').write_text(source)
        (root / 'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
            dict(id='render', file=dict(path='/tmp/rendered', template='settings.template', permissions_mode='0600'))])])))
        result = subprocess.run([mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    def test_mmhotline_trusts_every_commit_on_origin_and_holds_no_signing_settings(self):
        text = self.rendered_mmhotline_settings(['ssh-ed25519 AAAA desk'])
        self.assertEqual(re.findall(r'(?m)^systems_repository_commits:\n  trusted_commits: (.*)$', text), ['every_commit_on_origin'])
        # Commit trust is outside the triage agent section, so a setup without a triage agent has it.
        self.assertNotIn('trusted_commits', text.split('\ntriage_agent:\n', 1)[1].split('\nmmhotline_down_alarm:', 1)[0])
        for removed in ('commit_signing_public_key', 'trusted_commit_signing_public_keys',
                        'commits_without_a_trusted_signature_are_approved_by', 'paths_only_a_person_may_approve'):
            self.assertNotRegex(text, r'(?m)^\s*' + removed + ':')
        # A lock-out leaves MMHotline's settings as they are: the lock-out stops
        # triage runs and util01's jobs on util01 itself, so the settings need no desk review.
        self.assertNotIn('everyone_locked_out_except_desk', (TEMPLATE / 'mmhotline_settings.yml').read_text())
        self.assertNotIn('mmhotline_settings', (TEMPLATE / 'playbooks/lock_everyone_out.yml').read_text())

    def test_the_triage_key_among_root_ssh_public_keys_is_counted_by_its_key_part(self):
        playbook = (TEMPLATE / 'playbooks/every_server.yml').read_text()
        task = playbook.split('      - id: count_the_root_ssh_public_keys_that_are_the_triage_key\n', 1)[1]
        script = re.search(r'^          script: (.*)$', task, re.M)[1]
        self.assertEqual(re.search(r'^          dryrun: (.*)$', task, re.M)[1], script)
        program = '\n'.join(line[14:] for line in re.search(r'            PROGRAM: \|\n(.*?)\n            [A-Z_]+:', task, re.S)[1].splitlines())
        self.assertIn('number_equals: ["{{ .node_tasks.count_the_root_ssh_public_keys_that_are_the_triage_key.stdout }}", 0]', task)
        triage = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPsX9pp+bDzWfdnB2oQs5Hfkdg86mfoXg/fTLpSaAVrE util01, the triage agent'
        desk = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIR+J8OoEVNHl3P/KSWFruheEQaq8Cgw/PziDAinSTJJ alex on desk01'
        for keys, count in (([desk], '0'), ([desk, triage], '1'), ([desk, 'ssh-ed25519  AAAAC3NzaC1lZDI1NTE5AAAAIPsX9pp+bDzWfdnB2oQs5Hfkdg86mfoXg/fTLpSaAVrE another comment'], '1')):
            with self.subTest(keys=keys):
                result = subprocess.run(['bash', '-c', script], text=True, capture_output=True, timeout=10,
                                        env={**os.environ, 'ROOT_SSH_PUBLIC_KEYS': json.dumps(keys), 'TRIAGE_SSH_PUBLIC_KEY': triage, 'PROGRAM': program})
                self.assertEqual((result.returncode, result.stdout.strip()), (0, count), result.stderr)


if __name__ == '__main__':
    unittest.main()
