# Add or update a program from outside the distribution

**When to use this page:** a server needs a program that the distribution
does not supply, or MMWatchdog's `pinned_program_releases` warns about a
newer release of a pinned program.

**What this page does:** the program is installed from the vendor's apt
repository or from a pinned download, and gets an entry in the software
inventory, `software_outside_the_distribution.yml`. For an update, the
pin names the new release.

**Who acts:** the coding agent does every step from the systems desk.
The triage agent never changes a pin: a person's coding agent commits the
pin from a systems desk, because the pin is in `mmx_project_settings.yml`.
When `gpg` is missing on the desk, the person runs
`review-and-apply-the-systems-desk-settings` (step 1.2).

## Find your situation

| Situation | Follow |
| --- | --- |
| A new program that the distribution lacks or supplies outdated | [Adding a program from outside the distribution](#adding-a-program-from-outside-the-distribution) |
| A newer release of a program the system has, or a `pinned_program_releases` warning | [Updating a program from outside the distribution](#updating-a-program-from-outside-the-distribution) |
| A new stack version that needs a newer MMX | [A change that needs a newer MMX comes after its pin](#a-change-that-needs-a-newer-mmx-comes-after-its-pin) |

## Before you start

- **Use a vendor package only if the distribution lacks the program or
  supplies an outdated version,** as with Caddy.
  The distribution's own packages receive security fixes with the distribution.
  MMWatchdog checks the distribution's packages.
- **Commit the program's installation settings and software inventory
  entry with the role change that installs the program.**
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: run `every_server`
  or the playbook the step names.

## Adding a program from outside the distribution

1. **Choose how to install the program.**
   - Prefer the vendor's apt repository, added with an `apt_repository`
     task and the vendor's committed signing key, like Caddy's in
     `roles/tunnel_connector_and_caddy/main.yml`. On servers with
     automatic updates, unattended-upgrades installs vendor updates
     alongside security updates.
     `roles/every_server/files/unattended_upgrades.conf` controls which
     vendor repositories receive automatic updates: its
     `Unattended-Upgrade::Origins-Pattern` lists each vendor's Origin and
     Codename, from the repository's Release file.
   - For a downloaded program, pin its release: save the exact version
     under `stack_software` in `mmx_project_settings.yml`: `version`,
     `download_url`, and `sha256`.

   The steps for a vendor's apt repository, with the role that installs
   the program, such as `ROLE`, and the program's name, such as `PROGRAM`:

   1. **From the vendor's own installation page for Debian, write down**
      the repository's address, its suite and component, the signing key's
      address, and the key's fingerprint as the vendor publishes it.
      **Check:** none; step 1.2 checks the fingerprint.
   2. **Save the signing key in the role,** beside Caddy's example:

      ```sh
      # This systems desk, in the coding agent's checkout:
      curl -fsSL https://packages.example.com/PROGRAM/gpg.key -o roles/ROLE/files/PROGRAM_apt_signing_key.asc
      gpg --show-keys --with-colons roles/ROLE/files/PROGRAM_apt_signing_key.asc | awk -F: '$1 == "fpr" {print $10; exit}'
      ```

      **Check:** the printed fingerprint must equal the vendor's. Reason: the key
      decides which packages every server accepts as the vendor's, so a
      key swapped on the way would let someone else's packages in.
      The desk review installs GnuPG on the systems desk. On a desk whose
      last review came before, `gpg` is missing: ask the person to run
      `review-and-apply-the-systems-desk-settings`, and stop before
      committing the key.
   3. **Add an `apt_repository` task and the package to the role,** like
      `add_the_caddy_apt_repository` and `install_caddy_cloudflared_and_curl`
      in `roles/tunnel_connector_and_caddy/main.yml`: `name`, `uris`,
      `suites`, `components`, and `signing_key_source:
      files/PROGRAM_apt_signing_key.asc`, then the package with
      `version: newest_when_first_installed`.
      **Check:** `mmx validate` passes.
   4. **Read the repository's Origin and Codename for automatic updates:**

      ```sh
      # This systems desk, in the coding agent's checkout, with the suite from step 1:
      curl -fsSL https://packages.example.com/PROGRAM/dists/SUITE/Release | grep -E '^(Origin|Codename):'
      ```

      Add the line `"origin=ORIGIN,codename=CODENAME";` to
      `Unattended-Upgrade::Origins-Pattern` in
      `roles/every_server/files/unattended_upgrades.conf`, as Caddy's line
      `"origin=cloudsmith/caddy/stable,codename=any-version";` is. Without
      the line, the program never gets updates by itself.
      **Check:** the command printed both an `Origin:` and a `Codename:`
      line, and the new line uses those values.
   5. **After the run, check one server that runs the program.**
      **Check:** `ssh -F ssh/config root@10.20.1.1 'apt-cache policy PROGRAM'`
      names the vendor's repository, and the entry's
      `installed_version_command` prints the version.
2. **Add the program's entry to `software_outside_the_distribution.yml`.**
   For a downloaded program, use the program's entry name from
   `stack_software` in `mmx_project_settings.yml`.
   Include all five fields:

   - `installed_on_server_groups`: the inventory groups whose servers can
     run the program, or `all` for every server.
   - `installed_from`: `vendor_apt_repository` or `downloaded_binary`,
     according to the installation method.
   - `installed_version_command`: the command that prints the program's
     installed version.
   - `releases_page`: the URL where the vendor publishes releases.
   - `security_advisories_page`: the URL where the vendor publishes security
     advisories.

   `installed_on_server_groups` names every group whose servers may run the program.
   Include groups where later operating procedures run the program too.
   For example, Caddy and `cloudflared` need `load_balancer_servers` in
   `installed_on_server_groups` now, before
   [adding load-balancer servers](add_load_balancer_servers.md).
   Moving Caddy and `cloudflared` to load-balancer servers later then needs no
   change to `installed_on_server_groups`.
   **Check:** the entry has all five fields.
3. **Change no internet permission.** Adding the software inventory entry
   needs no separate internet permission change. MMHotline reads
   `software_outside_the_distribution.yml` in MMHotline's copy of the
   systems repository.
   MMHotline allows the triage agent to reach the hosts of the program's
   releases and advisories pages.
   The agent's internet access is "listed hosts only".
   MMHotline pushes the triage agent's commits only when they change
   nothing but its notes and one-time playbooks, so the triage agent
   cannot change `software_outside_the_distribution.yml`.
   **Check:** none; this step changes nothing.

Then commit, push and run `every_server` on `util01`, as
[Making a change](../AGENTS.md#making-a-change) says, and do step 1.5.

## Updating a program from outside the distribution

1. **Read the release notes** before changing a pin or pushing an update.
   A minor release of MMX, MMWatchdog, or MMHotline lists the required project edits.
   **Check:** each required project edit is in the same change.
2. **Update the program.**
   - A program from a vendor's apt repository, such as Caddy or
     `cloudflared`, receives updates automatically, except on the database
     servers: there,
     [Update and restart the database servers](update_and_restart_the_database_servers.md)
     installs vendor updates in the team's maintenance window.
   - For a downloaded program, change its pin in `stack_software`, then
     commit, push, and run `every_server` on `util01`.

   Each systems desk that runs MMX installs the same MMX release as `util01`.
   **Check:** the run passes. For an MMX pin, see
   [A new MMX pin takes effect from the next run](#a-new-mmx-pin-takes-effect-from-the-next-run).

### The pinned-release warning

MMWatchdog's check group `pinned_program_releases` on `util01` warns when a
pinned program has a newer release, and the triage agent's report gives the
release's security fixes and the new pin's `version`, `download_url`, and
`sha256`.

The warning stays open, without repeating, until the pin names the newest
release, and a later release while it is open sends no new alert. A team
that will not take a release leaves the warning open. The triage agent
records the release in `triage_agent_notes/open_software_findings.md`, and
the [weekly system review](do_the_weekly_system_review.md) checks for a
newer release than the one recorded.

## If something is different

### A new MMX pin takes effect from the next run

The run of the pin's own commit uses MMX's old release. The run installs
the new release on `util01` partway through, in the stage `util_server`.
The run that applies a pin fixing an MMX fault can therefore fail once
more because of the MMX fault.
The coding agent's next run uses the newly installed release. Read the
failed task before rerunning, and verify the fault is corrected.

The fault may stop the run before `util01` receives the new release,
for example in `util01`'s own `every_server` stage.
If the fault stops the run before the new MMX release reaches `util01`:

1. Install the new release on a systems desk, following the
   [systems desk installation instructions in chapter 2: Set up your laptop and your systems desk](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#chapter-3-make-your-server-account-and-your-systems-desk).
2. Run once from the systems desk:
   `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only`.
   **Check:** the run passes.

### A change that needs a newer MMX comes after its pin

Changes that need a newer MMX include a new stack version whose files
require the newer MMX.

1. Push only the MMX pin first, using project files that the old MMX
   release can read.
2. Wait for `util01`'s run of the pin's commit to pass before pushing the
   dependent change.
   **Check:** `./server_management_scripts/run_mmx_on_util01 results`
   from the desk shows the pin's run, and the run passed.
3. Push the dependent change.

Reason: if the MMX pin and the change requiring newer MMX share one commit,
`util01`'s old MMX release refuses the new files before running anything
(MMX exit status 4).
The run never reaches the installation of the new release.
On every retry, the old MMX release refuses the new files before installing
the new release.
