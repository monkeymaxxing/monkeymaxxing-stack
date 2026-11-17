#!/usr/bin/env python3
"""The team's main copy of the systems repository on util01.

Runs the util_server role's own script, as `mmx explain every_server`
renders it, to make the bare repository in a temporary directory, then
pushes to it with real Git: main only grows (no force push, no branch
deletion), each change to main is logged, and MMHotline's clone step skips
an empty main copy instead of failing. Needs MMX on PATH or MMX_BINARY.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'


def util01_tasks():
    mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
    if not mmx:
        raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')
    explained = subprocess.run([mmx, 'explain', 'every_server', '--json'], cwd=TEMPLATE, text=True, capture_output=True, check=True)
    tasks = {}

    def walk(value):
        if isinstance(value, dict):
            if value.get('node') == 'util01' and 'path' in value and 'arguments' in value:
                tasks[value['path'].rsplit('/', 1)[1]] = {argument['field']: argument.get('value') for argument in value['arguments']}
            for inner in value.values():
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)
    walk(json.loads(explained.stdout))
    return tasks


class TheMainCopy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = util01_tasks()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.environment = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
        create = self.tasks['create_the_main_copy_of_the_systems_repository']
        self.assertEqual(create['shell.skip_if_this_path_exists'], create['shell.env.MAIN_COPY'])
        self.main_copy = self.root/'systems_repository.git'
        subprocess.run(['bash', '-c', create['shell.script']], check=True,
                       env={**self.environment, 'MAIN_COPY': str(self.main_copy)})
        self.desk = self.root/'desk'
        self.git(self.root, 'init', '--quiet', '-b', 'main', str(self.desk))
        self.commit('one')
        self.git(self.desk, 'remote', 'add', 'origin', str(self.main_copy))

    def git(self, cwd, *arguments, check=True):
        result = subprocess.run(['git', '-c', 'user.name=A', '-c', 'user.email=a@example.com', '-c', 'commit.gpgsign=false',
                                 *arguments], cwd=cwd, text=True, capture_output=True, env=self.environment)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def commit(self, text):
        (self.desk/'inventory.yml').write_text(text + '\n')
        self.git(self.desk, 'add', 'inventory.yml')
        self.git(self.desk, 'commit', '--quiet', '-m', text)

    def test_the_main_copy_is_closed_to_other_users(self):
        self.assertEqual(self.main_copy.stat().st_mode & 0o777, 0o700)

    def test_mmhotlines_clone_waits_for_the_first_push_and_reaches_the_main_copy_on_util01_itself(self):
        clone = self.tasks['clone_mmhotline_copy_of_the_systems_repository']
        self.assertEqual(clone['shell.env.SYSTEMS_REPOSITORY_SSH_URL'], 'root@127.0.0.1:' + self.tasks[
            'create_the_main_copy_of_the_systems_repository']['shell.env.MAIN_COPY'])
        # MMX explain leaves out guards, so the guard comes from the role's text.
        role = (TEMPLATE/'roles/util_server/main.yml').read_text().split('id: clone_mmhotline_copy_of_the_systems_repository', 1)[1]
        guard = re.search(r'run_only_if_this_command_succeeds:\n\s+script: (.*)\n', role).group(1)
        false_exit_codes = json.loads(re.search(r'false_exit_codes: (\[.*\])', role).group(1))
        empty = subprocess.run(['bash', '-c', guard], env={**self.environment, 'SYSTEMS_REPOSITORY_SSH_URL': str(self.main_copy)})
        self.assertIn(empty.returncode, false_exit_codes, 'an empty main copy skips the clone')
        self.git(self.desk, 'push', '--quiet', '-u', 'origin', 'main')
        pushed = subprocess.run(['bash', '-c', guard], env={**self.environment, 'SYSTEMS_REPOSITORY_SSH_URL': str(self.main_copy)})
        self.assertEqual(pushed.returncode, 0)

    def test_main_only_grows_and_each_change_is_logged(self):
        self.git(self.desk, 'push', '--quiet', '-u', 'origin', 'main')
        self.commit('two')
        self.git(self.desk, 'push', '--quiet', 'origin', 'main')
        self.git(self.desk, 'reset', '--quiet', '--hard', 'HEAD~1')
        self.commit('rewritten')
        refused = self.git(self.desk, 'push', '--quiet', '--force', 'origin', 'main', check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('non-fast-forward', refused.stderr)
        deleted = self.git(self.desk, 'push', '--quiet', 'origin', ':main', check=False)
        self.assertNotEqual(deleted.returncode, 0)
        reflog = self.git(self.main_copy, 'reflog', 'show', '--format=%gs', 'refs/heads/main').stdout.splitlines()
        self.assertEqual(len(reflog), 2, reflog)


if __name__ == '__main__':
    unittest.main()
