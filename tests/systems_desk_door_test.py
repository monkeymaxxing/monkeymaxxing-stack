#!/usr/bin/env python3
"""The systems desk's SSH door, and the coding agent's publish-branch-to-main.

  MMX_BINARY=/path/to/mmx python3 tests/systems_desk_door_test.py

The door: renders the desk role's sshd files with `mmx explain` on a copy
of the template, and asks a real sshd (`sshd -T`) what each login from a
laptop gets, before and after the lock. publish-branch-to-main: runs the command
on real Git repositories, with a stand-in main copy on util01 (a bare repository).
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
FILES = T/'roles/systems_desk/files'
SSHD = shutil.which('sshd') or '/usr/sbin/sshd'
LAPTOP = '10.20.10.1'    # an allowed laptop, in private_ip_ranges.systems_desk_laptops
SERVER = '10.20.0.1'     # util01: a WireGuard address that is no laptop


def explain(settings_changes=()):
    """The desk playbook's node tasks, by name, from mmx explain."""
    mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
    if not mmx:
        raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)/'systems'
        shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
        template_values.fill_the_values_the_setup_fills(root)
        settings = root/'mmx_project_settings.yml'
        text = settings.read_text()
        for old, new in settings_changes:
            assert old in text, old
            text = text.replace(old, new)
        settings.write_text(text)
        explained = subprocess.run([mmx, 'explain', 'systems_desk', '--var', 'desk_name=desk01', '--json'],
                                   cwd=root, text=True, capture_output=True)
    if explained.returncode:
        raise AssertionError(explained.stderr)
    return [(stage['path'], task) for stage in json.loads(explained.stdout)['fleet_stages'] for task in stage['node_tasks']]


def rendered(tasks, name):
    for _, task in tasks:
        if task['path'].endswith('/' + name):
            return task['rendered_templates'][0]['text']
    raise AssertionError('no task %s' % name)


def before_the_lock_file():
    """The before-the-lock file, rendered as the desk role renders it. MMX
    does not render a template of a task whose condition reads the node, so
    the test fills in its one value, the laptops' address block."""
    text = (FILES/'sshd_root_login_before_the_lock.conf').read_text()
    reference = '{{ .inputs.systems_desk_laptop_addresses }}'
    assert text.count('{{') == 1 and reference in text, 'the file reads one value'
    return text.replace(reference, '10.20.10.0/24')


