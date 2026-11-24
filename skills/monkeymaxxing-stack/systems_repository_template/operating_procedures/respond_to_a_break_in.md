# Respond to a break-in

**When to use this page:** someone has entered the system without permission, or credible evidence suggests a break-in.

**What this page does:** the coding agent works through this page with the person. First the two find out how the
intruder got in and what the intruder can reach. Then the two choose the smallest response that stops the harm,
replace the keys that the intruder reached, put the data back, and tell the people who must hear.
Every desk, `util01` and the triage agent keep working, except in the few cases that
[The lock-out: only for these cases](#the-lock-out-only-for-these-cases) names.

**Who acts:**

- **The coding agent,** on the person's laptop, reads the logs and settings through its desk login
  (`ssh desk01-agent`), proposes each step with its reason, prepares and publishes each commit, gives the person each
  command, and runs MMX. Outside a lock-out, it runs MMX on `util01` with
  `./server_management_scripts/run_mmx_on_util01`. During a lock-out, it runs MMX with its MMX button on the desk
  that keeps access.
- **The person** decides each step and does the work at each company's website. The person types, on the laptop,
  with a phone code: the lock-out button `ssh -t desk01 sudo lock-everyone-out`, each Cloudflare key replacement,
  and `ssh desk01-review` after the incident. The evidence copy of step 2 runs in the person's own desk login,
  `ssh desk01`.
- **Only a person starts or undoes a lock-out,** from a desk that shows no signs of the break-in. The triage agent
  never does. The coding agent recommends a lock-out only when the facts match one of the cases in
  [The lock-out: only for these cases](#the-lock-out-only-for-these-cases).

**Names:** use `desk01`, `alex`, `shop` and `example_systems` below only when those names match the inventory and project.

**Terms:** this page uses the Stack's terms, such as lock-out button, desk that keeps access, triage agent, vault
and provider console. [Technical terms](../talking_with_the_team.md#technical-terms) explains each term.

**Before you start:** a trusted systems desk, and the team's **Break-in response** page in the password manager
([step 0](#0-prepare-the-response-page)). Open the incident record that the response page names. Write each fact
and each decision there, with its time.

The page bends the step form in one place. Step 4 keeps its seven numbered items, each with several actions,
because other procedures refer to them by number, such as "step 4's item 3".

## What did you see?

The coding agent asks the person what the person saw, and reads the evidence, before anyone changes anything.
Reason: the right response depends on how the intruder got in. A response that is too wide, such as a lock-out for
a break-in through the app, cuts off the people and agents that the team needs for the work.

| What you saw | What the intruder can reach | Go to |
| --- | --- | --- |
| The app misbehaves: an admin account that nobody made, an app secret seen in public, or data that nobody on the team changed | The app's own data, uploaded files and outside-service keys | [A break-in through the app](#a-break-in-through-the-app) |
| An unknown commit in the systems repository | What a run of that commit would do on every server | [An unknown commit in the systems repository](#an-unknown-commit-in-the-systems-repository) |
| An alert, or a session that nobody recognises, at the server provider, Cloudflare, the registry, the password manager or the coding-agent vendor | That company's account | [An unknown session at a company](#an-unknown-session-at-a-company) |
| A laptop is lost or stolen, or a laptop ran malware | The laptop's desk-login keys and tokens | [Recover from a lost or stolen laptop](recover_from_a_lost_or_stolen_laptop.md) |
| A team member left and kept a credential | That credential | [A member left with a credential](#a-member-left-with-a-credential) |
| `util01` or the triage agent is suspect; an unknown root login, process or MMX run on the servers; or a desk or a kept credential is suspect and nobody knows which | Root on the servers | [The lock-out: only for these cases](#the-lock-out-only-for-these-cases) |
| Signs on your own systems desk, and the team has another person with a desk | Root on every server, through your desk | [When your own desk was the way in](#when-your-own-desk-was-the-way-in), "With a teammate" |
| Signs on your own systems desk, and you work alone | Root on every server, through your desk | [When your own desk was the way in](#when-your-own-desk-was-the-way-in), "Working alone" |
| A false alarm after a lock-out, or the rebuild of step 4 is done | Nothing new | [Undo a lock-out](#undo-a-lock-out) |
| A demand for money | Unknown | [6. Handle an extortion demand](#6-handle-an-extortion-demand) |
| Before any incident: write the team's answers down | Nothing | [0. Prepare the response page](#0-prepare-the-response-page) |
| Optional practice | Nothing | [7. Practice the response](#7-practice-the-response) |

Signs on your own desk are, for example, a commit that nobody on the team made but your desk's key pushed, or a
login to your desk that you do not recognise.

When the facts fit no row, start with [Find out what happened](#find-out-what-happened): the log reads in that section
change nothing. Ask incident help, whom the response page of step 0 names, when the logs leave the way in unclear.

## A break-in through the app

**When:** the app itself was the way in, through a flaw in the app's code, a stolen app password, or a leaked app
secret. This is the most common break-in.

**What the intruder can reach:** only what the app can reach.

- The app's own database, as the app's own database role. The database servers admit that role only to the app's
  database (`pg_hba`).
- The app's uploaded files in R2. The intruder can delete the uploaded files. `util01`'s copies in B2 are under Object Lock, so
  nobody can delete those copies.
- The app's keys for outside services, such as a payment service.

The app runs in a confined container: a read-only file system, its own user namespace (`UserNS=auto`), an AppArmor
profile, and no Linux capabilities. So the intruder reaches no other server and cannot delete a backup.

**Do not lock out.** Every desk, `util01` and the triage agent keep working. Reason: the lock-out does not close
the app's way in, and the lock-out cuts off the people and agents that the team needs for this work. When the logs
show that the intruder reached further, such as a root login on a server, go to
[The lock-out: only for these cases](#the-lock-out-only-for-these-cases).

Work through the sections below in order. When the intruder may still be active, such as data that keeps changing
or an unknown admin account that is still signed in, stop the harm first with what you already know. Then find out
what happened. Reason: each minute of investigation while the intruder acts costs data.

### Stop the harm with the smallest step

Choose the first of these steps that stops the harm. Close the way in before you replace the secrets.
Reason: through an open flaw, the intruder can read the new secrets too.

1. **When the intruder is destroying data now,** send the app's requests to the status page, as
   [Send the app's requests to the status page](#send-the-apps-requests-to-the-status-page) says. This step is the
   most urgent, because the status page stops every request at once.
   **Check:** the checks of that section.
2. **When the intruder uses an account or a feature, turn the account or the feature off** in the app's own
   controls. Reset affected app administrator accounts and end those accounts' sessions.
   **Check:** the person signs in to the app and sees the account or the feature off.
3. **When the flaw came with a recent release, roll back,** as
   [A rollback](deploy_and_roll_back_an_app_release.md#a-rollback) says. A rollback does not wait for the
   person's approval. A rollback does not undo the migrations.
   **Check:** the rollback's checks pass, and the request that the intruder used now fails.

### Find out what happened

1. **The person snapshots the disk of the app server whose logs show the activity,** or of `app001` when the logs
   do not show one, at the provider, and records the snapshot and server IDs.
   Reason: each app server's journal holds the app's logs, but only for a limited time. A snapshot keeps the logs
   without a change to the server. The evidence copy of step 2 runs only during a lock-out, so the provider
   snapshot is the evidence copy of a break-in through the app.
   **Check:** the provider shows the snapshot.
2. **The coding agent reads the app's logs on each app server,** over SSH, which changes nothing. The date below is
   an example:

   ```sh
   ssh -F ssh/config root@10.20.1.1 'journalctl -u "shop-web-*" --since "2026-11-03 00:00" --no-pager'
   ```

   Start a day or more before the first sign. Read the requests and errors near each sign.
   **Check:** the output shows the web containers' lines. When the journal starts after the first sign, the logs
   before that time are gone: record the gap in the incident record.
3. **The coding agent finds the changed data with read-only queries on the primary database server.**
   The query results stay on the production servers, as
   ["Production data stays on the production servers"](../AGENTS.md#the-rules) says. Select only the columns the
   question needs. The query below is an example for the app's own tables:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run-command --nodes db01 --run-as-node-user-account postgres -- "psql -d shop -c 'SET default_transaction_read_only = on' -c 'SELECT id, created_at, updated_at FROM users ORDER BY updated_at DESC LIMIT 50'"
   ```

   Reason: `default_transaction_read_only` makes Postgres refuse a write in that session, so a mistake in the query
   changes nothing.
   **Check:** the output answers the question, such as when the unknown admin account was made.
4. **The person reads Cloudflare's record of requests** for the app's host name, on Cloudflare's website, in the
   zone's Security and Analytics pages.
   **Check:** the person tells the coding agent the addresses, paths and times that match the app's logs.
5. **Record when the break-in started:** the first known access, the way in, the affected accounts, the data viewed
   or changed, and the evidence for each conclusion.
   An absent log does not prove that data stayed private.
   **Check:** incident help reviews uncertain findings.

### Tell the people affected

Tell people early, and send the full notices later.
Reason: a person whose account the intruder took over can protect the account only after hearing about it.

1. **Post to the status page** while customers see a problem, as [Post to the status page](post_to_the_status_page.md) says.
   **Check:** the checks of Post to the status page.
2. **As soon as the scope is known, tell the people whose accounts the intruder took over,** such as by email from
   the app, so each person can change a password. The coding agent drafts the message from the facts in the incident
   record. The person sends the message.
   **Check:** the incident record names who was told, and when.
3. **Send the full notices,** as [5. Tell people](#5-tell-people) says, once the investigation is complete.
   **Check:** the checks of step 5.

### Replace the app's secrets

Replace every secret that the app holds, because the intruder could read each one.

1. **Replace each app secret,** as [App secrets](rotate_a_secret.md#app-secrets) says: the secrets the app makes
   itself, such as `shop_SECRET_KEY_BASE`, and the keys that outside companies issued, such as
   `shop_STRIPE_API_KEY`. Replace app signing secrets and webhook credentials through each app's own controls.
   **Check:** the checks of App secrets.
2. **Replace the app's database password,** as [App database passwords](rotate_a_secret.md#app-database-passwords) says.
   **Check:** the checks of App database passwords.
3. **The person replaces the app's R2 key,** on the laptop, with a phone code:

   ```sh
   ssh -t desk01 set-up-outside-services cloudflare --replace-key shop_R2_ACCESS_KEY_ID --delete-the-old-keys-at-once
   ```

   The command deletes the old key at Cloudflare at once, as [Cloudflare keys](rotate_a_secret.md#cloudflare-keys)
   says. Then the coding agent runs `./server_management_scripts/run_mmx_on_util01 run every_server`.
   Until that run ends, the app cannot reach the app's uploaded files.
   **Check:** an upload in the app works, and the uploaded file shows in the app's bucket.

### Put the data back

1. **Choose the time:** one minute before the first known access, in UTC, as
   [Bring the whole database back to a chosen minute](recover_when_every_database_server_is_lost.md#bring-the-whole-database-back-to-a-chosen-minute) shows.
   **Check:** the person agrees with the time, in UTC and in the person's own time zone.
2. **When the intruder changed or deleted some rows,** follow
   [Recover rows lost to a bad change](recover_rows_lost_to_a_bad_change.md). The procedure restores a copy from
   the chosen time on `restore01`, and keeps every later customer change.
   **Check:** the checks of that procedure.
3. **When most of the database must go back,** follow
   [Bring the whole database back to a chosen minute](recover_when_every_database_server_is_lost.md#bring-the-whole-database-back-to-a-chosen-minute).
   Every customer change after the chosen minute is lost, so the coding agent tells the person what is lost
   before the person chooses this step.
   **Check:** the checks of that section.

### Check the uploaded files

1. **Read MMWatchdog's check `uploads_backup/the_latest_copy_hid_no_unusual_share_of_an_apps_files`** on `util01`.
   The check warns when the nightly copy found many of an app's files deleted or changed.
   **Check:** the check is healthy, or the warning names the app and the share of files.
2. **When the intruder deleted or overwrote uploaded files,** follow
   [Restore an uploaded file](restore_an_uploaded_file.md), after the app's R2 key was replaced, with the same time
   as the database. For many files, follow
   [Restore all of an app's uploaded files](restore_an_uploaded_file.md#restore-all-of-an-apps-uploaded-files).
   **Check:** the checks of that procedure.

### Fix the flaw

1. **Fix the flaw in the app's repository, and add a test that repeats the intruder's request.** Use invented data
   from the app's seed command, never production data.
   **Check:** the new test fails on the old code and passes on the fixed code.
2. **Try the fix on `staging01`,** when the team has `staging01`, as [A release](deploy_and_roll_back_an_app_release.md#a-release) says.
   **Check:** the checks of A release, on `staging01`.
3. **Deploy the fix to production,** as [A release](deploy_and_roll_back_an_app_release.md#a-release) says.
   **Check:** the checks of A release.
4. **Undo the temporary steps:** turn the abused feature back on, and send requests back to the app, as
   [Send the app's requests to the status page](#send-the-apps-requests-to-the-status-page) says.
   **Check:** the app answers at its public address.

### Send the app's requests to the status page

When the intruder is destroying data, send public requests to the status page. Customers then see the status page,
and nobody, the intruder included, reaches the app from outside.

1. **The coding agent sets `send_app_requests_to_the_status_page: true`** in `mmx_project_settings.yml`,
   commits and pushes.
2. **The coding agent redirects public requests through the existing web entry,** with its MMX button:

   ```sh
   sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only \
     --only-fleet-stages find_the_releases_the_app_servers_run,find_the_live_and_new_web_ports_on_the_app_servers,point_every_caddy_at_the_live_web_containers
   curl -fLsS https://shop.example.com/
   ```

   Reason: the button runs at once and does not wait for `util01`'s lock. Outside a lock-out, first check with
   `./server_management_scripts/run_mmx_on_util01 status` that `util01` runs nothing.
   **Check:** the public request must show the independent status page at `status_page_host_name`.
3. **To return requests to the app,** the coding agent sets `send_app_requests_to_the_status_page: false`, commits,
   pushes and reruns the command.
   **Check:** the public request shows the app.

## An unknown commit in the systems repository

**When:** a commit that nobody on the team made is on `main` in the main copy on `util01`.

**What the intruder can reach:** MMHotline and `util01` trust every commit on the main copy
(`systems_repository_commits.trusted_commits: every_commit_on_origin`), so the next run applies the commit on every server as root.
Only a key in `root_ssh_public_keys` can push to the main copy, as root: a desk's production key or `util01`'s
`mmhotline` key. So a commit nobody made means one of those keys is in someone else's hands.
The triage agent cannot push: MMHotline pushes its commits only when they change nothing but its notes and one-time
playbooks.

1. **Undo the unknown commit at once.** The coding agent reverts it in its clone and publishes the revert, as
   [Making a change](../AGENTS.md#making-a-change) says. It runs nothing else yet.
   Reason: after the revert, a run of `main` applies nothing of the unknown change.
   Never remove the commit with a force push: the main copy refuses it, and the commit is evidence.
   **Check:** `git show` of the revert removes every line of the unknown commit.
2. **Find the key that pushed.** On `util01`, the main copy's reflog gives the time of each change to `main`, and
   sshd's journal gives the key that logged in as root at that time, by its fingerprint and source address:

   ```sh
   ssh -F ssh/config root@10.20.0.1 'git -C /var/lib/systems_repository.git reflog show --date=iso refs/heads/main | head -20'
   ssh -F ssh/config root@10.20.0.1 'journalctl -u ssh --since "2026-11-17 10:00" --until "2026-11-17 10:10" | grep "Accepted publickey for root"'
   ```

   Match the fingerprint with `ssh-keygen -l` of each key in `root_ssh_public_keys`: its comment names the desk, such
   as `alex on desk01`, or `util01, the mmhotline user`.
   **Check:** the reflog's change and a journal line name the same time, and the key is known.
3. **Find what already ran.** The coding agent reads MMX's run history with
   `./server_management_scripts/run_mmx_on_util01 results`, and MMHotline's triage runs in its dashboard, from the
   time of the unknown commit on.
   **Check:** each run since that time is known.
4. **Go to the lock-out.** The desk or `util01` whose key pushed is suspect, and its key has root on every server:
   go to [The lock-out: only for these cases](#the-lock-out-only-for-these-cases). When the pushing key is your own
   desk's, go to [When your own desk was the way in](#when-your-own-desk-was-the-way-in).
   Reason: whoever holds that key has root on every server, so the key goes, not only the commit.
   **Check:** the lock-out's own checks.

**A commit only at the Git host's backup** never reached a server: the Git host is a backup that nothing reads. It
shows as a refused backup push ("The main copy and the backup at the Git host" in
[`AGENTS.md`](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)). Never merge it. The person does the Git
host row of ["At each company's website"](#1-lock-everyone-out), and nothing else on this page is needed.

## An unknown session at a company

**When:** a company sends an alert, or the company's website lists a session or a token that nobody on the team
recognises.

For each company, the person ends the unknown sessions and tokens first, as the company's row of
["At each company's website"](#1-lock-everyone-out) says. Then the person reads the company's audit log with the
coding agent, from the first unknown session on.

- **The server provider's account,** on the provider's website, console or API, means root on every server: the provider console
  opens each server, and the provider can copy or replace each disk. No lock-out helps, because the provider console
  stays a way in during a lock-out. Revoke at the provider: sessions, API tokens, console access and registered
  provisioning keys. Replace the [provider API token](rotate_a_secret.md#the-provider-api-token) and the
  [shared root console password](rotate_a_secret.md#the-shared-root-console-password). When the audit log shows a
  console login, a disk copy or a new server, rebuild the affected servers, as
  [4. Rebuild and replace exposed keys](#4-rebuild-and-replace-exposed-keys) says.
- **Cloudflare** holds the tunnels, the Access admission, the R2 buckets and the DNS records. Remove other people's
  Access admission and revoke Access sessions. Then the person replaces every Cloudflare key with
  `--replace-every-key --delete-the-old-keys-at-once`, as step 4's item 5 shows. The coding agent compares the DNS
  records and Access policies with the team's records.
- **The registry:** the servers deploy each image by its tag, and pull an image only when the server lacks it.
  So an image that the intruder pushed under an existing tag reaches only a new or replaced server.
  Replace the [registry credentials](rotate_a_secret.md#the-container-registry-token). Compare the registry's tags,
  on the registry's package page that the person opens signed in, or with `gh` when it is signed in on the laptop,
  with `deployed_image_tags` in `inventories/servers.yml`. Build the image again from the reviewed source, in CI or,
  without CI, in a container on the laptop, push the image under a new tag, and deploy the new tag, before a server is
  added or replaced.
- **The password manager or the identity provider** holds the recovery logins and the recovery passphrase, which
  opens the recovery bundle: the production key, the WireGuard key of the desk it covers, and the vault passphrase. So every kept credential is suspect: go to
  [The lock-out: only for these cases](#the-lock-out-only-for-these-cases). The person changes the master password
  from a clean device.
- **The coding-agent vendor's account** holds the stored conversations and may hold the triage agent's credential.
  The coding agent never reads a secret, so the conversations hold no secret. Revoke affected personal
  subscriptions, API keys and active sessions. Replace the [triage agent credential](rotate_a_secret.md#the-triage-agent-credential).
  When the vendor's records show a session that nobody on the team ran, the laptop it ran on, and so its desk, was
  the way in: [When your own desk was the way in](#when-your-own-desk-was-the-way-in).
- **Staging's Access token** reaches only `staging01`'s pages behind Cloudflare Access. The person replaces the token
  with `ssh -t desk01 set-up-outside-services cloudflare --replace-key STAGING_ACCESS_CLIENT_SECRET`, as
  [Cloudflare keys](rotate_a_secret.md#cloudflare-keys) says.

**Check:** at each company, the lists of sessions and tokens show only the team's, and the audit log shows no
change that nobody on the team made.

## A member left with a credential

**When:** a person left the team and still holds a credential, such as a token, a password or a laptop.

Follow [Add or remove a team member](add_or_remove_a_team_member.md#adding-or-removing-a-person), "Leaving", and
replace each secret that the person knew, as [Rotate a secret](rotate_a_secret.md) says. Every other desk,
`util01` and the triage agent keep working. Reason: removing the person's key and peer with a normal run closes the
person's way into the servers.

**Check:** the checks of the two procedures. When the evidence shows that the person logged in to a server as root
after leaving, go to [The lock-out: only for these cases](#the-lock-out-only-for-these-cases).

## The lock-out: only for these cases

**Do this now, when the facts match one of the three cases below:**

1. For a desk with no signs ([Check a desk for signs](#check-a-desk-for-signs)), the coding agent that works through that desk publishes
   the one-line commit `everyone_locked_out_except_desk: desk01`, with that desk's name, under the top-level `vars`
   of `inventories/servers.yml`.
2. You run the lock-out button for that desk, on its laptop:

   ```sh
   # On the laptop:
   ssh -t desk01 sudo lock-everyone-out
   ```

3. Read each line, type `yes`, and continue with step 3 of [Lock everyone out now](#lock-everyone-out-now).

The rest of this section explains the cases, what the lock-out closes, and which desk runs the button.

The lock-out button, `sudo lock-everyone-out`, cuts off at the servers every way in except the desk that runs the
button. Use the lock-out only in these cases:

- **`util01` or the triage agent is suspect:** `util01` or the triage agent did something that nobody asked for, or
  evidence shows that someone else used `util01`.
- **An unknown root login, process or MMX run on the servers.** A desk that was the way in counts here, because a
  desk holds root on every server ([When your own desk was the way in](#when-your-own-desk-was-the-way-in)).
- **A desk, or a credential that a desk or the password manager keeps, is suspect, and nobody knows which.**

In every other case, the lock-out harms more than the lock-out helps. The lock-out cuts off every other desk,
`util01` and the triage agent: the people and agents that the team needs to find and fix the break-in. And the
lock-out closes no way in through the app, a company's account or the provider console. So the coding agent
recommends the lock-out only when the facts match one of the three cases, and the person runs the one command.
Within those cases, credible evidence is enough to start, because a lock-out can be undone
([Undo a lock-out](#undo-a-lock-out)) and customers keep using the app.

**What the lock-out closes:**

- every other desk's production key, WireGuard peer and SSH sessions at the servers;
- `util01`'s root key, and the triage agent;
- MMX's HTTPS service on every server, and a running MMX job;
- the sessions of the private Cloudflare Access applications.

**What the lock-out does not close:**

- the desk that runs the button, which keeps working;
- the provider console;
- the app, and each company's account.

**Which desk runs the button.** The lock-out cannot shut out the desk that runs the lock-out. So with a team, the
person on a desk with no signs runs the button. A lock-out from a suspect desk leaves the suspect desk as the only way
in, and a colleague's own button then fails, because the colleague's desk is cut off. Working alone, the person runs
the button on the person's own desk, as [When your own desk was the way in](#when-your-own-desk-was-the-way-in) says.

When the team has two desks, each person checks their own desk, as
[Check a desk for signs](#check-a-desk-for-signs) says, and the desk with no signs runs the button. When both desks
show signs, no desk is trusted: the person who leads the response follows "Working alone" in
[When your own desk was the way in](#when-your-own-desk-was-the-way-in) on the lead's desk, and the other person
powers off the other desk at the provider.

The same command undoes the lock-out ([Undo a lock-out](#undo-a-lock-out)).

### Check a desk for signs

The person runs these two reads in their own desk login, `ssh desk01` and a phone code. Both reads change nothing.

```sh
# On the desk, as the person:
sudo -u coding-agent git -C /home/coding-agent/systems_repository log --since="14 days ago" --date=iso --format='%h %ad %an %s'
sudo journalctl -u ssh.service --since "-14 days" --grep "Accepted" --no-pager
```

- **Commits:** each line shows the commit, its time, its author and its message. A commit that nobody on the team
  made is a sign. [An unknown commit in the systems repository](#an-unknown-commit-in-the-systems-repository) says
  how to find the key that pushed it.
- **Logins:** each `Accepted` line shows a login to the desk, as the person or as `coding-agent`, with its time and
  its address. First check whether the login is your own or your coding agent's: your laptop's address is in the
  desk's `allowed_laptops` in `inventories/servers.yml`, such as `10.20.10.1`, and the time matches a time you or
  your coding agent worked. A login from another address, or at a time nobody worked, is a sign.

**Check:** a desk with no such commit and no such login shows no signs.

### Lock everyone out now

The lock-out button cuts off every other desk and `util01` at the servers, and stops the triage agent.
Customers keep using the app. You and your coding agent keep working from your desk, the desk that keeps access.

**First: could this desk be the way in?** Check this desk, as [Check a desk for signs](#check-a-desk-for-signs)
says. When this desk shows signs:

- **With a teammate whose desk shows no signs,** do not use this desk. The teammate follows these steps on the
  teammate's desk. Then follow "With a teammate" in [When your own desk was the way in](#when-your-own-desk-was-the-way-in).
- **Working alone,** follow these steps on this desk, because no other desk exists. Then follow "Working alone" in
  [When your own desk was the way in](#when-your-own-desk-was-the-way-in).

1. **Your coding agent, on your laptop, prepares and publishes a one-line commit:** `everyone_locked_out_except_desk: desk01`,
   with your desk's name, under the top-level `vars` of `inventories/servers.yml`, as
   [Making a change](../AGENTS.md#making-a-change) describes. The coding agent never applies the setting itself:
   only the lock-out button starts a lock-out.
   **Check:** the coding agent tells you the commit and gives you the command below. When the coding agent cannot
   be used, [make the commit by hand](#make-the-lock-out-commit-by-hand).
   On a desk that shows signs, your laptop and its coding agent are suspect too, because only your laptop reaches
   your desk. So read the commit yourself, in your own desk login:
   `sudo -u coding-agent git -C /home/coding-agent/systems_repository show HEAD` must change only the one line in
   `inventories/servers.yml`. Or make the commit by hand.
2. **You run the lock-out button,** on the laptop, with a phone code:

   ```sh
   # On the laptop:
   ssh -t desk01 sudo lock-everyone-out
   ```

   The lock-out button pulls the coding agent's commit, shows every server and the desk that keeps access,
   and asks you to type `yes`.
3. **Read each line before you type `yes`.**
   **Check:** the list shows `everyone_locked_out_except_desk` as you expect, and every server is one you know.
   If a server is not one you know, press Enter: nothing changes. Ask your coding agent where the server came from,
   and to remove it from `inventories/servers.yml` and push, before you run the lock-out button again.
   Reason: the lock-out connects every server with the servers the inventory names, so a server that an intruder
   pushed to the main copy on `util01` would join the private network through the lock-out itself.
4. **Type `yes`, then read the last lines.**
   **Check:** they end with how to undo the lock-out. A line that starts "MMX ended with exit code"
   names what failed: [step 1](#1-lock-everyone-out) says what to do.

Then continue with [step 1](#1-lock-everyone-out).

### Make the lock-out commit by hand

**When the coding agent cannot be used,** make the commit by hand in the desk's checkout, in your own desk login
(`ssh desk01` and a phone code). `agent_git` runs Git as the coding agent, with the desk's production key, so the
checkout stays the coding agent's own:

```sh
# On the desk, as the person:
cd /home/coding-agent/systems_repository
agent_git() { sudo -u coding-agent env SSH_AUTH_SOCK=/run/desk-ssh-agent/socket GIT_CONFIG_SYSTEM=/etc/systems-desk/coding-agent-gitconfig git -c core.hooksPath=/dev/null "$@"; }
agent_git pull --ff-only
# Adds the setting as the first line under the inventory's top-level vars:. GNU sed, as on the desk.
sudo -u coding-agent sed -i '0,/^vars:$/s//vars:\n  everyone_locked_out_except_desk: desk01/' inventories/servers.yml
grep -n -A1 '^vars:$' inventories/servers.yml
```

The last line prints the setting under `vars:`, and the existing values stay:

```yaml
vars:
  everyone_locked_out_except_desk: desk01
```

Commit and push the setting to the main copy on `util01`:

```sh
agent_git add inventories/servers.yml
agent_git commit -m 'Lock production administration to desk01 during incident response'
agent_git push origin main
```

When `util01` does not answer, or the push is refused, go on: the lock-out button uses the desk's checkout as it is.
Then run `sudo lock-everyone-out` in the same login.

### What the lock-out leaves running

The desk that keeps access retains production access. Other desks retain local sessions but lose their production keys and peers.
On the desk that keeps access, you and the coding agent keep working: the coding agent's login to the desk, its buttons and the API proxy keep running.
Server triage stops. The lock-out button also revokes sessions for the configured private Cloudflare Access applications.
A failed Cloudflare revocation is reported after local containment. Complete that revocation at Cloudflare's website.

### What the lock-out button does, in order

1. It pulls `main` from the main copy on `util01` into the desk's own copy, through your coding agent's checkout.
   When the pull does not work, because `util01` does not answer, the lock-out button says so in one sentence and goes
   on with the desk's copy as it is. Reason: a break-in must not wait for `util01`.
   Then check that the list below shows `everyone_locked_out_except_desk` as you expect.
2. It shows every server of the inventory, one line each, with its pool, its private address and its public
   address; then the desk that keeps access and the desks that lose access; and asks you to type `yes`.
   If a server is not one you know, press Enter: nothing changes (step 3 of [Lock everyone out now](#lock-everyone-out-now)).
3. It runs the lock-out programs that your last desk review installed, root-owned in
   `/usr/local/lib/systems-desk/lock-everyone-out/`: the playbook `lock_everyone_out`, its two lock-out roles,
   `start_break_in_lockout.py`, the SSH settings, and the files the lock-out installs on the servers:
   the WireGuard peer template, the triage user's sudo rules and `mmhotline_settings.yml`.
   It takes only data from the pulled repository: the inventory, the servers' host keys, the settings and the vault.
   When the pulled repository changes one of those reviewed files, the lock-out button names the file and uses the
   reviewed copy. After the incident, run `ssh desk01-review` and read the change before you approve it.
   Reason: an intruder who can push to the main copy on `util01` must not get root on your desk, or on every server,
   through the lock-out; a pushed change to a lock-out program reaches root only through your desk review.
   The lock-out button stops before changing anything when a node's `ssh_config` in the inventory is not one of the
   reviewed SSH settings files.
4. It keeps this desk's own production key, `/etc/systems-desk/production_key.pub`, its own WireGuard address,
   from `/etc/wireguard/wg0.conf`, and its own WireGuard public key, from `/etc/wireguard/wg0.private_key`, never values
   from the pulled repository. When `nodes.desk01.vars.production_ssh_public_key`, `nodes.desk01.vars.private_ip`
   or `nodes.desk01.vars.wireguard_public_key` differs from them, the lock-out button stops before changing any server and
   names the value to correct. It also stops when the inventory no longer lists this desk in `systems_desks`, or
   `root_ssh_public_keys` no longer holds this desk's key. The undo checks the same, so no press cuts off the desk it
   runs on ([Undo a lock-out](#undo-a-lock-out)).
5. Its last lines say how to undo the lock-out, and name what failed: a server, which stays a way in until you
   isolate it at the provider, or only the desk's revocation of Cloudflare Access sessions, which you then do at
   Cloudflare's website, as the table under "At each company's website" in step 1 says. Its run history stays in `/var/lib/systems-desk/lock-everyone-out-run/`:
   `sudo mmx results` there shows the last run.

## 1. Lock everyone out

Use a trusted desk to cut off administration while customers keep using the app.
Step 1 starts once [Lock everyone out now](#lock-everyone-out-now) has run the lock-out button from a desk that is
not the way in; this step says what to do next, and why.

1. **Read the result for every server.**
   **Check:** a failed server remains an open way in until isolated at the provider: isolate it there. When only
   the desk's revocation of Cloudflare Access sessions failed, complete that revocation at Cloudflare's website,
   as the table under "At each company's website" below says.
2. **At each company's website, keep the trusted response identity and revoke the affected identities.**
   When a desk was the way in, the suspect desk's own tokens and keys count as affected identities too, even when
   the suspect desk is your own:

   | Company | What the person ends |
   | --- | --- |
   | Git host | Other members' sessions, personal tokens, SSH keys and app authorizations. Disable untrusted CI and publishing credentials. The Git host holds the app's code and the systems repository's backup; no desk or server key is there. |
   | Cloudflare | Other members' account sessions and API tokens, and the suspect desk's desk token and posting key. Remove other people's Access admission, revoke Access sessions, and revoke exposed staging service tokens. |
   | Server provider | Other members' sessions, API tokens, console access and registered provisioning keys, and the suspect desk's provider token. |
   | Registry | Other members' sessions and publishing tokens. Preserve the running servers' pull identity until step 4 replaces that identity. |
   | Object storage | Other members' console sessions and personal keys, including status-posting keys. Preserve runtime upload and backup identities until step 4. |
   | Password manager and identity provider | Other members' sessions, recovery methods, organization membership and shared-vault access. |
   | Coding-agent vendor | Affected personal subscriptions, API keys and active sessions. |

   Reason: a copied token remains usable until the issuing company revokes the token.
   **Check:** at each company, the lists of sessions and tokens show only the trusted response identity's.
3. **At the provider, snapshot each suspect desk's disk, record the snapshot and server IDs, then power off that desk.**
   Reason: no command from the desk that keeps access reaches into another desk.
   **Check:** the provider shows the snapshot, and the desk powered off.
4. **If an interrupted restore drill left `restore01`, snapshot and power off `restore01` at the provider too.**
   Keep the drill's server-ID receipt from the evidence copy for later removal.
   Reason: the temporary restore server peers only with util01 and has no direct administration path from the desk that keeps access.
   **Check:** the provider shows `restore01` powered off.
5. **If the attacker is destroying data,** send public requests to the status page, as
   [Send the app's requests to the status page](#send-the-apps-requests-to-the-status-page) says.
   **Check:** the checks of that section.

**During a lock-out, the coding agent runs every MMX command with its MMX button,**
`sudo -n -u servers-mmx run-mmx-on-the-servers`, on the desk that keeps access, with `--connection ssh_only`.
Reason: `util01` has lost admission at the servers, and the lock-out stopped MMX's HTTPS service on every server.
During a lock-out, `every_server` runs only from the desk that keeps access: anywhere else, util01 included, its first checks refuse the run and change nothing.
They also refuse, and change nothing, when the inventory's desk, `private_ip`, `wireguard_public_key` or `production_ssh_public_key`
for the desk that keeps access differs from what the lock-out button recorded when you pressed it. To change one of them, you run the lock-out button again.

## 2. Save the evidence

Copy the retained logs before investigation, secret changes or server replacement can overwrite evidence.
The evidence copy runs only on the desk that keeps access during a lock-out, and refuses otherwise. Outside a
lock-out, provider snapshots keep the evidence, as [Find out what happened](#find-out-what-happened) shows.

1. **Run the evidence copy** in the person's terminal on the desk that keeps access:

   ```sh
   sudo --preserve-env=SSH_AUTH_SOCK \
     python3 /usr/local/lib/systems-desk/lock-everyone-out/server_management_scripts/save_break_in_evidence.py \
     --desk-name desk01 --database-server-with-backup-credentials db01 --output-dir /home/alex/break-in-evidence
   ```

   The command runs the evidence script that the person's last desk review installed, with the
   reviewed SSH settings beside it, never the pulled repository's script or SSH settings.
   Reason: the script reads this desk's own logs as root.
   **Check:** the command prints the evidence directory and verifies encrypted copies in the production backup
   bucket. `collection.log` records missing paths and live files changing during collection. `manifest.json`
   records checksums and failed servers.
2. **If a server is unreachable, snapshot the server's disk at the provider and record the gap before replacement.**
   **Check:** the provider shows the snapshot.
3. **Keep evidence and the manifest outside Git. Keep the backup encryption passphrase in the vault as it is.**
   **Check:** none, because both are places to keep things, not commands.

The copies include journals, retained authentication and web logs, MMX run records, private MMX failure details, and the histories of the desk that keeps access.
The helper copies every inventory server except other desks. Provider snapshots preserve those desks' evidence.

To open a downloaded `.tar.gz.enc` evidence copy, the person runs this on the desk that keeps access, in their own login.
The backup passphrase, `pgbackrest_repository_cipher_passphrase`, goes straight from the vault into OpenSSL.
Nobody sees it, and nobody opens the vault.

```sh
# On the desk that keeps access, as the person, in the folder with the evidence copy:
work=$(mktemp -d)
cp /home/coding-agent/systems_repository/secrets_vault.age "$work/"
sudo install -o "$USER" -m 0600 /etc/systems-desk/vault-passphrase "$work/vault-passphrase"
# `mmx secrets pipe-to` writes the one item to openssl's standard input: nobody sees it, and the vault stays unchanged.
MMX_VAULT_PASSWORD_FILE="$work/vault-passphrase" mmx secrets pipe-to --vault "$work/secrets_vault.age" \
  pgbackrest_repository_cipher_passphrase -- \
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 -pass stdin \
    -in desk01.tar.gz.enc -out desk01.tar.gz
rm -r "$work"
```

## 3. Find what was taken

Build a timeline from the copies so the team can distinguish exposed information from guesses.

1. **Open the copies:**

   ```sh
   sudo find /home/alex/break-in-evidence -name manifest.json -o -name collection.log
   printf 'Paste the evidence directory printed in step 2: '
   IFS= read -r evidence_dir
   sudo less "$evidence_dir/util01/journal.export"
   sudo tar -tzf "$evidence_dir/util01/retained-files.tar.gz"
   ```

   Read copied journal exports as text.
   **Check:** `find` lists each `manifest.json` and `collection.log`, and the journal and file list open.
2. **Inspect authentication records, Git changes, MMX runs, provider events and company audit logs.**
   **Check:** none, because the next item records what this finds.
3. **Record the first known access, affected accounts, viewed or changed data, and evidence for each conclusion.**
   An absent log does not prove that data stayed private.
   **Check:** ask incident help to review uncertain findings: the response page of step 0 names who provides
   incident help and how to reach that person.

## 4. Rebuild and replace exposed keys

Replace affected machines from reviewed repository files, because removing a login cannot remove an attacker's installed code.

Keep containment set during rebuilding. The coding agent works from the desk that keeps access, using `--connection ssh_only`.
For linked procedures, replace each `./server_management_scripts/run_mmx_on_util01` run with the coding agent's MMX button:

```sh
sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only
```

Use each linked procedure's actual playbook name and arguments when the procedure names a different playbook.
Apply the following order. Verify each replacement before revoking the old working runtime credential.

Before item 3, decide with the person whether the database goes back to a time before the break-in.
When the timeline of step 3 shows that the intruder changed or deleted data in the database, follow
[Bring the whole database back to a chosen minute](recover_when_every_database_server_is_lost.md#bring-the-whole-database-back-to-a-chosen-minute):
the section gives the time to choose, the command, and which rebuild steps of item 3 to skip.
Reason: the restore refuses while the new failover monitor knows an old database server, and item 3's rebuild registers them.
When the uploaded files were deleted or overwritten too, follow
[Restore all of an app's uploaded files](restore_an_uploaded_file.md#restore-all-of-an-apps-uploaded-files)
after item 5 replaced the app's own R2 key, with the same time as the database.

1. **Recover company ownership and review Git history, roles, images and pending MMHotline approvals.**
   Reject untrusted queued requests. Read each commit since the break-in with the person, and revert each one
   nobody on the team made, as
   [An unknown commit in the systems repository](#an-unknown-commit-in-the-systems-repository) says. Replace personal company credentials using [Personal desk credentials](rotate_a_secret.md#personal-desk-credentials).
   Rebuild suspect desks using fresh production SSH, WireGuard, host and phone identities when the old identities were exposed,
   in the order that [When your own desk was the way in](#when-your-own-desk-was-the-way-in) gives.
   Update each desk's `production_ssh_public_key` alongside `root_ssh_public_keys` when replacing a production key.
   Load the replacement private key into the person's private SSH agent before applying its new public mapping.
   **Check:** each replacement works before the old credential is revoked.
2. **Replace the [vault passphrase](add_or_remove_a_team_member.md#replace-the-vault-passphrase-and-secrets) and [shared root console password](rotate_a_secret.md#the-shared-root-console-password).**
   Old vault copies remain readable with the old passphrase, so continue replacing exposed vault secrets.
   **Check:** the checks of the two linked sections.
3. **Follow [Rebuild util01](rebuild_the_utility_server_util01.md), with the coding agent's MMX button in place of each `util01` run, as above.**
   When the database goes back to a time before the break-in, skip rebuild steps 5 and 6, as the restore section says.
   A fresh util01 generates new controller and triage SSH keys and a new MMWatchdog hub identity and join secret.
   Record the generated public keys in `root_ssh_public_keys` and `triage_ssh_public_key`, and replace the controller's provider registrations.
   Apply the new utility peer and rejoin reporting nodes. Rejoin each trusted desk locally through `systems_desk`.
   Do not restore old generated private keys or the old MMWatchdog state directory.
   **Check:** the checks of Rebuild util01.
4. **Follow [Replace a server](replace_a_server.md) for app, jobs, load-balancer and database servers.**
   Replace a server copies the running database, the intruder's changes included. When the database goes back
   to a time before the break-in, the restore section's new database server replaces the database servers instead.
   New first-boot payloads admit only the production key and peer of the desk that keeps access while containment remains set.
   Generate each replacement server's WireGuard pair before creation, as the creation procedure describes.
   New machines generate fresh SSH host keys and MMX's `/var/lib/mmx/tls.key`.
   Replace the corresponding inventory public keys, endpoints and verified host-key lines.
   MMX HTTPS authenticates with the production SSH keys. Do not restore old `/var/lib/mmx` identity files from evidence.
   **Check:** the checks of Replace a server, for each server.
5. **Replace every Cloudflare key:** the tunnel tokens, each app's R2 key, `util01`'s R2 key, the MMHotline-down alarm's token,
   the status page's R2 key, the person's own desk token and posting key, and with `staging01` staging's service token.
   The person types, on the laptop of the desk that keeps access, with a phone code:

   ```sh
   ssh -t desk01 set-up-outside-services cloudflare --replace-every-key --delete-the-old-keys-at-once
   ```

   The command makes each new key, saves it in the vault or the token file, and deletes each old key at Cloudflare
   without waiting for the servers' run, as [Cloudflare keys](rotate_a_secret.md#cloudflare-keys) says.
   Reason: an outside attacker may hold the old keys, and a few minutes of failed uploads and status posts are the smaller harm.
   Then run `every_server` with the coding agent's MMX button, as above: until that run ends, the apps cannot reach
   their uploads and MMHotline cannot post to the status page.
   Delete each other team member's Cloudflare tokens with `--delete-tokens-of-person`, as
   [Add or remove a team member](add_or_remove_a_team_member.md#adding-or-removing-a-person) says;
   each member makes new ones with `ssh -t desk02 set-up-outside-services cloudflare`, with their own desk name,
   after the lock-out is undone.
   Replace [registry credentials](rotate_a_secret.md#the-container-registry-token),
   [app secrets](rotate_a_secret.md#app-secrets), [database passwords](rotate_a_secret.md#app-database-passwords),
   [monitor passwords](rotate_a_secret.md#the-failover-monitor-password), and [replication passwords](rotate_a_secret.md#the-replication-password).
   Reset affected app administrator accounts and end those accounts' sessions.
   Replace app signing secrets and webhook credentials through each app's own controls.
   **Check:** the checks of each linked section of Rotate a secret, after the `every_server` run.
6. **Replace [B2 keys](rotate_a_secret.md#backblaze-b2-keys),** with `--delete-the-old-keys-at-once` for the same reason,
   [provider credentials](rotate_a_secret.md#the-provider-api-token), [triage credentials](rotate_a_secret.md#the-triage-agent-credential),
   [Pushover keys](rotate_a_secret.md#pushover-keys),
   [MMHotline-down alarm check-in tokens](rotate_a_secret.md#the-mmhotline-down-alarm-check-in-token),
   and [fleet signing secrets](rotate_a_secret.md#the-fleet-hub-signing-secret).
   Preserve `pgbackrest_repository_cipher_passphrase` to retain access to earlier backups.
   **Check:** the checks of each linked section of Rotate a secret.
7. **Verify the app, a backup, alerts, fresh trusted logins and the independent status page.**
   Remove containment only after replacing exposed identities. Then [undo the lock-out](#undo-a-lock-out) and recheck the restored paths.
   **Check:** each of the five works, before the undo and again after it.

## Undo a lock-out

After a false alarm, or at the end of [step 4](#4-rebuild-and-replace-exposed-keys), undo the lock-out the same way.
The lock-out button's last line after a lock-out names this section.

**Before you start:** the keys that the undo lets in are only trusted keys. The undo lets in, on every server, each
key in `root_ssh_public_keys` as root and `triage_ssh_public_key` as the triage user, from
`mmx_project_settings.yml`. `root_ssh_public_keys` holds each desk's production key and `util01`'s key
([The rules](../AGENTS.md#the-rules)). After step 4, those are the trusted desks' current production keys and the
new `util01`'s keys (step 4, items 1 and 3). When a desk was the way in, the list holds the fresh desk's key. The old
desk's key is already out when a teammate's desk runs the undo, and comes out after the undo when you work alone
([When your own desk was the way in](#when-your-own-desk-was-the-way-in)).

**The undo never cuts off the desk it runs on.** Before it changes any server, the lock-out button checks that what
it installs still lets this desk in: this desk's production key is in `root_ssh_public_keys`, and the inventory
still lists this desk in `systems_desks` with this desk's own WireGuard address and keys. Otherwise it stops, says
which value to correct, and says "Nothing changed". Reason: an undo that removed its own desk's key would lose its
SSH connection after some servers changed, with the servers still locked out and no desk able to finish it.

1. **Your coding agent lists each key in `root_ssh_public_keys` and `triage_ssh_public_key`,** with its comment and
   its fingerprint as `ssh-keygen -l` shows it, and says whose key each one is. On a desk that showed signs, you
   read the list yourself, in your own desk login.
   Reason: the lock-out button shows only the keys added or removed since your last desk review, so a key that
   arrived earlier is not shown at the undo.
   **Check:** each key belongs to a trusted desk or to `util01`. If a key is not one you know, your coding agent
   removes it from `mmx_project_settings.yml` and publishes before the undo.
2. **Your coding agent prepares and publishes the commit that removes `everyone_locked_out_except_desk` from
   `inventories/servers.yml`, and gives you the command.**
   When the coding agent cannot be used, remove the line by hand, as [step 1](#make-the-lock-out-commit-by-hand) shows for adding it.
   **Check:** the coding agent tells you the commit.
3. **You run `ssh -t desk01 sudo lock-everyone-out` again,** on the laptop, with a phone code.
   The lock-out button shows the servers and asks you to type `yes`.
   When the inventory names an SSH settings file, such as `ssh/desk03`, that your last desk review did not install,
   the button stops with nothing changed: run `ssh desk01-review` first. That desk review
   shows the key changes too, and records them.
   **Check:** when a key was added or removed since your last desk review, the lock-out button shows each one and
   asks you a second time. When your desk review just showed them, the button says instead that the keys are the
   same as at your last desk review. If a key is not one you know, or a key you need is gone, press Enter: nothing changes.
   Ask your coding agent to correct the keys in `mmx_project_settings.yml` and publish, then run the lock-out button again.
   Step 4 replaces keys on purpose, so expect the lock-out button to show those new keys at the final undo.
4. **Read the last line.**
   **Check:** when the undo fails on a server, its last line says so: that server is still locked out, so `util01` and the other
   desks cannot reach it yet. Your coding agent fixes the cause, and you run `ssh -t desk01 sudo lock-everyone-out` again.
   When no desk reaches a server any more, follow [Recover a half-undone lock-out](#recover-a-half-undone-lock-out).

After the undo, MMHotline and `util01` run every commit on the main copy again, as before the lock-out.

The undo lets in, on every server, each key in `root_ssh_public_keys` as root and `triage_ssh_public_key` as the triage user,
from `mmx_project_settings.yml`. So the lock-out button compares those keys with the ones your last desk review recorded.
When they match, it goes on. When a key was added or removed, it shows each one, with its comment and its fingerprint
as `ssh-keygen -l` shows it, and asks you a second time.
Reason: anyone who can push to the main copy on `util01` could add a key, and the undo would let that key in as root on every server.
Other desks start fresh SSH sessions to the servers. Company-side revocations need fresh credentials and sign-ins at each company.

## When your own desk was the way in

**When:** signs on your own systems desk, as [Check a desk for signs](#check-a-desk-for-signs) finds them, or a
process on your desk that nobody started.

**What the intruder can reach:** everything that your desk reaches. That is root on every server, `util01` included,
and your desk's production SSH key, WireGuard key, provider token and Cloudflare tokens. Your desk's key
can push to the main copy on `util01`, and `util01` runs every commit there. So a desk that was the way in counts as an unknown root login, one of
the lock-out cases.

**A trusted laptop** is a new laptop, or your laptop after its operating system is reinstalled, as
[Recover from a lost or stolen laptop](recover_from_a_lost_or_stolen_laptop.md#before-you-start) says.
Reason: only your laptop reaches your desk, so a desk that was the way in makes the laptop and its coding agent
suspect too. An untrusted program may still be running there.

**Why the new desk gets fresh keys:** [Rebuild a systems desk](rebuild_a_systems_desk.md) restores the old desk's
production and WireGuard keys from the recovery bundle. Here the intruder may hold copies of those keys. So the new
desk is built with fresh keys, as a new team member's desk is, and the old desk's key leaves `root_ssh_public_keys`.

**The order of the key change:** the new desk's key goes into `root_ssh_public_keys` before the undo, so the undo lets
the new desk in. The old desk's key comes out without ever cutting off the desk that runs the undo:

- With a teammate, the teammate's desk runs the undo, so one commit adds the new key and removes the old key.
- Working alone, the old desk runs the undo, so its key stays in until the undo has finished and the new desk has
  joined. Then the new desk removes the old key. The undo refuses to remove the key of the desk it runs on.

The old desk is deleted at the end, in both orders.

### With a teammate

1. **Tell your teammate.** The teammate, on a desk with no signs, follows
   [Lock everyone out now](#lock-everyone-out-now), with the teammate's own desk in `everyone_locked_out_except_desk`.
   Reason: the lock-out cannot shut out the desk that runs the lock-out.
   **Check:** the button's last lines on the teammate's desk say how to undo the lock-out.
2. **Snapshot and power off your desk at the provider,** and record the snapshot and server IDs, as step 1's item 3 says.
   **Check:** the provider shows the snapshot, and your desk powered off.
3. **Revoke your desk's tokens** at each company, as the table in step 1's item 2 says for the suspect desk: the
   provider token, and the Cloudflare desk token and posting key.
   **Check:** each company lists none of your desk's tokens or keys.
4. **The teammate continues with steps 1 to 3** from the teammate's desk.
   **Check:** the checks of those steps.
5. **Build a new desk from a trusted laptop with fresh keys,** under the next desk name, such as `desk03`, as
   "Joining" steps 2 to 7 of [Add or remove a team member](add_or_remove_a_team_member.md#joining) say for a
   new person. Never restore the old desk's keys from the recovery bundle.
   **Check:** the new desk's patch file reaches the teammate, as "Joining" step 7 says.
6. **The teammate's coding agent adds the new desk and removes the old desk's key, in one commit:** the new desk's
   entry and key, as "Joining" step 8 says, and the old desk's key out of `root_ssh_public_keys`. The coding agent
   publishes the commit, but does not run `every_server` for the new key.
   Reason: during the lock-out, the servers admit only the desk that keeps access. The undo lets the new key in.
   **Check:** the diff adds the new key and removes only the old desk's key.
7. **The teammate runs a desk review, `ssh desk02-review`, continues with step 4, then undoes the
   lock-out,** as [Undo a lock-out](#undo-a-lock-out) says. Reason: the undo connects only with SSH settings files
   that a desk review installed, and the new desk's `ssh/` file is new.
   **Check:** the desk review shows the new desk's key added and the old desk's key removed, and the undo then says
   the keys are the same as at the last desk review.
8. **Finish the new desk,** as "Joining" steps 9 to 13 of Add or remove a team member say.
   Reason for after the undo: the new desk fetches `main` from the main copy on `util01`, and during the lock-out
   `util01` admits only the desk that keeps access.
   **Check:** the checks of that step, and from the new desk, `ssh -F ssh/config root@10.20.1.1 true` works.
9. **Delete the old desk** by the old desk's verified provider ID, as
   [Find the old desk at the provider](rebuild_a_systems_desk.md#find-the-old-desk-at-the-provider) and step 22 of
   Rebuild a systems desk say. Then remove the old desk's entry, its `ssh/` settings file and its known-host lines,
   as step 2 of "Leaving" in Add or remove a team member says.
   **Check:** a fresh provider listing no longer shows the old desk.

### Working alone

Working alone, your desk is the only desk, so you run the lock-out on your own desk. The lock-out still cuts off
`util01`, the triage agent and MMX's HTTPS service. Your desk stays a way in until the provider powers the desk off.
You use the old desk again for a few minutes, for items 6 and 7, because during a lock-out the servers admit only
that desk, so only that desk can run the undo.

1. **Lock out from your own desk,** as [Lock everyone out now](#lock-everyone-out-now) says, with your desk's name.
   Read the one-line commit yourself before you press, because your laptop and its coding agent are suspect.
   Reason: `util01` runs every commit on the main copy, and your desk's key can push there, so the lock-out stops
   what the intruder pushes.
   **Check:** the button's last lines say how to undo the lock-out.
2. **Save the evidence,** as [2. Save the evidence](#2-save-the-evidence) says, on your desk.
   **Check:** the checks of step 2.
3. **Revoke your desk's provider token and Cloudflare desk token and posting key** at each company.
   **Check:** each company lists none of the revoked tokens.
4. **Snapshot and power off your desk at the provider,** and record the snapshot and server IDs.
   Power the desk on again only for items 6 and 7.
   **Check:** the provider shows the snapshot, and the desk powered off.
5. **Build a new desk from a trusted laptop with fresh keys,** under the next desk name, such as `desk02`, as
   "Joining" steps 2 to 7 of [Add or remove a team member](add_or_remove_a_team_member.md#joining) say.
   Never restore the old desk's keys from the recovery bundle.
   **Check:** the new laptop's coding agent wrote the patch file, `~/add-desk02.patch`.
6. **On the old desk, you add the new desk and its key by hand, and keep the old desk's key.** Copy the patch file
   to the old laptop. From the old laptop, `scp add-desk02.patch desk01:` and log in, `ssh desk01`, each with a
   phone code. In the desk's checkout, set up `agent_git` as
   [Make the lock-out commit by hand](#make-the-lock-out-commit-by-hand) shows, then read the patch and apply it:
   `agent_git am ~/add-desk02.patch` and `agent_git push origin main`.
   Reason: the undo in item 7 runs on the old desk, so the old desk's key stays in `root_ssh_public_keys` until the
   undo has finished.
   **Check:** the diff adds the new desk's entry, `ssh/` file and known-host lines and its key in
   `root_ssh_public_keys`, and removes nothing.
7. **On the old desk, undo the lock-out:** in the same login, run `review-and-apply-the-systems-desk-settings`,
   then `sudo lock-everyone-out`, as [Undo a lock-out](#undo-a-lock-out) says. For the undo's step 1, read the key
   list yourself; remove the lock-out line by hand, as for adding it.
   Then power off the old desk again.
   **Check:** the desk review shows the new desk's key added; the undo's last line names no failed server; the
   provider shows the old desk powered off. Write down the undo commit's ID.
8. **Finish the new desk,** as "Joining" steps 9 to 12 of Add or remove a team member say. Then the new laptop's
   coding agent removes the old desk's key from `root_ssh_public_keys`, publishes, and runs `every_server`, as
   [Making a change](../AGENTS.md#making-a-change) says.
   Reason: once that run applies the list, `util01` and the servers stop trusting the old key: it can no longer log
   in or push to the main copy.
   **Check:** `origin/main` on the new desk is the undo commit of item 7; if `main` is past it, stop: someone pushed
   after the undo, and your coding agent reads that commit with you first. From the new desk, `ssh -F ssh/config root@10.20.1.1 true`
   works, and `ssh -F ssh/config root@10.20.1.1 cat /root/.ssh/authorized_keys` no longer shows the old desk's key.
9. **Delete the old desk, then continue with step 4 from the new desk,** as item 9 of
   "With a teammate" says. `util01` is suspect, because your old desk had root on `util01`: step 4's item 3
   rebuilds `util01`.
   **Check:** a fresh provider listing no longer shows the old desk, and the checks of step 4.

## Recover a half-undone lock-out

**When:** a lock-out or its undo stopped partway, and no desk reaches some servers: SSH from every desk says
`Permission denied (publickey)` or times out. The undo's own check prevents this for a desk that removes its own key,
so this is for a cause the check cannot see, such as a server that changed by hand.

On each server that no desk reaches, put back one desk's way in by hand, from the provider's rescue system, as
[Rescue system instead of a console login](repair_ssh_or_wireguard_from_the_provider_console.md#rescue-system-instead-of-a-console-login)
says. Pick the working desk: a desk with no signs, whose entry and keys are in `inventories/servers.yml` and
`root_ssh_public_keys`. Its values below are `desk02`'s from the inventory; use the working desk's own.

1. **Enable the rescue system, reset the server, and mount its disk** at `/mnt/root`, as steps 1 to 3 of that
   section say.
   **Check:** `ls /mnt/root/etc/ssh/sshd_config.d/` lists `00-incident-lockout.conf`.
2. **Empty the lock-out's SSH admission, and, on `util01`, remove the lock-out's triage record:**

   ```sh
   printf '# Managed by MMX. Empty while normal access is restored.\n' > /mnt/root/etc/ssh/sshd_config.d/00-incident-lockout.conf
   rm -f /mnt/root/etc/mmhotline/everyone-locked-out
   ```

   **Check:** `cat /mnt/root/etc/ssh/sshd_config.d/00-incident-lockout.conf` shows only the comment line.
3. **Make sure root's keys hold the working desk's key:** `cat /mnt/root/root/.ssh/authorized_keys`. When the
   working desk's `production_ssh_public_key` is missing, add that line from `inventories/servers.yml` at the end of
   the file, typed exactly.
   **Check:** the file shows the working desk's key line.
4. **Make sure WireGuard peers with the working desk:** `grep -A3 '^# desk02' /mnt/root/etc/wireguard/wg0.conf`.
   When the working desk's peer is missing, add it at the end of the file, with the desk's `wireguard_public_key`,
   `public_ipv4_address` and `private_ip` from `inventories/servers.yml`:

   ```ini
   [Peer]
   # desk02
   PublicKey = the desk's wireguard_public_key
   Endpoint = the desk's public_ipv4_address:443
   AllowedIPs = the desk's private_ip/32
   ```

   This is a file repair, which the rescue system allows: `wg-quick` reads the file when the server boots.
   **Check:** the `grep` shows the peer.
5. **Unmount the disk and reboot,** as step 5 of that section says.
   **Check:** from the working desk, `ssh -F ssh/config root@10.20.1.1 true` works, with that server's address.
6. **When every server answers, press the lock-out button again on the working desk:** `sudo lock-everyone-out`.
   With `everyone_locked_out_except_desk` removed from `inventories/servers.yml`, the press applies normal access on
   every server; with the setting naming the working desk, it locks everyone else out again. Either way it replaces
   each hand edit with the repository's settings.
   **Check:** the last line names no failed server.

## 5. Tell people

Use the prepared response page so the right person sends each required notice on time.

1. **Record confirmed facts, the next update time and the person responsible for each notice.**
   **Check:** none, because the record is the incident record itself.
2. **Follow [Post to the status page](post_to_the_status_page.md) for customer updates.**
   **Check:** the checks of Post to the status page.

## 6. Handle an extortion demand

Give the demand and preserved evidence to the lawyer and response lead so the business can decide what to do.

Record the demand, receipt time and the business decision in the incident record.

## 0. Prepare the response page

Answer these questions once, in a password-manager page named **Break-in response**.

1. **The coding agent proposes every answer from what it knows:** the people in
   `mmhotline_settings.yml`, the status page's host name, the accounts and
   the recovery bundle the setup saved, and this procedure's place in the systems
   repository.
   Reason: correcting a filled-in page takes minutes; a blank page of
   questions waits for days.
   **Check:** the proposal answers every question below.
2. **The person corrects the proposal and saves the page.**
   **Check:** the page opens in the password manager without a working systems desk. Record the result in the
   checklist item `break_in_response_page`.

The questions:

- Who leads the response, and who takes over if the lead cannot answer?
- How can the team contact each other if company email or chat is unavailable?
- Who provides incident help, and how can the team reach that person?
- Which lawyer, insurer, and business owner must the team contact?
- Which notices does the business owe, to whom, by when, and who confirms those requirements?
- Where are the provider, Git, Cloudflare, registry, storage and password-manager recovery logins?
- Where are the recovery passphrase, the recovery bundle and this procedure?
- Which public status-page address can customers use?
- Where will the team record decisions, evidence locations, times and notices during an incident?

"Not decided yet" is a fine answer for the lawyer, the insurer and the notices the business owes.
Write it down as the answer, and the page is finished with what the team knows today.
Reason: a small team often has no lawyer or insurer yet, and the rest of the page is what helps in the first hour.
When the team decides an answer later, the coding agent writes the answer in the page.

## 7. Practice the response

Rehearsing the response is optional practice. A team that rehearses once a year knows the commands before an incident. The setup does not run the drill.

First, practice the choice. The person describes an invented sign to the coding agent, such as an admin account in
the app that nobody made. **Check:** the coding agent picks [A break-in through the app](#a-break-in-through-the-app)
from [What did you see?](#what-did-you-see), and does not recommend a lock-out.

Then rehearse containment.
Use an isolated staging system with two actual systems desks and harmless company tokens.
Open a second desk login, the coding agent's desk login, a triage run, server SSH sessions and proxy requests.
Keep an HTTP client requesting the reference app throughout containment.
Follow steps 1 and 2, including both undo commands. Verify the following results:

- The desk that keeps access session works and customer requests have no failures during the access lock.
- The second desk's local sessions survive, but existing server sessions end and fresh server SSH and MMX attempts fail.
- The second desk cannot use the token proxy of the desk that keeps access. No desk-management path joins the desks.
- On the desk that keeps access, the coding agent's login, its buttons and the proxy keep working. Triage stops on every server.
- The coding agent's `sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only` on the desk that keeps access retains the lock.
- The same command on the second desk, and `./server_management_scripts/run_mmx_on_util01 run every_server`, refuse with the message that only the person starts a lock-out.
- The status switch shows the independent status page, and its undo restores the app.
- Evidence lands on the desk that keeps access and in the backup bucket, with matching checksums.
- Undo restores fresh authorized sessions, SSH and HTTPS MMX, and proxy access. Re-enroll the harmless revoked company identities separately.

Record the measured results in the checklist: in `break_in_staging_drill` the first time, and in `break_in_yearly_drill` when the team practices again.
