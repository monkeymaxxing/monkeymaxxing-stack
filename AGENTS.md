# Working on the Monkeymaxxing Stack

## Product goal

A developer or startup founder's coding agent takes their web app to a live,
quiet, high-availability production system (alerts, locked backups, automatic
database failover, triage agent) in a few hours, in their own accounts.

- **Ease is the security goal:** Setup feels like steady progress, not an exam.
  The agent and APIs do the heavy lifting while the person decides and watches.
- **Quiet and hands-off:** Alert only when a person must act; upgrade only for
  a real reason; reject operational theater.
- **The coding agent is trusted:** Never build fences against the team's coding
  agent. Keep secrets off laptops, out of agent logs, and away from outsiders.
- **Text rules beat code:** Teach a coding agent a nuance with a clear rule in
  the guide; never add code or checks where a text rule works.

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
