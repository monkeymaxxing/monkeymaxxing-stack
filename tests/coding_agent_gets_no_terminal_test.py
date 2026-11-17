#!/usr/bin/env python3
"""Root's commands give a process that runs as coding-agent no terminal.

A coding-agent process that held the person's terminal could repaint the
screen after the desk review's diff, or type into it, and the person would
approve a desk playbook they never saw. Each command below runs from a
terminal here (a pseudo-terminal, as the person's ssh login has), with a
stand-in for the coding-agent Git that records whether its standard
input, output and error are a terminal and whether /dev/tty opens.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pty
import tempfile
import traceback
import unittest
from unittest.mock import patch

FILES = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/roles/systems_desk/files'


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace('-', '_'), str(FILES/name))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


STAND_IN = '''#!/usr/bin/env python3
import json, os
found = {"terminal_on": [n for n in (0, 1, 2) if os.isatty(n)]}
try:
    os.close(os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY))
    found["dev_tty_opens"] = True
except OSError:
    found["dev_tty_opens"] = False
with open(%r, "w") as report:
    json.dump(found, report)
'''


class TheCodingAgentGetsNoTerminal(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.report = self.root/'report.json'
        self.stand_in = self.root/'git-as-coding-agent'
        self.stand_in.write_text(STAND_IN % str(self.report))
        self.stand_in.chmod(0o755)

    def from_a_terminal(self, call):
        """Runs call in a child whose controlling terminal is a new
        pseudo-terminal, and returns what the stand-in found."""
        pid, terminal = pty.fork()
        if pid == 0:
            try:
                call()
                os._exit(0)
            except BaseException:
                traceback.print_exc()
                os._exit(1)
        said = b''
        while True:
            try:
                chunk = os.read(terminal, 4096)
            except OSError:
                break
            if not chunk:
                break
            said += chunk
        os.waitpid(pid, 0)
        os.close(terminal)
        self.assertTrue(self.report.exists(), said.decode(errors='replace'))
        return json.loads(self.report.read_text())

    def assert_no_terminal(self, found):
        self.assertEqual(found, {'terminal_on': [], 'dev_tty_opens': False})

    def test_the_stand_in_sees_a_terminal_that_it_is_given(self):
        # The check itself: a child that inherits the terminal is seen.
        import subprocess
        found = self.from_a_terminal(lambda: subprocess.run([str(self.stand_in)]))
        self.assertEqual(found, {'terminal_on': [0, 1, 2], 'dev_tty_opens': True})

    def test_the_desk_reviews_and_the_lock_out_buttons_pull(self):
        # lock-everyone-out pulls with the desk review's own function.
        self.assertIn('pull_main_into_the_desks_copy', (FILES/'lock-everyone-out').read_text())
        review = load('review-and-apply-the-systems-desk-settings')
        with patch.object(review, 'CODING_AGENT_GIT', [str(self.stand_in)]), \
                patch.object(review, 'CODING_AGENT_GIT_ENVIRONMENT', {'PATH': os.environ['PATH']}):
            self.assert_no_terminal(self.from_a_terminal(lambda: review.as_the_coding_agent('fetch')))

    def test_starting_the_systems_repository(self):
        start = load('start-the-systems-repository')
        with patch.object(start, 'CODING_AGENT_GIT', [str(self.stand_in)]), \
                patch.object(start, 'CODING_AGENT_ENVIRONMENT', {'PATH': os.environ['PATH']}), \
                patch.object(start, 'REPOSITORY', self.root):
            self.assert_no_terminal(self.from_a_terminal(lambda: start.git('status')))


if __name__ == '__main__':
    unittest.main()
