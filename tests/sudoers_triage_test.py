#!/usr/bin/env python3
"""Checks that the triage user may confirm a fix of every check group.

  /usr/bin/python3 tests/sudoers_triage_test.py

After a fix, the triage agent runs the check group's scheduled checks now,
with `sudo mmwatchdog check-now GROUP --count-as-scheduled-run`, so the
warning closes. sudo allows exactly the lines of the template's
roles/every_server/files/sudoers_triage, one for each production check group in
mmwatchdog_checks/; a group without its line is refused, and the triage
agent can't confirm a fix of it.

The check-group files are MMX templates, so they are read as text: a check
group is a key two spaces in, under check_groups:, including a group that
only some servers get, inside a template's {{ if }}. A group whose name the
template fills in fails the test, because sudoers_triage can list only
fixed names.

Systems desks have no triage user. Their desk-only check file is excluded;
the shared every_server.yml and all production check files remain covered.

It needs Python 3 and nothing else.
"""

import glob
import os
import re
import unittest

TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills/monkeymaxxing-stack/systems_repository_template",
)
SUDOERS_TRIAGE = os.path.join(TEMPLATE, "roles/every_server/files/sudoers_triage")
DESK_CHECK_GROUP_FILE = os.path.join(TEMPLATE, "mmwatchdog_checks/systems_desks.yml")
CHECK_GROUP_FILES = sorted(path for path in glob.glob(os.path.join(TEMPLATE, "mmwatchdog_checks/*.yml"))
                           if path != DESK_CHECK_GROUP_FILE)

CHECK_GROUP_LINE = re.compile(r"^  ([^\s#][^:]*):\s*(#.*)?$")
CHECK_NOW_LINE = re.compile(
    r"^triage ALL=\(root\) NOPASSWD: /usr/local/bin/mmwatchdog check-now (\S+) --count-as-scheduled-run$"
)
PLAIN_NAME = re.compile(r"^[a-z0-9_]+$")


def check_groups_of(path):
    """The check groups' names in one file of mmwatchdog_checks/, in order."""
    names = []
    under_check_groups = False
    with open(path) as file:
        for line in file:
            line = line.rstrip("\n")
            if line == "check_groups:":
                under_check_groups = True
                continue
            match = CHECK_GROUP_LINE.match(line)
            if under_check_groups and match:
                names.append(match.group(1))
    return names


def check_now_groups():
    """The check groups that sudoers_triage lets the triage user check now."""
    with open(SUDOERS_TRIAGE) as file:
        return [match.group(1) for match in map(CHECK_NOW_LINE.match, file.read().splitlines()) if match]


class TheTriageUsersCheckNowLines(unittest.TestCase):
    def setUp(self):
        self.check_groups = {}
        for path in CHECK_GROUP_FILES:
            names = check_groups_of(path)
            file_name = os.path.relpath(path, TEMPLATE)
            self.assertTrue(names, f"{file_name} has no check group under check_groups:")
            for name in names:
                self.assertRegex(
                    name, PLAIN_NAME,
                    f"{file_name}: the check group {name!r} takes its name from the template; "
                    "give it a fixed name, which sudoers_triage can list",
                )
                self.check_groups[name] = file_name
        self.assertTrue(self.check_groups, "found no file in mmwatchdog_checks/")

    def test_every_check_group_has_its_check_now_line(self):
        missing = [f"{name} (in {file_name})" for name, file_name in self.check_groups.items() if name not in check_now_groups()]
        self.assertEqual(
            missing, [],
            "add to roles/every_server/files/sudoers_triage, for each: "
            "triage ALL=(root) NOPASSWD: /usr/local/bin/mmwatchdog check-now GROUP --count-as-scheduled-run",
        )

    def test_every_check_now_line_names_a_check_group(self):
        unknown = [name for name in check_now_groups() if name not in self.check_groups]
        self.assertEqual(unknown, [], "these lines of sudoers_triage name no check group in mmwatchdog_checks/")


if __name__ == "__main__":
    unittest.main()
