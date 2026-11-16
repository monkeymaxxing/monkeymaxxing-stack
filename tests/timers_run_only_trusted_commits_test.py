#!/usr/bin/env python3
"""util01's scheduled jobs run only a commit that MMHotline trusts: a push alone changes no server.

Runs each job's script from roles/util_server/main.yml, with
roles/util_server/files/find_the_trusted_commit_of_the_systems_repository, real
Git against a local origin, and a stand-in for `sudo -n /usr/local/bin/mmhotline
commit-reviews check`. The stand-in answers as MMHotline does:
it fetches into the copy, moves the copy's checkout forward to the trusted
commit, prints the JSON answer, and exits 0 when the checked commit is trusted
and 1 when a commit waits for review. It fails the test when it is called while
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
JOBS = ('compare_every_server_with_the_repository', 'weekly_database_restore_drill', 'check_for_a_leftover_restore01')

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
if answer == 'down':
    sys.exit('mmhotline: the command socket /run/mmhotline/command.sock is missing: mmhotline serve is not running there')
if answer == 'locked_out':
    # MMHotline's answer during a lock-out, when its settings hold no trusted keys.
    print('mmhotline: The operation could not be saved. Please try again.', file=sys.stderr)
    sys.exit(4)
git = lambda *a: subprocess.run(['git', *a], check=True, capture_output=True, text=True).stdout.strip()
git('fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main')
trusted = {'trusts_everything': commit, 'waits': os.environ.get('TRUSTED', ''), 'trusts_nothing': ''}[answer]
if trusted:
    git('merge', '--ff-only', '-q', trusted)
waiting = [] if trusted == commit else [{'commit_id': commit, 'reason_kind': 'not_signed_by_a_trusted_key',
           'reason': 'which no key the team trusts signed', 'review_url': 'https://ops.example.com/approvals/commits/' + commit}]
print(json.dumps({'message': 'Checked.', 'web_url': 'https://ops.example.com', 'commit_check': {
    'checked_commit_id': commit, 'trusted_through_commit_id': trusted, 'commits_waiting_for_review': waiting}}))
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
        script.write_text(SCRIPT.read_text().replace('/etc/mmhotline/mmhotline_settings.yml', str(self.settings)))
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
        script = job_script(name).replace('/var/lib/mmhotline', str(self.root))
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
        head = self.push('signed by a systems desk')
        for job in JOBS[:2]:
            with self.subTest(job=job):
                result, commands = self.run_job(job)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.ran_at(commands), {head})
                self.assertIn(['mmhotline', '-n', '/usr/local/bin/mmhotline', 'commit-reviews', 'check', '--commit-id', head, '--json'], commands)
                self.assertLess(next(i for i, c in enumerate(commands) if c[0] == 'mmhotline'), next(i for i, c in enumerate(commands) if c[0] == 'mmx'))

    def test_a_commit_that_waits_leaves_the_job_at_the_older_trusted_commit(self):
        trusted = self.push('signed by a systems desk')
        waits = self.push('merged with the Git host web button')
        for job in JOBS[:2]:
            with self.subTest(job=job):
                result, commands = self.run_job(job, MMHOTLINE='waits', TRUSTED=trusted)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.ran_at(commands), {trusted})
                self.assertEqual(self.git(self.copy, 'rev-parse', 'HEAD'), trusted)
                self.assertIn("find_the_trusted_commit_of_the_systems_repository: commits waiting for review: 1, "
                              f'at https://ops.example.com/approvals. This job runs at the trusted commit {trusted[:12]}, not at main\'s {waits[:12]}\n', result.stderr)

    def test_mmhotline_that_does_not_answer_keeps_the_commit_util01_has(self):
        self.push('pushed while MMHotline is stopped')
        result, commands = self.run_job(JOBS[0], MMHOTLINE='down')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran_at(commands), {self.first})
        self.assertIn(f'find_the_trusted_commit_of_the_systems_repository: MMHotline did not answer the commit check (exit 1); '
                      f'this job runs at the commit util01 already has, {self.first[:12]}, and at nothing newer\n', result.stderr)

    def test_during_a_lock_out_one_plain_line_says_why_mmhotline_checks_nothing(self):
        self.push('pushed during the lock-out')
        self.settings.write_text(self.rendered_mmhotline_settings(['ssh-ed25519 AAAA desk'], everyone_locked_out_except_desk='desk01'))
        result, commands = self.run_job(JOBS[0], MMHOTLINE='locked_out')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran_at(commands), {self.first})
        self.assertEqual(result.stderr, 'find_the_trusted_commit_of_the_systems_repository: MMHotline checks no commit during a '
                         'lock-out, because its settings then hold no trusted keys; this job runs at the commit util01 already '
                         f'has, {self.first[:12]}, and at nothing newer\n')
        # Outside a lock-out the same refusal keeps MMHotline's own words and the did-not-answer line.
        self.settings.write_text(self.rendered_mmhotline_settings(['ssh-ed25519 AAAA desk']))
        result, commands = self.run_job(JOBS[0], MMHOTLINE='locked_out')
        self.assertEqual(result.stderr, 'mmhotline: The operation could not be saved. Please try again.\n'
                         'find_the_trusted_commit_of_the_systems_repository: MMHotline did not answer the commit check (exit 4); '
                         f'this job runs at the commit util01 already has, {self.first[:12]}, and at nothing newer\n')

    def test_nothing_new_runs_at_the_same_commit(self):
        result, commands = self.run_job(JOBS[0])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ran_at(commands), {self.first})
        self.assertEqual(result.stderr, '')

    def test_no_trusted_commit_runs_nothing_and_does_not_fail_the_unit(self):
        self.push('a whole history no key the team trusts signed')
        for job in JOBS:
            with self.subTest(job=job):
                result, commands = self.run_job(job, MMHOTLINE='trusts_nothing')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.ran_at(commands), set())
                self.assertFalse((self.root / 'lock-held').exists())
                self.assertIn('MMHotline trusts no commit of main yet', result.stderr)

    def test_an_unreachable_git_host_fails_the_job_and_asks_nothing(self):
        self.git(self.copy, 'remote', 'set-url', 'origin', str(self.root / 'missing.git'))
        for job in JOBS:
            with self.subTest(job=job):
                result, commands = self.run_job(job)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.asked(commands), [])
                self.assertIn('cannot read main at the Git host; nothing ran', result.stderr)

    def test_a_checkout_behind_the_trusted_commit_runs_nothing(self):
        # Only MMHotline moves the checkout. Here it could not, such as for a
        # local change, so the job refuses rather than run an older commit.
        head = self.push('trusted, but the copy did not move')
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

    def test_the_check_of_new_commits_asks_mmhotline_and_never_fails_or_runs(self):
        text = ROLE.read_text().split('      name: check_new_commits_on_main\n', 1)[1]
        self.assertIn('systemd_calendar_schedule: "*-*-* *:00/{{ .inputs.check_new_commits_on_main_every_minutes }}:00 UTC"', text)
        body = re.search(r'      script: \|\n((?:        .*\n)+)', text)[1]
        script = '\n'.join(line[8:] for line in body.splitlines()).replace('/var/lib/mmhotline', str(self.root))
        head = self.push('noticed within minutes')
        for answer in ('trusts_everything', 'waits', 'trusts_nothing', 'down'):
            with self.subTest(answer=answer):
                (self.root / 'commands').write_text('')
                result = subprocess.run(['bash', '-c', script], cwd=self.copy, text=True, capture_output=True, timeout=60,
                                        stdin=subprocess.DEVNULL, env={**self.env, 'MMHOTLINE': answer, 'TRUSTED': self.first})
                commands = self.asked([json.loads(line) for line in (self.root / 'commands').read_text().splitlines()])
                self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)
                self.assertEqual([c[0] for c in commands], ['mmhotline'])
                self.assertEqual(commands[0][6], head)
                self.assertFalse((self.root / 'lock-held').exists())
        # While another holder, such as the restore drill, has the lock, the
        # job asks nothing: MMHotline's waiting marker would end the drill.
        (self.root / 'commands').write_text('')
        result = subprocess.run(['bash', '-c', script], cwd=self.copy, text=True, capture_output=True, timeout=60,
                                stdin=subprocess.DEVNULL, env={**self.env, 'LOCK_BUSY': 'yes'})
        self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)
        self.assertEqual(self.asked([json.loads(line) for line in (self.root / 'commands').read_text().splitlines()]), [])

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
                      triage_agent_server_work={'minutes_between_the_warning_and_a_reboot': 10, 'sos_waits_for_a_server_replacement_minutes': 10, 'warn_waits_for_the_triage_agent_minutes': 3},
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

    def test_the_trusted_keys_are_root_ssh_public_keys(self):
        keys = ['ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIR+J8OoEVNHl3P/KSWFruheEQaq8Cgw/PziDAinSTJJ alex on desk01, "quoted"',
                'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN4Jcw7Fq2URbtI72IZ9N/p0WjdFGpZ0VJcet+YVhxZx util01, the mmhotline user']
        text = self.rendered_mmhotline_settings(keys)
        block = re.search(r'(?m)^  trusted_commit_signing_public_keys:\n((?:    - .*\n)+)', text)[1]
        self.assertEqual([json.loads(line[6:]) for line in block.splitlines()], keys)

    def test_the_triage_agent_approves_unsigned_commits_except_the_short_list_of_paths(self):
        """The triage agent approves by default; only the files that set its
        own powers and the trusted keys wait for a person, and each listed file exists."""
        text = self.rendered_mmhotline_settings(['ssh-ed25519 AAAA desk'])
        self.assertEqual(re.findall(r'(?m)^  commits_without_a_trusted_signature_are_approved_by: (.*)$', text),
                         ['a_person_or_the_triage_agent'])
        block = re.search(r'(?m)^  paths_only_a_person_may_approve:\n((?:    (?:#.*|- .*)\n)+)', text)[1]
        paths = [line.strip()[2:] for line in block.splitlines() if line.strip().startswith('- ')]
        self.assertEqual(paths, ['mmhotline_settings.yml', 'mmx_project_settings.yml', 'triage_agent_rules.md', 'AGENTS.md', 'CLAUDE.md',
                                 'roles/every_server/files/sudoers_triage',
                                 'roles/util_server/files/sudoers_triage_mmwatchdog_fleet_readings'])
        # A renamed or moved file must take the list with it, or MMHotline protects a path that no longer exists.
        for path in paths:
            self.assertTrue((TEMPLATE / path).is_file(), f'{path} is in paths_only_a_person_may_approve but not in the template')

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
