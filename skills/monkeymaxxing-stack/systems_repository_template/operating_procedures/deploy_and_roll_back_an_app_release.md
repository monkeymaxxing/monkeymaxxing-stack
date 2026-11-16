# Deploy and roll back an app release

**When to use this page:** releasing a new app version, or rolling back a
release that breaks something.

**What this page does:** a release records a new image tag in
`deployed_image_tags` in `inventories/servers.yml`, and `deploy` switches
the environment's app servers to the image with that tag.

**Who acts:** the coding agent commits, pushes, and runs `deploy` for the
selected environment. The person confirms that CI's run is green, approves
a production release while `production_releases_wait_for_a_persons_approval`
is `true`, approves a bigger `staging01`, and approves and runs a rollback
without the memory check. Commands that source the person's token file,
`~/.config/monkeymaxxing-stack/example_systems.env`, run only in the
person's own desk terminal, as the secrets rule in
[The rules](../AGENTS.md#the-rules) says.

## Find your situation

| Situation | Follow |
| --- | --- |
| A new app version is ready | [A release](#a-release) |
| A release breaks something | [A rollback](#a-rollback) |
| A deploy or a rollback stops at the memory check | [Memory for both releases](#memory-for-both-releases) |

## Before you start

- **A push alone deploys nothing.** Apply each configuration change as
  [Making a change](../AGENTS.md#making-a-change) says: a push alone
  changes no server, so run `every_server` or the playbook the step names.
- **Building an image alone changes no server.**

## A release

1. **The app code changes.** Tell the person what the new app commit
   changes and why.
   A migration is a database change made by the app, such as adding a table
   or column.
   **Check:** each new migration passes `verification` in the app's
   checklist item
   [`shop_migrations_keep_the_running_release_working`](../monkeymaxxing_stack_checklist.yml).
   Reason: the old version runs on the new database tables until the switch,
   and again after a rollback.
2. **Build and test the image.**
   - **With CI:** CI tests, builds, and pushes the image when the team has
     CI (chapter 3's ready GitHub Actions file does).
     **Check:** ask the person to confirm that CI's run for the full app
     commit is green (the repository's Actions tab, or
     `gh run list --commit FULL_APP_COMMIT_ID`) and that the last step's
     output names `linux/amd64`; that step asks the registry for the tag.
     The desk has no registry login to check with, and needs none (see
     [Why the desk does not check the registry](#why-the-desk-does-not-check-the-registry)).
   - **Without CI:** run the app's tests and the build only inside a
     container, as `coding-agent`, with `podman` and chapter 3's commands:
     never the app's own tools on the desk, never `--network host`, and
     never `/run` or a home directory mounted. Push the image with the
     desk's publishing login. Use the full app commit ID as the tag. Then
     check that the registry holds it, with `image` of the app from
     `vars.apps`:

     ```sh
     # This systems desk, as the coding agent, only for a team with no CI:
     podman manifest inspect IMAGE_NAME:FULL_APP_COMMIT_ID
     ```

     **Check:** it prints a manifest that names `linux/amd64`;
     `manifest unknown` means the tag is not at the registry.
   - **With `staging01`:** set staging's tag in the systems inventory,
     commit, push, and run:

     ```sh
     ./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=staging
     ```

     Read MMX's result, and check the staging app through Caddy on
     `staging01`:

     ```sh
     # This systems desk, as the coding agent:
     ssh -F ssh/config root@10.20.0.2 "curl -sS -o /dev/null -w '%{http_code}\n' -H 'Host: staging.shop.example.com' http://127.0.0.1/up"
     ```

     **Check:** the command prints `200`. When `staging_server` in the
     checklist is `open` and waits for this release, set it `done` with
     `verified_at` and `last_result` once the rest of its `verification`
     has passed.
   - **Without staging:** complete the available tests before the
     production step.
     **Check:** the tests pass.
3. **Tell the person what `deploy` does,** before production: it checks that
   each app server has the memory for the running and new versions.
   `deploy` runs the new version's database migrations once, while the old
   version still answers requests. Then `deploy` starts the new version
   beside the running version.
   Once every new web container passes the health check, `deploy` switches
   the requests to the new version and stops the old version.
   Then `deploy` checks the app through its public host name.
   [If something is different](#if-something-is-different-in-a-release)
   says what happens when a check fails.
   **Check:** none: this step only informs the person.
4. **Production.** Read `production_releases_wait_for_a_persons_approval`
   in `mmx_project_settings.yml`.
   - With `true`, the template's value, show the person the version on
     staging, or without `staging01` the change and its test results. Ask
     whether to release the version to production. Release only after the
     person says yes.
   - With `false`, tell the person which version goes to production now,
     and release the version without waiting.

   If the app's item `shop_deploys_without_dropping_requests` is open, start its
   checks now, and keep them running through the switch.
   Set production's tag to the tested image's full app commit ID. Commit,
   push, and run:

   ```sh
   ./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=production
   ```

   **Check:** the run passes; step 5 reads its result.
5. **The result.** Read MMX's result on `util01`.
   **Check:** the live app's release matches the requested tag on every
   app server.
   Report the public check and the memory check's numbers
   ([Memory for both releases](#memory-for-both-releases)).
   If you ran the checks for `shop_deploys_without_dropping_requests`,
   report the check results separately and update
   `shop_deploys_without_dropping_requests`.
   One release that passed does not promise that the next one drops no request.

### If something is different in a release

- **A migration waits for a table lock.** A migration that waits more
  than 5 seconds for a table lock fails, and the deploy stops before the
  switch. The 5 seconds are fixed in
  `roles/app_server/files/run_app_migrations`. Reason: a migration
  waiting longer for a lock would hold up live requests behind it.
- **A new web container fails the health check.** Users stay on the old
  version, and the run fails with the reason.
- **The public check fails.** The old version has already stopped, and
  `deploy` does not roll back by itself: read `./server_management_scripts/run_mmx_on_util01 results` from the desk for the cause, and roll back with
  [A rollback](#a-rollback) when the release broke the app.
- **A server lacks memory.** Follow
  [Memory for both releases](#memory-for-both-releases).

### Why the desk does not check the registry

The desk cannot read the app servers' registry token either, because the
token sits in the vault and is handed to each pull. The deploy's own first
image pull on the app servers (`pull_the_new_images`) uses that token, and
a missing tag stops the deploy there, before any migration or change to a
running container.

### Why the staging check goes over SSH

The check goes over SSH to Caddy on `staging01`,
so the coding agent needs no token: the Access service token stays in
the person's own token file and in CI's secrets, and the agent never
reads either. `deploy` also checks the health URL through the public
host name, which Access lets through without a sign-in. Reason: the
check shows whether the new release runs on `staging01`; a test with the
service token would add only a test of Access, and the Access policy
already states who Access admits.

## A rollback

A rollback does not wait for the person's approval, whatever
`production_releases_wait_for_a_persons_approval` says, with one
exception: a rollback that skips the memory check needs the person's
approval ([Memory for both releases](#memory-for-both-releases), "A release
that leaks memory"). Reason: the
rollback returns to a release that passed, and every minute of waiting
keeps users on the broken release.

1. **Find the previous image tag** with `git log -p inventories/servers.yml`.
   Choose a release whose deploy and public check passed, using MMX's history
   on `util01`.
   **Check:** MMX's history shows that release's deploy and public check passed.
2. **Set the environment's tag to the previous release,** commit,
   push, and run the same `deploy` command for the environment. Reuse the
   existing registry image.
   **Check:** the run passes. A rollback that fails the memory check is in
   [Memory for both releases](#memory-for-both-releases).
3. **Check every app server's live release after the switch,** including
   after a failed switch or a manual deploy.
   **Check:** every app server runs the previous release.
4. **Report the rollback's result** as step 5 of [A release](#a-release) describes.
   **Check:** none: the report repeats the checks of step 5.

A rollback does not undo the migrations: the previous version runs on the
newer database tables.

## Memory for both releases

Before changing anything, the deploy checks each app server in the
environment. If any server lacks room, the deploy stops without changing
anything. The failure reports how many MiB the server without room has and
needs.

1. **Read the memory check's numbers:** `./server_management_scripts/run_mmx_on_util01 results RUN_ID --fleet-stage check_that_each_app_server_has_memory_for_the_new_release --json`
   gives each app server's `memory_available_mib` and `memory_needed_mib`.
   MMX prints `RUN_ID` when the run starts; `./server_management_scripts/run_mmx_on_util01 status` from the desk also names the run.
   **Check:** `memory_needed_mib` is `live_web_containers_mib` plus `margin_mib`.
   Each value is rounded separately to a whole MiB, so the sum can be 1 MiB off.
   The same command verifies the check after a deploy that passed.
2. **Correct the capacity problem.** Another app server does not fix this,
   because the check runs on each app server alone. Replace the server
   without room with a bigger server from the pool's `server_types`
   ([Replace a server](replace_a_server.md)), or set a smaller
   `WEB_CONCURRENCY` in the app's own env (`vars.apps.<app>.env` in
   `mmx_project_settings.yml`). See also [Add an app server](add_an_app_server.md#choose-the-route).
   For `staging01`, use a bigger `staging01`
   ([Replace staging01](replace_staging01.md)). `staging01` is outside the
   growth limits, so ask the person first, with the bigger server's monthly
   price from the provider; replace `staging01` only after the person says yes.
   **Check:** step 1's numbers, after the change, leave room.
3. **Inspect live releases before a retry or rollback.** A failed switch
   can leave web or job containers on different releases. The inventory tag
   is a request, not proof of the running release.
   **Check:** you know which release each web and job container runs.
4. **Rerun the deploy explicitly.** No automatic retry runs.
   **Check:** the run passes the memory check.

### If something is different with the memory check

- **A release that leaks memory** can make the rollback fail the memory
  check.
  The leaking release's live web containers use more memory than the
  previous release will need.
  A person reviews the memory check's available and needed memory numbers
  and approves running the rollback without the memory check.
  Before the run, check that `deployed_image_tags.production` in
  `inventories/servers.yml` names the previous release's tag. Then the
  person runs the rollback without the memory check:
  `./server_management_scripts/run_mmx_on_util01 run deploy --var environment_name=production --var skip_the_memory_check=true`.
  Never skip the memory check without the person's approval.
- **A server runs another release than `deployed_image_tags` names.** The
  daily server settings comparison (`every_server` as a dryrun) reports
  it: its task `report_the_apps_not_on_the_deployed_image_tags` in the
  fleet stage `find_the_releases_the_app_servers_run` would change, and
  MMWatchdog warns.
  Finish the deploy or record the release that runs.

### How the memory check works

During a deploy's switch, each app server runs the old and new releases'
web containers together, from the start of the new containers until the old
containers stop.
Each app server must hold two copies of the web containers, plus the job
containers and the system, at peak memory use.

Each app server's available memory (`MemAvailable`) must fit another copy
of the web containers live on the app server, at the containers' current
memory use.
A tenth of the server's memory must also remain free for growth during the deploy, such as container
warm-up, jobs, and the file cache. The tenth is fixed in `playbooks/deploy.yml`, whose comment gives
the reason.
