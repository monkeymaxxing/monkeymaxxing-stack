# Turn on nightly backups of uploaded files

**When to use this page:** an app starts keeping uploaded files, for the
first app that keeps uploads or for a later one.

**What this page does:** `util01` copies each app's uploaded files from
the app's R2 bucket to a locked B2 bucket, with rclone.

**Who acts:** the coding agent edits and pushes the settings, checks the
vault's keys, and runs `every_server`. Only the person runs
`set-up-outside-services`, in the person's own desk terminal (steps 2
and 3), because the command makes keys and saves them in the vault.

## Before you start

- **While no app keeps uploads, `backups.uploads_backup_runs_on` is `[]`.**
  No MMX fleet stage copies uploads. A run needs neither the uploads'
  backup bucket nor the four keys for the uploads' copy.
- **Follow the steps in their order.** MMX loads all required secrets
  before changing anything. If the vault lacks a required key, the run
  stops immediately for every server. So the bucket and keys come first,
  and the setting that turns the copy on comes last.
- **A later app with uploads** needs only step 3 and the app's settings
  of step 1: see [If something is different](#if-something-is-different).

## Turning the uploads' copy on

For the first app that keeps uploads, prepare the bucket, keys, and settings in this order:

1. **Name the bucket and the app's settings** in `mmx_project_settings.yml`,
   committed and pushed, then pulled into the person's repository on the desk.
   - Under `vars.apps`, set the app's `production_uploads_r2_bucket` to the
     name of the app's production R2 bucket.
   - Set the app's `production_uploads_r2_key_variables` to the two names
     in its `secrets_from_vault` that hold its R2 key.
   - With `staging01`, also set the app's `staging_uploads_r2_bucket` to
     its own staging bucket. Add the two `staging_` keys to the staging
     `app_secrets` in `playbooks/every_server.yml`. Nothing copies the
     staging bucket to B2.
   - Set `backups.uploads_bucket` to a name for the uploads' B2 bucket.
   - Set `backups.uploads_r2_s3_endpoint` to the Cloudflare account's R2
     address, `https://CLOUDFLARE_ACCOUNT_ID.r2.cloudflarestorage.com`,
     using your account's ID.
   - Keep `backups.uploads_backup_runs_on: []` for now.

   **Check:** `git log -1` in the person's repository on the desk shows
   the settings' commit.
2. **The person runs `set-up-outside-services backblaze`**, in the person's
   own desk terminal, as [chapter 4 (set up your accounts and lock your desk)](../initial_setup/04_set_up_your_accounts_and_lock_your_desk.md#chapter-4-set-up-your-accounts-and-lock-your-desk)
   describes. The command:
   - creates the uploads' bucket, locked for the lock length in
     `backups.lock_backups_against_deletion_for_days`, with the lifecycle
     rule that keeps prior versions for
     `backups.keep_prior_file_versions_in_buckets_for_days`;
   - checks the lock;
   - saves `util01`'s uploads key, which cannot delete, as
     `uploads_backup_b2_write_key_id` and
     `uploads_backup_b2_write_application_key`.

   Prior versions are the copies B2 keeps when a file is overwritten or
   hidden after deletion from R2. Deleted or overwritten uploads remain
   recoverable for `backups.keep_prior_file_versions_in_buckets_for_days`
   without keeping old copies forever.
   **Check:** the command checks the lock itself; step 4 checks the keys.
3. **The person runs `set-up-outside-services cloudflare`.** The command:
   - creates the app's R2 bucket when missing;
   - saves the app's own R2 key under the app's two names;
   - saves `util01`'s read-only R2 key for every app's uploads bucket, as
     `uploads_r2_read_only_access_key_id` and
     `uploads_r2_read_only_secret_access_key`.

   The command commits and pushes the vault itself, signed.
   **Check:** step 4 checks the keys.
4. **Turn the copy on** in `mmx_project_settings.yml`:
   set `backups.uploads_backup_runs_on: [util_server]`.
   Add rclone's entry back to `software_outside_the_distribution.yml` if
   the entry was deleted while no uploads were backed up.
   Commit and push the setting.

   **Check:** `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage uploads_backup_b2_write_key_id`
   exits 0. Then run the same command for each key:
   `uploads_r2_read_only_access_key_id`,
   `uploads_r2_read_only_secret_access_key`, and
   `uploads_backup_b2_write_application_key`.
   Each command must exit 0, confirming that the vault defines the key.
5. **Run `every_server` on `util01`.** The run installs rclone and the copy job.
   rclone copies the uploaded files from the app's R2 bucket to B2.
   Until a copy passes, each run starts the copy in the background.
   A copy already running continues without a second copy starting.
   A large first copy can take hours, without holding up deployments.

   **Check:** inspect `copy_uploads_to_the_backup_bucket.service` on
   `util01` (`journalctl -u copy_uploads_to_the_backup_bucket`), and wait
   for the first copy to pass before verification.
   MMWatchdog warns after the uploads' backup checks have failed for 2 hours.
6. **Verify** with the `verification` of the checklist item
   `uploads_copied_to_the_locked_bucket_every_night`, then mark the item done.
   **Check:** the item's `verification` passes.

## If something is different

- **The run refuses an app's uploads.** If an app has a
  `production_uploads_r2_bucket` while `backups.uploads_backup_runs_on`
  is `[]`, the run refuses it.
  The run refuses the app's settings in the last MMX fleet stages, after
  every server's other work. Finish steps 2 to 4.
- **A later app with uploads.** The person runs
  `set-up-outside-services cloudflare` again before the app's settings
  reach `util01`. The command makes the app's own key and adds the app's
  bucket to `util01`'s read-only key, which keeps its value.
  An app added after the first app with uploads needs no further backup setup.
- **Restore files from the uploads' backup:** follow
  [Restore an uploaded file](restore_an_uploaded_file.md).

### The uploads key check

`util01`'s B2 key must not delete file versions. The check reads the key
from `util01`'s installed rclone settings, signs in to B2 with the key,
and prints only the key's bucket and capabilities, never the key:

```sh
# This systems desk, in the systems repository:
ssh -F ssh/config root@10.20.0.1 bash -s <<'CHECK'
set -o pipefail
awk -F ' = ' '
  /^\[/ { uploads_backup = ($0 == "[uploads_backup]") }
  uploads_backup && $1 == "account" { key_id = $2 }
  uploads_backup && $1 == "key" { application_key = $2 }
  END { if (key_id == "" || application_key == "") exit 1
        printf "user = \"%s:%s\"\n", key_id, application_key }
' /var/lib/mmhotline/uploads_backup_rclone.conf |
  curl -fsS --config - https://api.backblazeb2.com/b2api/v4/b2_authorize_account |
  jq -e '.apiInfo.storageApi.allowed | {buckets, capabilities} |
    if (.buckets | length) == 1 and
       (.capabilities | sort) == (["listBuckets","listFiles","readFiles","writeFiles"] | sort)
    then . else error("The uploads key must allow one bucket and exactly the four copy capabilities") end'
CHECK
```

The check passes when it prints one bucket, named as `backups.uploads_bucket`
in `mmx_project_settings.yml`, and the four capabilities `listBuckets`,
`listFiles`, `readFiles`, and `writeFiles`.
