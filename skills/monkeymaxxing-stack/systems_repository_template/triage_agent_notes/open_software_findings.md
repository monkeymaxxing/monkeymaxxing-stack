# Open software findings

The triage agent keeps this note, as "Report a finding once" in
`triage_agent_rules.md` and step 6 of `scheduled_software_review_task.md`
say. The next review compares its findings with this note, to report only
what is new or changed. A system review reads the note too.

The note starts with the start time of the review that wrote the note.
Then the note has three sections:

- **Findings a person must act on:** for each finding, the servers, the
  package or program, the flaw IDs (or the new release's version), the
  installed and the fixed version, whether CISA's list names the flaw,
  the date the fix was first seen, the date first reported, and the
  remedy, by its playbook or procedure name.
- **Other open findings:** the same facts, for a finding that waits for
  no person, such as a fix that the nightly updates install tonight, a
  database server's fix that waits for `update_database_servers`, or a downloaded program's
  security release whose flaw attackers do not exploit now.
- **Flaws with no fix yet:** for each package, the servers, the installed
  version, and the flaw IDs. A flaw with no fix is never reported until a
  fix appears. Flaws that Debian rates unimportant are left out.

A finding whose fix took effect leaves the note; Git keeps the earlier
versions of the note.

No open findings.
