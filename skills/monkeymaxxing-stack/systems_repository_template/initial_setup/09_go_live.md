# Chapter 9: Go live

**When:** after chapter 8's part 1 (read the backup results), once its
checks passed and Cloudflare shows the domain as "Active". Chapter 9 ends
the first sitting.

**What this chapter does:** the app has run on the servers since
chapter 7 (install everything on the production servers), but nobody has
been sent to it yet. The app's public host name is checked through
Cloudflare, the way users reach the app, and MMWatchdog's checks of the app
turn on. The first release goes out the way every later release does.

**Who acts:** you, the coding agent, check the app, change the settings,
and run the release through the desk. The person says "release" to
approve the first release to production, when
`production_releases_wait_for_a_persons_approval` is `true`.

**Tell the person when the chapter starts:**

> I am checking your app through Cloudflare, the way your users reach it.

## Before you start

- **The messages to the person.** Give each step's message as one short
  line, except the screen of step 2, which the person reads in full.
- **The release has its own messages.** For the release, follow [A release](../operating_procedures/deploy_and_roll_back_an_app_release.md#a-release):
  each of its steps says what to explain, and when to ask for approval.

## Steps

1. **The public host names.** From the laptop, confirm each
   app's health URL answers HTTP 200 through Cloudflare at the app's public
   host name, the way users reach it: `curl -fsS https://shop.example.com/up`.
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
   before marking the item done. Mark `tunnel_and_the_public_host_name`, then
   `cloudflare_caches_what_the_app_marks` and
   `mmwatchdog_with_the_default_checks`.
   MMWatchdog's fleet hub on `util01` checks each app at the app's public host name,
   but only after this step turns the checks on. Once every health URL
   answers, set `public_site_checks_run: true` in `mmx_project_settings.yml`,
   commit, push, and run `every_server` on `util01` (the
   [Making a change](../AGENTS.md#making-a-change) steps). Then
   `public_sites` exists on `util01`, and an app that stops answering sends
   an `sos` alert. The alert wakes the person on call only after the alerts
   sitting.

   **Tell the person:** no message, because step 2's screen gives the
   result.

   **Check:** each health URL answers HTTP 200 through Cloudflare, each app
   server has a healthy connector, and `public_sites` exists on `util01`.

2. **The app is live: tell the person, and ask for the first release.**
   Show the screen, with the checks that passed:

   ```text
   Your app is live:  https://example.com

   What I checked:
     - The site answers, through Cloudflare.
     - Backups run, and I restored one to a test server.
     - Every server reports in.

   YOUR SITE HAS NO PHONE ALERTS YET.  Say "set up alerts" to add them.  It takes about 15 minutes.

   Say "release" to put your app's newest version live.
   ```

   The person's "release" is the approval that
   [A release](../operating_procedures/deploy_and_roll_back_an_app_release.md#a-release)
   asks for. Ask nothing else about the first release. Check CI yourself,
   with `gh run watch` when `gh` is signed in. Without `gh`, `deploy`'s
   image pull proves the image. Never ask the person whether CI is green.

   **Check:** the person said "release".

3. **The first release,** by [A release](../operating_procedures/deploy_and_roll_back_an_app_release.md#a-release),
   follows the agent-run deployment used for every later release.
   The first release needs an image the app servers do not run yet,
   so the first release proves a real version switch.
   Use one of the app's own changes, or, when none waits, make a small
   change that users do not see, such as a line in the app's README, and
   ask nothing about it. Commit and push the change to the app's main
   branch from the app's folder on the laptop, with the person's own Git
   login, as "A release" describes. The person's "release" in step 2 is
   the one approval.
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

   **Tell the person:** the messages of "A release". Say that every later
   release follows the steps in "A release".

   **Tell the person after:**

   > Your first release is live: [the image tag]. A return to the previous version uses the previous image tag, [the previous tag].
   > The rollback test is [complete, or still open as `deploy_and_rollback` on the checklist].

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

   **Tell the person after,** which also ends the chapter:

   > Your first release is live. Your setup's first sitting is done.
   > When you are ready, say "set up alerts", so a broken site wakes you.

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

Next, in a later sitting: [Chapter 10: Write down how to run your system](10_write_down_how_to_run_your_system.md).
The alerts sitting comes first: [chapter 8, part 2](08_check_that_alerts_reach_your_phone_and_backups_restore.md#part-2-phone-alerts).
