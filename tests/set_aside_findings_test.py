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
    the install, and the step that puts the entries into effect;
    every_server runs them after the hub's own files and restart;
  - that step reloads the hub whenever the entries in effect differ from
    the installed file's, also when the install changed nothing, so a
    failed reload heals at the next run; it fails, naming both lists, when
    a reload does not bring them into effect, and when the hub or either
    listing does not answer;
  - its dryrun reloads nothing, and passes on a hub whose MMWatchdog does
    not have set-aside findings yet, as in the preview of an upgrade.
It needs Python 3, bash and jq.
"""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = template_values.TEMPLATE
ROLE_STEPS = ['write_the_candidate_set_aside_findings', 'check_the_candidate_set_aside_findings',
              'install_the_set_aside_findings', 'put_the_set_aside_findings_into_effect',
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

    def put_into_effect(self, installed, in_effect, dryrun=False, fleet_answers=True, knows_set_aside_findings=True,
                        reload_takes_effect=True):
        """Runs the step that puts the entries into effect, or its dryrun, with a stand-in mmwatchdog and hub socket.

        Returns the result and the stand-in's calls, one line each."""
        _, tasks = node_tasks(self.explain('apply_set_aside_findings'), 'apply_set_aside_findings')
        task = dict(tasks)['put_the_set_aside_findings_into_effect']
        program = argument(task, 'shell.env.PROGRAM')
        command = argument(task, 'shell.dryrun' if dryrun else 'shell.script')
        # A short directory: a Unix socket path has a length limit.
        root = Path(tempfile.mkdtemp(prefix='sa', dir='/tmp'))
        self.addCleanup(shutil.rmtree, root, True)
        stand_in = root/'mmwatchdog'
        help_line = '  mmwatchdog fleet set-aside-findings [--json]' if knows_set_aside_findings else ''
        stand_in.write_text('#!/bin/bash\n'
                            f'echo "$*" >> {root}/calls\n'
                            'case "$1" in\n'
                            f'  --help) echo "  mmwatchdog fleet findings CHECK_GROUP/CHECK"; echo "{help_line}" ;;\n'
                            f'  validate) cat {root}/installed ;;\n'
                            f'  fleet) {"cat " + str(root/"in_effect") if fleet_answers else "echo no hub >&2; exit 4"} ;;\n'
                            f'  reload) {"cp " + str(root/"after_reload") + " " + str(root/"in_effect") if reload_takes_effect else "true"} ;;\n'
                            '  *) exit 9 ;;\n'
                            'esac\n')
        stand_in.chmod(0o755)
        socket_path = root/'hub.sock'
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(socket_path))
        self.addCleanup(listener.close)
        (root/'installed').write_text(json.dumps({'valid': True, 'config': installed}))
        (root/'in_effect').write_text(json.dumps({'set_aside_findings': in_effect}))
        listed = [dict(entry, covered_node_count=0, covered_nodes=[], matches_no_node_now=True, nodes_that_cannot_check_now=0)
                  for entry in installed.get('set_aside_findings', [])]
        (root/'after_reload').write_text(json.dumps({'set_aside_findings': listed}))
        replace = lambda text: text.replace('/usr/local/bin/mmwatchdog', str(stand_in)).replace(
            '/run/mmwatchdog/mmwatchdog.sock', str(socket_path))
        result = subprocess.run(['bash', '-c', replace(command)], env=dict(os.environ, PROGRAM=replace(program)),
                                text=True, capture_output=True)
        calls = (root/'calls').read_text().splitlines() if (root/'calls').exists() else []
        return result, calls

    ENTRY = {'check': 'installed_packages/known_exploited_flaws', 'finding': 'CVE-2026-123158 openssh',
             'exact_finding': 'Debian:13 CVE-2026-123158 openssh 1:10.0p1-7+deb13u4; fixed version: none',
             'reason': 'Debian rates it unimportant.',
             'investigation_note': 'docs/investigations/2026-11-23-openssh.md', 'set_aside_by': 'Matt',
             'set_aside_on': '2026-11-23'}

    def listed(self, entry):
        return dict(entry, covered_node_count=3, covered_nodes=['app001', 'db01', 'util01'],
                    matches_no_node_now=False, nodes_that_cannot_check_now=0)

    def test_an_entry_for_routine_security_updates_is_refused_before_anything_goes_live(self):
        _, tasks = node_tasks(self.explain('apply_set_aside_findings'), 'apply_set_aside_findings')
        names = [name for name, _ in tasks]
        check = 'check_the_candidate_set_aside_findings'
        self.assertLess(names.index(check), names.index('install_the_set_aside_findings'))
        program = argument(dict(tasks)[check], 'shell.env.PROGRAM')
        root = Path(tempfile.mkdtemp(prefix='sa', dir='/tmp'))
        self.addCleanup(shutil.rmtree, root, True)
        # MMWatchdog's own parse is what the step reads (block, quoted-key, flow and folded spellings all reach
        # .config.set_aside_findings[].check, checked against the real binary), so a stand-in prints that parse as validate --json does.
        stand_in = root/'mmwatchdog'
        stand_in.write_text(f'#!/bin/bash\ncat {root}/answer\nexit $(cat {root}/code)\n')
        stand_in.chmod(0o755)
        program = program.replace('/usr/local/bin/mmwatchdog', str(stand_in))
        routine = 'security_updates/no_security_update_waits'
        other = dict(self.ENTRY, reason=f'Not for {routine}.\ncheck: {routine}\n')
        for config, code in (({}, 0), ({'set_aside_findings': [self.ENTRY]}, 0), ({'set_aside_findings': [other]}, 0),
                             ({'set_aside_findings': [self.ENTRY, dict(self.ENTRY, check=routine, finding='debian 13')]}, 1)):
            (root/'answer').write_text(json.dumps({'valid': True, 'config': config}))
            (root/'code').write_text('0')
            result = subprocess.run(['bash', '-c', program], text=True, capture_output=True)
            self.assertEqual(result.returncode, code, str(config) + result.stdout + result.stderr)
        self.assertIn('installed, not set aside', result.stdout)
        self.assertIn('installed_packages/known_exploited_flaws', result.stdout)
        # A file MMWatchdog refuses fails the step too, with its answer shown.
        (root/'answer').write_text('{"valid": false}')
        (root/'code').write_text('1')
        result = subprocess.run(['bash', '-c', program], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('"valid": false', result.stdout)

    def test_the_step_runs_also_when_the_install_changed_nothing(self):
        _, tasks = node_tasks(self.explain('apply_set_aside_findings'), 'apply_set_aside_findings')
        task = dict(tasks)['put_the_set_aside_findings_into_effect']
        # No condition on the install, and no guard that skips it while the hub is down.
        self.assertEqual(task['status'], 'ready')
        self.assertEqual([item['field'] for item in task['arguments'] if 'when' == item['field'] or 'run_only_if' in item['field']], [])

    def test_nothing_reloads_when_the_hub_has_the_installed_entries_in_effect(self):
        result, calls = self.put_into_effect({'set_aside_findings': [self.ENTRY]}, [self.listed(self.ENTRY)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('The fleet hub has 1 set-aside findings in effect', result.stdout)
        self.assertNotIn('reload', calls)
        # No entry: MMWatchdog leaves the empty list out of its configuration.
        result, calls = self.put_into_effect({}, [])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('reload', calls)

    def test_entries_that_differ_reload_the_hub_also_after_an_earlier_failed_reload(self):
        # The installed file already has the removal; the hub still has the entry, as after a reload that failed.
        result, calls = self.put_into_effect({}, [self.listed(self.ENTRY)])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('reload', calls)
        self.assertIn('The fleet hub has 0 set-aside findings in effect', result.stdout)
        # A changed reason counts too: the hub names it in its alerts.
        changed = dict(self.ENTRY, reason='Debian rates it minor.')
        result, calls = self.put_into_effect({'set_aside_findings': [changed]}, [self.listed(self.ENTRY)])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('reload', calls)
        # So does each of the other fields of an entry: the hub lists them as evidence and attribution.
        for field, value in (('investigation_note', 'docs/investigations/2026-11-24-openssh.md'),
                             ('set_aside_by', 'Ana'), ('set_aside_on', '2026-11-24')):
            changed = dict(self.ENTRY, **{field: value})
            result, calls = self.put_into_effect({'set_aside_findings': [changed]}, [self.listed(self.ENTRY)])
            self.assertEqual(result.returncode, 2, field + ': ' + result.stdout + result.stderr)
            self.assertIn('reload', calls, field)

    def test_it_fails_when_a_reload_does_not_bring_the_entries_into_effect(self):
        changed = dict(self.ENTRY, exact_finding=self.ENTRY['exact_finding'].replace('u4', 'u5'))
        result, _ = self.put_into_effect({'set_aside_findings': [self.ENTRY]}, [self.listed(changed)], reload_takes_effect=False)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r'does not have the entries of /etc/mmwatchdog/set_aside_findings.yml in effect')
        self.assertIn('u5', result.stdout)

    def test_it_fails_when_the_hub_does_not_answer(self):
        # Both listings empty: the comparison must not pass on two empty answers.
        result, calls = self.put_into_effect({}, [], fleet_answers=False)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('reload', calls)
        self.assertIn('mmwatchdog fleet set-aside-findings', result.stdout)

    def test_the_dryrun_reloads_nothing_and_reports_a_difference(self):
        result, calls = self.put_into_effect({}, [self.listed(self.ENTRY)], dryrun=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('reload', calls)
        result, calls = self.put_into_effect({'set_aside_findings': [self.ENTRY]}, [self.listed(self.ENTRY)], dryrun=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_dryrun_passes_on_a_hub_whose_mmwatchdog_has_no_set_aside_findings_yet(self):
        # MMWatchdog 0.1.x, before the upgrade to the Stack version that brings set-aside findings.
        result, calls = self.put_into_effect({}, [], dryrun=True, fleet_answers=False, knows_set_aside_findings=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('fleet set-aside-findings --json', calls)
        # A real run after the install of the new release still checks.
        result, _ = self.put_into_effect({}, [], fleet_answers=False, knows_set_aside_findings=False)
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
