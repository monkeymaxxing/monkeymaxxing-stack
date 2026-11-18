# Chapter 9: Go live

**When:** after chapter 8's part 1 (read the backup results), once its
checks passed and Cloudflare shows the domain as "Active". Chapter 9 ends
the first part of the setup.

**What this chapter does:** the app has run on the servers since
chapter 7 (install everything on the production servers), but nobody has
been sent to it yet. The app's public host name is checked through
Cloudflare, the way users reach the app, and MMWatchdog's checks of the app
turn on. The first release goes out the way every later release does.

**Who acts:** you, the coding agent, check the app, change the settings,
and run the release through the desk. The first release asks the person
for no approval, because the person approved the app's changes in
chapter 2, the first release's README line among them. To ask for the
approval again, set `first_release_waits_for_a_persons_approval` to `true`
in `mmx_project_settings.yml`; the steps below say where it applies.

**Tell the person when the chapter starts:**

> I am checking your app through Cloudflare, the way your users reach it.

## Before you start

- **The messages to the person.** Give each step's message as one short
  line, except the screen of step 2, which the person reads in full.
- **The release has its own messages.** For the release, follow [A release](../operating_procedures/deploy_and_roll_back_an_app_release.md#a-release):
  each of its steps says what to explain, and when to ask for approval.

## Steps

1. **The public host names.** Never look up an app's address from the
   laptop, with `curl`, `dig` or a browser, before chapter 5 made its DNS
   record. Reason: the laptop then remembers "no such address" for
   minutes, and in a newcomer test run the live site failed to open on
   the laptop for that reason. From the laptop, confirm each
   app's health URL answers HTTP 200 through Cloudflare at the app's public
   host name, the way users reach it: `curl -fsS https://shop.example.com/up`.
   In the first part of the setup, chapter 8's part 1 already started this
   check as a bounded background wait; its end wakes you here. When it
   ended at its bound, such as while the domain is still "Pending" at
   Cloudflare, say so in one line, with when you check next, and start the
   same wait again.
   A connector is `cloudflared`, the program on the app server that
   connects to Cloudflare and brings requests to Caddy.
   Cloudflare's API lists a healthy connector of the `example_systems-apps` tunnel on each
   app server
   (`GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel/TUNNEL_ID/connections`,
   with `ACCOUNT_ID` from `vars.cloudflare_account_id`).
   Match each connection's `origin_ip` to the app server's public address.
   A connection's `origin_ip` can be the server's IPv6 address rather than
   the inventory's `vars.public_ipv4_address`.
   [Adding load-balancer servers](../operating_procedures/add_load_balancer_servers.md#adding-load-balancer-servers), step 3,
   explains how to find the addresses in the API response and on a server.

   Use each item's `verification` in
   [monkeymaxxing_stack_checklist.yml](../monkeymaxxing_stack_checklist.yml)
   before marking the item done. Mark `tunnel_and_the_public_host_name`
   and `cloudflare_caches_what_the_app_marks`.

   **Tell the person:** no message, because step 2's screen gives the
   result at once.

   **Check:** each health URL answers HTTP 200 through Cloudflare, and
   each app server has a healthy connector.

2. **The app is live: tell the person at once.** The moment step 1's
   check passes, the site is live, and the person hears it in the reply
   that ends your turn. Never hold the screen back for a later step, such
   as the `every_server` run below or MMWatchdog's first check of the
   site. Before the screen, only start the next work, in a few seconds
   each: set `public_site_checks_run: true` in `mmx_project_settings.yml`,
   commit, publish (the [Making a change](../AGENTS.md#making-a-change)
   steps), start the `every_server` run on `util01` as a desk job, and
   start its wait as a background command with its bound, such as
   `ssh desk01-agent wait-for-a-desk-job NAME --at-most-minutes 5`, and
   start it again each time it ends unfinished, as the skill's "No wait longer than 5 minutes; each end gets one line" says. Then end your
   reply with the live screen, with no tool call after it:

   ```text
   YOUR SITE IS LIVE:  HTTPS://EXAMPLE.COM

   Open it now.

     ✓ 1. Your app
     ✓ 2. Your accounts
     ✓ 3. Your keys locked away
     ✓ 4. Your servers
     ✓ 5. Live

   YOUR SITE HAS NO PHONE ALERTS YET.  Say "set up alerts" to add them.  It takes about 15 minutes.

   Still open:
     I am turning on the checks that watch your site, and putting your app's newest
     version live, the way every later release goes.  Your site stays up meanwhile.

   Next for you: nothing.  I'll tell you when it's done (about 15 minutes).
   ```

   The live screen is the first thing in the reply, and nothing comes
   before it: no line about the check, the release, a commit, an image
   tag, an HTTP code or the checklist. Reason: in a newcomer test run,
   the last reply opened with a commit ID, an HTTP code, an image tag and
   the checklist, and the live screen came only below them. With several
   apps, give each app's address on its own line at the top. "Still open"
   has at most 4 lines, in the person's words ("The person's words" in the
   skill): no commit IDs, image tags, HTTP codes, restore times, check
   names such as "pin check" or "memory check", and no "checklist". A
   known security flaw on a brand-new server goes there plainly, or waits
   for the weekly system review:

   ```text
     One program on util01 has a known security flaw.  Its fix is not published yet.
     Nothing for you to do: the weekly system review tracks it.
   ```

   When the first release also ended before you wrote this reply, its
   result is one line under "Still open", such as "Your app's newest
   version is live too, the way every later release goes.", and the last
   line is step 5's "Say "set up alerts" ..." line. With
   `first_release_waits_for_a_persons_approval` set to `true`, the last
   line is instead: Say "release" to put your app's newest version live.
   The checks still turn on meanwhile.

   When the wait ends, say the result in one line. `public_sites` then
   exists on `util01`: MMWatchdog's fleet hub on `util01` checks each app
   at its public host name, and an app that stops answering sends an
   `sos` alert. The alert wakes the person on call only after the alerts
   part of the setup. Mark `mmwatchdog_with_the_default_checks` once
   `mmwatchdog fleet` on `util01` shows the public check. To wait for that
   first check, use a bounded wait, such as
   `timeout 5m bash -c 'until CHECK; do sleep 15; done'`, never an
   unbounded loop.

   Without the setting, go on to step 3 once the run ended. With it, the
   person's "release" is the approval that
   [A release](../operating_procedures/deploy_and_roll_back_an_app_release.md#a-release)
   asks for. Ask nothing else about the first release. Check CI yourself:
   the `ci-report` branch of the app's repository, as chapter 2's step 7
   says, or `gh run watch` when `gh` is signed in. The image at the
   registry: `./server_management_scripts/wait_for_the_app_image IMAGE:TAG`;
   when it cannot tell (exit 3), `deploy`'s image pull proves the image. Never ask
   the person whether CI is green.

   **Check:** the screen ended the reply right after step 1's check, and
   `public_sites` exists on `util01`; with the setting, the person said
   "release"; without it, step 3 started.

3. **The first release,** by [A release](../operating_procedures/deploy_and_roll_back_an_app_release.md#a-release),
   follows the agent-run deployment used for every later release.
   The first release needs an image the app servers do not run yet,
   so the first release proves a real version switch.
   Use the README line the person approved with the app's changes in
   chapter 2's step 7, or the change the person chose there instead, and
   ask nothing about it: "Your servers" and "Live" told the person there
   is nothing to do. Never a change the person did not approve there.
   Commit and push the change to the app's main
   branch from the app's folder on the laptop, with the person's own Git
   login, as "A release" describes. The first release skips the approval
   that "A release" asks for when `production_releases_wait_for_a_persons_approval`
   is `true`, unless `first_release_waits_for_a_persons_approval` is `true`.
   Then the person's "release" in step 2 is the one approval.
   The new app commit must follow the app commit whose image chapter 7 (install everything on the production servers)
   started.

   `deploy` ends with a check through the app's public host name.
   The public check passes only once Cloudflare shows the domain as "Active".

   With `staging01`, the first release goes to `staging01` first, as "A
   release" says, and finishes `staging_server`'s `verification` with the
   checks in step 8 of
   [Add staging01](../operating_procedures/add_staging01.md#adding-staging01)
   that waited for the domain.

   `deploy_and_rollback` stays `open` until a commit of the previous image
   tag rolls back the app. The rollback commit changes `deployed_image_tags`
   in the systems repository's `inventories/servers.yml`.
   The rollback must pass the memory check and the check through the public
   host name, as the first production deploy did.

   If CI builds the image, inspect CI's credentials and verify no server
   key or vault passphrase is available. CI needs only registry access.

   **Tell the person:** nothing while it runs beyond the wait lines of the
   skill's "No wait longer than 5 minutes; each end gets one line": the
   live screen already said what happens. "A release"'s messages are for
   later releases. Its result, the memory check's numbers, the commit and
   the image tags go into the checklist's `last_result`, never into the
   reply. Step 5 gives the result.

   An open rollback test can remain for the handover, which records
   outstanding checks.

   **Check:** `deploy` passed, with its check through the app's public host
   name.

4. **Inspect and verify.** Read MMX's deployment result on `util01` and
   compare every live app release with the selected tag. Follow
   [Memory for both releases](../operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases)
   when a leaking release needs an approved rollback without the memory
   check. Every deployment still records the selected tag in a commit.

   **Tell the person:** no message, because step 3's message gave the
   result.

   **Check:** every live app release equals the selected tag, and a commit
   records the tag.

5. **Note the waiting restore drill check queries.** Chapter 2 (get your app ready to deploy) left out each
   check query that needs data people create, such as a page view or an
   order from the last two days, because a new system holds no such data.
   Do not add them now. The checklist's improvement item
   `restore_drill_checks_data_people_create` waits for the first customer
   data; when production holds that data, add each such query to the app's
   `restore_drill_check_queries` in `mmx_project_settings.yml`, then commit
   and push. The next weekly drill pulls the commit before it starts.

   **Tell the person after,** which also ends the chapter and the
   person's five parts, as the last text of your reply. The live screen
   of step 2 already showed the five parts ticked, so this reply shows no
   map again:

   ```text
   Your app's newest version is live, the way every later release goes.  All five parts are done.

   Still open:
     Going back to an earlier version is tested with your next release.
     Then, when you want them: an agent that answers alerts before they reach you,
     a status page for your customers, and a written guide to running your system.

   YOUR SITE HAS NO PHONE ALERTS YET.  Say "set up alerts" when you are ready, so a broken site wakes you.
   It takes about 15 minutes.
   ```

   "Still open" keeps the rules of step 2's screen: at most 4 lines, in
   the person's words.

   **Check:** `restore_drill_checks_data_people_create` waits for its
   trigger in the checklist.

## If something is different

- **CI builds the image** (step 3): inspect CI's credentials, as step 3
  says.
- **With `staging01`** (step 3): the first release goes to `staging01`
  first.
- **A leaking release needs a rollback** (step 4): follow
  [Memory for both releases](../operating_procedures/deploy_and_roll_back_an_app_release.md#memory-for-both-releases).

## Why the chapter works this way

**The checks turn on only now.** Reason: until go-live the domain can still be "Pending" and the app is
not announced, so the checks would send `sos` alerts for a system that
was never live.

**The restore drill waits for real data.** Reason: the weekly restore drill then also checks that the restored
copy holds the data people create. A query for recent data, such as an
order from the last two days, also fails when a restore brings back an
old database.

Next, in a later part of the setup: [Chapter 10: Write down how to run your system](10_write_down_how_to_run_your_system.md).
The alerts part of the setup comes first: [chapter 8, part 2](08_check_that_alerts_reach_your_phone_and_backups_restore.md#part-2-phone-alerts).
