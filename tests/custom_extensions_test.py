#!/usr/bin/env python3
"""A team's custom MMWatchdog check file, and the places a recipe adds to.

  MMX_BINARY=/path/to/mmx python3 tests/custom_extensions_test.py

Each group of inventories/servers.yml lists its MMWatchdog check files in
mmwatchdog_check_files. The roles mmwatchdog_joined_node (every server and
desk) and util_server (util01) render, check and install exactly those files,
and delete every other file from the candidate directory and from
/etc/mmwatchdog/check_groups. A team's file starts with custom_ and reads its
settings from `custom:` in mmx_project_settings.yml, which the playbooks pass
as the role input `custom`.

These tests copy the template with the setup's values filled in, add
mmwatchdog_checks/custom_example.yml (it reads
{{ .inputs.custom.example_threshold }}) to a pool and to util_server, and
read the real playbooks with `mmx validate` and `mmx explain`: no server is
needed. The file-name check is an assert task that runs on the server, so the
tests read its regex from the explained task and apply it to a bad name.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server_connections_test as connections  # noqa: E402

T = connections.T
CUSTOM_FILE = 'custom_example.yml'
CUSTOM_CHECK = '''# Managed by MMX. A custom check file of the team, from a recipe.
check_groups:
  custom_example:
    check_every: 1m
    time_limit_per_run: 30s
    alert_after_failing_for: 5m
    recovered_after_healthy_for: 1m
    checks:
      the_example_is_below_its_threshold:
        # {{ .inputs.custom.example_threshold }} is the team's custom.example_threshold.
        every_disk_and_network_filesystem:
          filesystems_to_ignore: []
        fail_when_measurement_above:
          space_used_percent: {{ .inputs.custom.example_threshold }}
          inodes_used_percent: {{ .inputs.custom.example_threshold }}
        alert_severity: info
'''
POOL_LINE = '[every_server.yml, app_servers.yml]'
UTIL_LINE = '[every_server.yml, util_server.yml]'
# The last MMWatchdog stage of every_server for most servers, and util01's stage.
POOL_STAGE = 'mmwatchdog_joins_the_fleet_hub_after_the_roles'
UTIL_STAGE = 'util_server'


def argument(task, field):
    return next(a for a in task['arguments'] if a['field'] == field)


class CustomExtensions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX playbooks and templates.')

    def project(self, pool_files=POOL_LINE, util_files=UTIL_LINE, custom='{example_threshold: 7}'):
        """A filled copy of the template with the custom check file added to the lists given."""
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)/'systems'
        connections.make_project(root)
        (root/'mmwatchdog_checks'/CUSTOM_FILE).write_text(CUSTOM_CHECK)
        inventory = (root/'inventories/servers.yml').read_text()
        for old, new in ((POOL_LINE, pool_files), (UTIL_LINE, util_files)):
            old, new = f'mmwatchdog_check_files: {old}\n', f'mmwatchdog_check_files: {new}\n'
            self.assertEqual(inventory.count(old), 1, old)
            inventory = inventory.replace(old, new)
        (root/'inventories/servers.yml').write_text(inventory)
        settings = (root/'mmx_project_settings.yml').read_text()
        self.assertEqual(settings.count('  custom: {}\n'), 1)
        (root/'mmx_project_settings.yml').write_text(settings.replace('  custom: {}\n', f'  custom: {custom}\n'))
        return root

    def mmx_run(self, root, *arguments):
        return subprocess.run([self.mmx, *arguments], cwd=root, text=True, capture_output=True)

    def validate(self, root):
        result = self.mmx_run(root, 'validate')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tasks(self, root, stage, node):
        """The explained tasks of one node in one fleet stage of every_server."""
        result = self.mmx_run(root, 'explain', 'every_server', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        stages = [s for s in json.loads(result.stdout)['fleet_stages'] if s['path'] == stage]
        self.assertEqual(len(stages), 1, stage)
        return [t for t in stages[0].get('node_tasks') or [] if t['node'] == node]

    def check_file_tasks(self, tasks):
        """The five kinds of task that handle check files, by the last part of their path."""
        found = {}
        for task in tasks:
            name = task['path'].rsplit('/', 1)[1]
            found.setdefault(re.sub(r'\[\d+\]$', '', name), []).append(task)
        return found

    def assert_the_files_are_handled(self, tasks, files):
        by_name = self.check_file_tasks(tasks)
        for candidate_or_live in ('create_the_candidate_check_groups_directory', 'delete_every_other_check_group'):
            self.assertEqual(len(by_name[candidate_or_live]), 1, candidate_or_live)
            self.assertEqual(argument(by_name[candidate_or_live][0], 'directory.delete_everything_inside_except')['value'], files,
                             f'{candidate_or_live} keeps exactly the listed files')
        self.assertEqual([argument(t, 'file.template')['value'] for t in by_name['write_the_candidate_check_groups']],
                         [f'../../mmwatchdog_checks/{f}' for f in files])
        self.assertEqual([argument(t, 'file.path')['value'] for t in by_name['write_the_candidate_check_groups']],
                         [f'/usr/local/lib/mmwatchdog/candidate_config/check_groups/{f}' for f in files])
        self.assertEqual([argument(t, 'file.path')['value'] for t in by_name['install_the_check_groups']],
                         [f'/etc/mmwatchdog/check_groups/{f}' for f in files])

    def test_a_pool_renders_installs_and_keeps_a_custom_check_file(self):
        root = self.project(pool_files=f'[every_server.yml, app_servers.yml, {CUSTOM_FILE}]')
        self.validate(root)
        files = ['every_server.yml', 'app_servers.yml', CUSTOM_FILE]
        for stage, node in ((POOL_STAGE, 'app001'), (POOL_STAGE, 'jobs001')):
            with self.subTest(stage=stage, node=node):
                files_of_node = files if node == 'app001' else ['every_server.yml', 'jobs_servers.yml']
                self.assert_the_files_are_handled(self.tasks(root, stage, node), files_of_node)

    def test_util01_renders_installs_and_keeps_a_custom_check_file(self):
        root = self.project(util_files=f'[every_server.yml, util_server.yml, {CUSTOM_FILE}]')
        self.validate(root)
        self.assert_the_files_are_handled(self.tasks(root, UTIL_STAGE, 'util01'),
                                          ['every_server.yml', 'util_server.yml', CUSTOM_FILE])

    def test_a_server_whose_group_lists_no_custom_file_deletes_one_it_had(self):
        # Dropping a file from the list removes it from both directories:
        # the list is exactly what a server keeps.
        root = self.project()
        self.validate(root)
        files = ['every_server.yml', 'app_servers.yml']
        self.assert_the_files_are_handled(self.tasks(root, POOL_STAGE, 'app001'), files)
        self.assertNotIn(CUSTOM_FILE, json.dumps(self.tasks(root, POOL_STAGE, 'app001')))

    def test_the_custom_file_reads_the_custom_settings(self):
        pool = f'[every_server.yml, app_servers.yml, {CUSTOM_FILE}]'
        util = f'[every_server.yml, util_server.yml, {CUSTOM_FILE}]'
        for name, root in (('a pool', self.project(pool_files=pool, custom='{}')),
                           ('util01', self.project(util_files=util, custom='{}'))):
            with self.subTest(file_is_listed_for=name):
                result = self.mmx_run(root, 'validate')
                self.assertNotEqual(result.returncode, 0, 'a missing custom.example_threshold must refuse')
                self.assertIn('.inputs.custom.example_threshold', result.stderr)
                self.assertIn(CUSTOM_FILE, result.stderr)
        self.validate(self.project(pool_files=pool, util_files=util))

    def test_mmx_refuses_a_file_name_with_a_folder_part_at_validate(self):
        # The names of a whole-list reference go into paths, so MMX refuses
        # a name that climbs out of, or goes below, the check groups directory
        # before any server is reached. The role's assert is the second guard.
        listings = {'pool': ('pool_files', '[every_server.yml, app_servers.yml, {}]'),
                    'util01': ('util_files', '[every_server.yml, util_server.yml, {}]')}
        for name, reason in (('../bad.yml', 'has a .. part'), ('sub/custom_x.yml', 'must name a direct child')):
            for where, (argument_name, template) in listings.items():
                with self.subTest(name=name, listed_for=where):
                    root = self.project(**{argument_name: template.format(name)})
                    (root/'bad.yml').write_text('check_groups: {}\n')
                    (root/'mmwatchdog_checks/sub').mkdir()
                    (root/'mmwatchdog_checks/sub/custom_x.yml').write_text('check_groups: {}\n')
                    result = self.mmx_run(root, 'validate')
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn(reason, result.stderr)

    def test_the_role_refuses_a_name_that_is_not_plain_before_any_change(self):
        # MMX accepts an upper-case name that exists, so validate passes and
        # the role's own first task, an assert that runs on the server,
        # refuses it. The tests read the assert's regex from the explained task.
        for stage, node, argument_name, plain in (
                (POOL_STAGE, 'app001', 'pool_files', 'app_servers.yml'),
                (UTIL_STAGE, 'util01', 'util_files', 'util_server.yml')):
            with self.subTest(node=node):
                listed = f'[every_server.yml, {plain}, Custom_Other.yml]'
                root = self.project(**{argument_name: listed})
                (root/'mmwatchdog_checks/Custom_Other.yml').write_text('check_groups: {}\n')
                self.validate(root)
                tasks = self.tasks(root, stage, node)
                asserts = [t for t in tasks if '/refuse_a_check_file_name_that_is_not_plain[' in t['path']]
                self.assertEqual(len(asserts), 3, 'one assert for each listed file')
                block = next(i for i, t in enumerate(tasks) if '/mmwatchdog_reports_to_the_fleet_hub/' in t['path']
                             or '/mmwatchdog_fleet_hub/' in t['path'])
                first = tasks.index(asserts[0])
                self.assertEqual([tasks.index(a) for a in asserts], [first, first + 1, first + 2])
                self.assertLess(tasks.index(asserts[-1]), block, 'the refusal comes before the block changes the server')
                regex = argument(asserts[0], 'assert.that')['reference']['matches'][1]
                messages = [argument(t, 'assert.message')['value'] for t in asserts]
                refused = [m for m in messages if 'Custom_Other.yml' in m]
                self.assertEqual(len(refused), 1)
                self.assertIn('Nothing changed.' if node == 'app001' else 'Stopped before changing MMWatchdog on util01.', refused[0])
                self.assertNotIn('Nothing changed.' if node == 'util01' else 'Stopped before', refused[0],
                                 'util01 runs about 860 lines of tasks before this assert, so it never says nothing changed')
                for name, accepted in (('every_server.yml', True), ('app_servers.yml', True), ('custom_example.yml', True),
                                       ('custom_my-pool_2.yml', True), ('Custom_Other.yml', False), ('../bad.yml', False),
                                       ('sub/custom_x.yml', False), ('/etc/passwd', False), ('custom_example.yaml', False),
                                       ('.hidden.yml', False)):
                    with self.subTest(name=name):
                        self.assertEqual(re.search(regex, name) is not None, accepted)


    def test_the_role_refuses_an_empty_list_of_check_files_before_any_change(self):
        # An empty list would delete every check group from the server, and
        # the per-name assert has nothing to loop over, so a separate assert
        # refuses it. MMX accepts the empty list at validate.
        for stage, node, argument_name in ((POOL_STAGE, 'app001', 'pool_files'), (UTIL_STAGE, 'util01', 'util_files')):
            with self.subTest(node=node):
                root = self.project(**{argument_name: '[]'})
                self.validate(root)
                tasks = self.tasks(root, stage, node)
                guard = [t for t in tasks if '/refuse_an_empty_list_of_check_files' in t['path']]
                self.assertEqual(len(guard), 1)
                block = next(i for i, t in enumerate(tasks) if '/mmwatchdog_reports_to_the_fleet_hub/' in t['path']
                             or '/mmwatchdog_fleet_hub/' in t['path'])
                self.assertLess(tasks.index(guard[0]), block, 'the refusal comes before the block changes the server')
                self.assertIn('delete every MMWatchdog check', argument(guard[0], 'assert.message')['value'])
                # The condition runs on the server; explain shows it as written.
                self.assertEqual(argument(guard[0], 'assert.that')['reference'],
                                 {'not': {'equals': ['{{ .inputs.mmwatchdog_check_files }}', []]}})


class TheTemplateKeepsTheSeams(unittest.TestCase):
    def read(self, path):
        return (T/path).read_text()

    def test_every_group_lists_every_server_first_and_files_that_exist(self):
        lines = re.findall(r'(?m)^      mmwatchdog_check_files: \[(.*)\]$', self.read('inventories/servers.yml'))
        self.assertEqual(len(lines), 6, 'six groups list their check files; the desk list lives in playbooks/systems_desk.yml')
        for line in lines:
            files = [f.strip() for f in line.split(',')]
            self.assertEqual(files[0], 'every_server.yml')
            for f in files:
                self.assertTrue((T/'mmwatchdog_checks'/f).is_file(), f)

    def test_the_old_one_file_name_is_gone_everywhere(self):
        stale = []
        for path in T.rglob('*'):
            if path.is_file() and path.suffix in ('.yml', '.md', '.py', '.bash', ''):
                if re.search(r'mmwatchdog_check_file\b', path.read_text(errors='ignore')):
                    stale.append(str(path.relative_to(T)))
        self.assertEqual(stale, [])

    def test_the_slots_have_three_unchanging_lines_above_and_below(self):
        boundary = '# Keep these three boundary comment lines intact for clean upgrades.'
        for path in ('playbooks/every_server.yml', 'mmx_project_settings.yml'):
            with self.subTest(path=path):
                lines = self.read(path).splitlines()
                start = lines.index(next(l for l in lines if l.strip() == '# --- Custom extensions (start) ---'))
                end = lines.index(next(l for l in lines if l.strip() == '# --- Custom extensions (end) ---'))
                block = [l.strip() for l in lines[start:end + 1]]
                self.assertEqual(block.count(boundary), 2)
                first, second = block.index(boundary), len(block) - 1 - block[::-1].index(boundary)
                self.assertEqual(first, 2, 'three comment lines above the team\'s lines')
                self.assertEqual(len(block) - 1 - second, 2, 'three comment lines below')

    def test_the_fleet_slot_comes_before_the_mmwatchdog_join_and_custom_is_away_from_stack_software(self):
        playbook = self.read('playbooks/every_server.yml')
        self.assertLess(playbook.index('# --- Custom extensions (end) ---'),
                        playbook.index('- id: mmwatchdog_joins_the_fleet_hub_after_the_roles\n'))
        settings = self.read('mmx_project_settings.yml')
        self.assertIn('  custom: {}\n', settings)
        self.assertGreater(settings.index('  stack_software:') - settings.index('  custom: {}\n'), 10000,
                           'custom sits well away from stack_software, which changes in every release')

    def test_the_checklist_lists_no_custom_extension_and_the_triage_agent_may_not_apply_one(self):
        self.assertRegex(self.read('monkeymaxxing_stack_checklist.yml'), r'(?m)^custom_extensions: \[\]$')
        rules = self.read('triage_agent_rules.md')
        self.assertIn('custom_recipes/', rules)
        self.assertIn('Never fetch or apply a recipe', rules)


if __name__ == '__main__':
    unittest.main()
