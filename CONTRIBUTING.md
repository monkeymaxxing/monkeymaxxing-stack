# Contributing to the Monkeymaxxing Stack

Bug reports, ideas, and pull requests are welcome. `CONTRIBUTING.md` explains
how bug reports, ideas, and pull requests become changes to the Stack.

## Reporting a bug or asking for a feature

Open an issue on GitHub. For a bug, include:

- `stack_version` and `stack_commit` from your systems repository's
  `monkeymaxxing_stack_checklist.yml`;
- the setup chapter or operating procedure, and the step, where the problem
  happened;
- the coding agent you use, such as Claude Code or Codex;
- what you expected, and what happened, with the output of the command that
  failed. Remove secrets, keys, and addresses you do not want to publish.

For a feature, start with the problem: what you are trying to do, and how you
do it today. [The design](docs/design.md) gives the reason for each of the
Stack's decisions, and a proposal is compared with those reasons.

## Reporting a security problem

Do not open an issue for a security problem: everyone can read issues. The
Stack's instructions and playbooks run as root on your servers. Report the
problem privately with **Report a vulnerability** on the repository's
**Security** tab on GitHub. Only the Stack's maintainers see the report and
reply in the private vulnerability report.

## A pull request is a proposal

The Stack's maintainers write every change that lands in the Stack.
Maintainers do not merge code from outside the project. Coding agents follow
the Stack's instructions with root access to your servers, so the origin of
every line is known. No text or code arrives from a source whose license,
authorship, or tools the project cannot check.

So a pull request is read as a proposal: a precise description of a change,
with text or code that shows it. When a maintainer accepts a proposal, the
maintainer writes the change, with its tests and documentation, and credits
you in the commit message:

```text
Proposed by @your-github-name in #123
```

The pull request is then closed with a link to the maintainer's commit.
A proposal that is not accepted is closed with the reason.

A proposal is easiest to accept when it:

- changes one thing, and says why;
- includes a test that fails without the change, where one is possible;
- follows the writing rules in
  [Talking with the team](skills/monkeymaxxing-stack/systems_repository_template/talking_with_the_team.md).

## Where the rules for changes live

| Document | What the document gives you |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Where to start, for people and coding agents alike |
| [The design](docs/design.md) | The conventions every file follows, and the reason for each decision |
| [Acceptance contracts](docs/acceptance.md) | The outcomes every change must keep |
| [Testing guide](docs/testing.md) | Which tests a change needs, and how to run them |

## License

The Monkeymaxxing Stack is licensed under the [Apache License 2.0](LICENSE).
Submissions in an issue or a pull request are offered under the Apache
License 2.0, as section 5 of the license says.
