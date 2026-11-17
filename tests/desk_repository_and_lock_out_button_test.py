#!/usr/bin/env python3
"""Check the desk's repository commands without a desk.

start-the-systems-repository, the bootstrap's step, writes the desk's
production key into the settings; these tests run its edits on the
template's own files. The desk review and the lock-out button pull main
into the desk's own copy; these tests pull from a stand-in main copy.
lock-everyone-out, the lock-out button, pulls main, shows the
inventory's servers and asks for yes, and runs the reviewed copies that the
desk review installed, with only data from the pulled repository; these
tests build its run directory from a pulled repository whose lock-out
script a push changed, and check what the person sees and types.
"""
import base64
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
import types
import unittest
from unittest.mock import patch

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


SETUP = load('start_the_systems_repository', T/'roles/systems_desk/files/start-the-systems-repository')
BUTTON = load('lock_everyone_out', T/'roles/systems_desk/files/lock-everyone-out')
DESK_REVIEW = load('review_and_apply_the_systems_desk_settings', T/'roles/systems_desk/files/review-and-apply-the-systems-desk-settings')
KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGfakefakefakefakefakefakefakefakefakefakefake alex on desk01'


def root_keys(text):
    """The root_ssh_public_keys list, read as the settings write it: the
    test runs on laptops without a YAML library."""
    block = re.search(r'(?m)^  root_ssh_public_keys:.*\n((?:    - .*\n|[ \t]*#.*\n)*)', text)
    return [line[len('    - '):] for line in block.group(1).splitlines() if line.startswith('    - ')]


def desk_key(text, desk):
    node = text[text.index('\n  %s:\n' % desk):]
    return re.search(r'(?m)^\s+production_ssh_public_key: (.*)$', node).group(1)


class ProductionKeyInTheSettings(unittest.TestCase):
    def test_the_key_replaces_this_desks_example_and_keeps_the_others(self):
        text = (T/'mmx_project_settings.yml').read_text()
        changed = SETUP.set_root_ssh_public_keys(text, KEY, 'desk01')
        keys = root_keys(changed)
        self.assertEqual(keys[0], KEY)
        self.assertFalse(any(key.endswith(' on desk01') and key != KEY for key in keys), keys)
        self.assertTrue(any('util01, the mmhotline user' in key for key in keys), keys)
        # Nothing else changed.
        self.assertEqual(re.sub(r'(?ms)^  root_ssh_public_keys:.*?\n(?=\S|  \S)', '', changed),
                         re.sub(r'(?ms)^  root_ssh_public_keys:.*?\n(?=\S|  \S)', '', text))
        self.assertEqual(SETUP.set_root_ssh_public_keys(changed, KEY, 'desk01'), changed, 'a rerun changes nothing')

    def test_an_empty_list_gets_the_key(self):
        text = 'vars:\n  root_ssh_public_keys: []\n  other: 1\n'
        self.assertEqual(SETUP.set_root_ssh_public_keys(text, KEY, 'desk01'), 'vars:\n  root_ssh_public_keys:\n    - %s\n  other: 1\n' % KEY)

    def test_the_desks_own_inventory_entry_gets_the_key_and_no_other_node(self):
        text = (T/'inventories/servers.yml').read_text()
        changed = SETUP.set_desk_production_key(text, KEY, 'desk01')
        self.assertEqual(desk_key(changed, 'desk01'), KEY)
        self.assertEqual(changed.count(KEY), 1)
        with self.assertRaises(SETUP.Stop):
            SETUP.set_desk_production_key(text, KEY, 'desk02')


