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
- The systems repository template ships values only the setup knows empty
  (so `mmx validate` on the bare template refuses by design). Any example
  domains or addresses in prose or examples use the documentation ranges
  (`example.com`, `203.0.113.0/24`).
- Follow [`docs/testing.md`](docs/testing.md) for testing changes. The
  `tests/*_test.py` suite validates filled-in copies of the template (such
  as `python3 tests/staging_server_test.py`) and checks the template's
  helpers, roles, and rules. For `set_up_outside_services/`, run
  `go vet ./...`, `go test ./...`, and `gofmt -l .` inside that directory.
- Write for a stranger who never saw how this repository was made: no
  machine names, paths, or accounts of the people who build the stack.
