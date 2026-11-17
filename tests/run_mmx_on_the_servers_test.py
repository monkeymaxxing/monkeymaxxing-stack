#!/usr/bin/env python3
"""Check the server button's CLI boundary without a guest or credentials."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
BUTTON = TEMPLATE / 'roles/systems_desk/files/run-mmx-on-the-servers'
FETCH_PUSHED_MAIN = TEMPLATE / 'roles/systems_desk/files/fetch-pushed-main-from-the-coding-agents-checkout'


class ServersMmxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'systems_repository/.git').mkdir(parents=True)
        binary = self.root / 'bin'
        binary.mkdir()
        (binary / 'git').write_text('#!/bin/sh\ncase "$*" in *rev-parse*) echo 0123456789abcdef;; esac\n')
        (binary / 'mmx').write_text('#!/usr/bin/env python3\nimport json,os,sys\nprint(json.dumps({"args":sys.argv[1:],"vault_file":os.environ.get("MMX_VAULT_PASSWORD_FILE"),"vault_password":os.environ.get("MMX_VAULT_PASSWORD")}))\n')
        (binary / 'flock').write_text('#!/bin/sh\nexit 0\n')
        (binary / 'fetch-pushed-main').write_text('#!/bin/sh\necho 0123456789abcdef\n')
        for name in ['git', 'mmx', 'flock', 'fetch-pushed-main']:
            (binary / name).chmod(0o755)
        self.button = self.root / 'run-mmx-on-the-servers'
        self.button.write_text(BUTTON.read_text()
            .replace('/var/lib/servers-mmx', str(self.root))
            .replace('/etc/systems-desk/everyone-locked-out', str(self.root / 'everyone-locked-out'))
            .replace('export PATH=/usr/local/bin:/usr/bin:/bin', f'export PATH={binary}:/usr/bin:/bin')
            .replace('/usr/local/bin/fetch-pushed-main-from-the-coding-agents-checkout', str(binary / 'fetch-pushed-main'))
            .replace('/usr/local/bin/mmx', str(binary / 'mmx')))

    def invoke(self, *arguments):
        return subprocess.run(['bash', str(self.button), *arguments], text=True,
                              capture_output=True, env={**os.environ, 'MMX_VAULT_PASSWORD': 'CALLER_VALUE'})

    def args(self, *arguments):
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.splitlines()[-1])['args']

    def test_every_server_learns_the_lock_out_button_s_record_on_this_desk(self):
        # every_server applies a lock-out only where this equals the inventory,
        # and its undo only where it is empty (playbooks/every_server.yml, the
        # every_server stage).
        for command in ['run', 'dryrun', 'explain', 'validate', 'nodes']:
            with self.subTest(command=command):
                self.assertEqual(self.args(command, 'every_server', '--connection', 'ssh_only'),
                                 [command, '--inventory', 'servers', '--var', 'lock_out_button_record_on_this_desk=',
                                  'every_server', '--connection', 'ssh_only'])
        (self.root/'everyone-locked-out').write_text('desk01 10.20.9.1 KEY= ssh-ed25519 AAAA alex on desk01\nThe person pressed the lock-out button on this desk.\n')
        for playbook in ['every_server', 'every_server.yml', 'playbooks/every_server.yml']:
            with self.subTest(playbook=playbook):
                self.assertEqual(self.args('run', playbook)[:4], ['run', '--inventory', 'servers', '--var'])
                self.assertEqual(self.args('run', playbook)[4], 'lock_out_button_record_on_this_desk=desk01 10.20.9.1 KEY= ssh-ed25519 AAAA alex on desk01')
        # Other playbooks do not declare the variable, which MMX would refuse.
        self.assertEqual(self.args('run', 'deploy', '--var', 'app=shop'), ['run', '--inventory', 'servers', 'deploy', '--var', 'app=shop'])

    def test_the_caller_cannot_say_that_the_lock_out_button_ran(self):
        for arguments in [('run', 'every_server', '--var', 'lock_out_button_record_on_this_desk=desk01'),
                          ('run', 'every_server', '--var=lock_out_button_record_on_this_desk=desk01')]:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 64)
                self.assertIn('sets lock_out_button_record_on_this_desk itself', result.stderr)

    def test_preserves_arguments_and_supplies_vault_and_inventory(self):
        arguments = ['run', 'variable_proof', '--limit', 'app001', '--var', 'message=words with spaces']
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(value['args'], ['run', '--inventory', 'servers', *arguments[1:]])
        self.assertEqual(value['vault_file'], '/etc/systems-desk/vault-passphrase')
        self.assertIsNone(value['vault_password'])

    def test_refuses_each_vault_source_spelling(self):
        for option in ['-vault-password-file', '--vault-password-file', '-vault-password-file=/tmp/pass', '--vault-password-file=/tmp/pass']:
            with self.subTest(option=option):
                result = self.invoke('run', 'app', option, '/tmp/pass')
                self.assertEqual(result.returncode, 64)
                self.assertIn('own vault', result.stderr)

    def test_refuses_desk_playbook_and_desk_variable(self):
        for arguments in [('run', 'systems_desk'), ('explain', 'playbooks/systems_desk.yml'), ('run', 'app', '--var', 'desk_name=desk01'), ('run', 'app', '--var=desk_name=desk01')]:
            with self.subTest(arguments=arguments):
                self.assertEqual(self.invoke(*arguments).returncode, 64)

    def test_refuses_inventory_replacements(self):
        for option in ['-inventory', '--inventory']:
            for arguments in [(option, '/tmp/desk.yml'), (option+'=/tmp/desk.yml',)]:
                with self.subTest(arguments=arguments):
                    self.assertEqual(self.invoke('run', 'app', *arguments).returncode, 64)

    def test_command_delimiter_preserves_literal_command_options(self):
        result = self.invoke('run-command', '--nodes', 'app001', '--', 'printf', '--vault-password-file=literal')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])['args'][-3:], ['--', 'printf', '--vault-password-file=literal'])

    def test_refuses_the_vault_editor_and_the_passphrase_change(self):
        # mmx secrets edit opens vi on the decrypted vault, and vi's :! is a
        # shell as servers-mmx, which reads the vault passphrase file.
        for action in ['edit', 'passwd']:
            with self.subTest(action=action):
                result = self.invoke('secrets', action)
                self.assertEqual(result.returncode, 64)
                self.assertIn('secrets set, add-random, list-keys, diff-keys and usage', result.stderr)

    def test_accepts_the_vault_actions_that_show_key_names_or_take_a_value(self):
        for action in ['set', 'add-random', 'list-keys', 'diff-keys', 'usage']:
            with self.subTest(action=action):
                self.assertEqual(self.args('secrets', action)[:4], ['secrets', action, '--inventory', 'servers'])

    def test_refuses_a_vault_file_outside_the_pushed_repository(self):
        for arguments in [('secrets', 'list-keys', '--vault', '/etc/systems-desk/x'), ('secrets', 'usage', '-vault=/x'),
                          ('secrets', 'set', 'KEY', '--vault=/x'), ('secrets', 'add-random', '--new-vault-password-file', '/x'),
                          ('secrets', 'diff-keys', '-new-vault-password-file=/x')]:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 64)
                self.assertIn('vault of pushed main', result.stderr)

    def test_refuses_commands_that_open_a_pager_or_write_files_on_the_desk(self):
        # describe-module pages through less -FRX on a terminal; less's ! is a
        # shell. The others write files the button would only throw away.
        for arguments in [('describe-module', 'file'), ('init',), ('new-one-time-playbook', 'x'),
                          ('module-json', 'request'), ('secrets',), ('no-such-command',)]:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 64)
                self.assertIn('run-mmx-on-the-servers runs only', result.stderr)

    def test_local_commands_receive_no_invented_options(self):
        for arguments in [('version',), ('module-usage', '--module', 'file'), ('help',)]:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout.splitlines()[-1])['args'], list(arguments))

    def test_secrets_inventory_option_follows_the_action(self):
        result = self.invoke('secrets', 'list-keys', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])['args'], ['secrets', 'list-keys', '--inventory', 'servers', '--json'])

    def test_accepts_the_repository_inventory(self):
        self.assertEqual(self.invoke('nodes', '--inventory', 'servers').returncode, 0)



class PushedMainFromTheDeskCheckout(unittest.TestCase):
    """The button reads pushed main from the coding agent's checkout, with real Git."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull}
        self.main_copy, self.checkout = self.root / 'main_copy.git', self.root / 'checkout'
        self.git(self.root, 'init', '--quiet', '-b', 'main', str(self.checkout))
        self.commit('pushed')
        binary = self.root / 'bin'
        binary.mkdir()
        (binary / 'mmx').write_text('#!/bin/sh\ncat inventory.yml\n')
        (binary / 'flock').write_text('#!/bin/sh\nexit 0\n')
        for name in ['mmx', 'flock']:
            (binary / name).chmod(0o755)
        (self.root / 'servers-mmx').mkdir()
        self.button = self.root / 'run-mmx-on-the-servers'
        self.button.write_text(BUTTON.read_text()
            .replace('/var/lib/servers-mmx', str(self.root / 'servers-mmx'))
            .replace('/home/coding-agent/systems_repository', str(self.checkout))
            .replace('/etc/systems-desk/everyone-locked-out', str(self.root / 'everyone-locked-out'))
            .replace('export PATH=/usr/local/bin:/usr/bin:/bin', f'export PATH={binary}:/usr/bin:/bin:/usr/local/bin')
            .replace('/usr/local/bin/fetch-pushed-main-from-the-coding-agents-checkout', str(FETCH_PUSHED_MAIN))
            .replace('/usr/local/bin/mmx', str(binary / 'mmx')))

    def git(self, cwd, *arguments):
        subprocess.run(['git', '-c', 'user.name=A', '-c', 'user.email=a@example.com', '-c', 'commit.gpgsign=false', *arguments],
                       cwd=cwd, check=True, capture_output=True, env=self.environment)

    def commit(self, text):
        (self.checkout / 'inventory.yml').write_text(text + '\n')
        self.git(self.checkout, 'add', 'inventory.yml')
        self.git(self.checkout, 'commit', '--quiet', '-m', text)

    def run_the_button(self):
        result = subprocess.run(['bash', str(self.button), 'version'], text=True, capture_output=True, env=self.environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()[-1]

    def test_before_util01_exists_the_checkouts_main_is_pushed_main(self):
        self.assertEqual(self.run_the_button(), 'pushed')

    def test_with_util01_as_origin_a_commit_only_on_the_desk_is_not_pushed_main(self):
        self.git(self.root, 'init', '--quiet', '--bare', '-b', 'main', str(self.main_copy))
        self.git(self.checkout, 'remote', 'add', 'origin', str(self.main_copy))
        self.git(self.checkout, 'push', '--quiet', '-u', 'origin', 'main')
        self.commit('committed on the desk, not pushed')
        self.assertEqual(self.run_the_button(), 'pushed')


if __name__ == '__main__':
    unittest.main()