class TheDeskDoor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SSHD):
            raise unittest.SkipTest('needs sshd for sshd -T')
        cls.tasks = explain()
        cls.directory = tempfile.TemporaryDirectory()
        cls.host_key = Path(cls.directory.name)/'host_key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(cls.host_key)], check=True)
        # The desk runs Debian 13's OpenSSH, and its settings use PerSourcePenalties (OpenSSH 9.8).
        # An older sshd, such as Ubuntu 24.04's 9.6, refuses the file before it can judge a login.
        probe = Path(cls.directory.name)/'probe_sshd_config'
        probe.write_text(f'HostKey {cls.host_key}\nPerSourcePenalties no\n')
        if subprocess.run([SSHD, '-t', '-f', str(probe)], capture_output=True).returncode != 0:
            cls.directory.cleanup()
            raise unittest.SkipTest('needs OpenSSH 9.8 or later, as on Debian 13: this sshd does not know PerSourcePenalties')

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def login(self, files, user, address):
        """What sshd decides for a login of user from address, with these
        files in sshd_config.d, as sshd -T prints it: keyword -> values."""
        with tempfile.TemporaryDirectory() as temporary:
            included = Path(temporary)/'sshd_config.d'
            included.mkdir()
            for name, text in files.items():
                (included/name).write_text(text)
            main = Path(temporary)/'sshd_config'
            # Debian's own sshd_config includes the directory first, as here.
            main.write_text('Include %s/*.conf\nHostKey %s\n' % (included, self.host_key))
            shown = subprocess.run([SSHD, '-T', '-f', str(main), '-C', 'user=%s,addr=%s,host=laptop,laddr=10.20.9.1,lport=22'
                                    % (user, address)], text=True, capture_output=True)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        values = {}
        for line in shown.stdout.splitlines():
            keyword, _, value = line.partition(' ')
            values.setdefault(keyword, []).append(value)
        return values

    def locked(self, tasks=None):
        return {'00-systems-desk.conf': rendered(tasks or self.tasks, 'write_the_desk_sshd_policy')}

    def before_the_lock(self):
        return {**self.locked(), '00-systems-desk-root-login-before-the-lock.conf': before_the_lock_file()}

    def test_after_the_lock_the_person_and_the_coding_agent_need_the_key_and_a_phone_code(self):
        for user in ('alex', 'coding-agent'):
            login = self.login(self.locked(), user, LAPTOP)
            self.assertEqual(login['allowusers'], ['alex', 'coding-agent'])
            self.assertEqual(login['authenticationmethods'], ['publickey,keyboard-interactive'])

    def test_after_the_lock_root_never_logs_in_from_a_laptop(self):
        login = self.login(self.locked(), 'root', LAPTOP)
        self.assertNotIn('root', login['allowusers'])
        self.assertEqual(login['permitrootlogin'], ['no'])
        self.assertIn('root', self.login(self.locked(), 'root', '127.0.0.1')['allowusers'])

    def test_before_the_lock_root_logs_in_from_a_laptop_with_the_key_alone(self):
        login = self.login(self.before_the_lock(), 'root', LAPTOP)
        self.assertIn('root', login['allowusers'])
        self.assertEqual(login['authenticationmethods'], ['publickey'])
        # Debian's sshd prints the older name of the same value.
        self.assertIn(login['permitrootlogin'], [['prohibit-password'], ['without-password']])

    def test_before_the_lock_root_logs_in_from_no_other_address_and_the_others_keep_their_door(self):
        self.assertNotIn('root', self.login(self.before_the_lock(), 'root', SERVER)['allowusers'])
        for user in ('alex', 'coding-agent'):
            self.assertEqual(self.login(self.before_the_lock(), user, LAPTOP)['authenticationmethods'],
                             ['publickey,keyboard-interactive'])

    def test_no_desk_login_accepts_a_key_that_the_mmx_buttons_runs_can_use(self):
        # A pushed inventory can name this desk under any address. The
        # button's MMX runs as servers-mmx with the production key in the
        # agent socket; no account on the desk may accept that key.
        desk = '10.20.9.1'   # desk01's own WireGuard address
        for name, files in (('locked', self.locked()), ('before the lock', self.before_the_lock())):
            for address in ('127.0.0.1', '::1', desk, SERVER, LAPTOP):
                with self.subTest(files=name, address=address):
                    self.assertNotIn('servers-mmx', self.login(files, 'servers-mmx', address)['allowusers'])
                    root = self.login(files, 'root', address)
                    if address in ('127.0.0.1', '::1'):
                        self.assertEqual(root['allowusers'], ['root'])
                    elif not (name == 'before the lock' and address == LAPTOP):
                        self.assertNotIn('root', root['allowusers'])
                    for user in ('alex', 'coding-agent'):
                        login = self.login(files, user, address)
                        if address in ('127.0.0.1', '::1'):
                            self.assertNotIn(user, login['allowusers'])
                        else:
                            self.assertEqual(login['authenticationmethods'], ['publickey,keyboard-interactive'])
        # Root's keys: only the root-owned self-management key, every time.
        root_keys = [task for _, task in self.tasks if task['action'] == 'authorized_keys']
        self.assertEqual(len(root_keys), 3)
        for task in root_keys:
            fields = {argument['field']: argument for argument in task['arguments']}
            self.assertEqual(fields['authorized_keys.for_user_account'].get('value') or
                             fields['authorized_keys.for_user_account'].get('reference'), 'root')
            keys = [argument.get('reference') or argument.get('value') for field, argument in fields.items()
                    if field.startswith('authorized_keys.keys[')]
            self.assertEqual(len(keys), 1)
            self.assertRegex(keys[0], r'^\{\{ \.node_tasks\.(create|read)_the_root_owned_self_management_key\.public_key \}\}$')
        # The person's and coding-agent's keys: the allowed laptops' keys only.
        inventory = (template_values.filled_copy()/'inventories/servers.yml').read_text()
        production_key = inventory.split('production_ssh_public_key: ', 1)[1].split('\n', 1)[0].split()[1]
        for name in ('allow_exactly_the_allowed_laptops_ssh_keys', 'allow_the_allowed_laptops_ssh_keys_for_the_coding_agent'):
            with self.subTest(task=name):
                lines = [line for line in rendered(self.tasks, name).splitlines() if line]
                self.assertEqual(lines, ['ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIORZZg3NlYdxJ28janK/DsJ1O0O2YgF7KN2aiEPskegs alex@work-laptop'])
                self.assertNotIn(production_key, rendered(self.tasks, name))
        # The agent socket holds the production key alone; the self-management key never enters it.
        agent = rendered(self.tasks, 'install_the_persistent_ssh_agent')
        self.assertEqual([line for line in agent.splitlines() if 'ssh-add' in line and not line.startswith('#')],
                         ['ExecStartPost=/usr/bin/ssh-add /home/alex/.ssh/production_key'])
        for path in T.rglob('*'):
            if path.is_file() and 'systems_desk_self_management_key' in path.read_text(errors='replace'):
                self.assertNotIn('ssh-add', path.read_text(errors='replace'), path)

    def test_the_desks_own_server_id_is_root_owned_and_reaches_the_api_proxy(self):
        # The API proxy refuses a request other than GET that names this ID.
        task = [task for _, task in self.tasks if task['path'].endswith('/write_the_desks_own_server_id_for_the_api_proxy')][0]
        fields = {argument['field']: argument['value'] for argument in task['arguments']}
        self.assertEqual((fields['file.content'], fields['file.owner'], fields['file.group'], fields['file.path']),
                         ('4242424242\n', 'root', 'root', '/etc/systems-desk/desk-server-id'))
        name = [task for _, task in self.tasks if task['path'].endswith('/write_the_desks_own_server_name_for_the_api_proxy')][0]
        self.assertEqual({argument['field']: argument['value'] for argument in name['arguments']}['file.path'], '/etc/systems-desk/desk-server-name')
        self.assertIn('LoadCredential=desk-server-name:/etc/systems-desk/desk-server-name', (T/'roles/systems_desk/files/provider-api-proxy.service').read_text())
        self.assertIn('LoadCredential=desk-server-id:/etc/systems-desk/desk-server-id', (T/'roles/systems_desk/files/provider-api-proxy.service').read_text())

    def test_the_coding_agent_gets_the_socket_and_its_git_settings_and_no_forwarding(self):
        login = self.login(self.locked(), 'coding-agent', LAPTOP)
        self.assertEqual(login['setenv'], ['SSH_AUTH_SOCK=/run/desk-ssh-agent/socket',
                                           'GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig'])
        self.assertEqual(login['disableforwarding'], ['yes'])
        person = self.login(self.locked(), 'alex', LAPTOP)
        self.assertNotIn('setenv', person)
        self.assertEqual(person['disableforwarding'], ['no'])

    def test_the_desk_ends_the_coding_agents_unused_login_after_the_setting(self):
        self.assertEqual(self.login(self.locked(), 'coding-agent', LAPTOP)['unusedconnectiontimeout'], ['3600'])
        changed = explain([('  coding_agent_login_idle_minutes: 60\n', '  coding_agent_login_idle_minutes: 45\n')])
        self.assertEqual(self.login(self.locked(changed), 'coding-agent', LAPTOP)['unusedconnectiontimeout'], ['2700'])
        self.assertEqual(self.login(self.locked(), 'alex', LAPTOP)['unusedconnectiontimeout'], ['none'])

    def test_the_longest_login_follows_its_setting(self):
        changed = explain([('  coding_agent_login_longest_hours: 10\n', '  coding_agent_login_longest_hours: 8\n')])
        job = [task for _, task in changed if task['path'].endswith('/end_the_coding_agents_long_logins')][0]
        values = {argument['field']: argument.get('value') for argument in job['arguments']}
        self.assertEqual(str(values['systemd_scheduled_job.env.LONGEST_HOURS']), '8')

    def test_both_accounts_read_the_one_root_owned_phone_code(self):
        lines = [line.split() for line in (FILES/'sshd_pam').read_text().splitlines() if 'pam_google_authenticator' in line
                 and not line.startswith('#')]
        self.assertEqual(lines, [['auth', 'required', 'pam_google_authenticator.so', 'nullok',
                                  'secret=/etc/systems-desk/phone-code', 'user=root']])

    def test_the_desk_installs_no_coding_agent_or_terminal_of_its_own(self):
        installed = [task for _, task in self.tasks if task['action'] == 'apt_package'
                     and not any(argument['field'] == 'apt_package.state' and argument.get('value') == 'absent'
                                 for argument in task.get('arguments') or [])]
        names = {argument.get('value') for task in installed for argument in task.get('arguments') or []
                 if argument['field'].endswith('.name')}
        self.assertTrue(names & {'git', 'openssh-server'}, names)
        self.assertFalse(names & {'claude-code', 'rex'}, names)
        def values(task):
            return {argument['field']: argument.get('value') for argument in task.get('arguments') or []}
        written = [values(task).get('file.path') for _, task in self.tasks if values(task).get('file.state') != 'absent']
        self.assertNotIn('/usr/local/bin/start-the-coding-agent', written)

    def test_the_lock_refuses_without_a_phone_code_and_closes_roots_login_last(self):
        lock = [task['path'].rsplit('/', 1)[-1] for stage, task in self.tasks if stage == 'lock']
        self.assertEqual(lock[0], 'refuse_the_lock_before_the_phone_code_is_set_up')
        self.assertEqual(lock[-1], 'restart_ssh_without_the_root_login')


