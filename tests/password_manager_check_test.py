#!/usr/bin/env python3
"""Chapter 1 checks for a password manager on Linux too, and asks before it recommends.

  python3 tests/password_manager_check_test.py

Run 1's laptop was Linux, the check looked only in /Applications, and the
agent recommended Bitwarden to a person who used 1Password.
"""
from pathlib import Path
import re
import unittest

CHAPTER = next((Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/initial_setup').glob('01_*.md'))


class PasswordManagerCheck(unittest.TestCase):
    def setUp(self):
        self.text = re.sub(r'\s+', ' ', CHAPTER.read_text())

    def test_linux_is_checked_where_a_linux_laptop_keeps_its_programs(self):
        self.assertIn('On Linux, look for `1password`, `bitwarden`, and `keepassxc` on `PATH` and in `~/.local/share/applications`', self.text)

    def test_finding_none_asks_which_one_the_person_uses_before_recommending(self):
        self.assertIn('which one do you use?', self.text)
        self.assertNotIn('none found. I recommend Bitwarden', self.text)


if __name__ == '__main__':
    unittest.main()