class BreakInButton(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.reviewed, self.repository, self.run_directory = root/'reviewed', root/'repository', root/'run'
        shutil.copytree(T, self.repository)
        # What the desk review installed.
        for path in BUTTON.REVIEWED_PATHS:
            (self.reviewed/path).parent.mkdir(parents=True, exist_ok=True)
            if (T/path).is_dir():
                shutil.copytree(T/path, self.reviewed/path)
            else:
                shutil.copy(T/path, self.reviewed/path)

    def test_a_pushed_change_to_a_lock_out_program_does_not_run(self):
        pushed = self.repository/'server_management_scripts/start_break_in_lockout.py'
        pushed.write_text(pushed.read_text() + '\nimport os; os.system("cp /home/alex/.ssh/production_key /tmp/k")\n')
        (self.repository/'roles/systems_desk_lockout/main.yml').write_text('node_tasks: []\n')
        (self.repository/'playbooks/lock_everyone_out.yml').write_text('fleet_stages: []\n')
        (self.repository/'ssh/desk01').write_text('Host *\n  ProxyCommand sh -c "cat /home/alex/.ssh/production_key"\n')
        # Data a push may change, which the button takes from the pull.
        (self.repository/'ssh/known_hosts').write_text('db09 ssh-ed25519 AAAAnew\n')
        (self.repository/'inventories/servers.yml').write_text(
            (T/'inventories/servers.yml').read_text().replace('vars:\n', 'vars:\n  everyone_locked_out_except_desk: desk01\n', 1))
        (self.repository/'external_modules').mkdir()
        (self.repository/'external_modules/evil.star').write_text('x\n')
        BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)
        for path in ['server_management_scripts/start_break_in_lockout.py', 'roles/systems_desk_lockout/main.yml',
                     'playbooks/lock_everyone_out.yml', 'ssh/desk01']:
            self.assertEqual((self.run_directory/path).read_text(), (T/path).read_text(), path)
        self.assertEqual((self.run_directory/'ssh/known_hosts').read_text(), 'db09 ssh-ed25519 AAAAnew\n')
        self.assertIn('everyone_locked_out_except_desk: desk01', (self.run_directory/'inventories/servers.yml').read_text())
        self.assertFalse((self.run_directory/'external_modules').exists())

    def test_a_pushed_change_to_what_the_lock_out_installs_on_the_servers_waits_for_a_desk_review(self):
        pushed = {
            'roles/every_server/files/wireguard_wg0.conf': '\n[Peer]\nPublicKey = AAAApushed\nAllowedIPs = 10.20.0.0/16\n',
            'roles/every_server/files/sudoers_triage': 'triage ALL=(root) NOPASSWD: ALL\n',
            'roles/util_server/files/sudoers_triage_mmwatchdog_fleet_readings': 'triage ALL=(root) NOPASSWD: ALL\n',
            'mmhotline_settings.yml': 'fleet_view_command: [/bin/sh, -c, "cp /etc/shadow /tmp"]\n',
        }
        for path, line in pushed.items():
            with open(self.repository/path, 'a') as file:
                file.write(line)
        BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)
        for path in pushed:
            self.assertEqual((self.run_directory/path).read_text(), (T/path).read_text(), path)
        self.assertEqual(BUTTON.paths_that_differ(self.repository, self.reviewed), [
            'roles/every_server/files/wireguard_wg0.conf', 'roles/every_server/files/sudoers_triage',
            'roles/util_server/files/sudoers_triage_mmwatchdog_fleet_readings', 'mmhotline_settings.yml'])
        # The person's next desk review installs the change.
        shutil.copy(self.repository/'roles/every_server/files/wireguard_wg0.conf',
                    self.reviewed/'roles/every_server/files/wireguard_wg0.conf')
        BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)
        self.assertIn('AAAApushed', (self.run_directory/'roles/every_server/files/wireguard_wg0.conf').read_text())

    def test_new_host_keys_are_not_a_difference(self):
        (self.repository/'ssh/known_hosts').write_text('db09 ssh-ed25519 AAAAnew\n')
        self.assertEqual(BUTTON.paths_that_differ(self.repository, self.reviewed), [])

    def test_a_pushed_link_out_of_the_repository_is_refused(self):
        outside = Path(self.directory.name)/'agent_writable'
        (outside/'files').mkdir(parents=True)
        shutil.rmtree(self.repository/'roles/every_server')
        (self.repository/'roles/every_server').symlink_to(outside)
        with self.assertRaisesRegex(BUTTON.Stop, 'roles/every_server in the pulled systems repository is a link to .*outside'):
            BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)
        self.assertFalse((outside/'files/wireguard_wg0.conf').exists())
        (self.repository/'roles/every_server').unlink()
        shutil.copytree(T/'roles/every_server', self.repository/'roles/every_server')
        (self.repository/'inventories/servers.yml').unlink()
        (self.repository/'inventories/servers.yml').symlink_to('/tmp/servers.yml')
        with self.assertRaisesRegex(BUTTON.Stop, 'inventories/servers.yml in the pulled systems repository is a link'):
            BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)

    def test_a_link_inside_the_repository_cannot_move_a_reviewed_copy(self):
        shutil.rmtree(self.repository/'roles/util_server')
        (self.repository/'roles/util_server').symlink_to('app_server')
        with self.assertRaisesRegex(BUTTON.Stop, 'roles/util_server in the pulled systems repository is a link, and the lock-out button'):
            BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)

    def test_the_run_history_stays_and_old_files_go(self):
        (self.run_directory/'.mmx').mkdir(parents=True)
        (self.run_directory/'.mmx/history').write_text('a run\n')
        (self.run_directory/'left_over.yml').write_text('x\n')
        BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)
        self.assertEqual((self.run_directory/'.mmx/history').read_text(), 'a run\n')
        self.assertFalse((self.run_directory/'left_over.yml').exists())

    def test_a_desk_without_reviewed_copies_is_refused(self):
        shutil.rmtree(self.reviewed/'roles/everyone_locked_out')
        with self.assertRaisesRegex(BUTTON.Stop, 'review-and-apply-the-systems-desk-settings'):
            BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)

    def test_only_reviewed_ssh_settings_connect(self):
        BUTTON.build_run_directory(self.repository, self.reviewed, self.run_directory)
        inventory = {'nodes': {'desk01': {'ssh_config': 'ssh/desk01'}, 'util01': {'ssh_config': 'ssh/config'}}}
        BUTTON.check_connection_settings(self.run_directory, inventory)
        for value in ['ssh/pushed_config', '/home/coding-agent/ssh.conf', 'ssh/known_hosts']:
            with self.subTest(value), self.assertRaisesRegex(BUTTON.Stop, 'nodes.util01.ssh_config'):
                BUTTON.check_connection_settings(self.run_directory, {'nodes': {'util01': {'ssh_config': value}}})
        (self.run_directory/'ssh/config').write_text('Include /home/alex/example_systems/ssh/more\n')
        with self.assertRaisesRegex(BUTTON.Stop, 'ssh/config, line 1, includes another file'):
            BUTTON.check_connection_settings(self.run_directory, inventory)

    def test_the_desk_role_installs_every_reviewed_copy_the_button_reads(self):
        role = (T/'roles/systems_desk/main.yml').read_text()
        installed = set(re.findall(r'/usr/local/lib/systems-desk/lock-everyone-out/([\w/.]+\.\w+)', role))
        installed |= set(re.findall(r'\{source: [\w/.]+, path: ([\w/.]+)\}', role))
        # The evidence copy is installed beside the button's copies, for its
        # reviewed SSH settings, but the button itself does not read it.
        self.assertEqual(installed - {'server_management_scripts/save_break_in_evidence.py'}, set(BUTTON.REVIEWED_PATHS))
        self.assertEqual(str(BUTTON.REVIEWED), '/usr/local/lib/systems-desk/lock-everyone-out')


def reviewed_inventory():
    """An inventory the last desk review recorded, as JSON: the
    test runs on laptops without a YAML library, and JSON is YAML."""
    def server(address, key):
        return {'address': address, 'ssh_user': 'root', 'ssh_known_hosts': 'ssh/known_hosts', 'ssh_config': 'ssh/config',
                'vars': {'public_ipv4_address': '203.0.113.%s' % address.split('.')[-1], 'private_ip': address,
                         'wireguard_public_key': key}}
    return {'vars': {'wireguard_network': '10.20.0.0/16', 'is_app_server': False,
                     'deployed_image_tags': {'production': {'shop': '3f2a1c97d4e85b60a1c2d3e4f5061728394a5b6c'}}},
            'nodes': {'desk01': {'address': '127.0.0.1', 'ssh_config': 'ssh/desk01',
                                 'vars': {'private_ip': '10.20.9.1', 'wireguard_public_key': 'desk01key='}},
                      'util01': server('10.20.0.1', 'util01key='), 'db01': server('10.20.2.1', 'db01key=')},
            'groups': {'systems_desks': {'nodes': ['desk01']}, 'util_server': {'nodes': ['util01']},
                       'database_servers': {'nodes': ['db01'], 'vars': {'is_database_server': True}}}}


