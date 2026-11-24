# Scheduled software review

This file is the task of the scheduled software review. At each review,
MMHotline on `util01` gives this file to the triage agent as the team's
instructions. The review runs only while
`triage_agent.software_review_interval_hours` in `mmhotline_settings.yml`
is a number of hours. With `off`, the template's setting, nothing reads
this file and the review costs nothing.
[Turn on the scheduled software review](operating_procedures/turn_on_the_scheduled_software_review.md)
says how the coding agent fits this task to the team's software.

## The task

You are the triage agent. Check the servers' software for known flaws and
new releases, then send at most one report. Follow "The scheduled software
review" and "Levels of vulnerability findings" in `triage_agent_rules.md`
for the level of each finding.

**At most one report for each review.** Put every new or changed finding
into one summary report. Send no report when nothing is new or changed:
the review's record on MMHotline's Triage agent page already shows that
the review ran, what the review cost, and when the review ended. MMHotline's
own instructions for a review agree: send the reports the team's task asks
for, and no report when nothing is new. Reason: the first review on a test
system sent 9 alerts, 7 of them at warn, and a phone that rings 7 times
for one review teaches the team to ignore warnings.

Work in this order:

1. Read your notes of the last review,
   `triage_agent_notes/open_software_findings.md`.
2. Check the programs from outside the distribution.
3. Check the distribution's packages.
4. Look up each flaw in CISA's list of known exploited flaws.
5. Compare what you found with the notes, to find what is new or changed.
6. Update the notes and commit the notes, with any one-time playbook.
7. Send the one report, or no report.

### 1. Read the notes of the last review

`triage_agent_notes/open_software_findings.md` holds what the last
review found: each open finding, and each flaw with no fix yet. The
notes are your memory between reviews, because MMHotline gives you only
the start time of the last review that finished. The notes file says
"No open findings." before the first review.

### 2. Programs from outside the distribution

Read `software_outside_the_distribution.yml`. For each program, run the
program's `installed_version_command` on each server of the program's
`installed_on_server_groups`, such as `ssh triage@app001 caddy version`.
`inventories/servers.yml` lists the servers of each group, and `all`
means every server. A server of a listed group without the program is not
a finding. When SSH to a server is refused, such as to a systems desk,
name the server under "What I checked" in the report. The refusal alone
is not a finding.

Then find the newest release, and read the security advisories:

- **An entry with a `releases_page`:** read the newest release there.
  Read the advisories on the `security_advisories_page` published since
  the last review that finished. At the first review, read every advisory
  for the installed version.
- **An entry with an empty `releases_page`:** the program has no public
  release list yet, so fetch no page for the program. The newest release
  the team has is the pin in `stack_software` in `mmx_project_settings.yml`.
  Compare the installed version with the pin's `version`.
- **An empty `security_advisories_page`:** the program has no advisory
  page. Fetch nothing, and do not report the missing page.

A program from a vendor's apt repository, such as Caddy, installs its
updates with the nightly security updates. A downloaded program, such as
Litestream, changes only when a person changes its pin.

### 3. The distribution's packages

On each server, list the installed source packages and the Debian release:

    ssh triage@app001 "dpkg-query --show --showformat='\${db:Status-Abbrev} \${source:Package} \${source:Version}\n'" | awk '$1 == "ii" {print $2, $3}' | sort -u
    ssh triage@app001 cat /etc/os-release

Leave out every package whose name starts with `linux`: a kernel flaw has
one remedy, a new kernel and a reboot, which MMWatchdog's checks cover.
Ask OSV.dev in batches of at most 1,000 queries, with the ecosystem
`Debian:VERSION_ID` from `/etc/os-release`, such as `Debian:13`:

    curl --silent --request POST https://api.osv.dev/v1/querybatch --header 'Content-Type: application/json' --data '{"queries":[{"package":{"ecosystem":"Debian:13","name":"openssl"},"version":"3.5.1-1"}]}'

Results come in query order. When a result has `next_page_token`, repeat
the result's query with `"page_token"` set to that value. Read each flaw at
`https://api.osv.dev/v1/vulns/ID` for the flaw's fixed version, Debian's
urgency, and the CVE ID.

