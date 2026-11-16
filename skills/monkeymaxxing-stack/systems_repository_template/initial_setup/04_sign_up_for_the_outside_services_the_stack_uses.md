# Chapter 4: Sign up for the outside services the Stack uses

**When:** after chapter 3 (get your app ready to deploy), before chapter 5
(put your site behind Cloudflare and lock your private pages). The desk's
app checkout credentials, the last part, are made when chapter 3 needs the
app's clone.

**What this chapter does:** the team gets its accounts at other companies,
for servers, backups, and alerts, and every key the servers need goes into
the vault. The desk's API proxy starts, so the coding agent reaches the
provider and Cloudflare without reading a token.

**Who acts:** the person makes each account on its website, approves each
cost, and runs each `set-up-outside-services` command in the person's own
desk terminal. You, the coding agent, explain each account when its turn
comes, set the settings, commit and push them, and check each result.

**Tell the person when the chapter starts:**

> The next step sets up the accounts at other companies: for servers,
> backups, and alerts. Separate accounts keep backups accessible if you lose
> access to the server-provider or Cloudflare account.
> I will guide you through one account at a time.
> Before you approve a charge, I will explain what the account is
> for and what it costs.
>
> Keep account logins in your password manager.
> Enter secrets only in your own terminal or editor.
> Do not put secrets in this chat, because the chat is stored at my provider.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, and "Tell the person
  after" with the result and its link. Say each message when its step
  comes, in your own words, with the team's own names and links. Each
  "Ask the person" asks for one fact or one action.
