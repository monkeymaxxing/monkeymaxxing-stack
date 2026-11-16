#!/usr/bin/env python3
"""The coding agent that systems_desk_coding_agent picks on a systems desk.

  MMX_BINARY=/path/to/mmx python3 tests/systems_desk_coding_agent_test.py

Reads `mmx explain systems_desk` on a copy of the template with each value
of the setting, and runs the rendered start-the-coding-agent with stand-in
id, sudo and coding agent programs.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


class SystemsDeskCodingAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')

    def tasks(self, value):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            settings = root/'mmx_project_settings.yml'
            text = settings.read_text()
            self.assertIn('  systems_desk_coding_agent: claude_code\n', text)
            settings.write_text(text.replace('  systems_desk_coding_agent: claude_code\n', '  systems_desk_coding_agent: %s\n' % value))
            explained = subprocess.run([self.mmx, 'explain', 'systems_desk', '--var', 'desk_name=desk01', '--json'],
                                       cwd=root, text=True, capture_output=True)
            self.assertEqual(explained.returncode, 0, explained.stderr)
        return {task['path'].rsplit('/', 1)[-1]: task for stage in json.loads(explained.stdout)['fleet_stages']
                for task in stage['node_tasks']}

    def test_rootless_podman_for_the_coding_agent_can_start_a_container(self):
        """Seen on a real desk: no passt ("could not find pasta") and no user session
        ("sd-bus call: Permission denied") made every container and every
        podman build RUN step fail for coding-agent."""
        tasks = self.tasks('claude_code')
        packages = {package['name'] for argument in tasks['install_the_desk_packages']['arguments']
                    if argument['field'] == 'apt_package.packages' for package in argument['value']}
        self.assertIn('podman', packages)
        self.assertIn('passt', packages)
        # Debian's podman only Recommends aardvark-dns; without it a
        # container on a podman network resolves no names (a test database, a module proxy).
        self.assertIn('aardvark-dns', packages)
        linger = tasks['keep_the_coding_agents_user_session_running']
        shown = json.dumps(linger)
        self.assertIn('loginctl enable-linger coding-agent', shown)
        self.assertIn('/var/lib/systemd/linger/coding-agent', shown)
        order = list(tasks)
        self.assertGreater(order.index('keep_the_coding_agents_user_session_running'), order.index('create_the_coding_agent_account'))

    def launcher(self, tasks):
        return tasks['install_the_command_that_starts_the_coding_agent']['rendered_templates'][0]['text']

    def run_launcher(self, text, user):
        """Run the launcher with stand-ins; returns what each stand-in was asked."""
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            directory = Path(temporary)
            (directory/'home/systems_repository').mkdir(parents=True)
            stand_ins = {'id': 'echo %s' % user, 'sudo': 'echo "sudo $*"', 'claude': 'echo "claude in $PWD: $*"',
                         'codex': 'echo "codex in $PWD: $*"'}
            for name, body in stand_ins.items():
                (directory/name).write_text('#!/bin/bash\n%s\n' % body)
                (directory/name).chmod(0o755)
            (directory/'launcher').write_text(text)
            result = subprocess.run(['bash', str(directory/'launcher'), '--resume', 'two words'], text=True, capture_output=True,
                                    env={'PATH': '%s:/usr/bin:/bin' % directory, 'HOME': str(directory/'home')})
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.replace(str(directory/'home'), '~')

    def test_claude_code_is_installed_and_started_by_default(self):
        tasks = self.tasks('claude_code')
        self.assertEqual(tasks['install_claude_code_for_the_coding_agent']['status'], 'ready')
        self.assertEqual(tasks['install_codex_for_the_coding_agent']['status'], 'skipped')
        text = self.launcher(tasks)
        self.assertEqual(self.run_launcher(text, 'coding-agent'), 'claude in ~/systems_repository: --resume two words\n')
        self.assertEqual(self.run_launcher(text, 'alex'),
                         'sudo -u coding-agent -i /usr/local/bin/start-the-coding-agent --resume two words\n')

    def test_codex_is_installed_from_the_pinned_release_and_started(self):
        tasks = self.tasks('codex')
        self.assertEqual(tasks['install_claude_code_for_the_coding_agent']['status'], 'skipped')
        self.assertEqual(tasks['add_the_claude_code_apt_repository']['status'], 'skipped')
        self.assertEqual(tasks['unpack_the_codex_release']['status'], 'ready')
        self.assertEqual(self.run_launcher(self.launcher(tasks), 'coding-agent'), 'codex in ~/systems_repository: --resume two words\n')

    def test_each_login_gets_its_own_ssh_agent_so_the_persons_plain_git_commit_signs(self):
        """/etc/profile.d/desk-buttons.sh, as the desk review renders it: the
        person alex gets the agent that holds the production key, which Git's
        SSH signing reads only from SSH_AUTH_SOCK; the coding agent its relay."""
        profile = self.tasks('claude_code')['install_the_login_profile_with_each_accounts_ssh_agent']['rendered_templates'][0]['text']
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            directory = Path(temporary)
            (directory/'profile.sh').write_text(profile)
            seen = {}
            for user in ['alex', 'coding-agent', 'sam']:
                (directory/'id').write_text('#!/bin/sh\necho %s\n' % user)
                (directory/'id').chmod(0o755)
                result = subprocess.run(['sh', '-c', '. "$1"; echo "${SSH_AUTH_SOCK:-none} ${GIT_CONFIG_SYSTEM:-none}"', 'sh',
                                         str(directory/'profile.sh')], text=True, capture_output=True,
                                        env={'PATH': '%s:/usr/bin:/bin' % directory})
                self.assertEqual(result.returncode, 0, result.stderr)
                seen[user] = result.stdout.strip()
        self.assertEqual(seen, {'alex': '/run/desk-ssh-agent/private.sock none',
                                'coding-agent': '/run/desk-ssh-agent/socket /etc/systems-desk/coding-agent-gitconfig',
                                'sam': 'none none'})

    def test_any_other_value_is_refused_before_any_change(self):
        role = (T/'roles/systems_desk/main.yml').read_text()
        check = role[role.index('  - id: check_the_systems_desk_coding_agent_setting'):]
        check = check[:check.index('\n  - id: ', 1)]
        self.assertIn('{equals: ["{{ .inputs.systems_desk_coding_agent }}", claude_code]}', check)
        self.assertIn('{equals: ["{{ .inputs.systems_desk_coding_agent }}", codex]}', check)
        self.assertEqual(role.index('  - id: check_the_systems_desk_coding_agent_setting'), role.index('node_tasks:\n') + len('node_tasks:\n'))


if __name__ == '__main__':
    unittest.main()
