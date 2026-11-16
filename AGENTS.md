# Working on the Monkeymaxxing Stack

This repository is the stack itself: the skill and the systems repository
template it copies. Read [`docs/design.md`](docs/design.md) before changing
any file. `docs/design.md` records the conventions that every file
follows.

- Write documentation in Plain English, as
  [Talking with the team](skills/monkeymaxxing-stack/systems_repository_template/talking_with_the_team.md)
  describes. `talking_with_the_team.md` holds the writing rules, the
  technical terms, and the example messages that every coding agent
  follows with the team.
- Follow the [acceptance contracts](docs/acceptance.md) when you
  change what the person reads or hears, or the rules for what the person
  reads or hears.
- Every value in the systems repository template is written out. A value
  the team must replace uses the documentation ranges (`example.com`,
  `203.0.113.0/24`).
- Check the systems repository template with `mmx validate`, run inside
  `skills/monkeymaxxing-stack/systems_repository_template/`.

  If you change the template's helper `run_mmx_on_util01`, run
  `python3 tests/run_mmx_on_util01_test.py` from the stack repository root.
  Run `python3 tests/server_scripts_test.py` for server helper changes.

  If you change the template's check groups, in `mmwatchdog_checks/`, or
  the triage user's sudo lines, in `roles/every_server/files/sudoers_triage`,
  run `python3 tests/sudoers_triage_test.py` from the stack repository root.
- Write for a stranger who never saw how this repository was made: no
  machine names, paths, or accounts of the people who build the stack.