- **Commands that source the person's token file,** `~/.config/monkeymaxxing-stack/example_systems.env`,
  run only in the person's own desk terminal, as the secrets rule in
  [The rules](../AGENTS.md#the-rules) says.
- **One account at a time, in this order.** Give each account's explanation only when its turn comes.
  Identify the website and the next action on that website. When the
  account costs money, read its current price on the company's website,
  tell the person, and get their approval.
- **Each key.** Before a key, state who owns it, what access it gives, and where it belongs.
  Distinguish a personal token from a token that the servers use.
- **The checklist.** Each account has a checklist item; mark it `done` once its
  `verification` passed, and keep an item whose check needs the servers
  `open` until the chapter that proves it. Check each key when its check
  becomes possible. State which checks still need a running server. Do not
  describe checks that need a running server as complete before the server
  tests pass.
- **The chapter's parts.** The steps are numbered on through the parts,
  because chapter 8 cites step 7.

## Cloudflare and the company email

Cloudflare comes first: the API proxy starts only once both of
the person's tokens are on the desk, and the other steps, the company
email's DNS records included, work through it.

1. **Cloudflare's keys and storage.**

   **Tell the person first:**

   > Next, I set up Cloudflare, your app's front door, through its API: a company's way of taking commands from a program.
   > So I set things up from this systems desk, exactly and repeatably. You use the website only where the API cannot act, and I say where to click.
   > R2 stores your app's uploaded files outside the app servers. `util01` copies them to Backblaze each night, and chapter 8 tests the first copy.

   1. **The account's ID,** which is not a secret: the 32 characters after
      `dash.cloudflare.com/` in the browser's address bar on the account's
      home page. Set `vars.cloudflare_account_id` in
      `mmx_project_settings.yml`.

      **Ask the person:**

      > Please open your Cloudflare account's home page, and copy the 32 characters after `dash.cloudflare.com/` in the address bar.
      > That is your account's ID, which is not a secret. Paste it here.

   2. **R2.** The person turns on R2 once, by opening
      [R2 object storage](https://dash.cloudflare.com/?to=/:account/r2/overview)
      in the dashboard. Cloudflare asks for a payment method there before R2
      turns on, even though a small app stays inside R2's free allowance.

      **Ask the person:**

      > Cloudflare asks for a payment method before R2 turns on, even though a small app stays inside R2's free allowance.
      > Do you approve adding a payment method? Then open [R2 object storage](https://dash.cloudflare.com/?to=/:account/r2/overview), and tell me when R2 shows its overview.

   3. **Workers & Pages,** only when the account never had a
      Worker: the person opens
      [Workers & Pages](https://dash.cloudflare.com/?to=/:account/workers-and-pages)
      once, so the account gets
      its workers.dev address, where the MMHotline-down alarm answers.

      **Tell the person first:**

      > The MMHotline-down alarm is the alarm that wakes you if MMHotline itself goes silent.
      > The MMHotline-down alarm runs at Cloudflare, so the alarm keeps watching when your servers cannot.
      > You will meet the MMHotline-down alarm at chapter 8.

      **Ask the person,** only when the account never had a Worker:

      > Please open [Workers & Pages](https://dash.cloudflare.com/?to=/:account/workers-and-pages) once, and tell me when the page shows.

   4. **The status page's host name,** such as `status.example.com`, a new
      name in the domain's zone. Set `vars.status_page_host_name` in
      `mmx_project_settings.yml`.

      **Ask the person:**

      > Your status page tells your customers about a problem, even while every server is down.
      > Which web address do you want for it, such as `status.example.com`?

   5. **The uploads settings.** For each app that keeps uploads, check
      `production_uploads_r2_bucket` (chapter 3 (get your app ready to deploy))
      and `production_uploads_r2_key_variables`: the two names in the app's
      `secrets_from_vault` that hold its R2 key. Commit and push the
      settings; the person pulls them into the person's repository.

      **Tell the person:** no message, because substep 6 asks the person
      to pull the settings.

   6. **The person runs the command:**

      ```sh
      # This systems desk, in the systems repository, in the person's own terminal:
      . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services cloudflare
      ```

      **Tell the person first:**

      > `set-up-outside-services` is the Stack's own command for this work. It asks for each master key at a hidden prompt in your terminal.
      > It makes every bucket and key, saves each key straight into the vault, and prints what it did, why, and a link to see it. I never see a key.

      **Ask the person:**

      > Please run `git pull`, then the command above, in your own desk terminal.
      > The command prints a link to Cloudflare's token form with everything filled in. If Cloudflare asks which account, pick the one whose ID the command prints.
      > Keep the form's settings, the expiration too, select Continue to summary, then Create Token. Cloudflare shows the token only once: copy all of it and paste it at the hidden prompt.
      > That link token can only make tokens. The command sets it to end by itself after 24 hours, in case the run is cut off, and deletes it when the run ends.
      > Tell me what the command prints at the end.

      The link fills in the token's one permission, Account API Tokens
      Edit, and its name, such as
      `example_systems: alex makes tokens with set-up-outside-services, deleted after the run`.
      The person watches the command:
      - set the link token to end by itself 24 hours later, before it
        makes anything. When Cloudflare refuses, the command stops and
        says to make a new link token with the link;
      - make the person's desk token, `example_systems: alex's systems desk sets up Cloudflare`,
        with the permissions in the table below, and write it into the API
        API proxy's file, `/etc/systems-desk/cloudflare-api-token.conf`,
        and into the token file as `CLOUDFLARE_API_TOKEN`. With both of the
        proxy's token files in place, the command starts or restarts the
        proxy and checks a request through
        `http://127.0.0.1:8082/`;
      - create the tunnels `example_systems-apps` and `example_systems-util01`,
        each named after
        the project and locally managed, and save each tunnel's token in
        the vault (the table in
        [chapter 5 (put your site behind Cloudflare and lock your private pages)](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md#chapter-5-put-your-site-behind-cloudflare-and-lock-your-private-pages));
      - create each app's uploads bucket when missing;
      - set up the status page's bucket, host name, and rewrite rule with
        `mmhotline status-page set-up`, using the desk token, and
        write the page's bucket address into the token file as
        `MMHOTLINE_STATUS_PAGE_R2_BUCKET_URL`;
      - make each of the servers' tokens in the table below and save it in the vault;
      - make the person's own key for posting to the status page while
        `util01` is down, `example_systems: alex posts to the status page`,
        for the page's bucket only, and write it into the token file as
        `MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID` and
        `MMHOTLINE_STATUS_PAGE_R2_SECRET_ACCESS_KEY`;
      - add One-time PIN, Access's login method that emails a code, when
        the account lacks it, with a short-lived token that it deletes at once;
      - delete the link token.

      A rerun makes only what is missing, and each run takes a new link
      token from the same link. The person's own tokens follow one rule: the command
      keeps one while it is the only token of its name at Cloudflare and
      the token file holds it; otherwise it makes a new one, saves it, and
      deletes every other token of that name, such as one a rebuilt desk's
      old copy left.
      The command ends with the settings it found, none of them secret.
      Set `backups.uploads_r2_s3_endpoint` to
      `https://` followed by `vars.cloudflare_account_id` and
      `.r2.cloudflarestorage.com`, and keep the
      printed `r2_bucket_url` for the status page's settings in chapter 8 (check that alerts reach your phone and backups restore).
      The command commits the vault, signed through the person's own
      socket, and pushes it, the same way as the secrets step below. Pull,
      then check with
      `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage` that the
      keys below are defined.

      **Tell the person after:**

      > Cloudflare now has your tunnels, your uploads buckets, and the tokens your system uses, each saved in your vault: [tunnels](https://one.dash.cloudflare.com/?to=/:account/networks/tunnels).
      > The link token you made is deleted. I never saw any of the tokens.

      **Check:** `secrets usage` shows the keys below as defined. Keep
      `systems_desk_ready` open until a permitted provider read through
      `http://127.0.0.1:8081/` and a permitted Cloudflare read through
      `http://127.0.0.1:8082/` both succeed from `coding-agent`.

   Each Cloudflare token, in one place. `alex` stands for the person's
   account name on the desk, `vars.person_unix_username`:

   | Token at Cloudflare | Owned by | Can | Lives in |
   | --- | --- | --- | --- |
   | The link token, `example_systems: alex makes tokens with set-up-outside-services, deleted after the run` | The account | Make tokens, nothing else | Nowhere: entered at the prompt, set to end by itself after 24 hours, and deleted when the command ends. The person makes it on the website, from the command's link |
   | The person's desk token, `example_systems: alex's systems desk sets up Cloudflare` | The account, named after the person | On the account: Cloudflare Tunnel Write, Access: Apps and Policies Write, Access: Organizations, Identity Providers, and Groups Read, Access: Service Tokens Read, Workers R2 Storage Write. On every zone of the account: DNS Write, Cache Settings Write, Zone Read, Zone Transform Rules Write. These are the API's names; the website says Edit for Write | The API proxy and this desk's token file |
   | The person's posting key, `example_systems: alex posts to the status page` | The account, named after the person | Read and write the status page's bucket | This desk's token file |
   | Each app's R2 key, `example_systems: shop reads and writes its uploads` | The account | Read and write that app's uploads bucket | The vault, as the app's secrets |
   | Each app's staging R2 key, only with `staging01` ([Add staging01](../operating_procedures/add_staging01.md)) | The account | Read and write that app's staging uploads bucket | The vault, as the app's secrets with `staging_` in front, such as `staging_shop_R2_ACCESS_KEY_ID` |
   | `util01`'s R2 key for the uploads' copy, `example_systems: util01 reads the apps' uploads` | The account | Only read the apps' uploads buckets | The vault, as `uploads_r2_read_only_access_key_id` and `uploads_r2_read_only_secret_access_key` |
   | The MMHotline-down alarm's token, `example_systems: MMHotline uploads the MMHotline-down alarm` | The account | Upload the MMHotline-down alarm's Worker | The vault, as `mmhotline_down_alarm_cloudflare_api_token` |
   | The status page's R2 key, `example_systems: MMHotline posts to the status page` | The account | Read and write the status page's bucket | The vault, as `mmhotline_status_page_r2_access_key_id` and `mmhotline_status_page_r2_secret_access_key` |
   | The short-lived Access token, `example_systems: set-up-outside-services sets up Access, deleted after the run` | The account | Add a login method and make or renew a service token | Nowhere: deleted as soon as it did its work |
   | The tunnel tokens | The account | Connect a server to its tunnel | The vault |
   | Staging's Access service token, only with `staging01` | The account | Open the staging pages without a sign-in | This desk's token file, the password manager, and CI's secrets |

   `set-up-outside-services cloudflare` makes every token in the table
   except the link token. The person's own tokens carry the person's name,
   so anyone reading Cloudflare's token list sees whose each one is, and
   [Add or remove a team member](../operating_procedures/add_or_remove_a_team_member.md#adding-or-removing-a-person)
   deletes a leaving person's tokens by their names.

2. **Company email,** when the team has none, for access to the private pages:
   an address at the company's domain for each person. The email provider's
   DNS records go into Cloudflare (`company_email`).

   **Ask the person:**

   > Does your team have email at its domain, such as `alex@example.com`?

   **Ask the person,** only when the team has none:

   > Your private pages let in only addresses at `example.com`, so each person needs one.
   > Please sign up at an email provider for `example.com`, and tell me when it shows its DNS records. I add them at Cloudflare.

   **Tell the person after:** no message, because chapter 5 (put your site
   behind Cloudflare and lock your private pages) tests the address with
   the first sign-in.

   **Check:** the email provider's DNS records are in the domain's zone,
   read through the API proxy. `company_email` stays open until chapter 5's
   sign-in.

## The server provider

3. **The server provider, continued from chapter 2 (set up your laptop and your systems desk).** The provider account,
   personal token, location, and desk already exist. Do not create another personal token.
   Read the selected [provider guide](../provider_guides/README.md).
   Write the create, destroy, and list scripts in `server_management_scripts/`, using
   the [provider script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).
   The coding agent reaches the provider at `http://127.0.0.1:8081/`: through the desk's API proxy,
   which started with the Cloudflare token in step 1.
   The person provisions credentials in the person's desk terminal.
   When the scripts use a provider tool, add its pinned installation to `roles/util_server/main.yml`;
   the scripts of the OVHcloud, AWS EC2 and Google Compute Engine guides need only Debian's programs, which each
   guide names, and the Stack's `jq`.
   The person creates an account-owned restore identity for `util01`, separate from the person's identity:
   `util01_provider_api_token`. Step 9 below saves it in
   the vault: the guided step names the provider's page and asks for it at a hidden prompt.
   Register `/etc/systems-desk/production_key.pub` through the proxy for production creation and verify the registered key.
   Complete the provider guide's console activation before creating production servers.

   **Ask the person:**

   > `util01` needs its own API token at your provider, owned by the account, not by you, so it keeps working after anyone leaves.
   > Please make that token on [the provider's token page], and keep the page open. Step 9 asks for it at a hidden prompt.

   **Tell the person after:**

   > Your provider scripts work, and your desk's production key is registered at [the provider].
   > The server list shows `desk01`: [the provider's server page].

   **Check:** `./server_management_scripts/list_the_servers_at_the_provider`: exit 0 and `{"servers": [...]}`.
   A successful list includes `desk01`. Do not expect an empty account.

## The backups at Backblaze B2

4. **Backblaze B2.**

   **Tell the person first:**

   > The database backups get your data back after the worst kind of day: a deleted table, a hacked server, or a lost company account.
   > Backblaze B2 stores them, separate from your server provider and Cloudflare, so the backups stay safe if you lose either account.
   > Object Lock locks each database backup for 14 days by default: nobody can delete or change it, not even someone with the key or the account's owner.

   1. **The account,** on Backblaze's website, in the region nearest the
      servers' location, chosen above, and set when the account is made; its login into the
      password manager. Set `vars.backups` in `mmx_project_settings.yml`:
      the account's S3 endpoint and region, and the buckets' names,
      `production_bucket`, and when an
      app keeps uploads `uploads_bucket`, and MMHotline's bucket in
      `mmhotline_backup_replica_url`, such as
      `s3://example-mmhotline-backup/mmhotline?endpoint=https://s3.eu-central-003.backblazeb2.com&region=eu-central-003`.
      Bucket names are unique across all of Backblaze, so use the company's
      name in them. The three backup lengths keep the template's values,
      written out there with their reasons: `keep_database_backups_for_days`
      (21; at least 14), `lock_backups_against_deletion_for_days` (14; from 8
      up to `keep_database_backups_for_days`), and
      `keep_prior_file_versions_in_buckets_for_days` (14), which sets the
      lifecycle rule of the database backups' buckets and the uploads'
      bucket alike. If a law or a contract requires longer, raise the values. The
      command reads them, so set them before it runs. Commit and push; the
      person pulls.

      **Ask the person:**

      > Please make your team's account at Backblaze, in the region [the region nearest your servers], and save the login in your password manager.
      > Pick the region when you make the account, because Backblaze sets it then. Tell me when the account is ready.

      **Ask the person:**

      > Your backups are kept 21 days, and locked against deletion for 14.
      > Does a law or a contract require your team to keep data longer?

   2. **The master key:** on Backblaze's website, [Application Keys](https://secure.backblaze.com/app_keys.htm), the
      person generates the account's master application key, and keeps the
      page open. The master key stays out of the vault, the chat, and the
      repository. After the command ends, the person deletes the master key
      on the same page. A later key rotation asks for a
      new master key.

      **Ask the person:**

      > Please open [Application Keys](https://secure.backblaze.com/app_keys.htm), generate your account's master application key, and keep the page open.
      > Do not paste the key here. The next command asks for it in your own terminal.

   3. **The person runs the command:**

      ```sh
      # This systems desk, in the systems repository, in the person's own terminal:
      . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services backblaze
      ```

      **Ask the person:**

      > Please run `git pull`, then this command, in your own desk terminal, and paste the master key's keyID and applicationKey at its hidden prompts.
      > It creates your backup buckets and locks them, checks each lock by trying to delete a test file, and makes a separate key for each server with only the access it needs.
      > Your master key stays in the command's memory. I never see it, and the command never saves it.
      > Tell me what the command prints at the end.

      The person watches the command:
      - create each bucket the settings name, private, and for production's
        database backups and the uploads' copy with Object Lock
        in compliance mode and a default retention of the lock length
        (`backups.lock_backups_against_deletion_for_days`). A file becomes
        locked only when written into a locked bucket, so the lock comes
        before the first backup;
      - give every bucket the lifecycle rule that deletes a deleted or
        replaced version `backups.keep_prior_file_versions_in_buckets_for_days` after
        pgBackRest, rclone, or Litestream removed it, instead of keeping
        versions forever. A restore can still read a locked bucket as the
        bucket stood at any time in that period;
      - leave MMHotline's backup bucket unlocked;
      - check each lock: a new test file must get the lock length of
        compliance-mode retention, and Backblaze must refuse to delete it.
        A failed check stops the command before any key for that bucket
        exists. The test file stays, hidden, until its lock ends;
      - make each key, on its one bucket only, and save it in the vault:
        the database servers' write key (`pgbackrest_b2_write_key_id` and
        `pgbackrest_b2_write_application_key`), the restore drill's key
        that can only read, for `restore01` (`pgbackrest_b2_read_only_key_id`
        and `pgbackrest_b2_read_only_application_key`), when an app keeps
        uploads `util01`'s uploads key, which cannot delete
        (`uploads_backup_b2_write_key_id` and
        `uploads_backup_b2_write_application_key`), and MMHotline's backup key
        (`mmhotline_backup_access_key_id` and
        `mmhotline_backup_secret_access_key`).

      `util01`'s uploads key lacks Backblaze's `deleteFiles` permission, so
      `util01` uploads files and hides files removed
      from R2. Hiding removes a file from the current backup copy but keeps
      the saved versions. Only the bucket's lifecycle rule deletes saved
      versions, after `backups.keep_prior_file_versions_in_buckets_for_days`
      (the same setting sets the lifecycle rule of the database backups'
      buckets).

      A key that Backblaze issued but the vault could not save is revoked at
      once, and the command says so; a rerun makes it again. A rerun makes
      only what is missing and leaves every saved key as it is.
      The command commits and pushes the vault itself, signed.
      When an app keeps uploads, set `backups.uploads_backup_runs_on` to
      `[util_server]` now, after the uploads' keys exist; `[]` when none does.

      **Tell the person after:**

      > MMHotline keeps its alert history in a different backup bucket, with no deletion lock, because Litestream, the program that copies MMHotline's database, cannot upload into a locked B2 bucket.
      > The weekly restore drill, which you will meet at chapter 6, gets a key that can only read, so a drill can never change a backup.
      > Please delete the master key now on [Application Keys](https://secure.backblaze.com/app_keys.htm): every server has its own limited key.

   **Ask the person,** for the check:

   > Please open the command's link to your bucket page at Backblaze. For each locked bucket, tell me what you see:
   > Object Lock enabled, compliance mode, 14 days as default retention, and Lifecycle Settings that keep prior versions for 14 days.

   **Check:** `backblaze_b2_locked_backup_bucket`: the command's output shows the
   lock check passed for production's database bucket and the uploads
   backup bucket when an app
   keeps uploads. The person sees, for each locked bucket: Object Lock enabled, compliance
   mode, the lock length as default retention, and Lifecycle Settings that keep
   prior versions for `backups.keep_prior_file_versions_in_buckets_for_days`. Record what the person saw in `last_result`.

## Alerts on the phone and the app's email

5. **Pushover, the push app.** Read the current price on pushover.net, tell the person, and get approval
   before the person signs up.
   The person creates a [Pushover account](https://pushover.net/signup), then an
   [application](https://pushover.net/apps/build) for the alerts.
   If you run more than one system, create one application for each system
   and name the application after the system: the phone shows the
   application's name on every alert, and the hub-outage alerters' alerts name
   only a server, such as `app001`, which every system has.
   Next, the person creates a [delivery group](https://pushover.net/groups/create) containing everyone who can be
   on call.
   A person joins or leaves the Pushover group without changing the vault.
   Then the person installs the Pushover app on each on-call phone and
   allows alerts to sound in Silent Mode (Critical Alerts on iOS). Step 9
   saves the application's token, `pushover_application_token`, and the
   group's key, `mmwatchdog_pushover_user_or_group_key`, in the vault. Each person's
   own Pushover user key isn't a secret: they add it on MMHotline's page in
   [chapter 8 (check that alerts reach your phone and backups restore)](08_check_that_alerts_reach_your_phone_and_backups_restore.md#chapter-8-check-that-alerts-reach-your-phone-and-backups-restore)
   (`push_app_on_every_on_call_phone`).

   **Tell the person first:**

   > Pushover puts the alerts on your phone, loud enough to wake you, even in Silent Mode. Chapter 8 tests that.
   > The Pushover group holds everyone who can be on call. If util01 goes silent, two of your servers, the hub-outage alerters, alert everyone in the group, because they cannot know who is on call.

   **Ask the person:**

   > Pushover charges a one-time licence fee of [the current price] for each phone type, after a free trial.
   > Do you approve the Pushover fee?

   **Ask the person,** after the approval:

   > Please make a [Pushover account](https://pushover.net/signup), then an [application](https://pushover.net/apps/build) named after your system, and a [delivery group](https://pushover.net/groups/create) with everyone who can be on call.
   > Then install the Pushover app on each on-call phone and allow its alerts to sound in Silent Mode (Critical Alerts on iOS).
   > Keep the application's token and the group's key for step 9. Tell me when the app is on each phone.

   **Tell the person after:** no message, because chapter 8 (check that
   alerts reach your phone and backups restore) sends the first alert.

   **Check:** the person names the application and the group. Step 9
   checks that their keys reach the vault.

6. **An email sending service,** such as Resend, when the app sends email.
   The person adds the company's domain to the email service. The email
   service shows the SPF, DKIM, and DMARC records for the domain, and the
   agent adds them at Cloudflare through the API proxy. Add the
   name of the service's API key to the app's `secrets_from_vault`, such as
   `RESEND_API_KEY`; step 9 asks the person for it (Resend's page is
   [API Keys](https://resend.com/api-keys)) (`email_sending_service`).

   **Tell the person first:**

   > The email service sends your app's email. Its records for your company's domain let other mail services check that the email really comes from your company.
   > So your app's email is less likely to land in spam, and sending email in your company's name is much harder for anyone else.

   **Ask the person:**

   > Please add `example.com` to your email service, and tell me when it shows the domain's DNS records. I add them at Cloudflare.

   **Tell the person after:**

   > Your email service's records are in your domain: [DNS records](https://dash.cloudflare.com/?to=/:account/:zone/dns/records).

   **Check:** the SPF, DKIM, and DMARC records are in the domain's zone,
   read through the API proxy.

## The triage agent and the registry

7. **The triage agent's key** at the coding agent's provider.
   Step 9 saves the credential in the vault as
   `mmhotline_triage_agent_credential`. The triage agent uses the same
   coding agent as the systems desk, by default; no question. Set
   `triage_agent_coding_agent` in `mmx_project_settings.yml` to the value
   of `systems_desk_coding_agent`, `claude_code` or `codex`, before step 9,
   which reads it.
   `mmhotline_settings.yml` takes its `coding_agent` from that setting, and
   `util01` installs Codex only when the setting is `codex`, so the two
   always agree. Change the coding agent in that one place.
   For Claude Code, tell the person that it takes either of two kinds, and
   what each costs them:
   - An Anthropic API key (`credential_type: api_key`), made at the
     [API keys page](https://console.anthropic.com/settings/keys). It
     belongs to the company's account at Anthropic, so it keeps working
     when any person leaves, and it never expires.
   - A person's Claude subscription token (`credential_type:
     subscription_token`), which that person makes by running
     `claude setup-token` in their own terminal, where Claude Code is
     signed in to their Claude account. It is billed to that person's
     plan, lasts one year, and stops working when that person's account is
     removed. MMHotline warns 30 and 7 days before it expires, and when it
     stops working. Renewing it is the same `claude setup-token` step.

   For Codex, tell the person that it takes three kinds, and what each
   costs them:
   - An OpenAI API key (`credential_type: api_key`), made at the
     [OpenAI API keys page](https://platform.openai.com/api-keys). It
     belongs to the company's account at OpenAI, never expires, and has its
     own usage limits, so the agent still runs at 3 a.m. after a busy day.
   - A Codex access token (`credential_type: access_token`), for a ChatGPT
     Business or Enterprise workspace. The person creates it on the
     workspace's Access tokens page and picks an end date up to 90 days
     away. The end date goes in `credential_expires_on`, written
     `"YYYY-MM-DD"`; it is not a secret. MMHotline reminds the
     administrators 30 and 7 days before that date, and the person then
     makes a new token. It shares the workspace's usage limits.
   - A ChatGPT sign-in (`credential_type: chatgpt_sign_in`), for any other
     ChatGPT plan: the whole content of the `auth.json` file that signing in
     to Codex once makes, at most 64 KiB. The person signs in in a new empty
     folder used only for MMHotline, with a ChatGPT account that has no
     connected apps, because the sign-in can reach the account's connected
     apps. They never use that copy anywhere else, and never run
     `codex logout` on it. It shares the plan's usage limits.

   Recommend the API key, for either coding agent, for a small team.
   Choose a subscription kind
   when the team already pays for a Claude or ChatGPT plan and prefers its
   flat price to a bill that follows the number of alerts. Step 9 asks which kind the person has, and the agent then
   sets `credential_type` under `triage_agent` in `mmhotline_settings.yml`
   (`credential_expires_on` too, for a Codex access token); neither setting
   is a secret.

   **Tell the person first:**

   > The triage agent is an AI coding agent that investigates each alert, at any hour. You will meet it at chapter 8.
   > It uses Claude Code, like your desk's coding agent. It runs only when an alert arrives, unless you later turn on the scheduled software review.
   > It needs a key: an Anthropic API key, billed to your company's account by the number of alerts, or a person's Claude subscription token, billed to that person's plan.
   > I recommend the API key: it belongs to the company, so nobody's leaving or a lapsed plan silences the triage agent, and nothing needs renewing.

   **Ask the person:**

   > Which kind of key do you want for the triage agent: an API key, or a subscription token?

   **Tell the person after:** no message, because step 9 asks for the key
   at a hidden prompt.

   **Check:** `triage_agent_coding_agent` equals `systems_desk_coding_agent`,
   and you recorded the kind.

8. **The registry's read-only token.**
   On GitHub, the person makes a
   [classic token](https://github.com/settings/tokens/new) with
   `read:packages` only. Set `container_registry_read_only_username` in
   `mmx_project_settings.yml` to the username of the GitHub account that
   owns the token; the name is not a secret. Step 9 saves the token in the
   vault as `container_registry_read_only_token`. Nobody reads the token
   again, so its check has two parts. Now, the person opens GitHub's
   [Personal access tokens (classic)](https://github.com/settings/tokens)
   page and sees the token with `read:packages` and no other scope, so it
   cannot push, and sees the systems repository and each app's repository
   marked Private. In chapter 7 (install everything on the production
   servers), the first `every_server` run pulls each app's image on
   `app001` with the token from the vault, which proves its login; mark
   `git_host_and_container_registry` done then.

   **Tell the person first:**

   > The registry stores your packaged app versions. Its read-only token lets your servers download them.
   > The token can only read, so a server that is broken into cannot replace an app version.

   **Ask the person:**

   > Please make a [classic token](https://github.com/settings/tokens/new) at GitHub with `read:packages` only, and keep it for step 9.
   > Which GitHub username owns the token?

   **Ask the person,** for the check:

   > Please open [Personal access tokens (classic)](https://github.com/settings/tokens): does the token show `read:packages` and no other scope?

   **Ask the person,** for the second part of the check:

   > Do your systems repository and each app's repository show as Private at GitHub?

   **Tell the person after:** no message, because chapter 7 proves the
   token's login when `app001` pulls the first image.

   **Check:** what the person saw, recorded in `last_result`.
   `git_host_and_container_registry` stays open until chapter 7.

## The vault's other secrets

9. **The vault's other secrets, in one guided step.**
   Before the command, tell the person which of each app's
   `secrets_from_vault` come from an outside service, such as
   `STRIPE_API_KEY` or the email service's key, and which are random, such
   as `SECRET_KEY_BASE`: the command asks the person about each one.
   The person runs, in the person's own terminal, in the systems repository:

   ```sh
   # This systems desk, in the systems repository, in the person's own terminal:
   . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services secrets
   ```

   It walks each key the vault still lacks, in this order:
   - the keys only a website gives, each with its page: `util01_provider_api_token`
     (the provider's API token page), `pushover_application_token` and
     `mmwatchdog_pushover_user_or_group_key` (pushover.net),
     `mmhotline_triage_agent_credential` (it asks first whether the person
     has an API key or a Claude subscription token, then gives the API keys
     page or `claude setup-token`), and `container_registry_read_only_token`
     (GitHub's token page, with `read:packages` filled in). Enter alone leaves
     a key for a later run;
   - the servers' shared root console password, `shared_root_console_password_hash`:
     the command makes a password of six groups of five letters and shows it
     once. The person saves it in the team's password manager as a new item
     named `Shared root console password`, presses Enter, which clears the
     screen, and types the password back from the password manager at a
     hidden prompt. A mismatch shows the password again. The vault gets only
     the password's hash, which MMX writes to each server's root account in
     chapter 7;
   - each app's secrets from `secrets_from_vault`, except the R2 keys, which `set-up-outside-services
     cloudflare` made: the person types `random` for a value nobody needs to
     see, or presses Enter and pastes the outside service's value;
   - the random keys it makes without asking: the failover monitor's logins,
     `pg_auto_failover_autoctl_node_password` and
     `pg_auto_failover_replication_password`; each app's database password;
     production's backup passphrase, `pgbackrest_repository_cipher_passphrase`;
     and the fleet hub's signing secret,
     `mmhotline_signing_secret_of_the_fleet_hub`, as 64 hexadecimal characters.

   It skips every key the vault holds already; `--replace KEY` enters one
   again. Its summary names the keys saved, the keys left for later,
   and the keys another command makes.

   Every `set-up-outside-services` command that saves keys (`backblaze`,
   `cloudflare` and `secrets`) commits and pushes the vault itself. It
   refuses to start while the repository has uncommitted changes other than
   the vault, or commits not pushed yet, and pulls the team's `main` first,
   before it asks for anything. It ends by committing the vault, signed
   through the person's own socket, and pushing it. When it refuses, you
   commit and push your own changes first, then the person runs it again.

   **Tell the person first:**

   > One command now saves every remaining secret your servers need. For each key that only a website gives, it says what the key is for and where you make it, and you paste it at a hidden prompt.
   > It makes the secrets nobody needs to see, such as your app's database passwords, by itself, and shows none of them. Then it saves the vault to your Git host. I never see any of the values.
   > MMWatchdog's fleet hub on util01 signs MMWatchdog's alerts with a key shared with MMHotline, so MMHotline takes alerts only from your servers.

   **Ask the person:**

   > Please run the command above in your own desk terminal. Tell me what its summary prints at the end.

   **Tell the person,** just before the command reaches the shared root console password:

   > This is the password for your server provider's web console, the way in when SSH fails. Save it in the password manager now, because it shows only once.

   **Ask the person,** after the command:

   > Your backups cannot be read without the backup passphrase, so your password manager needs a copy.
   > Please run `set-up-outside-services show-recovery-items` again, as in chapter 2. It now shows the backup passphrase too. Tell me when it is saved.

   The person then copies the backup passphrase into the password manager:
   the person runs `set-up-outside-services show-recovery-items` again
   ([Recovery items and laptop cleanup in chapter 2 (set up your laptop and your systems desk)](02_set_up_the_laptop_and_the_systems_desk.md#recovery-items-and-laptop-cleanup)),
   which now shows the backup passphrase too.

   **Tell the person after:** no message, because step 10 ends the
   chapter with the person's own check.

   **Check:** pull, then check with
   `sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage` that no
   key it makes is `not defined`.

10. **The password manager's check, `team_password_manager`.** The person
    signs in to the four accounts whose loss would lock the team out, in a
    private browser window with the login saved in the password manager,
    while you name each account. The four accounts are Cloudflare, the
    server provider, Backblaze, and the Git host. The other accounts'
    logins are saved too, and the person finds a wrong saved login when the
    person first uses the account.

    **Ask the person,** for each of the four accounts in turn:

    > Please open a private browser window and sign in to Cloudflare with the login from your password manager.
    > Tell me whether the sign-in works.

    **Tell the person after,** which also ends the chapter:

    > Your four key accounts open from your password manager: Cloudflare, [the provider], Backblaze, and [the Git host].
    > Your outside services are ready. Next, I put your site behind Cloudflare.

    **Check:** in `team_password_manager`, record what the person saw in
    `last_result`.

## Make the desk's app checkout credentials

Every team needs the first credential here. Chapter 3 (get your app ready to
deploy) gives the desk a read-only clone of the app, as `coding-agent`, so
the coding agent can read the code and what each release changes. Only a team
with no CI also needs the second credential: with CI, CI pushes the images
with GitHub's own short-lived token, and the desk holds nothing that can
publish. The clone's credentials are separate from the production key, so a
leaked one can read the app's code, or with no CI also publish an image, but
reaches no server.

11. **Git access to the app's repository.** Make a key for the checkout
    yourself, as `coding-agent`, and print its public key:

    ```sh
    # This systems desk, as the coding agent:
    ssh-keygen -q -t ed25519 -N '' -C 'app checkout on desk01' -f ~/.ssh/app_checkout_key && cat ~/.ssh/app_checkout_key.pub
    ```

    The person registers the printed public key on the app's repository as
    a read-only deploy key: at GitHub, the repository's Settings, Deploy
    keys, `https://github.com/OWNER/REPOSITORY/settings/keys`, Add deploy
    key, with "Allow write access" left off.
    Then clone with that key alone. So the checkout's own
    `core.sshCommand` names the key and offers no other:

    ```sh
    # This systems desk, as the coding agent:
    app_ssh='ssh -i ~/.ssh/app_checkout_key -o IdentitiesOnly=yes -o IdentityAgent=none -o UserKnownHostsFile=/etc/systems-desk/git-known-hosts -o StrictHostKeyChecking=yes'
    git -c core.sshCommand="$app_ssh" clone git@github.com:OWNER/APP.git ~/apps/shop &&
      git -C ~/apps/shop config core.sshCommand "$app_ssh"
    ```

    Every later `git pull` in `~/apps/shop` uses the same key. When the
    app's repository is on another Git host than the systems repository,
    add that host's published SSH host keys to
    `git_host_ssh_known_hosts_lines` first.

    **Ask the person:**

    > Please add this public key to your app's repository as a deploy key, with "Allow write access" left off: `https://github.com/OWNER/REPOSITORY/settings/keys`.
    > The key only reads your app's code. Tell me when it is added.

    **Tell the person after:**

    > The desk now has a read-only copy of your app's code, so I can read what each release changes. It cannot push to your app.

    **Check:** the clone in `~/apps/shop` exists, and `git pull` there works.

12. **The registry publishing login. Only a team with no CI makes it.** The person makes a
    [classic token](https://github.com/settings/tokens/new) with `write:packages`, then signs the
    checkout in, in the person's own terminal:

    ```sh
    # This systems desk, in the person's own terminal:
    sudo -u coding-agent -i podman login ghcr.io --username GITHUB_USERNAME --authfile /home/coding-agent/.config/containers/auth.json
    ```

    Podman asks `Password:` and hides what the person pastes; press Enter.
    Save the token in the password manager. This token is not the read-only
    token the servers use. The login is saved in the coding agent's
    `~/.config/containers/auth.json`, where `podman push` finds it after a
    reboot too; Podman's own default place is cleared at every reboot.

    **Ask the person:**

    > Please make a [classic token](https://github.com/settings/tokens/new) at GitHub with `write:packages`, and save it in your password manager.
    > Then run the command above in your own desk terminal, and paste the token when Podman asks `Password:`. Tell me what Podman prints.

    **Tell the person after:**

    > The desk can now publish your app's images. That login reaches no server.

    **Check:** Podman prints `Login Succeeded!`.

## Why the chapter works this way

**Separate accounts.** Separate accounts for servers and backups preserve access to
backups if the server account is lost. Separate accounts do not keep the
site running after the server account is lost: losing the
server-provider or Cloudflare account can still stop the site.

**Later runs of `set-up-outside-services cloudflare`.** When `staging01` joins later, a rerun makes
staging's tunnel, keys, and Access service token
([Add staging01](../operating_procedures/add_staging01.md)). When an app joins later, a rerun makes the
new app's key and adds its bucket to `util01`'s read-only key, which
keeps its value.

**The status page waits for "Active".** The status page's part needs the domain to show "Active" at
Cloudflare, because Cloudflare connects the page's host name to its
bucket in the domain's zone. While the domain shows "Pending", the
command reads the domain's status, skips the status page and its two
keys, says "The status page waits until your domain example.com is
Active at Cloudflare" and "Run this command again then", and finishes
the rest. A rerun after the domain is Active makes the missing part.
Chapter 8 (check that alerts reach your phone and backups restore)
sets up the page's settings and tests the page.

**Account-owned credentials.** Reason: production recovery uses account-owned credentials after a person leaves.

**The Backblaze region.** A backup to a far-away region is slower.

**The master key goes away.** Every server has its own limited key and
nothing needs the master key again.

**MMHotline's backup bucket stays unlocked.** Litestream (checked with 0.5.18 on 2026-11-12) sends no checksum with its
uploads, and B2 refuses uploads into a locked bucket without one.

**Nobody reads a lock's settings from a server.** The server keys cannot read a bucket's lock settings because the server
keys lack `readBucketRetentions`, which they never need.

**The Pushover token's name.** The
token's name is for neither program, because MMWatchdog and MMHotline
both send with it.

**How well the subscription kinds are proven.** If the person asks how well the subscription types are proven, say in
one line: MMHotline has proven the subscription types only against
stand-in programs that behave as the vendors' documents say, and its
daily sign-in check alerts the administrators if a real sign-in stops
working. The person sees the result in
[chapter 8 (check that alerts reach your phone and backups restore)](08_check_that_alerts_reach_your_phone_and_backups_restore.md#chapter-8-check-that-alerts-reach-your-phone-and-backups-restore),
where util01 tests the credential with one prompt before MMHotline
saves it (`coding_agent_provider_key`).

**The vault is pushed by the command.** Reason: a vault that is not pushed leaves the servers without the new
keys, and the person should not have to get a commit and a push right by
hand.

**The app checkout's deploy key reads only.** Reason: the checkout only reads the app's code.
Your SSH agent socket holds the desk's
production key, which the Git host knows as the systems repository's
deploy key; offered first, it would sign in as that key and the app's
repository would answer "not found", so the clone uses the app's key
alone.

Next: [Chapter 5: Put your site behind Cloudflare and lock your private pages](05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md).
