#!/usr/bin/env python3
"""Check what the person's desk review compares and when it asks.

review-and-apply-the-systems-desk-settings runs the desk playbook as root only after the
person reviews what changed since the last desk review. These tests
build its view of the desk playbook from MMX's real explain output on a copy of
the template, change the copy the way a pushed commit would, and check
which changes the person is shown.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
loader = importlib.machinery.SourceFileLoader('desk_review', str(T/'roles/systems_desk/files/review-and-apply-the-systems-desk-settings'))
DESK_REVIEW = importlib.util.module_from_spec(importlib.util.spec_from_loader('desk_review', loader))
loader.exec_module(DESK_REVIEW)

# The inventory's connection settings, as JSON: the test needs no YAML
# library, and JSON is YAML.
CONNECTIONS = {'desk01': {'address': '127.0.0.1', 'ssh_user': 'root', 'connection': 'ssh_only',
                          'ssh_identity_file': '/root/.ssh/systems_desk_self_management_key',
                          'ssh_known_hosts': 'ssh/known_hosts', 'ssh_config': 'ssh/desk01'},
               'util01': {'address': '10.20.0.1', 'ssh_user': 'root', 'ssh_known_hosts': 'ssh/known_hosts', 'ssh_config': 'ssh/config'}}


class DeskRunView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.directory.name).resolve()/'systems'
        shutil.copytree(T, self.repository, symlinks=True)

    def tearDown(self):
        self.directory.cleanup()

    def view(self):
        explained = subprocess.run([self.mmx, 'explain', 'systems_desk', '--var', 'desk_name=desk01', '--json'],
                                   cwd=self.repository, text=True, capture_output=True)
        self.assertEqual(explained.returncode, 0, explained.stderr)
        return DESK_REVIEW.desk_run_view(self.repository, json.loads(explained.stdout), {'nodes': CONNECTIONS})

    def edit(self, name, old, new):
        path = self.repository/name
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def changed_lines(self, before, after):
        return [line for line in DESK_REVIEW.changes(before, after) if line.startswith(('+ ', '- '))]

    def test_a_pushed_root_command_in_the_desk_role_is_shown_with_its_task(self):
        before = self.view()
        self.edit('roles/systems_desk/main.yml', '  - id: keep_the_desk_clock_synchronized\n',
                  '  - id: copy_a_key\n    shell: {script: "install -m 0644 /home/alex/.ssh/production_key /home/coding-agent/k", dryrun: "true"}\n'
                  '  - id: keep_the_desk_clock_synchronized\n')
        diff = DESK_REVIEW.changes(before, self.view())
        added = [line for line in diff if line.startswith('+ ')]
        self.assertTrue(any('/home/alex/.ssh/production_key /home/coding-agent/k' in line for line in added), diff)
        self.assertIn('@@ Task systems_desk/systems_desk/copy_a_key on desk01: shell, ready', diff)
        self.assertFalse(any(line.startswith('- ') for line in diff))

    def test_unrelated_settings_comments_and_moved_lines_ask_nothing(self):
        before = self.view()
        # A deploy changes the image tags; the desk playbook does not read them.
        self.edit('inventories/servers.yml', '3f2a1c97d4e85b60a1c2d3e4f5061728394a5b6c', '0123456789abcdef0123456789abcdef01234567')
        self.edit('roles/systems_desk/main.yml', '# A person\'s systems desk.', '# A comment\n\n# A person\'s systems desk.')
        self.assertEqual(self.view(), before)

    def test_settings_the_desk_playbook_reads_and_files_it_copies_or_connects_with_are_shown(self):
        cases = [
            ('mmx_project_settings.yml', 'systems_desk_provider_api_url: https://api.hetzner.cloud/v1/',
             'systems_desk_provider_api_url: https://collector.example.com/v1/', 'collector.example.com'),
            ('roles/systems_desk/files/run-mmx-on-the-servers', '#!', '#!/bin/sh\n# added by a push\n#!', 'added by a push'),
            ('ssh/config', 'Host *\n', 'Host *\n  ProxyCommand sh -c "cat /home/alex/.ssh/production_key"\n', 'ProxyCommand sh -c'),
            ('inventories/servers.yml', 'ssh_config: ssh/desk01', 'ssh_config: ssh/desk01\n    mmx_runner_download_url: https://collector.example.com/r',
             None),
        ]
        for name, old, new, shown in cases:
            with self.subTest(name):
                before = self.view()
                self.edit(name, old, new)
                after = self.view()
                if shown is None:
                    # The inventory's connection settings come from the
                    # inventory the command reads; the test's stand-in
                    # inventory changes the same way.
                    CONNECTIONS['desk01']['mmx_runner_download_url'] = 'https://collector.example.com/r'
                    try:
                        after = self.view()
                    finally:
                        del CONNECTIONS['desk01']['mmx_runner_download_url']
                    shown = 'collector.example.com/r'
                self.assertTrue(any(shown in line for line in self.changed_lines(before, after)), name)
                self.edit(name, new, old)

    def test_adding_replacing_or_removing_a_server_shows_no_change(self):
        # The desk's peers for the servers follow the inventory through
        # update-this-desks-wireguard-peers, so a server change needs no
        # desk review, and must not make the next one show a change.
        before = self.view()
        self.edit('inventories/servers.yml', '  app001:\n',
                  '  app002:\n    address: 10.20.1.2\n    https_address: https://10.20.1.2:7443\n    ssh_user: root\n'
                  '    ssh_known_hosts: ssh/known_hosts\n    ssh_config: ssh/config\n    vars:\n'
                  '      public_ipv4_address: 203.0.113.12\n      private_ip: 10.20.1.2\n'
                  '      wireguard_public_key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n  app001:\n')
        self.edit('inventories/servers.yml', '    nodes: [app001]', '    nodes: [app001, app002]')
        with (self.repository/'ssh/known_hosts').open('a') as known_hosts:
            known_hosts.write('10.20.1.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAddedServerHostKeyAddedServerHostKeyAdded\n')
        self.assertEqual(self.view(), before)
        # Replacing a server changes its key and addresses.
        self.edit('inventories/servers.yml', 'public_ipv4_address: 203.0.113.11', 'public_ipv4_address: 203.0.113.99')
        self.assertEqual(self.view(), before)
        # Removing it takes it out of its group.
        self.edit('inventories/servers.yml', '    nodes: [app001, app002]', '    nodes: [app002]')
        self.assertEqual(self.view(), before)

    def test_a_pushed_change_to_the_lock_out_buttons_programs_is_shown(self):
        # The lock-out button runs the copies this desk review installs, so a
        # pushed change to them reaches root only through this review.
        for name in ['server_management_scripts/start_break_in_lockout.py', 'playbooks/lock_everyone_out.yml',
                     'roles/everyone_locked_out/files/end_untrusted_server_sessions', 'roles/systems_desk_lockout/main.yml']:
            with self.subTest(name):
                before = self.view()
                text = (self.repository/name).read_text()
                (self.repository/name).write_text(text + '\n# cp /home/alex/.ssh/production_key /tmp/k\n')
                changed = self.changed_lines(before, self.view())
                self.assertTrue(any('cp /home/alex/.ssh/production_key /tmp/k' in line for line in changed), name)
                (self.repository/name).write_text(text)

    def test_an_include_in_the_desk_ssh_settings_stops_the_desk_review(self):
        # An included file is outside the review: root's ssh refuses one in
        # the person's repository, and one elsewhere could change after it.
        lines = ['Include /home/coding-agent/ssh.conf', '  include ~/.ssh/extra', 'INCLUDE agent.conf',
                 'Include = "%s"' % (self.repository/'ssh/extra.conf'), 'Include\t' + str(self.repository/'ssh/*.conf')]
        for line in lines:
            with self.subTest(line):
                self.edit('ssh/config', 'Host *\n', line + '\nHost *\n')
                with self.assertRaisesRegex(DESK_REVIEW.Stop, r'ssh/config, line \d+, has an Include line'):
                    self.view()
                self.edit('ssh/config', line + '\nHost *\n', 'Host *\n')
        self.edit('ssh/config', 'Host *\n', '# Includes are refused\nHost *\n')
        self.view()

    def test_a_file_outside_the_repository_stops_the_desk_review(self):
        # MMX refuses a linked file.source, but follows a linked directory,
        # whose files could change after the review.
        outside = Path(self.directory.name)/'agent-writable'
        files = self.repository/'roles/systems_desk/files'
        shutil.move(files, outside)
        files.symlink_to(outside)
        with self.assertRaisesRegex(DESK_REVIEW.Stop, 'points outside the systems repository'):
            self.view()

    def test_control_characters_cannot_hide_a_line(self):
        before = self.view()
        self.edit('roles/systems_desk/files/run-mmx-on-the-servers', '#!', '#!/bin/sh\ncp key /tmp \x1b[1A\x1b[2K‮\n#!')
        added = self.changed_lines(before, self.view())
        self.assertTrue(any('cp key /tmp \\x1b[1A\\x1b[2K\\u202e' in line for line in added), added)
        self.assertFalse(any(re.search('[\x00-\x1f\x7f‮]', line) for line in added))


class Review(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.record = Path(self.directory.name)/'record'
        patcher = patch.object(DESK_REVIEW, 'RECORD_DIRECTORY', self.record)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.directory.cleanup)
        self.questions = []

    def review(self, view, answer):
        def ask(question):
            self.questions.append(question)
            return answer
        output = io.StringIO()
        with patch.object(DESK_REVIEW, 'ask_the_person', side_effect=ask), patch.object(os, 'chown'), contextlib.redirect_stdout(output):
            agreed = DESK_REVIEW.review(view, 'abc1234')
            if agreed:
                DESK_REVIEW.write_record(view, 'abc1234', [])
        return agreed, output.getvalue()

    def test_the_first_desk_review_asks_then_an_unchanged_one_runs_without_asking(self):
        view = ['Task a on desk01: shell, ready', '  shell.script: "true"']
        self.assertEqual(self.review(view, 'yes')[0], True)
        self.assertEqual(len(self.questions), 1)
        self.assertEqual(self.record.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.record/'desk_run_view').stat().st_mode & 0o777, 0o600)
        agreed, output = self.review(view, 'no answer is read')
        self.assertTrue(agreed)
        self.assertEqual(len(self.questions), 1)
        self.assertIn('same as at your last desk review (abc1234', output)

    def test_a_change_is_shown_and_runs_only_on_yes(self):
        old = ['Task a on desk01: shell, ready', '  shell.script: "true"']
        new = ['Task a on desk01: shell, ready', '  shell.script: "cat /home/alex/.ssh/production_key"']
        self.review(old, 'yes')
        for answer in ['', 'no', 'y']:
            agreed, output = self.review(new, answer)
            self.assertFalse(agreed)
            self.assertIn('+   shell.script: "cat /home/alex/.ssh/production_key"', output)
            self.assertEqual((self.record/'desk_run_view').read_text().split('\n'), old)
        self.assertTrue(self.review(new, 'YES')[0])
        self.assertEqual((self.record/'desk_run_view').read_text().split('\n'), new)


    def test_the_keys_the_lock_out_button_lets_in_are_shown_and_recorded(self):
        """The record is what the lock-out button compares with, so the desk review shows
        a pushed key before recording it."""
        keys = ['ssh-ed25519 AAAAone alex on desk01', 'ssh-ed25519 AAAAtwo util01, the mmhotline user']
        settings = {'vars': {'root_ssh_public_keys': keys, 'triage_ssh_public_key': 'ssh-ed25519 AAAAthree triage'}}
        old = DESK_REVIEW.lock_out_button_keys_view(settings)
        self.assertEqual(old, DESK_REVIEW.lock_out_button_keys_view({'vars': dict(settings['vars'], root_ssh_public_keys=keys[::-1])}),
                         'a reordered list is no change')
        settings['vars']['root_ssh_public_keys'] = keys + ['ssh-ed25519 AAAApushed backup key']
        new = DESK_REVIEW.lock_out_button_keys_view(settings)
        self.review(old, 'yes')
        agreed, output = self.review(new, '')
        self.assertFalse(agreed)
        self.assertIn('@@ Keys in mmx_project_settings.yml that the lock-out button lets in', output)
        self.assertIn('+   root_ssh_public_keys: ssh-ed25519 AAAApushed backup key', output)
        with patch.object(os, 'chown'):
            DESK_REVIEW.write_record([], 'abc1234', new)
        self.assertEqual(DESK_REVIEW.read_record('lock_out_button_keys_view')[0], new)


class FirstDeskReview(unittest.TestCase):
    """The bootstrap records the first desk review without a question, from
    a copy of the coding agent's checkout, with MMX's real explain output."""

    def setUp(self):
        self.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not self.mmx:
            raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name).resolve()
        environment = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull}
        checkout = root/'home/coding-agent/systems_repository'
        shutil.copytree(T, checkout, symlinks=True, ignore=shutil.ignore_patterns('.mmx', '__pycache__'))
        for arguments in (['init', '--quiet', '-b', 'main'], ['add', '--all'],
                          ['-c', 'user.name=A', '-c', 'user.email=a@example.com', '-c', 'commit.gpgsign=false',
                           'commit', '--quiet', '-m', 'Start the systems repository on desk01']):
            subprocess.run(['git', *arguments], cwd=checkout, check=True, capture_output=True, env=environment)
        (root/'repository-remote').write_text('git@github.com:example/systems.git\n')
        self.desk_copy = root/'var/lib/systems-desk/systems_repository'
        yaml = type(sys)('yaml')
        # The settings and the inventory as the review reads them: the test
        # runs on laptops without a YAML library.
        yaml.safe_load = lambda text: ({'default_inventory': 'servers', 'vars': {'root_ssh_public_keys': ['ssh-ed25519 AAAAone alex on desk01']}}
                                       if 'project_name:' in text else {'nodes': CONNECTIONS})
        for target, name, value in [(DESK_REVIEW, 'RECORD_DIRECTORY', root/'record'), (DESK_REVIEW, 'DESK_COPY', self.desk_copy),
                                    (DESK_REVIEW, 'CODING_AGENT_CHECKOUT', checkout), (DESK_REVIEW, 'MMX', self.mmx),
                                    (DESK_REVIEW, 'REPOSITORY_REMOTE', root/'repository-remote'), (DESK_REVIEW, 'GIT', 'git'),
                                    (DESK_REVIEW, 'GIT_ENVIRONMENT', environment), (os, 'geteuid', lambda: 0), (os, 'chown', lambda *a: None),
                                    (DESK_REVIEW.socket, 'gethostname', lambda: 'desk01')]:
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for patcher in (patch.dict(sys.modules, {'yaml': yaml}), patch.dict(os.environ, {'SUDO_USER': ''})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_bootstrap_records_the_first_desk_review_and_the_next_review_asks_nothing(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(DESK_REVIEW.record_the_first_desk_review(), 2)
            self.assertEqual(DESK_REVIEW.record_the_first_desk_review(), 0, 'a desk with a review records nothing new')
        remote = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=self.desk_copy, text=True, capture_output=True)
        self.assertEqual(remote.stdout.strip(), 'git@github.com:example/systems.git')
        self.assertEqual(self.desk_copy.stat().st_mode & 0o777, 0o700)
        view, _ = DESK_REVIEW.what_the_desk_playbook_does(self.desk_copy)
        self.assertTrue(any('write_the_desk_sshd_policy' in line for line in view))
        questions = []
        output = io.StringIO()
        with patch.object(DESK_REVIEW, 'ask_the_person', side_effect=questions.append), contextlib.redirect_stdout(output):
            self.assertTrue(DESK_REVIEW.review(view, 'abc1234'))
        self.assertEqual(questions, [])
        self.assertIn('same as at your last desk review', output.getvalue())

    def test_only_the_bootstrap_records_without_a_question(self):
        with patch.dict(os.environ, {'SUDO_USER': 'alex'}):
            with self.assertRaisesRegex(DESK_REVIEW.Stop, 'bootstrap'):
                DESK_REVIEW.record_the_first_desk_review()
        self.assertFalse((Path(self.directory.name)/'record').exists())


class Question(unittest.TestCase):
    def test_the_question_is_read_from_the_terminal_and_not_from_standard_input(self):
        import pty
        pid, terminal = pty.fork()
        if pid == 0:
            # Standard input is empty: only the terminal holds the answer.
            os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
            try:
                answer = DESK_REVIEW.ask_the_person('Type yes: ')
                os._exit(0 if answer == 'yes' else 1)
            except BaseException:
                os._exit(2)
        import time
        seen = b''
        deadline = time.monotonic() + 20
        while b'Type yes: ' not in seen and time.monotonic() < deadline:
            try:
                data = os.read(terminal, 1024)
            except OSError:
                break
            if not data:
                break
            seen += data
        self.assertIn(b'Type yes: ', seen)
        os.write(terminal, b'yes\r')
        status = None
        while status is None and time.monotonic() < deadline:
            done, raw = os.waitpid(pid, os.WNOHANG)
            if done:
                status = os.waitstatus_to_exitcode(raw)
                break
            import select
            if select.select([terminal], [], [], 0.2)[0]:
                try:
                    seen += os.read(terminal, 1024)
                except OSError:
                    pass
        os.close(terminal)
        if status is None:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        self.assertEqual(status, 0, seen)


if __name__ == '__main__':
    unittest.main()