Sort each flaw into one of three kinds:

- **Rated unimportant:** Debian's urgency is `unimportant`. Leave the flaw
  out entirely, from the report and from the notes. Debian uses the rating
  for a flaw that does not reach a Debian system, such as a flaw only in a
  build without PAM.
- **No fix yet:** the record has no fixed version for this Debian
  release. Record the flaw in the notes only, and send no alert. A person
  cannot act before Debian publishes a fix. The one exception is a flaw
  that attackers exploit now and that reaches the servers, which is SOS by
  "Levels of vulnerability findings", fix or no fix.
- **Fixed:** the fixed version is newer than the installed version. The
  fixed flaw is a finding.

For each fixed flaw, learn why the fix is not installed:

- On a database server, the nightly updates leave out `postgresql`,
  `pg-auto-failover`, `linux-` and `pgbouncer`. `update_database_servers`
  installs those packages in the team's weekly window.
- On every other server, the nightly security updates install the fix
  within a day of Debian publishing the fix. A fix that is still not
  installed a day later means the nightly updates failed or are missing.
  Read the cause in `journalctl -u apt-daily-upgrade.service --since -2days`
  on the server.

### 4. Known exploited flaws

Look up each flaw's CVE ID in CISA's list of known exploited
vulnerabilities, the flaws that attackers are known to use. Save the list
once, then search the list's `vulnerabilities` by `cveID`:

    curl --silent --output known_exploited_vulnerabilities.json https://raw.githubusercontent.com/cisagov/kev-data/main/known_exploited_vulnerabilities.json

### 5. Find what is new or changed

A finding is identified by its package or program and its flaw ID, or by
the release's version for a new release. Compare each finding of this
review with the finding in the notes:

- **New:** the notes do not have the finding.
- **Changed:** the notes have the finding with another state. For example,
  a flaw with no fix now has a fix, CISA's list now names the flaw, or a
  fix that waited a day is still not installed.
- **Fixed:** the notes have the finding, but this review did not find the
  finding, because the fix is installed and took effect.
- **Unchanged:** the notes have the finding in the same state. Do not
  report an unchanged finding again.

A new flaw with no fix changes only the notes, never the report. When
every finding is unchanged, or only new flaws with no fix appeared, send
no report.

### 6. Update the notes, and commit

Rewrite `triage_agent_notes/open_software_findings.md` with this review's
findings, in the sections the notes file names. Write the review's start
time at the top. Leave out every fixed finding, because Git keeps the
earlier versions. When a person must run a playbook, write the one-time
playbook with `mmx new-one-time-playbook`, such as
`mmx new-one-time-playbook install_security_updates_on_app001_and_app002`.
Commit the notes and the playbook together, with a message that names the
review. Request a playbook run only for an SOS finding. Reason: a request
that waits for a person's approval wakes the person on call.

### 7. The one report

The report's level decides who is disturbed, so choose the level by what a
person must do:

- **SOS:** a finding is SOS by "Levels of vulnerability findings": attackers
  exploit the flaw now, and the flaw reaches the servers.
- **warn:** a person must act. For example:
  - a fix that the nightly security updates did not install a day after
    Debian published the fix;
  - a security release of a program from a vendor's apt repository that
    the nightly updates did not install a day later.
- **info:** everything else that is new or changed. For example, a fix that
  the nightly updates install tonight, a database server's fix for the
  weekly window, a fix that waits for the weekly reboot, an installed fix,
  a new release with no security fix, or a downloaded program's security
  release whose flaw attackers do not exploit now, which a person installs
  with a new pin at the weekly review.

The report has this form, as "Reports: the why rule" in
`triage_agent_rules.md` asks:

1. **The title,** one plain line: the servers and the most important
   thing, such as "app001, app002: 3 security fixes wait for a person".
2. **One to three plain sentences:** what a person must do first, or that
   nobody needs to act.
3. **What a person must do,** at warn or SOS only, most urgent first.
   Give each item the exact playbook or procedure to run, by its file
   name, and the command. Never point to another report or another item,
   such as "the playbook from the brotli report".
