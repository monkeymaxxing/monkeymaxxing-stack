#!/usr/bin/env python3
"""start-a-desk-job: which runs the coding agent may leave running after its
login ends, and how the job records its end.

  python3 tests/desk_jobs_test.py

Runs the command with a stand-in systemd-run that records what it was asked
to start. The stand-in desk run proves the real unit (docs/testing.md).
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
COMMAND = T/'roles/systems_desk/files/start-a-desk-job'


class DeskJobs(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.runs = self.root/'runs'
        self.runs.mkdir()
        binary = self.root/'bin'
        binary.mkdir()
        self.started = self.root/'started.json'
        (binary/'systemd-run').write_text('#!/usr/bin/env python3\nimport json,sys\n'
                                          'open(%r,"w").write(json.dumps(sys.argv[1:]))\n' % str(self.started))
        (binary/'id').write_text('#!/bin/sh\n[ "$1" = -u ] && echo "${FAKE_UID:-1002}"\n')
        for name in ('systemd-run', 'id'):
            (binary/name).chmod(0o755)
        text = COMMAND.read_text()
        for old, new in (('export PATH=/usr/local/bin:/usr/bin:/bin', f'export PATH={binary}:/usr/bin:/bin'),
                         ('runs=/home/coding-agent/runs', f'runs={self.runs}'),
                         ('{{ .inputs.coding_agent_login_longest_hours }}', '10')):
            self.assertIn(old, text)
            text = text.replace(old, new)
        self.command = self.root/'start-a-desk-job'
        self.command.write_text(text)

    def invoke(self, *arguments, **env):
        return subprocess.run(['bash', str(self.command), *arguments], text=True, capture_output=True,
                              env={**os.environ, **env})

    def started_unit(self, *arguments):
        result = self.invoke(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(self.started.read_text())
        options, program = argv[:argv.index('--')], argv[argv.index('--') + 1:]
        return options, program

    def test_the_button_runs_as_servers_mmx_in_a_unit_that_ends_after_the_longest_login(self):
        options, program = self.started_unit('every-server-1', '--', 'run-mmx-on-the-servers',
                                             'run', 'every_server', '--connection', 'ssh_only')
        self.assertIn('--unit=desk-job-every-server-1', options)
        self.assertIn('--uid=coding-agent', options)
        self.assertIn('--property=RuntimeMaxSec=10h', options)
        self.assertIn('--property=ExecStopPost=/usr/local/bin/start-a-desk-job --record-the-end every-server-1', options)
        self.assertEqual(program, ['/usr/local/bin/start-a-desk-job', '--run-the-job', 'every-server-1',
                                   'sudo', '-n', '-u', 'servers-mmx', '/usr/local/bin/run-mmx-on-the-servers',
                                   'run', 'every_server', '--connection', 'ssh_only'])

    def test_the_util01_helper_and_publishing_run_as_the_coding_agent(self):
        _, program = self.started_unit('deploy-1', '--', 'run_mmx_on_util01', 'run', 'deploy', '--var', 'environment_name=production')
        self.assertEqual(program[3:], ['/home/coding-agent/systems_repository/server_management_scripts/run_mmx_on_util01',
                                       'run', 'deploy', '--var', 'environment_name=production'])
        _, program = self.started_unit('publish-1', '--', 'publish-branch-to-main', 'add-app002')
        self.assertEqual(program[3:], ['/usr/local/bin/publish-branch-to-main', 'add-app002'])

    def test_anything_else_is_refused_and_nothing_starts(self):
        refused = [
            ['job', '--', 'sh', '-c', 'curl https://example.com'],
            ['job', '--', 'ssh', '-R', '9000:127.0.0.1:22', 'outside.example'],
            ['job', '--', '/usr/local/bin/run-mmx-on-the-servers', 'run', 'every_server'],
            ['job', '--', '../run-mmx-on-the-servers', 'run', 'every_server'],
            ['job', '--', 'run-mmx-on-the-servers'],
            ['job', '--', 'run-mmx-on-the-servers', '--inventory', 'other', 'run', 'every_server'],
            ['job', '--', 'run-mmx-on-the-servers', 'secrets', 'edit'],
            ['job', '--', 'run_mmx_on_util01', 'results'],
            ['job', '--', 'publish-branch-to-main'],
            ['job', '--', 'publish-branch-to-main', 'add-app002', 'more'],
            ['job', '--', 'publish-branch-to-main', '--exec=sh'],
            ['--', 'job', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['job', 'run-mmx-on-the-servers', '--', 'run', 'every_server'],
            ['job', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['job', 'extra', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['../job', '--', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['a/b', '--', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['..', '--', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['-job', '--', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['Job', '--', 'run-mmx-on-the-servers', 'run', 'every_server'],
            ['job.service', '--', 'run-mmx-on-the-servers', 'run', 'every_server'],
            [],
        ]
        for arguments in refused:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 64, result.stderr)
                self.assertIn('Nothing started.', result.stderr)
                self.assertFalse(self.started.exists())

    def test_a_name_that_already_ran_is_refused(self):
        (self.runs/'done.exit').write_text('0\n')
        (self.runs/'linked.log').symlink_to('/nonexistent/target')
        for name in ('done', 'linked'):
            with self.subTest(name=name):
                result = self.invoke(name, '--', 'publish-branch-to-main', 'add-app002')
                self.assertEqual(result.returncode, 64)
                self.assertIn('already ran', result.stderr)
                self.assertFalse(self.started.exists())

    def test_the_job_writes_its_log_and_its_exit_code_or_why_the_desk_stopped_it(self):
        result = self.invoke('--run-the-job', 'one', 'sh', '-c', 'echo working; echo trouble >&2; exit 3')
        self.assertEqual(result.returncode, 3)
        self.assertEqual((self.runs/'one.log').read_text(), 'working\ntrouble\n')
        self.invoke('--record-the-end', 'one', EXIT_CODE='exited', EXIT_STATUS='3', SERVICE_RESULT='exit-code')
        self.assertEqual((self.runs/'one.exit').read_text(), '3\n')
        self.invoke('--record-the-end', 'two', EXIT_CODE='killed', EXIT_STATUS='TERM', SERVICE_RESULT='timeout')
        self.assertTrue((self.runs/'two.exit').read_text().startswith('stopped: '))
        self.assertIn('10 hours', (self.runs/'two.exit').read_text())

    def test_the_jobs_own_steps_refuse_to_run_as_root(self):
        for arguments in (['--run-the-job', 'x', 'id'], ['--record-the-end', 'x']):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments, FAKE_UID='0')
                self.assertEqual(result.returncode, 64)
                self.assertEqual(list(self.runs.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
