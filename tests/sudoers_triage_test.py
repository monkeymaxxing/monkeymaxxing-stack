#!/usr/bin/env python3
"""Checks that the triage user may confirm a fix of every check group.

  /usr/bin/python3 tests/sudoers_triage_test.py

After a fix, the triage agent runs the check group's scheduled checks now,
with `sudo mmwatchdog check-now GROUP --count-as-scheduled-run`, so the
warning closes. The template's roles/every_server/files/sudoers_triage allows
it with one sudo regex line for every check group, so a team's custom check
file (mmwatchdog_checks/custom_*.yml) needs no edit there. The one line is
safe only while every group name is a plain lower-case name that the regex
matches, and while no other check-now option is allowed. So this test checks
that the regex line is the only check-now line, that it allows nothing but
the group name and --count-as-scheduled-run, and that every production check
group's name matches it.

The check-group files are MMX templates, so they are read as text: a check
group is a key two spaces in, under check_groups:, including a group that
only some servers get, inside a template's {{ if }}. A group whose name the
template fills in fails the test.

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
CHECK_NOW_REGEX_LINE = (
    "triage ALL=(root) NOPASSWD: /usr/local/bin/mmwatchdog ^check-now [a-z0-9_]+ --count-as-scheduled-run$"
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


# Every non-comment line of sudoers_triage, in file order. A new sudo line
# must be added here on purpose, so an extra one cannot slip in unnoticed.
EXPECTED_RULE_LINES = [
    "triage ALL=(root) NOPASSWD: /usr/bin/ss -tulpn",
    "triage ALL=(root) NOPASSWD: /usr/bin/ss -tupn",
    "triage ALL=(root) NOPASSWD: /usr/sbin/ufw status verbose",
    "triage ALL=(root) NOPASSWD: /usr/bin/wg show",
    "triage ALL=(root) NOPASSWD: /usr/bin/podman ps --all",
    "triage ALL=(root) NOPASSWD: /usr/local/bin/mmwatchdog status --json",
    "triage ALL=(root) NOPASSWD: /usr/local/bin/mmwatchdog events --json",
    CHECK_NOW_REGEX_LINE,
]


def rule_lines():
    """Every line of sudoers_triage that is not blank and not a comment."""
    with open(SUDOERS_TRIAGE) as file:
        return [line for line in file.read().splitlines() if line.strip() and not line.lstrip().startswith("#")]


def check_now_lines():
    """Every line of sudoers_triage that allows mmwatchdog check-now."""
    with open(SUDOERS_TRIAGE) as file:
        return [line for line in file.read().splitlines()
                if not line.startswith("#") and "mmwatchdog" in line and "check-now" in line]


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

    def test_one_regex_line_is_the_only_check_now_line(self):
        self.assertEqual(
            check_now_lines(), [CHECK_NOW_REGEX_LINE],
            "sudoers_triage allows check-now with exactly one regex line, and no per-group line",
        )

    def test_the_rule_lines_are_exactly_the_expected_ones(self):
        self.assertEqual(
            rule_lines(), EXPECTED_RULE_LINES,
            "sudoers_triage holds exactly these rules; change EXPECTED_RULE_LINES only after deciding "
            "that the triage user may run a new command as root",
        )

    def regex_of_the_line(self):
        """The argument regex that sudo reads in the line: from ^ to $."""
        return re.compile(CHECK_NOW_REGEX_LINE[CHECK_NOW_REGEX_LINE.index("^check-now"):])

    def test_every_check_group_name_matches_the_regex(self):
        regex = self.regex_of_the_line()
        for name, file_name in self.check_groups.items():
            with self.subTest(check_group=name, file=file_name):
                self.assertRegex(f"check-now {name} --count-as-scheduled-run", regex)

    def test_the_regex_refuses_other_options_and_other_places(self):
        regex = self.regex_of_the_line()
        for refused in (
            "check-now disks",
            "check-now disks --without-daemon --count-as-scheduled-run",
            "check-now disks --count-as-scheduled-run --config-dir /tmp/x",
            "check-now ../disks --count-as-scheduled-run",
            "check-now disks;id --count-as-scheduled-run",
            "check-now Disks --count-as-scheduled-run",
        ):
            with self.subTest(arguments=refused):
                self.assertIsNone(regex.match(refused))


if __name__ == "__main__":
    unittest.main()
