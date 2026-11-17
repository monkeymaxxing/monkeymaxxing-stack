#!/usr/bin/env python3
"""Chapter 1's one approval: the rules the coding agent writes into Claude
Code's local settings, and the commands the guide gives it in their place
of loops and snippets that no rule can match.

  python3 tests/approval_rules_test.py
"""
import json
from pathlib import Path
import re
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
CHAPTER_1 = T/'initial_setup/01_answer_two_questions.md'


def approval_rules():
    section = CHAPTER_1.read_text().split('## First: one approval for the setup\'s commands', 1)[1].split('\n## ', 1)[0]
    blocks = re.findall(r'```json\n(.*?)```', section, re.S)
    assert len(blocks) == 1, blocks
    return json.loads(blocks[0])['permissions']


class ApprovalRules(unittest.TestCase):
    def setUp(self):
        self.permissions = approval_rules()

    def test_nothing_widens_what_the_agent_may_do(self):
        self.assertEqual(set(self.permissions), {'additionalDirectories', 'allow', 'deny'})
        for rule in self.permissions['allow']:
            with self.subTest(rule=rule):
                self.assertNotIn(rule, ('Bash', 'Bash(*)', 'Edit', 'Read', 'Write'))
                self.assertIsNone(re.match(r'Bash\((sudo |rm[ )]|rmdir|find |xargs|sh |bash |eval |env )', rule))
                self.assertNotIn('bypass', rule.lower())

    def test_folders_are_exact_never_wildcards(self):
        for folder in self.permissions['additionalDirectories']:
            with self.subTest(folder=folder):
                self.assertTrue(folder.startswith('/'), folder)
                self.assertNotIn('*', folder)
        for rule in self.permissions['allow']:
            if rule.startswith(('Edit(', 'Read(')):
                with self.subTest(rule=rule):
                    folder = rule[rule.index('(') + 1:].split('/**')[0]
                    self.assertNotIn('*', folder)

    def test_the_tools_and_the_desk_login_are_allowed_by_full_path_only(self):
        allow = self.permissions['allow']
        self.assertIn('Bash(~/.local/bin/mmx *)', allow)
        self.assertIn('Bash(~/.local/bin/doubleshell *)', allow)
        self.assertIn('Bash(~/code/example_systems/ssh/open-the-desk-login *)', allow)
        self.assertNotIn('Bash(mmx *)', allow)
        self.assertNotIn('Bash(doubleshell *)', allow)

    def test_two_in_place_edit_commands_are_denied(self):
        self.assertEqual(self.permissions['deny'], ['Bash(sed -i *)', 'Bash(perl -i *)'])


class TheGuideWaitsWithOneCommand(unittest.TestCase):
    def guide_texts(self):
        for path in [T/'AGENTS.md', *(T/'initial_setup').glob('*.md'), *(T/'operating_procedures').glob('*.md')]:
            yield path, path.read_text()

    def test_no_snippet_or_loop_waits_for_a_desk_job_the_setup_or_the_image(self):
        for path, text in self.guide_texts():
            for block in re.findall(r'```sh\n(.*?)```', text, re.S):
                with self.subTest(path=path.name, block=block[:80]):
                    if 'sleep' in block:
                        self.assertNotRegex(block, r'runs/|\.exit|setup_results|manifest|ghcr')
                    self.assertNotIn('code_script', block)
                    self.assertNotIn('podman manifest inspect', block)

    def test_the_guide_names_the_new_commands(self):
        agents = (T/'AGENTS.md').read_text()
        self.assertIn('~/code/example_systems/ssh/open-the-desk-login CODE', agents)
        self.assertIn('ssh desk01-agent wait-for-a-desk-job NAME', agents)
        chapter_4 = (T/'initial_setup/04_set_up_your_accounts_and_lock_your_desk.md').read_text()
        self.assertIn('ssh desk01-agent wait-for-the-setup', chapter_4)
        self.assertIn('./server_management_scripts/wait_for_the_app_image', chapter_4)


if __name__ == '__main__':
    unittest.main()