def stand_in_yaml():
    """JSON is YAML, and the test runs on laptops without a YAML library."""
    module = types.ModuleType('yaml')
    module.safe_load = json.loads
    return module


class LockOutButtonShowsTheServers(unittest.TestCase):
    """The lock-out peers every server with the servers the pulled inventory
    names, so the lock-out button shows each one and asks for yes at every
    press."""

    def setUp(self):
        self.questions = []

    def press(self, inventory, desk_that_keeps_access, answer, lock_out_recorded=True):
        def ask(question):
            self.questions.append(question)
            return answer
        output = io.StringIO()
        try:
            with patch.object(DESK_REVIEW, 'ask_the_person', side_effect=ask), contextlib.redirect_stdout(output):
                BUTTON.confirm_the_servers(DESK_REVIEW, inventory, desk_that_keeps_access, lock_out_recorded)
        finally:
            self.output = output.getvalue()

    def test_each_server_is_listed_with_its_pool_and_addresses_then_the_desk_that_keeps_access(self):
        inventory = reviewed_inventory()
        inventory['nodes']['desk02'] = {'vars': {'private_ip': '10.20.9.2'}}
        inventory['groups']['systems_desks']['nodes'].append('desk02')
        self.press(inventory, 'desk01', 'yes')
        lines = self.output.split('\n')
        self.assertIn('  db01    database_servers  10.20.2.1        203.0.113.1', lines)
        self.assertIn('  util01  util_server       10.20.0.1        203.0.113.1', lines)
        self.assertFalse(any(line.startswith('  desk0') for line in lines), 'desks are not servers')
        self.assertIn('The desk that keeps access: desk01, at 10.20.9.1.', lines)
        self.assertIn('Every other desk loses access to the servers: desk02.', lines)
        self.assertEqual(self.questions, ['Type yes to lock everyone out except desk01, or press Enter to stop: '])

    def test_a_pushed_server_is_shown_and_only_yes_goes_on(self):
        inventory = reviewed_inventory()
        inventory['nodes']['db09'] = {'vars': {'private_ip': '10.20.2.9', 'public_ipv4_address': '198.51.100.66',
                                               'wireguard_public_key': 'attackerkey='}}
        inventory['groups']['database_servers']['nodes'].append('db09')
        for answer in ['', 'no', 'y']:
            with self.subTest(answer), self.assertRaisesRegex(BUTTON.Stop, '^Stopped. Nothing changed.$'):
                self.press(inventory, 'desk01', answer)
            self.assertIn('  db09    database_servers  10.20.2.9        198.51.100.66', self.output.split('\n'))
        self.press(inventory, 'desk01', 'YES')

    def test_a_server_in_no_pool_and_control_characters_are_shown_escaped(self):
        inventory = reviewed_inventory()
        inventory['nodes']['evil\x1b[2K'] = {'vars': {'private_ip': '10.20.1.9'}}
        self.press(inventory, 'desk01', 'yes')
        self.assertIn('  evil\\x1b[2K  (in no pool)', self.output)
        self.assertNotIn('\x1b', self.output)
        self.assertRegex(self.output, r'10\.20\.1\.9 +\(none\)')

    def test_the_undo_says_so_in_the_list_and_in_the_question(self):
        self.press(reviewed_inventory(), '', 'yes')
        self.assertIn('everyone_locked_out_except_desk is not set, so this press undoes the lock-out', self.output)
        self.assertEqual(self.questions, ['Type yes to undo the lock-out, or press Enter to stop: '])

    def test_with_no_lock_out_set_or_recorded_it_says_what_the_press_does_instead(self):
        self.press(reviewed_inventory(), '', 'yes', lock_out_recorded=False)
        self.assertNotIn('undoes the lock-out', self.output)
        self.assertIn('No lock-out is set or recorded on this desk, so this press only applies normal access on every server', self.output)
        self.assertEqual(self.questions, ['Type yes to apply normal access on every server again, or press Enter to stop: '])