class PublishBranchToMain(unittest.TestCase):
    """publish-branch-to-main with its desk paths pointed at temporary ones."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name).resolve()
        self.root = root
        self.environment = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'HOME': str(root)}
        self.environment.pop('GIT_CONFIG_SYSTEM', None)
        self.socket = root/'agent.sock'  # the command exports it for Git's SSH; no test Git command uses it
        (root/'gitconfig').write_text('')
        # The main copy on util01, the desk checkout with util01 as origin, and the laptop.
        self.origin, self.desk, self.laptop = root/'origin.git', root/'systems_repository', root/'laptop'
        self.git(root, 'init', '--quiet', '--bare', '-b', 'main', str(self.origin))
        self.git(root, 'init', '--quiet', '-b', 'main', str(self.desk))
        for key, value in [('user.name', 'coding-agent on desk01'),
                           ('user.email', 'coding-agent@desk01'), ('remote.origin.url', str(self.origin)),
                           ('remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*')]:
            self.git(self.desk, 'config', key, value)
        (self.desk/'inventory.yml').write_text('servers: one\n')
        (self.desk/'settings.yml').write_text('setting: one\n')
        self.git(self.desk, 'add', '.')
        self.git(self.desk, 'commit', '--quiet', '-m', 'Start the systems repository on desk01')
        self.git(self.desk, 'push', '--quiet', '-u', 'origin', 'main')
        self.git(root, 'clone', '--quiet', str(self.desk), str(self.laptop))
        self.git(self.laptop, 'config', 'user.name', 'Alex Laptop')
        self.git(self.laptop, 'config', 'user.email', 'alex@example.com')
        # The command, with its desk paths and account pointed at this test's.
        script = (FILES/'publish-branch-to-main').read_text()
        for old, new in [('export SSH_AUTH_SOCK=/run/desk-ssh-agent/socket', 'export SSH_AUTH_SOCK=%s' % self.socket),
                         ('export GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig', 'export GIT_CONFIG_SYSTEM=%s' % (root/'gitconfig')),
                         ('repository=/home/coding-agent/systems_repository', 'repository=%s' % self.desk),
                         ('[ "$(id -un)" = coding-agent ]', '[ "$(id -un)" = "$(id -un)" ]')]:
            self.assertEqual(script.count(old), 1, old)
            script = script.replace(old, new)
        self.command = root/'publish-branch-to-main'
        self.command.write_text(script)

    def git(self, cwd, *arguments):
        environment = {**self.environment, 'SSH_AUTH_SOCK': str(self.socket), 'GIT_CONFIG_SYSTEM': str(self.root/'gitconfig')}
        result = subprocess.run(['git', *arguments], cwd=cwd, text=True, capture_output=True, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def laptop_commit(self, name, text, message, branch='work'):
        """A commit on the laptop, pushed to a branch of the desk checkout."""
        (self.laptop/name).write_text(text)
        self.git(self.laptop, 'add', name)
        self.git(self.laptop, 'commit', '--quiet', '-m', message)
        self.git(self.laptop, 'push', '--quiet', 'origin', 'HEAD:refs/heads/%s' % branch)

    def another_clone(self):
        """A clone of the main copy that stands in for util01, with a Git identity of its own."""
        other = self.root/'other'
        self.git(self.root, 'clone', '--quiet', str(self.origin), str(other))
        self.git(other, 'config', 'user.name', 'mmhotline on util01')
        self.git(other, 'config', 'user.email', 'mmhotline@util01')
        return other

    def publish_branch_to_main(self, branch='work'):
        return subprocess.run(['bash', str(self.command), branch], text=True, capture_output=True, env=self.environment)

    def published(self):
        return self.git(self.origin, 'log', '--format=%an <%ae> / %cn: %s', 'main').splitlines()

    def test_laptop_commits_are_published_with_the_laptops_author_and_no_signature(self):
        self.laptop_commit('inventory.yml', 'servers: two\n', 'Add a server')
        self.laptop_commit('settings.yml', 'setting: two\n', 'Change a setting')
        result = self.publish_branch_to_main()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.published(), ['Alex Laptop <alex@example.com> / Alex Laptop: Change a setting',
                                            'Alex Laptop <alex@example.com> / Alex Laptop: Add a server',
                                            'coding-agent on desk01 <coding-agent@desk01> / coding-agent on desk01: '
                                            'Start the systems repository on desk01'])
        self.assertIn('Published 2 commits on main', result.stdout)
        self.assertNotIn('gpgsig', self.git(self.origin, 'cat-file', 'commit', 'main'))
        self.assertEqual(self.git(self.desk, 'branch', '--list', 'work'), '', 'the branch is deleted')
        self.assertEqual(self.git(self.desk, 'rev-parse', 'main'), self.git(self.origin, 'rev-parse', 'main'))

    def test_commits_that_reached_the_main_copy_meanwhile_come_first(self):
        other = self.another_clone()
        (other/'notes.md').write_text('a note\n')
        self.git(other, 'add', 'notes.md')
        self.git(other, 'commit', '--quiet', '-m', 'A note from util01')
        self.git(other, 'push', '--quiet', 'origin', 'main')
        self.laptop_commit('inventory.yml', 'servers: two\n', 'Add a server')
        result = self.publish_branch_to_main()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([line.rsplit(': ', 1)[1] for line in self.published()],
                         ['Add a server', 'A note from util01', 'Start the systems repository on desk01'])

    def test_a_conflict_names_the_files_and_changes_nothing(self):
        other = self.another_clone()
        (other/'inventory.yml').write_text('servers: three\n')
        self.git(other, 'commit', '--quiet', '-am', 'Another server')
        self.git(other, 'push', '--quiet', 'origin', 'main')
        self.laptop_commit('inventory.yml', 'servers: two\n', 'Add a server')
        before = {name: self.git(repository, 'rev-parse', ref) for name, repository, ref in
                  [('desk main', self.desk, 'main'), ('branch', self.desk, 'work'), ('main copy', self.origin, 'main')]}
        result = self.publish_branch_to_main()
        self.assertEqual(result.returncode, 1)
        self.assertIn('stopped on a conflict in: inventory.yml', result.stderr)
        self.assertIn('Nothing changed', result.stderr)
        after = {name: self.git(repository, 'rev-parse', ref) for name, repository, ref in
                 [('desk main', self.desk, 'main'), ('branch', self.desk, 'work'), ('main copy', self.origin, 'main')]}
        self.assertEqual(after, before)
        self.assertEqual(self.git(self.desk, 'status', '--porcelain'), '')
        self.assertEqual(self.git(self.desk, 'symbolic-ref', '--short', 'HEAD').strip(), 'main')

    def test_before_util01_exists_the_desks_main_is_the_main_copy_and_nothing_is_pushed(self):
        self.git(self.desk, 'remote', 'remove', 'origin')
        self.laptop_commit('inventory.yml', 'servers: two\n', 'Add a server')
        result = self.publish_branch_to_main()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('on this desk, the main copy until util01 exists', result.stdout)
        self.assertEqual(self.git(self.desk, 'log', '--format=%s', 'main').splitlines(),
                         ['Add a server', 'Start the systems repository on desk01'])
        self.assertEqual(len(self.published()), 1, 'nothing reached the bare repository')

    def test_a_branch_that_was_not_pushed_or_main_is_refused(self):
        for branch, said in [('nothing-pushed', 'The desk has no branch nothing-pushed'), ('main', 'not main')]:
            result = self.publish_branch_to_main(branch)
            self.assertEqual(result.returncode, 1)
            self.assertIn(said, result.stderr)
        self.assertEqual(len(self.published()), 1)


if __name__ == '__main__':
    unittest.main()
