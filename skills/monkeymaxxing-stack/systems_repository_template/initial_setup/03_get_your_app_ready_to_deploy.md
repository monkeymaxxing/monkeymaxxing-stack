# Chapter 3: Get your app ready to deploy

**When:** after chapter 2 (set up your laptop and your systems desk). The
desk's read-only clone of the app needs the deploy key that
[chapter 4 (sign up for the outside services the Stack uses)](04_sign_up_for_the_outside_services_the_stack_uses.md#make-the-desks-app-checkout-credentials)
shows how to make.

**What this chapter does:** the app gets ready to run on several app
servers and to keep working after a database switch, so later the team
only needs to add a server to handle more requests. The systems repository
gets the app's settings, and the first tested image of the app reaches the
registry.

**Who acts:** you, the coding agent, read the app's code on the desk, fill
in the app's settings in the systems repository, and write each required
code change. The person reviews each code change and pushes it, because the
app's code is the person's, and chooses how images are built.

**Tell the person when the chapter starts:**

> Next, I will check that your app can run on several app servers and keep
> working after a database switch. I will prepare your app now, so later
> you only need to add a server to handle more requests. I will read your
> app's code and show you each required code change. You review each code
> change, because the app's code is yours.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, and "Tell the person
  after" with the result and its link. Say each message when its step
  comes, in your own words, with the team's own names and links.
- **The desk's clone of the app.** The systems desk holds a read-only clone of the app, as `coding-agent`, so I can read the code and what each release changes.
  [Chapter 4 (sign up for the outside services the Stack uses)](04_sign_up_for_the_outside_services_the_stack_uses.md#make-the-desks-app-checkout-credentials) shows how the person makes the clone's read-only deploy key.
  The clone cannot push to the app's repository.
- **Where images are built.** With CI, CI tests, builds, and pushes the image, and the desk holds no credential that can publish an image.
  Without CI, I test and build the image on the desk only inside a container, never with the app's own tools on the desk, and push it with the registry login that chapter 4 also makes.
- **Systems changes.** Record image tags in the systems repository on the desk as `coding-agent`.
  Commit, synchronize, and push the systems changes before running deployment through the desk's buttons.
- **More than one app.** Steps 2 to 8 are for each app.

## Steps

1. **The app's repository.** Ask where the app's repository is, and read it.

   **Ask the person:**

   > Where is your app's repository? Give me its address at your Git host, such as `git@github.com:OWNER/APP.git`.

   **Tell the person after:**

   > I read your app's code in the desk's read-only clone.
   > Next, I fill in your app's settings in the systems repository, then show you each code change your app needs.

   **Check:** the desk's clone holds the app's `main`.

2. **Its settings,** under `vars.apps` in `mmx_project_settings.yml`: an
   entry named after the app in place of `shop`, filled in from the app's
   code:
   - `image`, the image's name at the registry, such as `ghcr.io/<owner>/<repository>` in lowercase. The CI workflow pushes to the same name, so the two must match;
   - `web_ports`: two free ports from 8001 to 8099 that no other app uses,
     because the firewall opens only that range;
   - `health_url_path`, the app's health URL path, and `migration_command`,
     the app's database migration command;
   - `jobs_command`, the app's background-job command (`""` for an app
     with no background jobs: it then gets no job container, and its
     checklist item `<app>_background_jobs_run_from_one_command` is
     marked deviated, with no background jobs as the reason), and
     `jobs_connect_directly_to_postgres`, from the app's job library.
     Follow the comment above `jobs_connect_directly_to_postgres` in
     `mmx_project_settings.yml`;
   - the app's database pool size, set explicitly under `environment`
     rather than left to the framework's default, so the app's Postgres
     connections are known. Each framework guide in the stack repository's
     `docs/app-frameworks/`, under "Set the database connection budget",
     names the setting. Count every app's connections, as
     [Add an app server](../operating_procedures/add_an_app_server.md)
     describes before adding a server, and keep the total under 70, the
     level at which MMWatchdog's `connections_are_below_70_percent` warns;
   - `writable_temporary_directories`: every container runs with a read-only
     file system, so a framework that writes scratch files to its own
     disk, such as Rails' `tmp/` and `storage/`, or Laravel's compiled views
     in `/app/storage/framework/views`, fails at the first deploy with
     "read-only file system". Find where the app writes scratch files
     (the framework guide in `docs/app-frameworks/` names them) and list
     each directory. Each becomes a memory-backed directory, empty at every
     start, so list no directory that holds data that must last. Leave the
     key out when the app writes nowhere else;
   - `asset_directory`, `database_name`, `environment` (the app's settings
     that are not secret), and `secrets_from_vault` (the names of the
     app's secrets);
   - `production_uploads_r2_bucket`: the name of the R2 bucket for the app's
     uploaded files in production, such as `example-shop-uploads`, which
     [chapter 4 (sign up for the outside services the Stack uses)](04_sign_up_for_the_outside_services_the_stack_uses.md#chapter-4-sign-up-for-the-outside-services-the-stack-uses)
     creates; `""` when the app keeps no uploaded files;
   - `restore_drill_check_queries`: queries for the app's own tables, each
     answering true on the restored copy, so a restore that brings back an
     empty or old database fails the drill. An old database fails only a
     query for recent data, such as the example's order from the last two
     days. Leave out a query that needs data people create, such as any
     page view or an order from the last two days, until the app has such
     data. The comment above `restore_drill_check_queries` in
     `mmx_project_settings.yml` explains why a query waits for production
     data. The first drill runs at the end of chapter 7 (install everything on the production servers)'s run 2 (configure every server), before the
     database holds any customer's data. Once production holds
     the required data, the improvement item `restore_drill_checks_data_people_create`
     adds the remaining queries in a commit.

   **Tell the person:** no message, because the settings come from the
   app's code, and step 5 shows the person each change the app needs.

   **Check:** `mmx validate` passes, and each key above holds the app's
   value, not `shop`'s.

3. **The app's hostnames, image tags, and secret mappings:** in
   `inventories/servers.yml`, set the app's production host name in
   `public_host_names`, such as `shop.example.com`, and the app's
   `deployed_image_tags`. [Add staging01](../operating_procedures/add_staging01.md)
   adds staging's beside them. Each tag is the app's full Git commit, 40
   lowercase hexadecimal characters; the playbooks refuse any other tag.

   In `playbooks/every_server.yml`, the app needs entries under
   `app_secrets` in the two `app_server` role calls and the `jobs_server`
   role call. Add an entry for `<database_name>_database_password`.
   Add `<app>_<VARIABLE>` for each name in `secrets_from_vault`.
   Each entry maps the secret's name to the vault key with the matching
   name.

   Add the database to the role inputs and `database_passwords` outputs in
   each environment stage of `playbooks/end_connections_that_use_an_old_database_password.yml`.
   The app's database needs an entry under `database_passwords` in the
   production and `staging01` database fleet stages, keyed by
   `database_name`. In the stages for `staging01`, put `staging_` in front
   of each referenced vault key, so the app is ready for `staging01`
   whenever the team adds it; the stages skip themselves until then.
   `grep -rn shop --exclude=AGENTS.md --exclude=triage_agent_rules.md --exclude-dir=operating_procedures .`
   finds the remaining uses of the example app. Replace the example
   app's names and values with the app's names and values at each match.
   A comment that uses `shop` as an example can stay.

   **Tell the person:** no message, for the same reason as step 2.

   **Check:** the `grep` above finds `shop` only in comments that use it
   as an example, and `mmx validate` passes.

4. **Its checklist items:** copy the `apps.shop` block of the checklist
   under the app's name, with the app's name in each item's `id` and text.
   The app's items can mostly be verified only once the servers run: they stay
   `open`, with `waits_for: chapter 7 (install everything on the production servers)`, until
   [chapter 7 (install everything on the production servers)](07_install_everything_on_the_production_servers.md#chapter-7-install-everything-on-the-production-servers).
   An item whose `waits_for` in the checklist names a later step, such as
   `shop_deploys_without_dropping_requests`, which waits for the second
   deploy, keeps that `waits_for`.

   **Tell the person:** no message, because step 8 tells the person about
   each item the app cannot meet.

   **Check:** each of the app's items is `open` with its `waits_for`.

5. **The app's code, against each item's `verification`.** Each fix goes to
   the app's repository as a change the person reviews. The usual code fixes:
   - the web container listens on the port in `PORT` and on no other fixed
     port, because the containers share the server's network
     (`Network=host`). Rails 8's default Dockerfile starts Thruster on port
     80: change the Dockerfile's startup command to `./bin/rails server`;
   - each app server sets `WEB_CONCURRENCY` in the app's web containers to
     the app server's CPU count. The web server program must start the
     number of worker processes in `WEB_CONCURRENCY`, so a bigger app
     server takes more requests. Puma, Gunicorn, and Uvicorn read
     `WEB_CONCURRENCY` by themselves, unless the app's own
     settings fix the number. A Node app forks the number of workers in
     `WEB_CONCURRENCY` with its cluster module. A web server program that
     runs one process with threads on every CPU, as Go's, Java's, and
     .NET's do, needs nothing.

     An app whose workers need more memory than a CPU's share sets
     `WEB_CONCURRENCY` lower in the app's `environment`.
     The configured worker count replaces the app server's CPU count;
   - a framework that defaults to SQLite, such as Rails 8, uses Postgres;
   - uploads go to R2 (or another S3-compatible store, which is a
     deviation recorded in the checklist, because the nightly uploads
     backup copies only R2 buckets), with the bucket's keys among
     `secrets_from_vault`;
   - every database pool must read `DATABASE_URL`, or `DATABASE_READ_URL`
     for reads that can be a moment behind. Writes, and reads that must see
     the app's own latest write, use `DATABASE_URL`.

     Use each URL in the form required by the app's language and
     framework, with TCP keepalive on. Follow
     `files_for_your_app/database_driver_finds_the_primary.md` in the
     installed `monkeymaxxing-stack` skill's directory, beside `SKILL.md`.
     The database connection changes let the app find the new primary
     after failover, including when the old primary lost power.

     Some frameworks cannot read the stack's URL, which lists every
     database server. Rails stops at boot without the few lines for
     `config/boot.rb` in
     `files_for_your_app/database_driver_finds_the_primary.md`.
     Laravel reads the stack's URL wrong, and Django's dj-database-url
     refuses the stack's URL. A Node.js app
     copies the stack's
     `files_for_your_app/node/pg_with_multiple_database_servers.mjs` into its code
     and makes its pools with it;
   - the health URL fails until the app can reach its database;
   - a seed command in the app's image that fills an empty database with
     invented test data. Developers run the seed command on their laptops
     against a local database, and
     [Add staging01](../operating_procedures/add_staging01.md) runs it on
     `staging01`. Follow
     `files_for_your_app/write_the_seed_command.md` in the installed
     `monkeymaxxing-stack` skill's directory, beside `SKILL.md`.
     `write_the_seed_command.md` explains how to build the seed command
     from the app's schema and existing seed tools, with a worked example.

     The setup requires the seed command only for the fuller system,
     because `staging01` needs invented data in its database. Otherwise the
     checklist item `<app>_seed_command_fills_test_data`, a Later item,
     waits until developers need test data or the team adds `staging01`.

     The seed command runs only when `APP_ENV` is `development` or
     `staging`, so production never gets test data. Name the seed
     command's size option after the app's main record, such as
     `--orders 200000`. Many records show problems such as a slow query.
     Running the seed command again leaves the existing
     test records unchanged. The app's tests run the seed command on an
     empty database before every image build, so the seed command keeps
     working as the schema changes.

     Write the laptop steps in the app's README: start a local database,
     run the app's migrations, then run the seed command with
     `APP_ENV=development` and the local database's settings. The seed
     command and these laptop steps never run on the systems desk: the
     desk runs only the container commands of step 6.

     Production data stays on the production servers: no copy of
     production goes to a laptop, `staging01`, or CI, so the seed command
     is where test data comes from.

   **Tell the person first,** for each required change, with an example
   from this app. Explain ports and worker processes only when a required
   app change uses them:

   > Your app saves uploaded pictures on the app server's own disk, so a replacement app server would not have them.
   > Data that must survive a server replacement belongs in the database or in file storage, R2.
   > App files that ship with a release can stay on the app server.

   Before the matching change, explain:
   - a move from SQLite to Postgres, when the app uses SQLite, and a move
     of uploaded files to R2, before changing the upload code;
   - the primary, the database server that takes the writes, and a
     replica, before the database-connection work: the app must reconnect
     after a database switch, and a second database server is necessary
     for automatic failover;
   - that separate ports let two app versions operate at once, and that
     worker processes use the server's processors to handle requests.

   **Ask the person,** for each change:

   > Please review my change to your app: [the change at the Git host].
   > Push the change when you approve it, and tell me when it is on `main`.

   **Tell the person after:** no message, because step 7 shows the
   person the first image built from the changed code.

   **Check:** each of the app's items is met by the app's code on `main`,
   or step 8 records the item as a deviation.

6. **Choose how to build images. Recommend CI.** CI tests the app, builds
   the image from `Containerfile`, and pushes it to the registry whenever
   the code on `main` changes. A team that already has CI keeps it, with the steps
   below. A team without CI is best served by adding it; GitHub Actions is
   free for a private repository within its monthly allowance, and the
   person only has to put one file into the app's repository.

   **Tell the person first:**

   > An image packages your app for the servers. CI, your Git host's automated service, tests your app, builds the image, and pushes it to the registry whenever the code changes.
   > I recommend CI: the build runs on a clean machine instead of anyone's computer.
   > No password that can publish an image sits on your systems desk or your laptop.
   > Each image is tagged with the commit it came from, so a release names its code exactly.
   > Without CI, I do the same steps by hand on your systems desk, inside a container.

   **Ask the person:**

   > Do you want CI to build your app's images?

   **With CI.** The ready example is
   `test_build_and_push_the_app_image.yml`
   in the installed skill's `files_for_your_app/` directory, for GitHub
   Actions and GitHub's registry (GHCR). The desk's clone is read-only, so
   the file reaches the app's repository the way every other app code
   change does: the coding agent writes it, and the person reviews and
   pushes it (or the laptop's agent does). The file goes in as
   `.github/workflows/test_build_and_push_the_app_image.yml`. Change the two
   steps its comments mark `REPLACE` (the app's language and its test
   command, which includes the seed command), and commit it. On each push
   to `main` it does six things:

   1. checks out the code and starts a throwaway Postgres;
   2. runs the app's tests;
   3. builds the image for `linux/amd64`, the servers' architecture,
      passing the full commit as `RELEASE`, and tags it with the full
      commit, `${{ github.sha }}`;
   4. logs in to GHCR with the run's own `GITHUB_TOKEN`, which GitHub makes
      for that run and then discards, with `permissions: packages: write`;
      no long-lived token exists to leak;
   5. pushes the tag;
   6. asks the registry to list the tag, so a run that reports success has
      a tag at the registry.

   Two things must agree with the app. The image name is
   `ghcr.io/<owner>/<repository>` in lowercase, and it must be the same
   text as `image` of the app under `vars.apps` (step 2), or the servers pull
   a different image. The workflow builds `--file Containerfile`; an app
   with a `Dockerfile` renames it, or changes that `--file`. Either file
   must start with `ARG RELEASE`, and this step is where you make sure it
   does: add the build file if the app has none, and the `ARG` if it is
   missing (`reference_app`'s `Containerfile` is an example).

   The servers' registry read token is a different token, made in
   [chapter 4](04_sign_up_for_the_outside_services_the_stack_uses.md)
   (step "The registry's read-only token") and kept in the vault as
   `container_registry_read_only_token`. A GHCR package is private by
   default, so the servers cannot pull without it.

   Do not give CI server SSH keys, the vault passphrase, or a
   systems-repository write key.
   GitHub's page of the account's packages
   (`https://github.com/OWNER?tab=packages`) shows the package and its
   access settings.

   **Ask the person,** with CI:

   > Please review the CI file I wrote, `.github/workflows/test_build_and_push_the_app_image.yml`, and push it to your app's `main`.
   > Tell me when it is pushed. CI then builds your first image.

   **Without CI.** The coding agent tests and builds by hand on the desk.
   Both run only inside a container, as `coding-agent`, with `podman`:
   never the app's own tools on the desk, never `--network host`, and never
   `/run` or a home directory mounted. Mount only the app's clone.
   `podman build` counts as inside a container: the build's steps run in the
   build's own containers. Set these once; `IMAGE` is the app's language
   image, the one its build file starts `FROM`, and `IMAGE_NAME` is the
   app's `image` under `vars.apps` (step 2), never typed from memory:

   ```sh
   # On the systems desk, as the coding agent, in the app's clone, after `git pull`:
   test -z "$(git status --porcelain)" || { echo 'The clone has changes; the tag would not name the image code' >&2; exit 1; }
   image_tag=$(git rev-parse HEAD)
   IMAGE=docker.io/library/node:22                # the app's language image
   IMAGE_NAME=ghcr.io/example/shop                # `image` of this app in vars.apps
   OWNER_AND_REPOSITORY=example/shop              # the app's repository at GitHub
   # Tests with a database: a throwaway Postgres on a network of its own.
   podman network create test-net
   podman run -d --network test-net --name test-db -e POSTGRES_PASSWORD=throwaway-test-password docker.io/library/postgres:17
   until podman exec test-db pg_isready -U postgres; do sleep 1; done
   # TEST_DATABASE_URL is the setting the app's tests read. The tests include the seed command.
   podman run --rm --network test-net -v "$PWD":/app:Z -w /app -e TEST_DATABASE_URL=postgresql://postgres:throwaway-test-password@test-db:5432/postgres "$IMAGE" npm test
   podman rm -f test-db && podman network rm test-net
   # Build for the servers' architecture, and push.
   podman build --file Containerfile --platform linux/amd64 --build-arg RELEASE="$image_tag" --label "org.opencontainers.image.source=https://github.com/$OWNER_AND_REPOSITORY" --tag "$IMAGE_NAME:$image_tag" .
   podman push "$IMAGE_NAME:$image_tag"
   ```

   The label links a brand-new package to the repository, which keeps the
   first push from being refused with `denied`. The tag is the full commit ID of a clean clone.
   `RELEASE` gives the app the commit it was built from; a build file
   without `ARG RELEASE` ignores it. `--platform linux/amd64` builds for
   the servers.
   The person signs the desk in to the registry once, as
   [The registry publishing login](04_sign_up_for_the_outside_services_the_stack_uses.md#make-the-desks-app-checkout-credentials) says.
   That login can publish images and reach no server.

   **Tell the person after:** no message, because step 7 checks the image
   and tells the person the result.

   **Check:** with CI, the workflow file is on the app's `main`; without
   CI, `podman push` ended without an error.

7. **The first image.** Verify the pushed image exists at the registry and
   has the selected architecture. With CI, the workflow's last step asks
   the registry for the tag, so a green run on that commit is the proof.
   The desk holds no registry login, so the person looks.
   Without CI, the coding agent has the push login and runs one command:

   ```sh
   # This systems desk, as the coding agent:
   podman manifest inspect IMAGE_NAME:FULL_APP_COMMIT_ID
   ```

   It prints a manifest that names `linux/amd64`. An error such as
   `manifest unknown` means the tag is not at the registry: the push failed,
   or the name differs from `image` under `vars.apps`. The command sends the
   OCI and Docker index and manifest types itself; a hand-written HTTP request
   must list all four, because GHCR answers 404 when the image's own type is
   missing. Record the full app commit ID as the
   image tag in production's `deployed_image_tags`. Commit and push the systems repository change.
   Chapter 7 (install everything on the production servers) configures the servers with the first image.

   For later releases, the coding agent updates the environment's tag,
   commits, pushes, and runs `deploy --var environment_name=ENVIRONMENT`
   on `util01`. With `staging01`, staging and production reuse the same
   tested image; no second build changes the image between staging and
   production.

   **Ask the person,** with CI:

   > Please open your app's Actions tab, `https://github.com/OWNER/REPOSITORY/actions`, or run `gh run list --commit FULL_APP_COMMIT_ID`.
   > The run for your latest commit must be green, and its last step's output must name `linux/amd64`.
   > Tell me what you see.

   **Tell the person after:**

   > Your app's first image is ready at the registry, tagged with commit `FULL_APP_COMMIT_ID`.
   > Building an image changes no server. I record the image tag and run the deploy, and by default a release to production waits for your approval.
   > Some of your app's checks need running servers, so they wait for chapter 7: [the app's open checklist items].

   **Check:** the run is green and names `linux/amd64`, or
   `podman manifest inspect` names `linux/amd64`. `deployed_image_tags`
   holds the full app commit ID, pushed.

8. **An app requirement in the checklist that the app cannot meet** is a
   deviation, recorded with the reason. For example, a job queue in Redis,
   a separate data store that holds waiting background jobs, differs from
   the stack's requirement to keep the queue in Postgres.

   **Tell the person,** before you record each deviation:

   > Your app keeps its waiting background jobs in Redis, and the Stack keeps them in Postgres.
   > I record the difference in the checklist, with the reason, so the next person sees why.

   **Check:** each such item is `deviated`, with `deviation:` saying what
   differs and why.

## If something is different

- **An app whose tests need no database** (step 6, without CI): leave out
  the first four commands and the `--network` and `-e` options.
- **Another CI service** (step 6): it follows the same six steps; only the registry host,
  the login command, and the name of the publish-only token change.
- **GHCR refuses the first push of a brand-new package with `denied`**
  (step 6, with CI). The workflow's image label links the
  package to the repository, which normally prevents it; if it happens,
  rerun the failed job in the repository's Actions tab, with nothing
  changed. A second `denied` is a real permission problem.
- **An arm64 desk, without CI** (step 6): `--platform linux/amd64` needs
  emulation (`qemu-user-static`) that the desk does not install, so a team
  without CI uses an x86-64 desk.
- **A Git host other than GitHub, without CI** (step 6): the registry host,
  the login command, and the token's name change; the steps do not.

## An app you didn't write

A ready-made program that the team runs as one of its apps, such as a
newsletter tool, goes through the same steps, with these differences.

- **A small repository of the team's own builds the image** (steps 1 and 6).
  Its `Containerfile` starts from the program's published image, pinned by
  its digest, such as
  `FROM docker.io/listmonk/listmonk@sha256:DIGEST`, and adds only what the
  steps below need. CI builds it with the installed skill's
  `files_for_your_app/test_build_and_push_the_app_image.yml` and tags each
  image with that repository's full commit. Reason: an image tag in
  `deployed_image_tags` is a full commit, so one tag always names one image.
  A new release of the program is a commit that changes the digest, and is
  deployed and rolled back like any release.
- **The program's settings keep the program's own names** (step 2). Put
  its plain settings under the app's `env`, and its secrets in
  `secrets_from_vault`. When the program wants a value of `DATABASE_URL` in
  another form, such as a host, a port and a password, a short start script
  in the image reads `DATABASE_URL` and sets the program's variables, then
  starts the program.
- **The database server** (step 5, the app's item ending in `_database_driver_finds_the_primary`,
  such as `newsletter_database_driver_finds_the_primary`). When the program's driver takes
  `DATABASE_URL` with its list of servers, as "Each language" in the
  installed skill's `files_for_your_app/database_driver_finds_the_primary.md`
  lists, the item is met. When the program takes only one
  host and port, it reaches only the server that its start script names at
  start: with one database server, `db01`, which is how a system starts.
  Such a program does not follow a failover: after one, it keeps asking
  the old primary until its containers start again. PgBouncer does not
  change this, because PgBouncer runs on each database server, not in front
  of them. Record the item as `deviated`, with this reason, so the team
  decides about the program before
  [adding a second database server](../operating_procedures/add_a_second_database_server.md).
- **The checklist items the program cannot meet** (step 8), such as a seed
  command or migrations that keep the running release working, are
  `deviated` with the program's own reason: the team cannot change the
  program's code.

## Why the chapter works this way

**The desk only reads the app.** Reason: the clone only reads the code; an image can be published without a production private key or vault passphrase.

**The container.** Reason for the container: the app's install, test and build commands run code from the app's packages. A poisoned package would then run on the desk, next to its SSH socket and its API proxies at `127.0.0.1:8081` and `127.0.0.1:8082`. Inside a rootless container, with nothing but the app's clone mounted, a test on a real desk showed the code can reach neither.

**One tag names one image.** The playbooks refuse any tag other than the
full commit, so that one tag always names one image.

**The old-password check.** The database entries in
`playbooks/end_connections_that_use_an_old_database_password.yml` let
rotation check the current password without requiring staging secrets on a
production-only system.

**The app's code is the person's.** Each code fix is a change the person
reviews, because the app's code belongs to the person.

**Images from CI or the desk.** Reason: the image can come from CI or the systems desk; the deployment path
remains the coding agent's explicit MMX run. By default, a release to
production waits for the person's approval
(`production_releases_wait_for_a_persons_approval` in `mmx_project_settings.yml`).

**Test data comes from the seed command.** "Production data stays on the
production servers" in [The rules](../AGENTS.md#the-rules) gives the
whole rule and its reasons.

Next: [Chapter 4: Sign up for the outside services the Stack uses](04_sign_up_for_the_outside_services_the_stack_uses.md).
