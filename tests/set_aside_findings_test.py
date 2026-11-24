#!/usr/bin/env python3
"""Findings set aside after investigation reach MMWatchdog's fleet hub only.

  MMX_BINARY=/path/to/mmx python3 tests/set_aside_findings_test.py

The triage agent writes triage_agent_notes/set_aside_findings.yml and
requests playbooks/apply_set_aside_findings.yml; util01's every_server runs
the same role, roles/set_aside_findings_on_the_fleet_hub. This file proves,
with MMX's explain of the real playbooks on a filled copy of the template:
  - the template ships the file with an empty list, which MMX needs;
  - the playbook selects util01 alone and runs only the role;
  - both run the steps in order: the candidate, MMWatchdog's check of it,
    the install, the reload, and the confirmation; every_server runs them
    after the hub's own files and restart;
  - the confirmation passes when the hub has the installed entries in
    effect, and fails, naming both lists, when it has not.
It needs Python 3, bash and jq.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = template_values.TEMPLATE
ROLE_STEPS = ['write_the_candidate_set_aside_findings', 'check_the_candidate_set_aside_findings',
              'install_the_set_aside_findings', 'reload_mmwatchdog_for_the_set_aside_findings',
              'confirm_the_set_aside_findings_in_effect',
              'put_the_installed_set_aside_findings_back_into_the_candidate']


def node_tasks(explained, stage):
    """The explained node tasks of one fleet stage, by their last path part."""
    for fleet_stage in explained['fleet_stages']:
        if fleet_stage['path'] == stage:
            return fleet_stage, [(task['path'].rsplit('/', 1)[-1], task) for task in fleet_stage['node_tasks']]
    raise AssertionError(f'no fleet stage {stage}')


def argument(task, field):
    return next(item['value'] for item in task['arguments'] if item['field'] == field)


class SetAsideFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to explain the actual MMX playbooks.')
        cls.root = template_values.filled_copy()

    def explain(self, playbook):
        result = subprocess.run([self.mmx, 'explain', playbook, '--json'], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_template_ships_the_file_with_no_entry(self):
        lines = [line for line in (T/'triage_agent_notes/set_aside_findings.yml').read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual(lines, ['set_aside_findings: []'])

    def test_the_playbook_runs_only_the_role_on_util01(self):
        result = subprocess.run([self.mmx, 'validate', 'apply_set_aside_findings'], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        explained = self.explain('apply_set_aside_findings')
        self.assertEqual(len(explained['fleet_stages']), 1)
        stage, tasks = node_tasks(explained, 'apply_set_aside_findings')
        self.assertEqual(stage['nodes'], ['util01'])
        self.assertEqual([name for name, task in tasks if task['action'] not in ('role', 'task_block')], ROLE_STEPS)
        write = dict(tasks)['write_the_candidate_set_aside_findings']
        self.assertEqual(argument(write, 'file.source'), '../../triage_agent_notes/set_aside_findings.yml')
        self.assertEqual(argument(write, 'file.path'), '/usr/local/lib/mmwatchdog/candidate_config/set_aside_findings.yml')
        install = dict(tasks)['install_the_set_aside_findings']
        self.assertEqual(argument(install, 'file.path'), '/etc/mmwatchdog/set_aside_findings.yml')

    def test_every_server_runs_the_same_steps_after_the_hub_restarted(self):
        _, tasks = node_tasks(self.explain('every_server'), 'util_server')
        names = [name for name, _ in tasks]
        steps = [name for name in names if name in ROLE_STEPS]
        self.assertEqual(steps, ROLE_STEPS)
        # The check uses the installed MMWatchdog and its candidate directory, so it follows the hub's own files.
        self.assertLess(names.index('check_that_mmwatchdog_answers'), names.index('write_the_candidate_set_aside_findings'))

    def confirm(self, installed, in_effect):
        """Runs the confirmation step's program with a stand-in mmwatchdog."""
        _, tasks = node_tasks(self.explain('apply_set_aside_findings'), 'apply_set_aside_findings')
        program = argument(dict(tasks)['confirm_the_set_aside_findings_in_effect'], 'shell.env.PROGRAM')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stand_in = root/'mmwatchdog'
            stand_in.write_text('#!/bin/bash\n'
                                f'case "$1" in validate) cat {root}/installed ;; fleet) cat {root}/in_effect ;; *) exit 9 ;; esac\n')
            stand_in.chmod(0o755)
            (root/'installed').write_text(json.dumps({'valid': True, 'config': installed}))
            (root/'in_effect').write_text(json.dumps({'set_aside_findings': in_effect}))
            return subprocess.run(['bash', '-c', program.replace('/usr/local/bin/mmwatchdog', str(stand_in))],
                                  text=True, capture_output=True)

    ENTRY = {'check': 'installed_packages/known_exploited_flaws', 'finding': 'CVE-2026-123158 openssh',
             'exact_finding': 'Debian:13 CVE-2026-123158 openssh 1:10.0p1-7+deb13u4; fixed version: none',
             'reason': 'Debian rates it unimportant.'}

    def test_the_confirmation_passes_when_the_hub_has_the_installed_entries_in_effect(self):
        listed = dict(self.ENTRY, covered_node_count=3, covered_nodes=['app001', 'db01', 'util01'],
                      matches_no_node_now=False, nodes_that_cannot_check_now=0)
        result = self.confirm({'set_aside_findings': [self.ENTRY]}, [listed])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('The fleet hub has 1 set-aside findings in effect', result.stdout)
        # No entry: MMWatchdog leaves the empty list out of its configuration.
        result = self.confirm({}, [])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_confirmation_fails_when_the_hub_has_other_entries_in_effect(self):
        result = self.confirm({'set_aside_findings': [self.ENTRY]}, [])
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r'does not have the entries of /etc/mmwatchdog/set_aside_findings.yml in effect')
        changed = dict(self.ENTRY, exact_finding=self.ENTRY['exact_finding'].replace('u4', 'u5'))
        result = self.confirm({'set_aside_findings': [self.ENTRY]}, [changed])
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
