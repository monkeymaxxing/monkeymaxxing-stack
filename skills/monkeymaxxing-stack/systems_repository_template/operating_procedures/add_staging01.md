# Add staging01

Read [the systems repository rules](../AGENTS.md#the-rules) first.

**When:** the team chose the fuller system in
[chapter 1 (answer two questions)](../initial_setup/01_answer_two_questions.md),
and chapter 7 (install everything on the production servers) sends you
here; or, later, the team wants to try each release on a test server
before customers get it. Or the team no longer wants a test server.

**What this page does:** this page adds `staging01`, the test server, or
removes it. Each release then goes to `staging01` first.
[What staging01 is](#what-staging01-is) explains the server.

**Who acts:** you, the coding agent, do the steps on the laptop and
through your desk login, `ssh desk01-agent`. Only the person:

- approves `staging01`'s price before step 2 of
  [Adding staging01](#adding-staging01);
- types `ssh -t desk01 set-up-outside-services cloudflare` and a phone
  code, and makes one more Cloudflare link token (step 3);
- runs the Access check in their own desk login, `ssh desk01` (step 8);
- when removing `staging01`, deletes two kinds of token at Cloudflare and
  removes the `staging_` keys from the vault and the staging Access entry
  from the password manager.

**Terms:** this page uses the Stack's terms, such as vault, inventory and
fleet stage. [Technical terms](../talking_with_the_team.md#technical-terms)
explains each term.

## Choose the route

| Situation | Follow |
| --- | --- |
| The team wants a test server | [Adding staging01](#adding-staging01) |
| The team no longer wants a test server | [Removing staging01](#removing-staging01) |
| `staging01` must be replaced or rebuilt | [Replace staging01](replace_staging01.md) |

## Before you start

- **Tell the person** before step 1: what `staging01` is for, its monthly
  price with its public address, read from the provider as in step 2 of
  [chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md),
  and that the person makes one more Cloudflare link token in step 3.
  `staging01` is outside the growth limits, so the person approves its
  price before step 2. A team that chose the fuller system approved it in
  chapter 6.
- **A push alone changes no server.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change)
  says: a push alone changes no server, so run `every_server` or the playbook the step names.

## Adding staging01

1. **The staging settings,** in one commit:
   - In `inventories/servers.yml`, under `vars`, fill in staging's host
     name and image tag for each app, in the `staging: {}` entries beside
     production's. The tag is the image production runs now:

     ```yaml
     deployed_image_tags:
       production:
         shop: "3f2a1c97d4e85b60a1c2d3e4f5061728394a5b6c"
       staging:
         shop: "3f2a1c97d4e85b60a1c2d3e4f5061728394a5b6c"
     public_host_names:
       production:
         shop: shop.example.com
       staging:
         shop: staging.shop.example.com
     ```

   - In `mmx_project_settings.yml`, for each app with a
     `production_uploads_r2_bucket`, set `staging_uploads_r2_bucket` to the
     app's own staging bucket, such as `example-shop-staging-uploads`.
     `staging01` gets it as the app's `R2_BUCKET`. Reason: staging never
     reaches production's uploaded files.
   - In `mmx_project_settings.yml`, give each app with an `APP_ORIGIN` in
     `env` its own staging address in `staging_env`, such as
     `APP_ORIGIN: https://staging.shop.example.com`.
     `every_server` refuses to configure `staging01` while an app would keep
     production's bucket or address, and names the line to add.

   Run `mmx validate`, commit, and push.

   **Check:** `mmx validate` passes before the commit.

2. **Create the server.** Follow steps 1 to 4 of
   [Add a server](add_a_server.md), with the name
   `staging01`, the group `staging_server`, the private address
   `10.20.0.2`, and `db01`'s server type and location. In step 3, the
   group becomes:

   ```yaml
   staging_server:
     nodes: [staging01]
     vars:
       is_staging_server: true
       mmwatchdog_check_file: database_servers.yml
   ```

   **Check:** the checks of steps 1 to 4 of [Add a server](add_a_server.md).

3. **Staging's keys,** by the person, on the laptop, each command plus a
   phone code. Each command reads that `staging01` is in the inventory now
   and makes only what is missing:

   ```sh
   # On the laptop, in the person's own terminal:
   ssh -t desk01 set-up-outside-services cloudflare
   ssh desk01-secrets
   ```

   - `cloudflare` prints a link for a new link token, as in
     [chapter 4 (set up your accounts and lock your systems desk)](../initial_setup/04_set_up_your_accounts_and_lock_your_desk.md),
     and makes the tunnel `example_systems-staging_apps` with its token in
     the vault as `staging_apps_cloudflare_tunnel_token`; each app's
     staging uploads bucket and its R2 key, in the vault with `staging_`
     in front, such as `staging_shop_R2_ACCESS_KEY_ID`; and staging's
     Access service token, `example_systems: staging tests`, valid for a
     year, written into the person's token file as
     `STAGING_ACCESS_CLIENT_ID` and `STAGING_ACCESS_CLIENT_SECRET`. It
     prints the service token's ID.
   - `secrets` makes each app's staging secrets, the production names with
     `staging_` in front: the random ones itself, such as
     `staging_shop_database_password`, and at a hidden prompt the ones only
     a website gives, such as a payment service's test key for
     `staging_shop_STRIPE_API_KEY`. A test key, never production's.
   - Staging's Access service token stays in the person's token file on
     the desk. Cloudflare shows its secret only once. When CI
     tests against staging, the two values also become CI's secrets, and
     for local app tests the laptop's app-test environment gets them, and
     nothing else from the desk: an app test needs permission to reach
     staging, not permission to administer Cloudflare. Another
     person's desk enters them from the password manager with
     `ssh -t desk02 set-up-outside-services personal-token staging-access`,
     with that person's desk name.

   **Check:** after the commit of step 1 and the vault are pushed, check with
   `ssh desk01-agent sudo -n -u servers-mmx run-mmx-on-the-servers secrets usage` that every
   `staging_` key is defined.

4. **DNS and Access for each staging host name,** through the API token
   proxy, as in steps 3 and 4 of
   [chapter 5 (put your site behind Cloudflare and lock your private pages)](../initial_setup/05_put_your_site_behind_cloudflare_and_lock_your_private_pages.md):
   - a proxied CNAME record for the host name, to the staging tunnel's
     `TUNNEL_ID.cfargotunnel.com`
     (`GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/cfd_tunnel?name=example_systems-staging_apps&is_deleted=false`, `result[0].id`);
   - an Access application for the host name, with the Allow policy that
     admits only the company's people, as MMHotline's dashboard has, and a
     Service Auth policy, `"decision": "non_identity"`, whose include rule
     names the service token:
     `{"service_token": {"token_id": "TOKEN_ID"}}`. `TOKEN_ID` is the ID
     that step 3 printed, also `result[].id` of
     `GET http://127.0.0.1:8082/accounts/ACCOUNT_ID/access/service_tokens?name=example_systems%3A%20staging%20tests`;
   - a second Access application for the app's health URL path alone,
     such as `staging.shop.example.com/up` (`health_url_path` in
     `vars.apps`), with a Bypass policy, so MMWatchdog and `deploy`'s
     public check reach the health URL without a sign-in.

   Give the person the links to the
   [DNS records](https://dash.cloudflare.com/?to=/:account/:zone/dns/records)
   and the [Access applications](https://one.dash.cloudflare.com/?to=/:account/access/apps).

   No check of its own: step 8 checks the DNS record and Access through
   each staging host name.

5. **Set up the server.** Follow steps 5 to 7 of
   [Add a server](add_a_server.md). The
   `every_server` run sets up Postgres, PgBouncer when production uses it,
   the apps at staging's tags, Caddy, and the tunnel connector on
   `staging01`.

   **Check:** the checks of steps 5 and 6 of [Add a server](add_a_server.md).

6. **The desks:** each teammate's coding agent runs
   `sudo -n update-this-desks-wireguard-peers` at the start of its next
   session, as for any new server.

   No check: the other desks do this step in their own sessions.

7. **Fill staging's database** with each app's seed command, once,
   through MMX so the run is recorded, in the app's live web container,
   `shop-web-PORT`, with PORT from
   `/var/lib/monkeymaxxing-stack/live_web_ports/shop` on `staging01`.
   Staging and production share the app's `environment` settings, so the
   command sets `APP_ENV=staging` for the seed command alone. The example
   is a Rails app whose seed command is `bin/rails db:seed`; use the app's
   own seed command
   ([chapter 2 (get your app ready to deploy)](../initial_setup/02_get_your_app_ready_to_deploy.md)):

   ```sh
   # This systems desk, in the systems repository:
   ./server_management_scripts/run_mmx_on_util01 run-command --nodes staging01 -- podman exec --env APP_ENV=staging shop-web-8001 bin/rails db:seed
   ```

   An app without a seed command gets one now, following
   `files_for_your_app/write_the_seed_command.md` in the installed
   `monkeymaxxing-stack` skill's directory, and the app's item
   `<app>_seed_command_fills_test_data` in the checklist.

   **Check:** the command finishes without an error for each app. Step 8
   verifies the result.

8. **Verify.** For each app, the health URL answers through Caddy on
   `staging01`:

   ```sh
   # This systems desk, as the coding agent:
   ssh -F ssh/config root@10.20.0.2 "curl -sS -o /dev/null -w '%{http_code}\n' -H 'Host: staging.shop.example.com' http://127.0.0.1/up"
   ```

   The command prints `200`. Then the person runs, in their own desk
   login, `ssh desk01` and a phone code, the check that Access admits the service token and
   refuses everyone else; you read the two lines it prints:

   ```sh
   # On the desk, as the person:
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     curl -sS -o /dev/null -w 'with the service token: %{http_code}\n' \
       -H "CF-Access-Client-Id: $STAGING_ACCESS_CLIENT_ID" \
       -H "CF-Access-Client-Secret: $STAGING_ACCESS_CLIENT_SECRET" https://staging.shop.example.com/ &&
     curl -sS -o /dev/null -w 'without it: %{http_code} to %{redirect_url}\n' https://staging.shop.example.com/
   ```

   **Check:** with the token the app answers, such as `200`; without it Access
   answers `302` to the team's Access sign-in page,
   `https://TEAM.cloudflareaccess.com/...`. `ssh -F ssh/config root@10.20.0.2 mmwatchdog status`
   exits 0.

   Mark `staging_server` and each app's `<app>_seed_command_fills_test_data`
   in `monkeymaxxing_stack_checklist.yml` done once their `verification`
   passes. `staging_server`'s release check passes only with the next
   release, which goes to `staging01` first
   ([Deploy and roll back an app release](deploy_and_roll_back_an_app_release.md)),
   so until then set `staging_server` to `state: open`, with
   `waits_for: the next release, which goes to staging01 first`; that
   release's step 2 sets it `done`.
   Add `staging01` to the servers in `README.md`, and to its Operating
   links the row `| Test app, on staging01 | https://staging.shop.example.com |`,
   with each app's staging host name.

## Removing staging01

When the team no longer wants a test server:

1. **Destroy `staging01`** with `destroy_a_server_at_the_provider --server-id`
   and its provider ID from a fresh listing. Delete
   its line from `ssh/known_hosts`, its node from `inventories/servers.yml`,
   and its name from the group: `staging_server` keeps `nodes: []`.
   Set `deployed_image_tags.staging` and `public_host_names.staging` back
   to `{}`, set each `staging_uploads_r2_bucket` back to `""`, and each
   app's `staging_env` back to `{}`. Commit, push,
   and run `every_server`, which removes `staging01`'s peers and keys from
   every server. Each desk runs `sudo -n update-this-desks-wireguard-peers`.

   **Check:** the `every_server` run passes.

2. **Delete staging's parts at Cloudflare.** Through the API proxy, delete
   each staging host name's DNS
   record and its two Access applications, the tunnel
   `example_systems-staging_apps`, and each app's staging uploads bucket,
   after emptying it. The person deletes two kinds of token at Cloudflare,
   because the desk token cannot delete tokens: staging's Access service
   token, `example_systems: staging tests` (Zero Trust, Access controls,
   Service credentials, Service Tokens), and each app's staging R2 key,
   such as `example_systems: shop on staging reads and writes its uploads`
   (Manage Account, Account API Tokens).

   No separate check: each API call's answer says whether the deletion
   succeeded, and the person sees the tokens' lists at Cloudflare.

3. **The vault and the password manager.** The `staging_` keys in the
   vault are now unused, and stay there: no server reads them, and MMX has
   no command that removes one key. The person removes the staging Access
   entry from the password manager.

   No check of its own: only the person sees the vault's contents and the
   password manager.

4. **The checklist and the README.** Set `staging_server` back to
   `waits_for_its_trigger`, with `trigger:
   the team wants to test releases before production`, and each
   `<app>_seed_command_fills_test_data` back to `open`, with `waits_for:
   staging01, or developers needing test data`. Remove `staging01` and the
   test app's row from `README.md`.

   **Check:** `mmx validate` passes.

## If something is different

- **An app has no seed command (step 7):** the app gets one now, as step 7
  says, following `files_for_your_app/write_the_seed_command.md`.
- **The teammates' desks (step 6):** each teammate's coding agent
  runs `sudo -n update-this-desks-wireguard-peers` at the start of its
  next session.

## What staging01 is

`staging01` is the test server. It runs every role on one server: the
apps, Postgres outside the failover formation, Caddy, and a tunnel
connector, with invented data from each app's seed command. Each release
then goes to `staging01` first. `staging01` costs one server of
`db01`'s size, with its public address, every month. It holds no
production secret, reaches no production server, and keeps no backups:
its data comes from the seed command, so a new `staging01` fills its
database again ([Replace staging01](replace_staging01.md)). Its alerts go
no higher than warn, because staging serves no customers.