class LockOutButtonPress(unittest.TestCase):
    """The whole lock-out button, from the pull to MMX, with stand-ins for
    the pull, the YAML library and MMX."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repository, self.reviewed = self.root/'repository', self.root/'reviewed'
        shutil.copytree(T, self.repository)
        for path in BUTTON.REVIEWED_PATHS:
            (self.reviewed/path).parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if (T/path).is_dir() else shutil.copy)(T/path, self.reviewed/path)
        self.settings = reviewed_settings()
        self.inventory = reviewed_inventory()
        self.inventory['vars']['everyone_locked_out_except_desk'] = 'desk01'
        self.events = []
        self.results = {'entries': []}
        patcher = patch.object(DESK_REVIEW, 'RECORD_DIRECTORY', self.root/'record')
        patcher.start()
        self.addCleanup(patcher.stop)
        # A lock-out pressed on this desk earlier, which the undo removes.
        (self.root/'everyone-locked-out').write_text('recorded\n')
        patcher = patch.object(BUTTON, 'LOCK_OUT_RECORD', self.root/'everyone-locked-out')
        patcher.start()
        self.addCleanup(patcher.stop)
        with patch.object(os, 'chown'):
            DESK_REVIEW.write_record([], 'abc1234', DESK_REVIEW.lock_out_button_keys_view(reviewed_settings()))
        current = os.getcwd()
        os.chdir(self.repository)
        self.addCleanup(os.chdir, current)
        patcher = patch.object(DESK_REVIEW, 'DESK_COPY', self.repository)
        patcher.start()
        self.addCleanup(patcher.stop)

    def press(self, answers, pulled=(True, 'Pulled main from the main copy on util01: your repository is at abc1234.'), mmx_exit_code=0):
        def pull(repository):
            self.events.append(('pull', repository))
            # What the pull brings: the coding agent's pushed commit.
            (repository/'mmx_project_settings.yml').write_text(json.dumps(self.settings))
            (repository/'inventories/servers.yml').write_text(json.dumps(self.inventory))
            return pulled

        def ask(question):
            self.events.append(('question', question))
            return answers.pop(0)

        def run(command, **options):
            if command[1:2] == ['results']:
                return subprocess.CompletedProcess(command, 0, json.dumps(self.results), '')
            self.events.append(('mmx', command))
            return subprocess.CompletedProcess(command, mmx_exit_code)
        output = io.StringIO()
        try:
            with patch.dict(sys.modules, {'yaml': stand_in_yaml()}), patch.dict(os.environ, {'SUDO_USER': 'alex'}), \
                    patch.object(os, 'geteuid', return_value=0), patch.object(BUTTON.subprocess, 'run', side_effect=run), \
                    patch.object(BUTTON.signal, 'signal'), patch.object(BUTTON.socket, 'gethostname', return_value='desk01'), \
                    patch.object(BUTTON, 'REVIEWED', self.reviewed), patch.object(BUTTON, 'RUN_DIRECTORY', self.root/'button-run'), \
                    patch.object(BUTTON, 'load_the_desk_review_command', return_value=DESK_REVIEW), \
                    patch.object(DESK_REVIEW, 'pull_main_into_the_desks_copy', side_effect=pull), \
                    patch.object(DESK_REVIEW, 'ask_the_person', side_effect=ask), contextlib.redirect_stdout(output):
                return BUTTON.main([])
        finally:
            self.output = output.getvalue()

    def test_the_pull_comes_first_then_the_servers_then_mmx_then_how_to_undo(self):
        self.assertEqual(self.press(['yes']), 0)
        self.assertEqual([event[0] for event in self.events], ['pull', 'question', 'mmx'])
        self.assertEqual(self.events[0][1:], (self.repository,))
        self.assertIn('lock everyone out except desk01', self.events[1][1])
        command = self.events[2][1]
        self.assertEqual(command[:3], [BUTTON.MMX, 'run', 'lock_everyone_out'])
        self.assertIn('desk_name=desk01', command)
        self.assertTrue(self.output.startswith('Pulled main from the main copy on util01'))
        self.assertTrue(self.output.rstrip().endswith('(operating_procedures/respond_to_a_break_in.md, "Undo a lock-out").'), self.output)
        self.assertIn('your coding agent removes everyone_locked_out_except_desk', self.output)

    def test_a_failed_pull_says_why_and_goes_on_with_the_repository_as_it_is(self):
        self.press(['yes'], pulled=(False, 'The pull of main from the main copy on util01 did not work '
                                           '(util01 did not answer within 30 seconds).'))
        self.assertIn('did not answer within 30 seconds). The lock-out button goes on with the desk\'s copy as it is.', self.output)
        self.assertEqual([event[0] for event in self.events], ['pull', 'question', 'mmx'])

    def test_enter_at_the_servers_question_leaves_mmx_unrun(self):
        with self.assertRaisesRegex(BUTTON.Stop, 'Stopped. Nothing changed.'):
            self.press([''])
        self.assertNotIn('mmx', [event[0] for event in self.events])

    def test_a_failed_mmx_run_is_named_last(self):
        self.assertEqual(self.press(['yes'], mmx_exit_code=1), 1)
        self.assertIn('MMX ended with exit code 1.', self.output)
        self.assertIn('a server that failed is still a way in until you isolate it at the provider', self.output)

    def test_a_failed_undo_says_the_server_is_still_locked_out_not_a_way_in(self):
        # The 2026-11-12 run: the undo failed only at util01's MMHotline step.
        del self.inventory['vars']['everyone_locked_out_except_desk']
        self.results = {'entries': [self.entry('util01', {'task': 'apply_the_mmhotline_triage_lockout', 'status': 'failed'})]}
        self.assertEqual(self.press(['yes'], mmx_exit_code=1), 1)
        self.assertIn('MMX ended with exit code 1. Read the result for every server above: a server where the undo failed '
                      'is still locked out, so util01 and the other desks cannot reach it yet.', self.output)
        self.assertTrue(self.output.rstrip().endswith('you run sudo lock-everyone-out again.'), self.output)
        self.assertNotIn('a way in', self.output)

    def test_a_failed_press_without_a_lock_out_names_no_lock_out(self):
        del self.inventory['vars']['everyone_locked_out_except_desk']
        (self.root/'everyone-locked-out').unlink()
        self.assertEqual(self.press(['yes'], mmx_exit_code=1), 1)
        self.assertIn('a server that failed did not get normal access applied again', self.output)
        self.assertNotIn('a way in', self.output)
        self.assertNotIn('locked out', self.output.split('MMX ended')[1])

    @staticmethod
    def entry(node, *tasks, status='failed'):
        return {'node': node, 'response': {'status': status, 'results': [dict(task) for task in tasks]}}

    def test_when_only_the_desks_cloudflare_session_step_failed_it_says_that_and_not_isolate_a_server(self):
        self.results = {'entries': [
            self.entry('desk01', {'task': 'stop_untrusted_work_over_ordinary_ssh', 'status': 'succeeded'}, status='succeeded'),
            self.entry('app001', {'task': 'everyone_locked_out/apply', 'status': 'succeeded'}, status='succeeded'),
            self.entry('desk01', {'task': 'record_that_the_lock_out_button_ran_on_this_desk', 'status': 'succeeded'},
                       {'task': 'revoke_cloudflare_access_sessions', 'status': 'failed', 'exit_code': 1})]}
        self.assertEqual(self.press(['yes'], mmx_exit_code=1), 1)
        self.assertIn('Every server was locked out; only the revocation of Cloudflare Access sessions on this desk failed', self.output)
        self.assertIn('revoke their sessions at Cloudflare', self.output)
        self.assertNotIn('isolate it at the provider', self.output)

    def test_a_failed_server_still_gets_the_isolate_sentence_even_beside_the_cloudflare_step(self):
        cases = {
            'a server failed': [self.entry('app001', {'task': 'everyone_locked_out/apply', 'status': 'failed'})],
            'a server failed the first lock-out': [
                self.entry('desk01', {'task': 'stop_untrusted_work_over_ordinary_ssh', 'status': 'succeeded', 'exit_code': 3},
                           status='succeeded')],
            'a server was not reached': [self.entry('db01', status='failed')],
        }
        cloudflare = self.entry('desk01', {'task': 'revoke_cloudflare_access_sessions', 'status': 'failed', 'exit_code': 1})
        for case, entries in cases.items():
            with self.subTest(case=case):
                self.results = {'entries': entries + [cloudflare]}
                self.events.clear()
                self.press(['yes'], mmx_exit_code=1)
                self.assertIn('isolate it at the provider', self.output)
                self.assertNotIn('Every server was locked out', self.output)
        self.results = 'not the results'
        self.press(['yes'], mmx_exit_code=1)
        self.assertIn('isolate it at the provider', self.output)

    def test_the_undo_asks_about_changed_keys_too_and_names_no_undo_at_the_end(self):
        del self.inventory['vars']['everyone_locked_out_except_desk']
        self.settings['vars']['root_ssh_public_keys'].append(PUSHED)
        with self.assertRaisesRegex(BUTTON.Stop, 'Stopped. Nothing changed.'):
            self.press(['yes', ''])
        self.assertEqual([event[0] for event in self.events], ['pull', 'question', 'question'])
        self.assertIn('undo the lock-out', self.events[1][1])
        self.assertIn('+ root_ssh_public_keys: backup key', self.output)
        self.events.clear()
        self.press(['yes', 'yes'])
        self.assertEqual([event[0] for event in self.events], ['pull', 'question', 'question', 'mmx'])
        self.assertNotIn('To undo the lock-out', self.output)

    def test_arguments_are_refused(self):
        with self.assertRaisesRegex(BUTTON.Stop, 'takes no arguments'):
            BUTTON.main(['--rex-session-to-keep', 'x'])


class PullIntoTheDesksCopy(unittest.TestCase):
    """The pull that the desk review and the lock-out button share, on real
    Git repositories: a bare repository stands in for the main copy on
    util01, and a clone of it for the coding agent's checkout."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.origin, self.repository, self.other = root/'origin.git', root/'desk-copy', root/'other'
        self.checkout = root/'home/coding-agent/systems_repository'
        self.run_git('init', '--quiet', '--bare', '-b', 'main', str(self.origin), cwd=root)
        self.run_git('clone', '--quiet', str(self.origin), str(self.other), cwd=root)
        self.commit('one\n', 'first')
        self.run_git('clone', '--quiet', str(self.origin), str(self.repository), cwd=root)
        self.run_git('clone', '--quiet', str(self.origin), str(self.checkout), cwd=root)
        self.commit('two\n', 'second')
        environment = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull}
        for name, value in [('GIT', 'git'), ('CODING_AGENT_CHECKOUT', self.checkout),
                            ('CODING_AGENT_GIT', ['git', '-c', 'core.hooksPath=/dev/null']),
                            ('CODING_AGENT_GIT_ENVIRONMENT', environment), ('GIT_ENVIRONMENT', environment)]:
            patcher = patch.object(DESK_REVIEW, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_git(self, *arguments, cwd):
        subprocess.run(['git', '-c', 'commit.gpgsign=false', '-c', 'user.name=A', '-c', 'user.email=a@example.com', *arguments],
                       cwd=cwd, check=True, capture_output=True, text=True, env={**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull})

    def commit(self, text, message, checkout=None):
        """A commit pushed to the stand-in main copy from another checkout."""
        checkout = checkout or self.other
        (checkout/'inventory.yml').write_text(text)
        self.run_git('add', '.', cwd=checkout)
        self.run_git('commit', '--quiet', '-m', message, cwd=checkout)
        self.run_git('push', '--quiet', 'origin', 'main', cwd=checkout)

    def test_a_pull_makes_the_copy_main_of_the_main_copy_on_util01(self):
        """The coding agent's checkout is behind util01; the pull fetches util01's main through it."""
        pulled, said = DESK_REVIEW.pull_main_into_the_desks_copy(self.repository)
        self.assertTrue(pulled, said)
        self.assertEqual((self.repository/'inventory.yml').read_text(), 'two\n')
        self.assertIn('Pulled main from the main copy on util01', said)

    def test_a_commit_only_in_the_checkout_is_not_pushed_main(self):
        (self.checkout/'inventory.yml').write_text('committed on the desk, not pushed\n')
        self.run_git('commit', '--quiet', '-am', 'not pushed', cwd=self.checkout)
        pulled, said = DESK_REVIEW.pull_main_into_the_desks_copy(self.repository)
        self.assertTrue(pulled, said)
        self.assertEqual((self.repository/'inventory.yml').read_text(), 'two\n')

    def test_before_util01_exists_the_checkouts_own_main_is_pushed_main(self):
        self.run_git('remote', 'remove', 'origin', cwd=self.checkout)
        (self.checkout/'inventory.yml').write_text('only on the desk\n')
        self.run_git('commit', '--quiet', '-am', 'the desk is the main copy', cwd=self.checkout)
        pulled, said = DESK_REVIEW.pull_main_into_the_desks_copy(self.repository)
        self.assertTrue(pulled, said)
        self.assertEqual((self.repository/'inventory.yml').read_text(), 'only on the desk\n')
        self.assertIn('the main copy until util01 exists', said)

    def test_a_change_in_the_copy_never_runs_and_the_run_history_stays(self):
        """Nobody edits the desk copy; whatever is in it, the review sees pushed main."""
        (self.repository/'inventory.yml').write_text('a change nobody pushed\n')
        (self.repository/'unpushed.yml').write_text('x\n')
        (self.repository/'.mmx').mkdir()
        (self.repository/'.mmx/history').write_text('a run\n')
        pulled, said = DESK_REVIEW.pull_main_into_the_desks_copy(self.repository)
        self.assertTrue(pulled, said)
        self.assertEqual((self.repository/'inventory.yml').read_text(), 'two\n')
        self.assertFalse((self.repository/'unpushed.yml').exists())
        self.assertEqual((self.repository/'.mmx/history').read_text(), 'a run\n')

    def test_an_unreachable_util01_stops_the_pull_and_keeps_the_copy(self):
        self.run_git('remote', 'set-url', 'origin', str(self.origin) + '-gone', cwd=self.checkout)
        pulled, said = DESK_REVIEW.pull_main_into_the_desks_copy(self.repository)
        self.assertFalse(pulled)
        self.assertTrue(said.startswith('The pull of main from the main copy on util01 did not work (git said: '), said)
        self.assertEqual((self.repository/'inventory.yml').read_text(), 'one\n')

    def test_a_desk_without_a_copy_gets_one(self):
        """A desk from an earlier Stack version ran its desk reviews in the person's checkout."""
        missing = Path(self.directory.name)/'var/lib/systems-desk/systems_repository'
        pulled, said = DESK_REVIEW.pull_main_into_the_desks_copy(missing)
        self.assertTrue(pulled, said)
        self.assertEqual((missing/'inventory.yml').read_text(), 'two\n')
        self.assertEqual(missing.stat().st_mode & 0o777, 0o700)


def public_key_line(seed, comment):
    """An OpenSSH ed25519 public key line whose key belongs to nobody."""
    blob = b''.join(len(part).to_bytes(4, 'big') + part for part in [b'ssh-ed25519', bytes([seed]) * 32])
    return 'ssh-ed25519 %s %s' % (base64.b64encode(blob).decode(), comment)


def fingerprint(line):
    """The key's fingerprint as ssh-keygen -l prints it, which the person
    compares with their own key."""
    with tempfile.NamedTemporaryFile('w', suffix='.pub') as file:
        file.write(line + '\n')
        file.flush()
        return subprocess.run(['ssh-keygen', '-l', '-f', file.name], capture_output=True, text=True, check=True).stdout.split()[1]


ALEX = public_key_line(1, 'alex on desk01')
MMHOTLINE = public_key_line(2, 'util01, the mmhotline user')
TRIAGE = public_key_line(3, 'util01, the triage agent')
PUSHED = public_key_line(4, 'backup key')


def reviewed_settings():
    return {'default_inventory': 'servers',
            'vars': {'everyone_locked_out_except_desk': '', 'root_ssh_public_keys': [ALEX, MMHOTLINE],
                     'triage_ssh_public_key': TRIAGE}}


class LockOutButtonReviewsTheKeysItLetsIn(unittest.TestCase):
    """The undo, the press after everyone_locked_out_except_desk is removed,
    installs root_ssh_public_keys and triage_ssh_public_key from the pulled
    settings on every server, so the lock-out button compares them with the keys the
    last desk review recorded."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        patcher = patch.object(DESK_REVIEW, 'RECORD_DIRECTORY', self.root/'record')
        patcher.start()
        self.addCleanup(patcher.stop)
        keys_view = DESK_REVIEW.lock_out_button_keys_view(reviewed_settings())
        with patch.object(os, 'chown'):
            DESK_REVIEW.write_record(['Task a on desk01: shell, ready'] + keys_view, 'abc1234', keys_view)
        self.questions = []

    def press(self, settings, answer, inventory=None):
        def ask(question):
            self.questions.append(question)
            return answer
        output = io.StringIO()
        try:
            with patch.object(DESK_REVIEW, 'ask_the_person', side_effect=ask), contextlib.redirect_stdout(output):
                BUTTON.review_the_keys_it_lets_in(DESK_REVIEW, settings, inventory or reviewed_inventory())
        finally:
            self.output = output.getvalue()

    def test_unchanged_keys_ask_nothing_even_reordered(self):
        settings = reviewed_settings()
        settings['vars']['root_ssh_public_keys'].reverse()
        self.press(settings, 'no answer is read')
        self.assertEqual(self.questions, [])
        self.assertIn('The keys the lock-out button lets in are the same as at your last desk review (abc1234', self.output)

    def test_a_pushed_root_key_on_the_undo_is_shown_and_enter_stops(self):
        settings = reviewed_settings()
        settings['vars']['root_ssh_public_keys'].append(PUSHED)
        with self.assertRaisesRegex(BUTTON.Stop, '^Stopped. Nothing changed.$'):
            self.press(settings, '')
        self.assertEqual(len(self.questions), 1)
        self.assertIn('+ root_ssh_public_keys: backup key, %s (ssh-ed25519)' % fingerprint(PUSHED), self.output)
        self.assertNotIn('alex on desk01', self.output, 'only the changed keys are shown')
        for answer in ['no', 'y']:
            with self.subTest(answer), self.assertRaisesRegex(BUTTON.Stop, 'Nothing changed'):
                self.press(settings, answer)
        self.press(settings, 'YES')

    def test_a_removed_key_and_a_replaced_triage_key_are_shown(self):
        settings = reviewed_settings()
        settings['vars']['root_ssh_public_keys'].remove(MMHOTLINE)
        settings['vars']['triage_ssh_public_key'] = PUSHED
        self.press(settings, 'yes')
        self.assertEqual(len(self.questions), 1)
        self.assertIn('- root_ssh_public_keys: util01, the mmhotline user, %s (ssh-ed25519)' % fingerprint(MMHOTLINE), self.output)
        self.assertIn('- triage_ssh_public_key: util01, the triage agent, %s (ssh-ed25519)' % fingerprint(TRIAGE), self.output)
        self.assertIn('+ triage_ssh_public_key: backup key, %s (ssh-ed25519)' % fingerprint(PUSHED), self.output)

    def test_key_options_and_a_line_that_is_no_key_are_shown(self):
        settings = reviewed_settings()
        settings['vars']['root_ssh_public_keys'] += ['command="/bin/sh" ' + PUSHED, 'not a key\x1b[2K']
        self.press(settings, 'yes')
        self.assertIn('+ root_ssh_public_keys: backup key, %s (ssh-ed25519), with options command="/bin/sh"'
                      % fingerprint(PUSHED), self.output)
        self.assertIn('+ root_ssh_public_keys: not an SSH public key: not a key\\x1b[2K', self.output)

    def test_the_lock_out_press_lets_in_no_settings_key_and_asks_nothing(self):
        settings = reviewed_settings()
        settings['vars']['root_ssh_public_keys'].append(PUSHED)
        inventory = reviewed_inventory()
        inventory['vars']['everyone_locked_out_except_desk'] = 'desk01'
        self.press(settings, 'no answer is read', inventory)
        self.assertEqual(self.questions, [])
        # A server whose own vars undo the switch gets the keys on that press.
        inventory['nodes']['db01']['vars']['everyone_locked_out_except_desk'] = ''
        with self.assertRaises(BUTTON.Stop):
            self.press(settings, '', inventory)
        self.assertIn('+ root_ssh_public_keys: backup key', self.output)

    def test_a_desk_without_reviewed_keys_shows_them_all_and_asks(self):
        (DESK_REVIEW.RECORD_DIRECTORY/'lock_out_button_keys_view').unlink()
        with self.assertRaises(BUTTON.Stop):
            self.press(reviewed_settings(), '')
        self.assertIn('no reviewed record of the keys the lock-out button lets in yet', self.output)
        self.assertIn('+ root_ssh_public_keys: alex on desk01, %s (ssh-ed25519)' % fingerprint(ALEX), self.output)


class LockOutButtonQuestion(unittest.TestCase):
    """The answer comes from the person's terminal, never from standard
    input, which the coding agent could fill."""

    def answer_in_a_terminal(self, typed):
        import pty
        import select
        import time
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory)/'record'
            inventory = reviewed_inventory()
            inventory['nodes']['db09'] = {'vars': {'private_ip': '10.20.2.9', 'public_ipv4_address': '198.51.100.66'}}
            pid, terminal = pty.fork()
            if pid == 0:
                # Standard input is empty: only the terminal holds the answer.
                os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
                os.environ['LINES'] = '200'
                DESK_REVIEW.RECORD_DIRECTORY = record
                try:
                    BUTTON.confirm_the_servers(DESK_REVIEW, inventory, 'desk01')
                    os._exit(0)
                except BUTTON.Stop:
                    os._exit(1)
                except BaseException:
                    os._exit(2)
            seen = b''
            deadline = time.monotonic() + 20
            while b'press Enter to stop: ' not in seen and time.monotonic() < deadline:
                try:
                    data = os.read(terminal, 1024)
                except OSError:
                    break
                if not data:
                    break
                seen += data
            self.assertIn(b'198.51.100.66', seen)
            self.assertIn(b'press Enter to stop: ', seen)
            os.write(terminal, typed)
            status = None
            while status is None and time.monotonic() < deadline:
                done, raw = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = os.waitstatus_to_exitcode(raw)
                    break
                if select.select([terminal], [], [], 0.2)[0]:
                    try:
                        seen += os.read(terminal, 1024)
                    except OSError:
                        pass
            os.close(terminal)
            if status is None:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            return status, seen.decode(errors='replace')

    def test_yes_typed_in_the_terminal_runs(self):
        status, seen = self.answer_in_a_terminal(b'yes\r')
        self.assertEqual(status, 0, seen)

    def test_enter_typed_in_the_terminal_stops(self):
        status, seen = self.answer_in_a_terminal(b'\r')
        self.assertEqual(status, 1, seen)


# Files the lock-out loads from the person's pulled repository, as data
# that runs no command:
# - the inventory: it names the desk that keeps access and today's servers, so a server
#   added since the last desk review is still locked out. The lock-out
#   button shows every server and asks for yes at each press, and refuses a
#   node whose ssh_config is not a reviewed SSH settings file.
# - mmx_project_settings.yml: MMX's project settings and the vars. MMX runs
#   no command from any of its settings, and the lock-out keeps the kept
#   desk's key and address from the desk itself, not from these vars. The
#   keys the undo lets in are compared with the desk review's record:
#   DESK_REVIEW.SETTINGS_THE_BUTTON_LETS_IN.
# - ssh/known_hosts: new servers' host keys.
PULLED_DATA = ['inventories', 'mmx_project_settings.yml', 'ssh/known_hosts']
# Project settings the lock-out reads that let nobody in, so the button does
# not compare them:
# - everyone_locked_out_except_desk: the switch itself, which the person
#   sets; a server that a pushed value undoes gets the compared keys.
# - tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers:
#   whether app servers peer with each other, among the inventory's servers,
#   which the lock-out button shows.
# - cloudflare_account_id and util01_private_page_host_names: where the
#   lock-out ends Cloudflare Access sessions. A wrong value makes that step
#   fail, which the button reports.
# mmhotline_settings.yml, a reviewed copy, renders triage_ssh_public_key
# (compared), cloudflare_account_id, util01_private_page_host_names and
# status_page_host_name; MMX's explain output names no origin for those.
SETTINGS_THAT_LET_NOBODY_IN = {'everyone_locked_out_except_desk',
                               'tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers',
                               'cloudflare_account_id', 'util01_private_page_host_names'}


class EveryFileTheLockOutLoadsIsReviewed(unittest.TestCase):
    """The list of reviewed paths can't drift: every file that MMX's own
    explain output says the lock-out loads, the playbook, its roles and
    each file a task copies or renders, and the SSH files the inventory
    connects with, is a reviewed path or pulled data. A file left out of
    REVIEWED_PATHS would come from the pulled repository, so a push could
    change what the lock-out installs on the servers."""

    def test_every_loaded_file_is_reviewed_or_pulled_data(self):
        mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not mmx:
            raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')
        loaded = set()
        settings_read = set()
        # MMX leaves the arguments of a skipped task out of its explain
        # output, so the lock-out is explained in both states: normal access,
        # which the undo applies, and everyone locked out.
        for desk_that_keeps_access in ['', 'desk01']:
            with tempfile.TemporaryDirectory() as directory:
                repository = Path(directory).resolve()/'systems'
                shutil.copytree(T, repository, symlinks=True)
                if desk_that_keeps_access:
                    inventory = repository/'inventories/servers.yml'
                    inventory.write_text(inventory.read_text().replace(
                        'vars:\n', 'vars:\n  everyone_locked_out_except_desk: %s\n' % desk_that_keeps_access, 1))
                explained = subprocess.run([mmx, 'explain', 'lock_everyone_out', '--var', 'desk_name=desk01', '--json'],
                                           cwd=repository, text=True, capture_output=True)
                self.assertEqual(explained.returncode, 0, explained.stderr)
                loaded |= loaded_files(repository, json.loads(explained.stdout))
                settings_read |= {origin['field'].split('.')[1] for stage in json.loads(explained.stdout)['fleet_stages']
                                  for task in stage['node_tasks'] for argument in task.get('arguments', [])
                                  for origin in argument.get('origins', [])
                                  if origin.get('file') == 'mmx_project_settings.yml'}
        for path in ['roles/everyone_locked_out/files/root_authorized_keys', 'roles/every_server/files/wireguard_wg0.conf',
                     'server_management_scripts/start_break_in_lockout.py', 'ssh/config', 'ssh/known_hosts']:
            self.assertIn(path, loaded, 'the explain output and the inventory name the files the lock-out loads')
        pulled = sorted(path for path in loaded if not reviewed(path) and not covered(path, PULLED_DATA))
        self.assertEqual(pulled, [], 'the lock-out loads these from the pulled repository; add them to REVIEWED_PATHS '
                                     'in lock-everyone-out and to the reviewed copies in roles/systems_desk/main.yml')
        unused = [path for path in BUTTON.REVIEWED_PATHS if not any(covered(file, [path]) for file in loaded)]
        self.assertEqual(unused, [], 'reviewed paths the lock-out no longer loads')
        self.assertIn('root_ssh_public_keys', settings_read, 'the explain output names the settings the lock-out reads')
        self.assertEqual(sorted(settings_read - set(DESK_REVIEW.SETTINGS_THE_BUTTON_LETS_IN) - SETTINGS_THAT_LET_NOBODY_IN), [],
                         'the lock-out reads these project settings; add each one it installs as a key or an address to '
                         'SETTINGS_THE_BUTTON_LETS_IN in review-and-apply-the-systems-desk-settings, or the others to SETTINGS_THAT_LET_NOBODY_IN')


class EveryPressFirstChecksThatThisDeskKeepsItsAccess(unittest.TestCase):
    """Seen on test servers: an undo that installs keys without this
    desk's own cuts this desk off partway, with the servers still locked.
    So the first fleet stage of every press, the lock-out and the undo, runs
    the check of tests/break_in_response_test.py on this desk, and stops the
    run (on_node_failure: stop_run) before any fleet stage that changes a server."""

    def test_the_check_runs_first_in_the_lock_out_and_in_the_undo(self):
        mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not mmx:
            raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')
        playbook = (T/'playbooks/lock_everyone_out.yml').read_text()
        first_stage = playbook.split('\n  - id: ')[1]
        self.assertTrue(first_stage.startswith('verify_the_persons_own_desk\n'))
        self.assertIn('on_node_failure: stop_run', first_stage)
        for desk_that_keeps_access in ['', 'desk01']:
            with self.subTest(desk_that_keeps_access=desk_that_keeps_access or 'the undo'), \
                 tempfile.TemporaryDirectory() as directory:
                repository = Path(directory).resolve()/'systems'
                shutil.copytree(T, repository, symlinks=True)
                if desk_that_keeps_access:
                    inventory = repository/'inventories/servers.yml'
                    inventory.write_text(inventory.read_text().replace(
                        'vars:\n', 'vars:\n  everyone_locked_out_except_desk: %s\n' % desk_that_keeps_access, 1))
                explained = subprocess.run([mmx, 'explain', 'lock_everyone_out', '--var', 'desk_name=desk01', '--json'],
                                           cwd=repository, text=True, capture_output=True, stdin=subprocess.DEVNULL)
                self.assertEqual(explained.returncode, 0, explained.stderr)
                stage = json.loads(explained.stdout)['fleet_stages'][0]
                self.assertEqual((stage['path'], stage['nodes']), ('verify_the_persons_own_desk', ['desk01']))
                checks = [task for task in stage['node_tasks'] if task['action'] == 'shell' and task['status'] == 'ready'
                          and any('start_break_in_lockout.py --check-only' in str(argument.get('value'))
                                  for argument in task.get('arguments', []))]
                self.assertEqual(len(checks), 1, 'the first stage runs the check, in both states')
                values = {argument['field']: argument.get('value') for argument in checks[0]['arguments']}
                self.assertEqual(values.get('shell.env.DESK_THAT_KEEPS_ACCESS'), 'desk01', 'the check is about the desk that runs the press')


def covered(path, paths):
    return any(path == other or path.startswith(other + '/') for other in paths)


def reviewed(path):
    return covered(path, BUTTON.REVIEWED_PATHS) and not covered(path, BUTTON.PULLED_DATA_IN_REVIEWED_PATHS)


def loaded_files(repository, explain):
    """Every repository file the explained run reads: each task's playbook
    or role file, each file a value comes from, each file an argument names,
    such as file.source, file.template or wireguard_interface.template, and
    the SSH files the inventory names. A relative name is found beside the
    task's own file first, then at the repository's top, as MMX resolves it."""
    files = set()

    def add(candidate):
        if candidate.exists():
            files.add(os.path.relpath(candidate.resolve(), repository))
            return True
        return False

    for stage in explain['fleet_stages']:
        files.add(stage['source']['file'])
        for task in stage['node_tasks']:
            files.add(task['source']['file'])
            base = (repository/task['source']['file']).parent
            for argument in task.get('arguments', []):
                files.update(origin['file'] for origin in argument.get('origins', []) if 'file' in origin)
                if 'file' in argument.get('source', {}):
                    files.add(argument['source']['file'])
                value, last = argument.get('value'), argument['field'].rsplit('.', 1)[-1]
                if not isinstance(value, str) or not any(word in last for word in ('source', 'template', 'file')):
                    continue
                if value and not value.startswith('/') and '\n' not in value:
                    add(base/value) or add(repository/value)
    # The inventory's connection files, read as text: the test runs on
    # laptops without a YAML library.
    for inventory in (repository/'inventories').glob('*.yml'):
        for value in re.findall(r'(?m)^\s+(?:ssh_config|ssh_known_hosts|ssh_identity_file): *(\S+)', inventory.read_text()):
            if not value.startswith('/'):
                add(repository/value)
    return files

if __name__ == '__main__':
    unittest.main()