4. **What changed since the last review,** a short line for each new,
   changed, or fixed finding, with its flaw IDs. Group a package's flaws
   on one line.
5. **What I checked,** in a few lines: the servers, the sources, and
   the counts, such as "OSV.dev: 210 source packages on each server".
6. **Confidence,** and the notes file.

A remedy names one of these:

- a one-time playbook you committed, such as
  `one_time_playbooks/2026-11-12_install_security_updates_on_app001_and_app002.yml`,
  with the command a person runs on the systems desk:
  `./server_management_scripts/run_mmx_on_util01 run 2026-11-12_install_security_updates_on_app001_and_app002`;
- for a downloaded program, the procedure
  [Updating a program from outside the distribution](operating_procedures/add_or_update_a_program_from_outside_the_distribution.md#updating-a-program-from-outside-the-distribution),
  with the new pin's `version`, `download_url`, and `sha256`;
- for a database server's held package, the procedure
  [Update and restart the database servers](operating_procedures/update_and_restart_the_database_servers.md)
  in the weekly window;
- for a fix that waits for a reboot, the procedure
  [Reboot servers after updates](operating_procedures/reboot_servers_after_updates.md)
  in the weekly window.

### Example of a warn report

    app001, app002: 3 security fixes wait for a person because the nightly updates failed
    Debian's fixes for brotli, apt and expat are not installed on app001 and app002, a day after Debian published the fixes. The nightly security updates stopped on a package that apt could not configure. A person runs the one-time playbook below.

    What a person must do:
    1. Run one_time_playbooks/2026-11-12_install_security_updates_on_app001_and_app002.yml from the systems desk: ./server_management_scripts/run_mmx_on_util01 run 2026-11-12_install_security_updates_on_app001_and_app002. The playbook installs the waiting fixes on app001 and app002. Risk: low. needrestart restarts the services that use the old libraries.

    What changed since the last review (2026-11-11 06:00 UTC):
    - brotli CVE-2026-111497: fixed in 1.1.0-2+deb13u1, not installed. CISA's list names the flaw, but only internal tools decode brotli here.
    - apt CVE-2026-109518 and expat (6 flaws): fixed, not installed.
    - zlib (3 flaws): the fix is installed on every server.
    - 12 new flaws with no fix yet, in curl and glibc: in the notes only.

    What I checked: 4 servers; OSV.dev for 210 source packages on each; CISA's list of 2026-11-10; Caddy, cloudflared, Claude Code, Litestream and rclone at their release and advisory pages; mmx, MMHotline and MMWatchdog against their pins.
    Confidence: high. The notes are in triage_agent_notes/open_software_findings.md.

### Example of an info report

    Software review: zlib fix installed, a new curl fix installs tonight, Litestream 0.5.19 for the weekly review
    The nightly security updates installed Debian's zlib fix on every server. Debian published a curl fix today, and the nightly updates install the curl fix tonight. Litestream 0.5.19 fixes a flaw that attackers do not exploit now; a person updates its pin at the weekly review. Nobody needs to act now.

    What changed since the last review (2026-11-12 06:00 UTC):
    - zlib (3 flaws): the fix is installed on every server.
    - curl CVE-2026-90211: fixed in 8.14.1-2+deb13u2 today, which the nightly updates install tonight.
    - db01: the postgresql-17 fix for CVE-2026-88410 waits for the weekly window, update_database_servers on Sunday at 03:00 UTC.
    - Caddy 2.11.10: a new release with no security fix, which the nightly updates install.
    - Litestream 0.5.19: a security release (GHSA-xxxx-xxxx-xxxx) that attackers do not exploit now. At the weekly review, a person follows operating_procedures/add_or_update_a_program_from_outside_the_distribution.md, "Updating a program from outside the distribution", with version 0.5.19, download_url https://github.com/benbjohnson/litestream/releases/download/v0.5.19/litestream-0.5.19-linux-x86_64.tar.gz, and sha256 from the release's checksums.txt.

    What I checked: 4 servers; OSV.dev for 210 source packages on each; CISA's list of 2026-11-10; the programs in software_outside_the_distribution.yml.
    Confidence: high. The notes are in triage_agent_notes/open_software_findings.md.
