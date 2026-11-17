#!/usr/bin/env python3
"""The first part of the setup asks for no approval of the first release; one setting puts it back.

  python3 tests/first_release_approval_test.py

The first release at the end of chapter 9 is the image the person approved in
chapter 2. first_release_waits_for_a_persons_approval is false by default;
setting it to true is the one line that asks again. The coding agent follows
the setting from chapter 9's text, so the test checks that the setting is
false in the project settings and that chapter 9 asks for the person's
"release" only under that setting.
"""
from pathlib import Path
import re
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
SETTING = 'first_release_waits_for_a_persons_approval'


class TheFirstReleaseNeedsNoApproval(unittest.TestCase):
    def test_the_setting_is_false_by_default(self):
        self.assertRegex((T/'mmx_project_settings.yml').read_text(), r'(?m)^  %s: false$' % SETTING)

    def test_the_live_screen_asks_for_no_release_word_without_the_setting(self):
        chapter = (T/'initial_setup/09_go_live.md').read_text()
        screen = chapter.split('Your app is live:', 1)[1].split('```', 1)[0]
        self.assertNotIn('Say "release"', screen)
        asking = [line for line in chapter.splitlines() if 'Say "release"' in line or 'person said "release"' in line]
        self.assertTrue(asking)
        text = re.sub(r'\s+', ' ', chapter)
        for phrase in ('With `%s` set to `true`, the last line is instead: Say "release"' % SETTING,
                       'with the setting, the person said "release"'):
            self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
