# Upgrade to a new stack version

Stable systems upgrade only for a reason: a flaw being exploited, support
ending, or something the team needs. Otherwise stay on the version you
have. The coding agent knows the end-of-support dates of the Debian
release, Postgres, and the pinned programs, and raises one when it
matters.

**When to use this page:** the person asks to move the system to a new
stack version.

**What this page does:** the systems repository takes the template's
changes between the system's recorded stack commit and the new one, keeps
the team's values and deviations, and one run on `util01` applies them.

**Who acts:** the coding agent does the steps on the laptop, in its clone
of the systems repository, `~/code/example_systems`, and runs MMX through
the desk. The person decides each conflict with a
recorded deviation, reviews each updated app file, approves the commit
before the push, picks the quiet hour, and adds each missing vault key.

## Find your situation

| Situation | Follow |
| --- | --- |
| The template changed since `stack_commit` in `monkeymaxxing_stack_checklist.yml` | [A new version](#a-new-version) |
| An entry of a version newer than the system's old `stack_version` names a one-time step | Step 6 of [A new version](#a-new-version), with [What each version changes](#what-each-version-changes) |

## Before you start

- **Edit on the laptop.** You edit in the laptop's clone and publish each
  commit, as [Making a change](../AGENTS.md#making-a-change) says. The
  Stack's own clone, `STACK_REPOSITORY` below, is on the laptop too.
- **A new stack version never changes a running system by itself.** Only
  the run in step 5 of [A new version](#a-new-version) applies it.

## A new version

**Before you start:**

- The stack's repository tags each version with `v` and its number, such as `v0.1.0`.
  A team uses the Stack at a version tag, never at `main`. Reason: between
  releases, `main` pins the Stack's programs with SHA-256 values of zeros,
  which `every_server` and the desk playbook refuse.
- `STACK_REPOSITORY` below is the path to a clone of the stack's repository.
  Use the clone from which the Monkeymaxxing Stack skill was installed,
  or a fresh `git clone https://github.com/monkeymaxxing/monkeymaxxing-stack.git`.
- `NEW_VERSION` is the new version's tag, such as `v0.2.0`. Bring it into
  the clone with `git -C STACK_REPOSITORY fetch --tags`, then
  `git -C STACK_REPOSITORY checkout NEW_VERSION`. Follow this page as that
  checkout holds it. The installed skill is a copy, not a link, so copy
  the new version's skill directory in place of the old copy, as the
  Stack's README says:
  `rm -rf ~/.claude/skills/monkeymaxxing-stack` and
  `cp -R STACK_REPOSITORY/skills/monkeymaxxing-stack ~/.claude/skills/`
  (Codex: `~/.agents/skills`). Reason: a symbolic link makes Claude Code
  ask permission for each read outside the working folders, even in auto
  mode.
- `NEW_COMMIT` is the new version's release commit,
  `git -C STACK_REPOSITORY rev-parse HEAD` after the checkout.
- Read `OLD_COMMIT` from `stack_commit` in
  `monkeymaxxing_stack_checklist.yml`, which records the source commit of
  the systems repository's files.
  If the checklist has no `stack_commit`, use the checklist's
  `stack_version`, the old version's tag, as `OLD_COMMIT` instead.
- `OLD_VERSION` is the checklist's `stack_version` before step 3 changes
  it, such as `0.1.0`.
- The template is the example systems repository in the stack's repository,
  at `skills/monkeymaxxing-stack/systems_repository_template`.
- `VERSION_CHANGE_DIRECTORY` is a new, empty directory outside the systems
  repository, such as a directory made by `mktemp -d`.
- In the commands below, replace `STACK_REPOSITORY` and
  `VERSION_CHANGE_DIRECTORY` with the directory paths described above.
  Replace `OLD_COMMIT` and `NEW_COMMIT` with the commit or tag values
  described above.
- The system needs a new version when the template changed between
  `OLD_COMMIT` and `NEW_COMMIT`:
  `git -C STACK_REPOSITORY diff --quiet OLD_COMMIT NEW_COMMIT -- skills/monkeymaxxing-stack/systems_repository_template`
  exits 1.

When the person asks to move the system to the new version, work in the
laptop's clone, `~/code/example_systems`:

1. **The team's deviations:** the differences from the template at the
   old commit. The differences between the systems repository and the old
   template are the team's values, such as the apps, the servers, and the
   SSH keys; the recorded deviations, the checklist items marked
   `deviated`; and records such as
   `triage_agent_notes/`.
   Keep the team's values, recorded deviations, and records.

   ```sh
   git -C STACK_REPOSITORY archive OLD_COMMIT skills/monkeymaxxing-stack/systems_repository_template | tar -x -C VERSION_CHANGE_DIRECTORY
   diff -ru --exclude=.git --exclude=.mmx VERSION_CHANGE_DIRECTORY/skills/monkeymaxxing-stack/systems_repository_template .
   ```

   **Check:** each difference the command lists is a team value, a
   recorded deviation, or a record.
2. **The version's changes:** apply the template's difference between the
   two commits, and merge each part that doesn't apply by hand, keeping
   the team's values and deviations. When a change of the new version
   conflicts with a recorded deviation, tell the person what each choice
   means, and keep the deviation until the person decides.

   The team's custom extensions stay as they are. Never overwrite or
   delete them: the folder `custom_recipes/`, the list `custom_extensions:`
   in the checklist, every file `mmwatchdog_checks/custom_*.yml` and its
   `custom_*.yml` entry inside each group's `mmwatchdog_check_files` in
   `inventories/servers.yml`, the `## Custom extensions` section of
   `AGENTS.md`, the team's `custom:` settings, and each block between the
   `# --- Custom extensions (start) ---` and
   `# --- Custom extensions (end) ---` comment lines in `playbooks/` and
   `mmx_project_settings.yml`. The new template ships those blocks empty,
   so a change that would empty one is a change to undo. A new version
   never applies a recipe again: the stamp in `custom_recipes/` says which
   commit of the recipe the team applied.

   The patch names each file's old version by its Git object, so Git can
   merge a part that changed both in the template and in the team's file.
   Start with a clean working tree (`git status` lists nothing), bring the
   Stack's objects into the clone, and apply with a three-way merge:

   ```sh
   git -C STACK_REPOSITORY diff --binary OLD_COMMIT NEW_COMMIT --relative=skills/monkeymaxxing-stack/systems_repository_template > VERSION_CHANGE_DIRECTORY/new_version.patch
   git fetch STACK_REPOSITORY OLD_COMMIT NEW_COMMIT    # only brings in objects: no branch or remote changes
   git apply --3way VERSION_CHANGE_DIRECTORY/new_version.patch
   ```

   `git apply --3way` exits with 1 both for a conflict and for a refusal, so
   read what it printed and what `git status` shows:

   - **A conflict** prints `Applied patch ... with conflicts`. Conflict
     markers are now in those files, and the rest of the patch is applied.
     Merge the markers by hand. Do not run `--reject`: the patch is already
     applied, and a second apply would repeat it.
   - **A refusal** prints `error:` (such as `repository lacks the necessary
     blob`, or an older Git) and leaves `git status` clean, because it
     changed nothing. Only then fall back to `--reject`. It applies every
     part that fits and leaves each part that doesn't in a `.rej` file
     beside its file:

   ```sh
   git apply --reject VERSION_CHANGE_DIRECTORY/new_version.patch
   ```

   A conflict or a `.rej` part that lands inside a custom extension block
   is a sign the block's boundary lines changed. Merge it by hand with the
   team's lines kept, and restore the three boundary comment lines above
   and below the block.

   **Check:** every conflict marker and every `.rej` file is merged by
   hand; step 5 commits with no `.rej` file and no conflict marker left;
   `git diff HEAD | grep -nE '^-.*[Cc]ustom'` prints no line you did not
   remove on purpose, so each custom extension is still there.
3. **The checklist:**
   - Add each new item missing from
     `monkeymaxxing_stack_checklist.yml` as `open`.
     Set each new item's `waits_for` to say that the item came with the new
     version and what must happen first. A new item of
     `growth_and_improvement_items` gets `state: waits_for_its_trigger` and
     the template's `trigger`.
   - If the new version widened a `done` item's `verification`, so that the
     new verification checks more than what passed, set the item to `open`
     again.
     Keep the new verification.
     Remove the item's `verified_at` and `last_result`, which the Git history
     keeps.
     Set `waits_for` to say which added verification must pass first.
   - Set `stack_version` to the value in the new template's
     `monkeymaxxing_stack_checklist.yml`.
     Set `stack_commit` to `NEW_COMMIT`.

   **Check:** `mmx validate` passes in step 5.
4. **Check the new parts:**
   - The patch can add the template's example app `shop`, `example.com`,
     `203.0.113.`, or a placeholder of zeros.
     Replace each new example value with the system's actual value, as
     the initial setup replaced the earlier example values.
     A comment can keep an example value.
     The following command lists new lines with example values:
     `grep -nE '^\+.*(shop|example|203\.0\.113\.|0{40})' VERSION_CHANGE_DIRECTORY/new_version.patch`
   - A new setting for a part this system doesn't use yet takes the value
     its comment gives for that, such as `""` for `backups.uploads_bucket`
     and `backups.uploads_r2_s3_endpoint` while `backups.uploads_backup_runs_on`
     is `[]`.
   - After the push in step 5, before its preview,
     `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage`
     exits 0: the vault defines every key the new files read, except those
     the command marks "secret key not needed with the selected inventory".
     For each key it lists as `not defined`, the person types
     `ssh desk01-secrets` and a phone code. The command asks for each
     missing key, and commits and pushes the vault, as
     [Secrets in chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#secrets) says.
   - The apps' files from the stack:
     `git -C STACK_REPOSITORY diff --stat OLD_COMMIT NEW_COMMIT -- skills/monkeymaxxing-stack/files_for_your_app`
     lists changed app files, such as `pg_with_multiple_database_servers.mjs`.
     For each listed file an app copied, you, the coding agent, copy the
     update into the app's repository.
     The person reviews the updated app file.

   **Check:** each check in the list above passes, the `secrets usage`
   check after the push in step 5.
5. **One commit** in the systems repository, except for a separate MMX pin
   when required below.

   When the new version pins a newer MMX, commit the MMX pin alone on the
   old version's files.
   - The MMX pin is `stack_software.mmx` in `mmx_project_settings.yml`.
   - Push the MMX pin's commit when the person asks.
   - Wait for `util01`'s run of the MMX pin's commit to pass before pushing
     the stack version's commit.
   - The laptop needs the new MMX before `mmx validate`, and the desk
     needs it before the dryrun of the version's files. The desk gets it
     from a desk review: the person types `ssh desk01-review` and a phone
     code, after `util01`'s run of the pin passed.

   Then the stack version's commit:
   - Commit the stack version's changes with no `.rej` file left.
     The commit message must name the old and new stack versions and the new
     items.
   - Run `mmx validate` and show the person the commit's changes.
   - After approval, publish the commit, as
     [Making a change](../AGENTS.md#making-a-change) says. Check the vault
     keys with
     `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage` (step 4),
     then preview the pushed commit with
     `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers dryrun every_server --connection ssh_only` and show the results.
   - When the preview shows only the expected changes, run MMX on `util01` to apply the version.
     Applying the version can restart services, so run MMX in a quiet hour, an
     hour that the person picks when the apps have few users,
     after you check [What each version changes](#what-each-version-changes).

   Reason: the button previews only the pushed `main`, and any desk's next run applies a pushed commit,
   so the person approves before the push.
   **Check:** `util01`'s run of the version's commit passes.
6. **One-time steps:** once `util01`'s run of the version's commit passed,
   and when the person asks, do each one-time step that
   [What each version changes](#what-each-version-changes), in the new
   version of `operating_procedures/upgrade_to_a_new_stack_version.md`,
   names for a version newer than `OLD_VERSION`, such as a one-time playbook that removes files an older version wrote.
   **Check:** each one-time step's own check passes.

### If something is different

- **The pin and the version's files share one commit.** When the version's
  files need the newer MMX, a commit that holds both the pin and the files
  fails: `util01`'s old MMX refuses the new files at once (exit status 4)
  and installs nothing, the new MMX included (the systems repository's
  [add_or_update_a_program_from_outside_the_distribution.md](add_or_update_a_program_from_outside_the_distribution.md#updating-a-program-from-outside-the-distribution), "Updating a program from outside the distribution").
  Split the commit as step 5 says.
- **`secrets usage` lists a key as `not defined`.** The person types
  `ssh desk01-secrets`, as step 4 says, before the preview.

## What each version changes

Later Stack releases add their one-time steps here, such as a one-time
playbook that removes files an older version wrote. Each entry names the
Stack version that brought its change, such as `0.2.0`. An entry
applies when its version is newer than `OLD_VERSION`, the system's
`stack_version` before the upgrade. Compare versions number by number,
so `0.10.0` is newer than `0.9.1`;
`printf '%s\n' OLD_VERSION ENTRY_VERSION | sort -V | tail -n 1` prints the
newer one.

Before you push, read each entry that applies: an entry can say what the
version restarts, or what to do before the push. After `util01`'s run of
the version's commit passed, do each entry's one-time step, as step 6 of
[A new version](#a-new-version) says.

Apply each configuration change as [Making a change](../AGENTS.md#making-a-change)
says: a push alone changes no server, so run `every_server` or the playbook the step names.

### 0.7.0: a quiet system that maintains itself

Before the push, tell the person what the upgrade run changes, in these
words or close to them:

- **The automatic weekly maintenance turns on.** At the start of the
  maintenance window (`maintenance_window` in `mmx_project_settings.yml`;
  the new template's default is Wednesday 03:00 UTC for 120 minutes, and
  an upgrade keeps the team's own window), `util01` installs updates and
  reboots every server whose restart the users do not see, then itself,
  and each desk reboots itself when nobody uses it. A production pool's
  only server, such as `app001` alone or `db01` alone, never restarts by
  itself: MMWatchdog reminds after 30 days, and a person restarts it in
  the window. A team that wants no automatic restarts sets
  `automatic_weekly_maintenance: false` before the push.
- **The phone stays quiet for planned work.** Planned alert pauses send no
  notice, and `util01`'s own reboot is reported at `info`.
- **No weekly review.** No checklist item expires any more, and the
  review runs only when the person asks ("Review my system"), such as at
  an optional monthly check-in.
- **Secrets are replaced when someone leaves or a secret may have leaked,**
  not every year
  ([Why rotation follows events](rotate_a_secret.md#why-rotation-follows-events)).
- **`util01` refuses a push that adds a secret,** with gitleaks. Commits
  already on `main` are not checked again.

After the runs, ask the person to run `ssh desk01-review` once on each
desk: the version changes the lock-out button, which no longer applies
MMHotline's settings, adds the desk's quiet-hour reboot, and adds the
secret check to `publish-branch-to-main`. The review also removes the
desk's earlier copy of the MMHotline settings. From then on, a change of
`mmhotline_settings.yml` needs no desk review.

### 0.6.0: alerts that ask for action

Before the push, tell the person what the upgrade run changes, in these
words or close to them:

- Every warning now waits up to 15 minutes while the triage agent looks,
  so the person hears the agent's verdict instead of the raw warning. A
  team that changed `warn_waits_for_the_triage_agent_minutes` keeps its
  value, now from 0 to 30.
- MMWatchdog sends one alert for one finding across all servers. During
  the run, each server's open security-update warning closes once ("maybe
  not fixed") and opens again as one warning for each Debian release whose
  servers wait for updates; a newly waiting update sends no new alert.
- The triage agent has a run limit, 50 runs in 24 hours, which stops only
  agent runs, never alerts
  ([Change the triage agent's run limit](change_the_triage_agent_run_limit.md)).
- A routine release of the Stack or of a pinned program no longer shows
  anywhere; only a Stack release that fixes an exploited flaw warns.

The upgrade is two runs instead of one, `util01` first. Reason: MMWatchdog
0.2.0 on `util01`, the fleet hub, accepts reports from servers still on
0.1.x, but a hub still on 0.1.x refuses those of servers already on
0.2.0, which then alert on their own, one alert per server, and after
3 minutes say at SOS that they cannot reach the hub.

1. Just before the first run, check on every server except `util01` that
   `sudo mmwatchdog status --json` shows `delivery.queued_notifications`
   at `0`. A queued alert sent after the upgrade can leave its incident
   open in MMHotline, which then starts no new escalation for that check.
   Wait for a server that shows more, then check again.
2. Run `./server_management_scripts/run_mmx_on_util01 run every_server --limit util_server`.
3. Then run `every_server` as usual for every other server.

After the runs, ask the person to run `ssh desk01-review`: the version
changes `mmhotline_settings.yml` and the triage user's sudo lines on
`util01`, which reach the lock-out button only after the desk review.
