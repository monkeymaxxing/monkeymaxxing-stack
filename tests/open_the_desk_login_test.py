#!/usr/bin/env python3
"""ssh/open-the-desk-login: the laptop command that opens the coding agent's
desk login with one phone code, or says whether it is open.

  python3 tests/open_the_desk_login_test.py

Runs the command from a copy of the template, with a stand-in ssh that
answers the desk's question through SSH_ASKPASS, as OpenSSH does, and
records what it was asked.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
LAPTOP_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIORZZg3NlYdxJ28janK/DsJ1O0O2YgF7KN2aiEPskegs alex@work-laptop'

# A stand-in for OpenSSH: -O check succeeds while the master file exists;
# a login asks SSH_ASKPASS once and opens the master when the answer is the
# desk's code.
FAKE_SSH = '''#!/usr/bin/env python3
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(sys.argv[0]))
calls = os.path.join(here, 'calls.jsonl')
master = os.path.join(here, 'master-open')
record = {'argv': sys.argv[1:]}
if sys.argv[1:3] == ['-O', 'check']:
    open(calls, 'a').write(json.dumps(record) + '\\n')
    sys.exit(0 if os.path.exists(master) else 255)
answer = subprocess.run([os.environ['SSH_ASKPASS'], '(alex@desk) Verification code: '],
                        capture_output=True, text=True).stdout.strip()
record['askpass_answer'] = answer
record['askpass_require'] = os.environ.get('SSH_ASKPASS_REQUIRE')
open(calls, 'a').write(json.dumps(record) + '\\n')
if answer == open(os.path.join(here, 'desk-code')).read().strip():
    open(master, 'w').write('')
    sys.exit(0)
print('alex@desk: Permission denied (keyboard-interactive).', file=sys.stderr)
sys.exit(255)
'''


class OpenTheDeskLogin(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root/'example_systems'
        (self.repository/'ssh').mkdir(parents=True)
        (self.repository/'inventories').mkdir()
        shutil.copy2(T/'ssh/open-the-desk-login', self.repository/'ssh/open-the-desk-login')
        shutil.copy(T/'ssh/desk01', self.repository/'ssh/desk01')
        shutil.copy(template_values.filled_copy()/'inventories/servers.yml', self.repository/'inventories/servers.yml')
        self.home = self.root/'home'
        (self.home/'.ssh').mkdir(parents=True)
        (self.home/'.ssh/desk01.pub').write_text(LAPTOP_KEY + '\n')
        self.binary = self.root/'bin'
        self.binary.mkdir()
        (self.binary/'ssh').write_text(FAKE_SSH)
        (self.binary/'ssh').chmod(0o755)
        (self.binary/'desk-code').write_text('482913\n')
        self.temporary_files = self.root/'tmp'
        self.temporary_files.mkdir()

    def invoke(self, *arguments):
        env = {**os.environ, 'HOME': str(self.home), 'TMPDIR': str(self.temporary_files),
               'PATH': f'{self.binary}:/usr/bin:/bin'}
        env.pop('OPEN_THE_DESK_LOGIN_CODE', None)
        return subprocess.run([str(self.repository/'ssh/open-the-desk-login'), *arguments],
                              text=True, capture_output=True, env=env, cwd=self.root)

    def calls(self):
        path = self.binary/'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_anything_but_exactly_six_digits_is_refused_and_nothing_reaches_the_desk(self):
        for arguments in (['12345'], ['1234567'], ['12a456'], [''], [' 482913'], ['482913 '], ['482913\n'],
                          ['48 2913'], ['-482913'], ['482913', 'extra'], [], ['--check', '482913'], ['--open'],
                          ['--stay-open'], ['--stay-open', '--check'], ['--stay-open', '12345'],
                          ['--stay-open', '482913', 'extra'], ['482913', '--stay-open']):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
                self.assertEqual(self.calls(), [])
                self.assertEqual(list(self.temporary_files.iterdir()), [])

    def test_stay_open_runs_ssh_control_master_in_foreground_and_skips_when_already_open(self):
        result = self.invoke('--stay-open', '482913')
        self.assertEqual(result.returncode, 0, result.stderr)
        login = self.calls()[-1]
        self.assertEqual(login['argv'], ['-M', '-N', '-o', 'ControlPersist=no', '-o', 'NumberOfPasswordPrompts=1', 'desk01-agent'])
        self.assertEqual(login['askpass_answer'], '482913')
        self.assertEqual(login['askpass_require'], 'force')
        self.assertNotIn('482913', ' '.join(arg for call in self.calls() for arg in call['argv']))
        self.assertEqual(list(self.temporary_files.iterdir()), [])

        # Once open, --stay-open uses no code.
        before = len(self.calls())
        result = self.invoke('--stay-open', '222222')
        self.assertEqual(result.returncode, 0)
        self.assertIn('desk01-agent is open', result.stdout)
        self.assertEqual([call['argv'][:2] for call in self.calls()[before:]], [['-O', 'check']])

    def test_stay_open_refused_code_says_so_plainly(self):
        result = self.invoke('--stay-open', '111111')
        self.assertEqual(result.returncode, 1)
        self.assertIn('ask the person for a new code', result.stdout)
        self.assertEqual(list(self.temporary_files.iterdir()), [])

    def test_a_right_code_opens_the_agents_login_with_one_question_and_leaves_no_file(self):
        result = self.invoke('482913')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('The desk login desk01-agent is open.', result.stdout)
        login = self.calls()[-1]
        self.assertEqual(login['argv'], ['-o', 'NumberOfPasswordPrompts=1', 'desk01-agent', 'true'])
        self.assertEqual(login['askpass_answer'], '482913')
        self.assertEqual(login['askpass_require'], 'force')
        self.assertNotIn('482913', ' '.join(arg for call in self.calls() for arg in call['argv']))
        self.assertEqual(list(self.temporary_files.iterdir()), [])
        self.assertEqual(sorted(p.name for p in (self.repository/'ssh').iterdir()), ['desk01', 'open-the-desk-login'])

    def test_a_refused_code_says_so_plainly_and_leaves_no_file(self):
        result = self.invoke('111111')
        self.assertEqual(result.returncode, 1)
        self.assertIn('ask the person for a new code', result.stdout)
        self.assertEqual(list(self.temporary_files.iterdir()), [])

    def test_check_says_whether_the_login_is_open(self):
        result = self.invoke('--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('desk01-agent is closed', result.stdout)
        self.invoke('482913')
        result = self.invoke('--check')
        self.assertEqual(result.returncode, 0)
        self.assertIn('desk01-agent is open', result.stdout)
        self.assertEqual(self.calls()[-1]['argv'], ['-O', 'check', 'desk01-agent'])

    def test_an_open_login_uses_no_code(self):
        self.invoke('482913')
        before = len(self.calls())
        result = self.invoke('222222')
        self.assertEqual(result.returncode, 0)
        self.assertEqual([call['argv'][:2] for call in self.calls()[before:]], [['-O', 'check']])

    def test_the_desk_comes_from_the_repository_and_the_laptops_key(self):
        # A rebuilt desk, desk02, allows this laptop's new key; desk01's old key file stays on the laptop.
        new_key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINEWKEYNEWKEYNEWKEYNEWKEYNEWKEYNEWKEYNEWKEYab alex@work-laptop'
        inventory = self.repository/'inventories/servers.yml'
        inventory.write_text(inventory.read_text().replace(LAPTOP_KEY, new_key))
        shutil.copy(T/'ssh/desk01', self.repository/'ssh/desk02')
        (self.home/'.ssh/desk02.pub').write_text(new_key + '\n')
        self.invoke('--check')
        self.assertEqual(self.calls()[-1]['argv'], ['-O', 'check', 'desk02-agent'])

        (self.home/'.ssh/desk02.pub').unlink()
        result = self.invoke('--check')
        self.assertEqual(result.returncode, 64)
        self.assertIn('No desk', result.stderr)


if __name__ == '__main__':
    unittest.main()
