# Restore an uploaded file

**When to use this page:** a person or the app notices a file that is missing or wrong; or, after a break-in, an intruder
deleted or overwrote many of an app's uploaded files.

**What this page does:** a one-time playbook on `util01` copies the files
back from the uploads' B2 backup into the app's R2 bucket, as the backup
held the files at a time before the change.

**Who acts:** the coding agent writes, validates, pushes and runs each
one-time playbook ([Where the commands run](#before-you-start)). The person
says when the file changed, approves the restore, and confirms the files
in the app. The person runs `mmx secrets edit` in the person's own terminal,
to put the paths of [Restore listed files](#restore-listed-files) in the vault
and to delete them afterwards, and commits and pushes `secrets_vault.age`
there each time: the coding agent never opens the vault, and the person
commits the vault from the person's repository
([The rules](../AGENTS.md#the-rules)). The triage agent hands over to a
person on signs of data loss and does not follow this page
([When to hand over](../triage_agent_rules.md#when-to-hand-over)).

**Terms:** this page uses the Stack's terms, such as R2, B2, uploads' copy,
vault, one-time playbook, dryrun and Object Lock.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

## Find your situation

| Situation | Follow |
| --- | --- |
| One file or a few named files are missing or wrong | [Restore listed files](#restore-listed-files) |
| A break-in, or a mistake that deleted or overwrote many files | [Restore all of an app's uploaded files](#restore-all-of-an-apps-uploaded-files) |

## Before you start

- **Which app:** the person names the app, or MMWatchdog's warning names
  it: the line of
  `uploads_backup/the_latest_copy_hid_no_unusual_share_of_an_apps_files`
  names the app and the two numbers (`mmwatchdog_checks/util_server.yml`).
- **What can come back:** a file deleted or overwritten in R2 comes back, as the last copy before the change held the file,
  for `backups.keep_prior_file_versions_in_buckets_for_days` after the change (14 days in the template).
  A file deleted or overwritten longer ago cannot come back, and a file uploaded after the last copy before the change has no copy.

  Tell the person this time limit first, with the setting's value in `mmx_project_settings.yml`.
- **Where the commands run.** Normally the coding agent runs MMX on `util01` with
  `./server_management_scripts/run_mmx_on_util01`. During a lock-out
  ([Respond to a break-in](respond_to_a_break_in.md)), the coding agent runs the same playbook from the desk that keeps access
  with its MMX button: `sudo -n -u servers-mmx run-mmx-on-the-servers dryrun NAME --connection ssh_only`, and `run` in place of `dryrun`.
  Both reach `util01`, which holds rclone and the copy's settings.
- **The restore time** is in UTC, written as `2026-11-03T14:00:00Z`: rclone's `--b2-version-at` accepts no other form.
  For a time in the person's own time zone, run on the desk, which runs
  Debian and GNU `date`:

  ```sh
  date -u -d '2026-11-03 15:00 CET' '+%Y-%m-%dT%H:%M:00Z'
  # prints 2026-11-03T14:00:00Z
  ```

## Restore listed files

For one file or a few named files.

1. **Find the file's path in the app's bucket.**
   The app's records name each upload's path.
   If the app uses Active Storage, Rails' upload library, the path is in
   `active_storage_blobs.key`.
   **Check:** none here: step 8's playbook first counts the requested paths
   present in the backup, and copies nothing for a wrong path.
2. **Find a time before the change.**
   Use the app's logs or ask the person who noticed to find when the file changed.
   Write the time in UTC, as [Before you start](#before-you-start) shows.
   **Check:** the file was uploaded before the latest passed copy, or it
   has no copy: `ssh -F ssh/config root@10.20.0.1 cat /var/lib/uploads_backup/latest_passed_copy`
   prints the start time of the latest copy that passed for every app
   (`roles/uploads_backup/files/copy_uploads_to_the_backup_bucket`). The
   copy runs every `backups.uploads_copy_every_hours` hours. Step 8's
   playbook counts the requested paths present in the backup at the
   restore time, and copies nothing for a wrong time.
3. **Put paths in the vault, never in Git.** A path may name a customer.
   MMX keeps each run's command, variables, and output in its controller history.
   The person opens `mmx secrets edit` in the person's own terminal and sets `uploaded_file_paths_to_restore` to
   paths within the app's R2 bucket, one per line.
   Leave out the R2 bucket's name, and the folder named after the app that
   the B2 backup puts in front of each path. The vault entry, in the
   editor that `mmx secrets edit` opens, looks like this; it is not part
   of the playbook in step 5:

   ```yaml
   uploaded_file_paths_to_restore: |
     variants/ab/cd/abcd1234
   ```

   Then the person commits and pushes `secrets_vault.age` from the
   person's repository, in the person's own terminal.
   **Check:** none here: the coding agent never opens the vault, and step
   8's count finds a missing or wrong path.
4. **Create the one-time playbook on `util01`:**
   `mmx new-one-time-playbook restore_uploaded_files_of_shop_on_util01`.
   **Check:** the generated file is under `one_time_playbooks/`.
5. **Copy the requested uploads back into the app's R2 bucket, with the
   playbook below.**
   Replace the example `fleet_stages` section in the generated file with the
   section below, the playbook, which holds the
   `restore_uploaded_files_of_shop` fleet stage.
   The example restores files for `shop` as the backup held the files at
   `2026-11-03T14:00:00Z`:

   - Replace `shop` and `SHOP` in the example's names and references with
     your app's name and uppercase name.
   - Use the generated playbook's date in the marker path and in the later
     playbook commands.
   - Set `READ_BACKUP_AS_OF` to the restore time from step 2.
   - `util01`'s own R2 key can only read. To write the restored files, the
     stage gives rclone the app's R2 key from the vault. Use the two
     names the app's `production_uploads_r2_key_variables` gives, with
     the app's name in front, in the example `shop_R2_ACCESS_KEY_ID` and
     `shop_R2_SECRET_ACCESS_KEY`.

   ```yaml
   fleet_stages:
     - id: restore_uploaded_files_of_shop
       nodes: util01
       node_tasks:
         - id: copy_the_files_back_from_the_uploads_backup
           shell:
             # The paths go in a list, which rclone reads as written.
             script: |
               set -eu
               list=$(mktemp)
               held=$(mktemp)
               trap 'rm -f "$list" "$held"' EXIT
               printf '%s\n' "$UPLOADED_FILE_PATHS" | grep . > "$list"
               rclone --config "$RCLONE_SETTINGS" lsf --recursive --files-only --b2-version-at "$READ_BACKUP_AS_OF" \
                 --files-from-raw "$list" "uploads_backup:$BACKUP_BUCKET/shop" > "$held"
               held_count=$(($(wc -l < "$held")))
               wanted_count=$(($(wc -l < "$list")))
               if [ "$held_count" -ne "$wanted_count" ]; then
                 echo "the backup held $held_count of the $wanted_count files at $READ_BACKUP_AS_OF; nothing was copied" >&2
                 exit 1
               fi
               rclone --config "$RCLONE_SETTINGS" copy --b2-version-at "$READ_BACKUP_AS_OF" \
                 --files-from-raw "$list" "uploads_backup:$BACKUP_BUCKET/shop" "shop_uploads:$UPLOADS_BUCKET"
             run_as_user_account: mmhotline
             run_only_once_marker_file: /var/lib/mmx/commands_run_once/2026-11-03_restore_uploaded_files_of_shop
             env:
               UPLOADED_FILE_PATHS: "{{ .secrets.uploaded_file_paths_to_restore }}"
               READ_BACKUP_AS_OF: "2026-11-03T14:00:00Z"
               RCLONE_SETTINGS: /var/lib/mmhotline/uploads_backup_rclone.conf
               BACKUP_BUCKET: "{{ .vars.backups.uploads_bucket }}"
               UPLOADS_BUCKET: "{{ .vars.apps.shop.production_uploads_r2_bucket }}"
               # A second R2 remote for rclone, with the app's own key, which can write.
               RCLONE_CONFIG_SHOP_UPLOADS_TYPE: s3
               RCLONE_CONFIG_SHOP_UPLOADS_PROVIDER: Cloudflare
               RCLONE_CONFIG_SHOP_UPLOADS_REGION: auto
               RCLONE_CONFIG_SHOP_UPLOADS_ENDPOINT: "{{ .vars.backups.uploads_r2_s3_endpoint }}"
               RCLONE_CONFIG_SHOP_UPLOADS_NO_CHECK_BUCKET: "true"
               RCLONE_CONFIG_SHOP_UPLOADS_ACCESS_KEY_ID: "{{ .secrets.shop_R2_ACCESS_KEY_ID }}"
               RCLONE_CONFIG_SHOP_UPLOADS_SECRET_ACCESS_KEY: "{{ .secrets.shop_R2_SECRET_ACCESS_KEY }}"
   ```

   The task reads secrets, so MMX hides its whole result. Neither the paths
   nor rclone's output reach the MMX result. First, the task counts the
   requested paths present in the backup at the restore time in
   `READ_BACKUP_AS_OF`. The restore task copies nothing unless the backup
   held every requested file.
   **Check:** step 6's `mmx validate`.
6. **Validate, commit and push:**
   `mmx validate 2026-11-03_restore_uploaded_files_of_shop_on_util01`,
   pull the person's vault commit with the synchronization snippet of
   [Making a change](../AGENTS.md#making-a-change), commit the generated
   one-time playbook, push.
   **Check:** `mmx validate` passes, and the push succeeds.
7. **Get the person's approval when the restore overwrites a live upload.**
   **Check:** the person approves, or no requested file is still in R2.
8. **Run the one-time playbook:**
   `./server_management_scripts/run_mmx_on_util01 run 2026-11-03_restore_uploaded_files_of_shop_on_util01`.
   **Check:** the run passes.
   If the task fails, the reason names a private file on `util01`:
   `/run/mmx/private/...-hidden-details-of-failed-node-tasks.txt`.
   Root can read the private failure-details file for 72 hours.
   The private failure-details file contains the details hidden from the
   summary, such as "the backup held 0 of the 1 files
   at 2026-11-03T14:00:00Z".
   A message reporting fewer backed-up files than requested means the
   backup lacked a requested upload at the restore time in
   `READ_BACKUP_AS_OF`, or a path or the time is wrong.
   The requested upload arrived after the preceding copy, or
   changed longer ago than `backups.keep_prior_file_versions_in_buckets_for_days`.
9. **Verify:** the app shows each file again, and the person confirms that
   each overwritten file has its contents from before the change.
   **Check:** the person confirms.
10. **The person deletes `uploaded_file_paths_to_restore` from the vault**
    (`mmx secrets edit`, in the person's own terminal), then commits and
    pushes the vault change.
    **Check:** none here: the coding agent never opens the vault.
11. **Complete the one-time playbook:**
    run `mmx complete-one-time-playbook 2026-11-03_restore_uploaded_files_of_shop_on_util01`,
    pull the person's vault commit, commit the completed one-time playbook,
    and push.
    **Check:** the playbook is in `one_time_playbooks/completed/`.

## Restore all of an app's uploaded files

For a break-in, or a mistake that deleted or overwrote many files: every file of one app comes back
as the backup held the app's files at a chosen time. After a break-in, use the same time as the database restore
([Bring the whole database back to a chosen minute](recover_when_every_database_server_is_lost.md#bring-the-whole-database-back-to-a-chosen-minute)),
in this file's form, and run the restore after the break-in procedure replaced the app's own R2 key,
so that the intruder's copy of the old key can no longer delete the restored files.

**Files in R2 that the backup did not hold at the chosen time** are the files uploaded after the last copy before that time:
customers' uploads since then, and files the intruder added. The restore either keeps them or deletes them,
by `FILES_ADDED_AFTER_THE_TIME` in the playbook below:

- `keep` (recommended): rclone `copy`. The restore writes back each deleted or changed file and deletes nothing.
  Reason: a customer's file uploaded after the chosen time may have no copy anywhere else, and a file kept by mistake
  can be deleted later, while a file deleted by mistake may be gone for good.
- `delete`: rclone `sync`. R2 then holds exactly what the backup held at the chosen time.
  Use `delete` only when the database went back to the same time, so no record refers to the later files,
  and the person wants the intruder's added files gone.

A file that a customer deleted on purpose after the chosen time comes back too; the app's records decide whether the app shows it.

1. **Choose the time and the rule** with the person: the chosen time, and `keep` or `delete`.
   **Check:** none here: the dry run in step 5 shows what the choice changes.
2. **Create the one-time playbook:** `mmx new-one-time-playbook restore_all_uploaded_files_of_shop_on_util01`.
   **Check:** the generated file is under `one_time_playbooks/`.
3. **Write the playbook.**
   Replace the example `fleet_stages` section with the section below. Replace `shop` and `SHOP` with your app's
   name and uppercase name, the date in the marker path with the generated playbook's date,
   `RESTORE_AS_OF` with the chosen time, and `FILES_ADDED_AFTER_THE_TIME` with the chosen rule, in both tasks.

   The first task compares the backup at the chosen time with R2 and prints only counts, never a path.
   It uses `util01`'s own settings, whose R2 key can only read, so its result stays visible.
   It refuses when the backup held no file of the app at the chosen time, such as for a wrong time or app name:
   with `delete`, such a restore would empty the app's bucket.
   The second task writes with the app's own R2 key from the vault, so MMX hides its result.

   ```yaml
   fleet_stages:
     - id: restore_all_uploaded_files_of_shop
       nodes: util01
       node_tasks:
         - id: count_what_the_restore_changes
           shell:
             script: bash -c "$COUNT_WHAT_THE_RESTORE_CHANGES"
             dryrun: bash -c "$COUNT_WHAT_THE_RESTORE_CHANGES"
             run_as_user_account: mmhotline
             changed_when: false
             env:
               # The same check runs in a dryrun and in a run.
               COUNT_WHAT_THE_RESTORE_CHANGES: |
                 set -euo pipefail
                 case "$FILES_ADDED_AFTER_THE_TIME" in
                   keep) command=copy ;;
                   delete) command=sync ;;
                   *) echo "FILES_ADDED_AFTER_THE_TIME is \"$FILES_ADDED_AFTER_THE_TIME\": use keep or delete; nothing was restored" >&2; exit 1 ;;
                 esac
                 # The comparison's report names each file, so only its counts leave this task.
                 status=0
                 report=$(rclone --config "$RCLONE_SETTINGS" "$command" --dry-run --quiet --use-server-modtime \
                   --b2-version-at "$RESTORE_AS_OF" --combined - \
                   "uploads_backup:$BACKUP_BUCKET/shop" "uploads_r2:$UPLOADS_BUCKET" 2>/dev/null) || status=$?
                 if [ "$status" -ne 0 ]; then
                   echo "rclone exited $status while comparing the backup with R2; nothing was restored" >&2
                   exit 1
                 fi
                 set -- $(printf '%s\n' "$report" | awk '
                   $1 == "+" { missing++ } $1 == "*" { changed++ } $1 == "=" { same++ } $1 == "-" { later++ }
                   END { print missing + 0, changed + 0, same + 0, later + 0 }')
                 missing=$1 changed=$2 same=$3 later=$4
                 held=$((missing + changed + same))
                 if [ "$held" -eq 0 ]; then
                   echo "the backup held no file of shop at $RESTORE_AS_OF: check the time and the app; nothing was restored" >&2
                   exit 1
                 fi
                 if [ "$FILES_ADDED_AFTER_THE_TIME" = delete ]; then what=deletes; else what=keeps; fi
                 echo "the backup held $held files of shop at $RESTORE_AS_OF"
                 echo "the restore writes $((missing + changed)) files into R2: $missing missing from R2 and $changed changed since"
                 echo "$same files are the same in R2 and stay as they are"
                 echo "$later files in R2 are not in the backup at that time: the restore $what them"
               RESTORE_AS_OF: "2026-11-03T14:00:00Z"
               FILES_ADDED_AFTER_THE_TIME: keep
               RCLONE_SETTINGS: /var/lib/mmhotline/uploads_backup_rclone.conf
               BACKUP_BUCKET: "{{ .vars.backups.uploads_bucket }}"
               UPLOADS_BUCKET: "{{ .vars.apps.shop.production_uploads_r2_bucket }}"
         - id: copy_every_file_back_from_the_uploads_backup
           shell:
             script: |
               set -euo pipefail
               case "$FILES_ADDED_AFTER_THE_TIME" in keep) command=copy ;; delete) command=sync ;; *) exit 1 ;; esac
               rclone --config "$RCLONE_SETTINGS" "$command" --use-server-modtime --b2-version-at "$RESTORE_AS_OF" \
                 "uploads_backup:$BACKUP_BUCKET/shop" "shop_uploads:$UPLOADS_BUCKET"
             dryrun: printf 'would copy the files of shop back into R2, as the backup held them at %s\n' "$RESTORE_AS_OF"
             run_as_user_account: mmhotline
             run_only_once_marker_file: /var/lib/mmx/commands_run_once/2026-11-03_restore_all_uploaded_files_of_shop
             env:
               RESTORE_AS_OF: "2026-11-03T14:00:00Z"
               FILES_ADDED_AFTER_THE_TIME: keep
               RCLONE_SETTINGS: /var/lib/mmhotline/uploads_backup_rclone.conf
               BACKUP_BUCKET: "{{ .vars.backups.uploads_bucket }}"
               UPLOADS_BUCKET: "{{ .vars.apps.shop.production_uploads_r2_bucket }}"
               # A second R2 remote for rclone, with the app's own key, which can write.
               RCLONE_CONFIG_SHOP_UPLOADS_TYPE: s3
               RCLONE_CONFIG_SHOP_UPLOADS_PROVIDER: Cloudflare
               RCLONE_CONFIG_SHOP_UPLOADS_REGION: auto
               RCLONE_CONFIG_SHOP_UPLOADS_ENDPOINT: "{{ .vars.backups.uploads_r2_s3_endpoint }}"
               RCLONE_CONFIG_SHOP_UPLOADS_NO_CHECK_BUCKET: "true"
               RCLONE_CONFIG_SHOP_UPLOADS_ACCESS_KEY_ID: "{{ .secrets.shop_R2_ACCESS_KEY_ID }}"
               RCLONE_CONFIG_SHOP_UPLOADS_SECRET_ACCESS_KEY: "{{ .secrets.shop_R2_SECRET_ACCESS_KEY }}"
   ```

   **Check:** step 4's `mmx validate`.
4. **Validate, commit and push:** run `mmx validate 2026-11-03_restore_all_uploaded_files_of_shop_on_util01`, commit and push the
   one-time playbook.
   **Check:** `mmx validate` passes, and the push succeeds.
5. **The dry run.** Run `./server_management_scripts/run_mmx_on_util01 dryrun 2026-11-03_restore_all_uploaded_files_of_shop_on_util01`.
   **Check:** the first task's result prints four lines, such as:

   ```text
   the backup held 1840 files of shop at 2026-11-03T14:00:00Z
   the restore writes 1838 files into R2: 1838 missing from R2 and 0 changed since
   2 files are the same in R2 and stay as they are
   12 files in R2 are not in the backup at that time: the restore keeps them
   ```

   A number of files far from what the app holds means a wrong time or app: correct the playbook and run the dry run again.
   The app's own records give the number it holds, such as a count of
   `active_storage_blobs` for an app that uses Active Storage, read on the
   primary as a count only.
6. **Tell the person the four numbers** in plain words, with the time limit above, and ask for approval.
   **Check:** the person approves.
7. **The restore.** After the person approves,
   `./server_management_scripts/run_mmx_on_util01 run 2026-11-03_restore_all_uploaded_files_of_shop_on_util01`.
   The run counts again, then copies. A large bucket takes as long as a first copy, which can be hours.
   **Check:** the run passes.
   If the copy task fails, its reason is in the private failure-details file, as in [Restore listed files](#restore-listed-files).
   The marker file stops a second run of the same playbook, so to restore again, such as after a fix,
   write a new one-time playbook with a new name.
8. **Verify:** run the dry run again.
   **Check:** it must print "0 missing from R2". A count of changed files above 0 is expected: the count of changed files then equals
   the files this restore wrote, because R2 gives each restored file a new upload time, and the count compares
   upload times; it does not mean the restore failed.
9. **Ask the person to open a few
   files in the app that the intruder or the mistake had deleted or changed.**
   **Check:** the person confirms the files.
10. **Complete the one-time playbook:** run
    `mmx complete-one-time-playbook 2026-11-03_restore_all_uploaded_files_of_shop_on_util01`, commit, and push.
    **Check:** the playbook is in `one_time_playbooks/completed/`.

## How the backup works

Each app keeps uploaded files in its R2 bucket, named by
`production_uploads_r2_bucket` in `mmx_project_settings.yml`.
Every `backups.uploads_copy_every_hours` hours, starting one hour after `nightly_work_starts_at`
(every 24 hours, at 02:00 UTC, in the template), `util01` copies each app's bucket to the
uploads' B2 bucket, `backups.uploads_bucket` in `mmx_project_settings.yml`.
Inside the B2 bucket, each app's folder uses the app's name under `apps`
in `mmx_project_settings.yml`.
The copy uses `util01`'s R2 key, which can only read, and a B2
key that cannot delete. A file deleted from R2 is hidden in B2, never deleted.
A restore writes into R2 with the app's own R2 key from the vault.

A normal copy uploads new and changed files. A full copy uploads
unchanged files again too.
When the last full copy is more than 6 days old,
`copy_uploads_to_the_backup_bucket` on `util01` makes another full copy.
Copying every file again keeps each file's newest backup under the B2
bucket's Object Lock, which prevents deletion for the lock length in `backups.lock_backups_against_deletion_for_days`.

Read the copy's log with
`journalctl -u copy_uploads_to_the_backup_bucket` on `util01`.
MMWatchdog warns when no copy has passed for `backups.uploads_copy_every_hours` plus 2 hours,
when no full copy has passed for 8 days, and when one copy hid an unusually large share of an app's files
(`backups.warn_when_one_uploads_copy_hides_more_than_percent_of_an_apps_files`).
The weekly restore drill reads one file per app from the backup and compares it with the R2 copy.
