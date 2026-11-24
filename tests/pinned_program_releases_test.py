#!/usr/bin/env python3
"""Check that every program pin is refused while it holds no release.

  MMX_BINARY=/path/to/mmx python3 tests/pinned_program_releases_test.py

Between releases, the Stack's main branch pins its programs with SHA-256
values of zeros. This file proves that every_server and the desk playbook
check every pin in stack_software for zeros before any task that downloads
or installs anything.
"""
import os
import re
import shutil
import subprocess
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


class PinsWithoutARelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def test_every_pin_is_checked_for_zeros_before_any_change(self):
        settings = (T/'mmx_project_settings.yml').read_text().split('\n  stack_software:\n', 1)[1]
        pins = sorted(re.findall(r'^    ([a-z0-9_]+):$', settings.split('\n\n', 1)[0], re.M))
        self.assertIn('set_up_outside_services', pins)
        for playbook, extra, first in (('every_server', [], 'util01 / refuse_programs_pinned_without_a_release/'),
                                       ('systems_desk', ['--var', 'desk_name=desk01'], 'desk01 / systems_desk/refuse_a_node_outside_systems_desks')):
            with self.subTest(playbook=playbook):
                result = subprocess.run([self.mmx, 'explain', playbook, *extra], cwd=template_values.filled_copy(), text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                tasks = re.findall(r'^  (\S+ / \S+): ', result.stdout, re.M)
                self.assertTrue(tasks[0].startswith(first), tasks[:3])
                zero_checks = [task for task in tasks if '/no_pin_has_a_sha256_of_zeros[' in task]
                self.assertEqual(sorted(re.search(r'\[(.*)\]', task)[1] for task in zero_checks), pins)
                # Each check comes before the first task that downloads or installs anything.
                last = max(tasks.index(task) for task in zero_checks)
                self.assertLessEqual(last, 1 + len(pins))
                self.assertIn('"' + '0' * 64 + '"', result.stdout)


if __name__ == '__main__':
    unittest.main()
