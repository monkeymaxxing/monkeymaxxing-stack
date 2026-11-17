#!/usr/bin/env python3
"""Chapter 3 installs no provider program; the Hetzner scripts use curl.

  python3 tests/no_provider_program_on_the_laptop_test.py

The agent reaches the provider through the API (the laptop key file on the
laptop, the API proxy on the desk), so no chapter tells it to install
Hetzner's `hcloud` program, and the Hetzner guide's scripts do not call it.
"""
from pathlib import Path
import re
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


class NoHcloud(unittest.TestCase):
    def test_no_chapter_or_guide_uses_the_hcloud_program(self):
        found = []
        for path in sorted([*(T/'initial_setup').glob('*.md'), *(T/'provider_guides').glob('*.md')]):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r'(?<![A-Za-z])hcloud(?![A-Za-z])', line) and 'No Hetzner command-line tool' not in line:
                    found.append(f'{path.name}:{number}: {line.strip()[:80]}')
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
