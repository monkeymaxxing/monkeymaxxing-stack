# Chapter 2: Get your app ready to deploy

**When:** right after chapter 1 (answer two questions).

**What this chapter does:** the app gets ready to run on several app
servers and to keep working after a database switch, so later the team
only needs to add a server to handle more requests. The systems repository
gets the app's settings. CI gets a workflow that builds the app's images.

**Who acts:** you, the coding agent, work on the laptop, in the app's
folder, where you can already read and push the code. You write every
change. The person approves the whole set once, because the app's code is
the person's. Then you push the changes and watch the first build.

**Tell the person when the chapter starts:**

> I am reading your app's code, to see what it needs to run on your servers.

## Before you start

- **Your laptop runs your app's packages. Use a container.** The app's
  install, test and build commands run code from the app's packages, such
  as `npm install` and `npm test`. A poisoned package would run as the
  person, on the laptop. From chapter 4 on, the laptop also holds an open
  login to the systems desk while you work. A poisoned package could use
  that login to act on production while the login is open. The package
  still cannot copy the production key, the vault, or the person's
  tokens, which stay on the desk. So run every install, test and build
  command of the app only inside a container on the laptop, with
  `podman` or `docker`, with only the app's folder mounted, written out:
  `podman run --rm -v /Users/alex/code/shop:/app -w /app IMAGE npm test`. CI runs the
  real tests and builds on a clean machine. When the laptop has no
  podman or docker, run none of these commands on the laptop: say on
  step 7's screen that the app's tests run in CI for this reason. Never
  ask the person to install a container tool. This risk is accepted when
  the team chooses one agent on the laptop. The guide states this risk
  here only.
- **Systems settings go into the laptop's copy,** `~/code/example_systems`,
  until chapter 3 copies it to the desk.
- **More than one app.** Steps 2 to 8 are for each app.

## Steps

1. **The app's repository.** The person started you in the app's folder.
   Read the app's code there. Record the repository's address from
   `git remote get-url origin`, such as `git@github.com:OWNER/shop.git`, and
   its owner, `OWNER`. Chapter 3 makes the systems repository at the same
   owner.

   **Tell the person:** no message, because the chapter's opening line
   said what you do.

   **Check:** you know the app's address, owner and main branch, and
   `git status` in the app's folder shows no change of the person's own.
   When the person has uncommitted work, ask once whether to wait, and
   never mix your changes with the person's.

2. **Its settings,** under `vars.apps` in `mmx_project_settings.yml` of the
   laptop's copy, `~/code/example_systems`: an
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
   - the app's database pool size, set explicitly under `env`
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
   - `asset_directory`, `database_name`, and `env`: the app's settings
     that are not secret, such as its public address, `APP_ORIGIN`. Leave
     the uploads bucket's name, `R2_BUCKET`, out of `env`: the Stack writes
     it from `production_uploads_r2_bucket`, so the app and the nightly
     copy of its uploads use the same bucket;
   - `staging_env`: the settings `staging01` takes in place of the same
     names in `env`, so staging never uses production's public address. Give
     it its own `APP_ORIGIN`, as the example app does. Write `{}` for none.
     The staging uploads bucket is `staging_uploads_r2_bucket`, which
     `staging01` gets as `R2_BUCKET`. When the team adds `staging01`,
     `every_server` refuses an app that would leave production's bucket or
     address in place;
   - `secrets_from_vault`: each secret the app reads, and where its value
     comes from, from the app's code, as the template's example app does:
     - `where_the_value_comes_from: generated_by_the_setup` for a value
       nobody needs to see, such as Rails' `SECRET_KEY_BASE`, and for the
       two R2 key variables. The setup makes it without a question;
     - `where_the_value_comes_from: an_outside_service` for a key another
       company gives, such as Stripe's API key, with `what_it_is_for`, one
       sentence the person reads, and `steps_to_get_it`, the steps on that
       company's website, one per line. Add `checked_with: stripe` for a
       Stripe key, and leave `checked_with` out for any other service. In
       chapter 4 the setup shows each such key on its own screen and asks
       the person for it;
   - `production_uploads_r2_bucket`: the name of the R2 bucket for the app's
     uploaded files in production, such as `example-shop-uploads`, which
     `go-live` makes in chapter 4, once the person turned R2 on there, and
     `production_uploads_r2_key_variables`, the two names in
     `secrets_from_vault` that hold the bucket's key; `""` and no
     `production_uploads_r2_key_variables` when the app keeps no uploaded
     files;
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
   app's code, and step 7 shows the person each change the app needs.

   **Check:** each key above holds the app's value, not `shop`'s, and
   `mmx validate every_server` stops, if at all, only on a value whose
   comment names a later chapter, as chapter 1's check says. Chapter 7's
   check runs the whole `mmx validate` once every value is filled.

3. **The app's hostnames, image tags, and secret mappings:** in
   `inventories/servers.yml`, set the app's production host name in
   `public_host_names` to the app's address from chapter 1's screen, such
   as `example.com`, and the app's
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
   as an example, and `mmx validate every_server` stops, if at all, only
   on a value whose comment names a later chapter.

4. **Its checklist items:** copy the `apps.shop` block of the checklist
   under the app's name, with the app's name in each item's `id` and text.
   The app's items can mostly be verified only once the servers run: they stay
   `open`, with `waits_for: chapter 7 (install everything on the production servers)`, until
   [chapter 7 (install everything on the production servers)](07_install_everything_on_the_production_servers.md#chapter-7-install-everything-on-the-production-servers).
   An item whose `waits_for` in the checklist names a later step, such as
   `shop_deploys_without_dropping_requests`, which waits for the second
   deploy, keeps that `waits_for`.

   **Tell the person:** no message, because step 8 records each item the
   app cannot meet.

   **Check:** each of the app's items is `open` with its `waits_for`.

5. **The app's code, against each item's `verification`.** Write each fix
   in the app's folder on the laptop, on the app's `main`, uncommitted. Step 7
   shows every fix at once. The usual code fixes:
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
     `WEB_CONCURRENCY` lower in the app's `env`.
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
   - **the app stops cleanly when asked:** on `SIGTERM`, which a release
     sends to the old version's containers, the web and job processes
     finish their current requests and exit within 30 seconds
     (`StopTimeout=30` in `roles/app_server/files/web_container.container`).
     In a container the app's first process is process 1, which ignores
     `SIGTERM` unless the program handles it. Puma and Gunicorn handle it
     already. A Go app calls `http.Server.Shutdown` on the signal. A
     Node.js app, with or without `cluster`, needs a `SIGTERM` handler
     that closes the server and the database pool, then exits. Read the
     app's start code for it, and make the fix
     here and name it on step 7's screen, such as "`server.js`: stops
     cleanly when the server asks, so a release never waits 30 seconds".
     Reason: in a newcomer test run, the agent found the missing handler
     only at the first release, after the site was live, and had to ask
     for another yes;
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
     command runs on laptops and on `staging01`, never in production.

     Production data stays on the production servers: no copy of
     production goes to a laptop, `staging01`, or CI, so the seed command
     is where test data comes from.

   **Tell the person:** no message, because step 7 shows every fix.

   **Check:** each of the app's items is met by a fix, or step 8 records
   the item as a deviation, and the app's start code handles `SIGTERM`
   as above.

6. **CI builds the images.** CI, the Git host's automated service, tests
   the app, builds the image from `Containerfile`, and pushes the image to
   the registry whenever the code on `main` changes. CI is the default, so
   there is no question. A team that already has CI keeps it, with the steps
   below. "No CI" stays a choice the person can name: see
   [If something is different](#if-something-is-different).

   The ready example is
   `test_build_and_push_the_app_image.yml`
   in the installed skill's `files_for_your_app/` directory, for GitHub
   Actions and GitHub's registry (GHCR). The file joins the fixes of step 5,
   as
   `.github/workflows/test_build_and_push_the_app_image.yml`. Change the two
   steps its comments mark `REPLACE` (the app's language and its test
   command, which includes the seed command). On each push
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

   Add one last step to the workflow, so you can read CI's result
   without the person (step 7): it pushes the run's result and the tests'
   output to a branch, `ci-report`, in the app's repository, success or
   failure. Make the test step save its output: the app's test command
   followed by `2>&1 | tee /tmp/test.log`, such as
   `run: go test ./... 2>&1 | tee /tmp/test.log`, with `shell: bash`,
   which still fails the step when the tests fail; set the job's
   `permissions: contents: write`, which lets the run push that branch,
   and add:

   ```yaml
         # CI's result, for a coding agent that cannot read this private repository's CI page.
         - name: Report the result to the ci-report branch
           if: always() && github.event_name == 'push'
           env:
             GITHUB_TOKEN_FOR_THIS_RUN: ${{ secrets.GITHUB_TOKEN }}
           run: |
             mkdir /tmp/ci-report && cd /tmp/ci-report && git init -q -b ci-report
             printf 'commit: %s\njob status: %s\n' "$GITHUB_SHA" "${{ job.status }}" > result.txt
             cp /tmp/test.log . 2>/dev/null || true
             git add . && git -c user.name=ci -c user.email=ci@localhost commit -qm "CI result for $GITHUB_SHA"
             git push -qf "https://x-access-token:${GITHUB_TOKEN_FOR_THIS_RUN}@github.com/${GITHUB_REPOSITORY}" HEAD:ci-report
   ```

   A push made with the run's own token starts no new run, and the
   workflow runs only for `main`, so the report never loops.

   Two things must agree with the app. The image name is
   `ghcr.io/<owner>/<repository>` in lowercase, and it must be the same
   text as `image` of the app under `vars.apps` (step 2), or the servers pull
   a different image. The workflow builds `--file Containerfile`; an app
   with a `Dockerfile` renames it, or changes that `--file`. Either file
   must start with `ARG RELEASE`, and this step is where you make sure it
   does: add the build file if the app has none, and the `ARG` if it is
   missing (`reference_app`'s `Containerfile` is an example).

   The servers' registry read token is a different token, made on the Git
   host's token screen in
   [chapter 4 (set up your accounts and lock your systems desk)](04_set_up_your_accounts_and_lock_your_desk.md#steps),
   step 6, and kept in the vault as
   `container_registry_read_only_token`. A GHCR package is private by
   default, so the servers cannot pull without it.

   Do not give CI server SSH keys, the vault passphrase, or a
   systems-repository write key.
   GitHub's page of the account's packages
   (`https://github.com/OWNER?tab=packages`) shows the package and its
   access settings.

   **Tell the person:** no message, because step 7 shows the CI file with
   the other changes.

   **Check:** the workflow file is among the uncommitted changes, with
   both `REPLACE` steps filled in.

7. **Show every change, once, and push.** Show the screen below, as the
   last text of your reply, with no tool call after it. Give each changed
   or new file one short line in plain words: what changes and why, such
   as "`src/uploads.js`: uploads go to R2, so every app server has every
   picture." Keep the file lines to about 8; when more files changed,
   group small ones on one line, such as "3 settings files: the database
   address", and name each file behind "show". Never paste the diff:
   Claude Code already showed each edit. Name every file that changed or
   is new, on the screen or behind "show": compare your list with
   `git status --short` in the app's folder, so a file such as
   `README.md` is not left out.

   **Ask the person:**

   ```text
   Your app needs 4 small changes to run on the servers.

     [one short line per changed file, about 8 lines at most]

   And one later change:  at the end of the setup I add one line to your README.md,
   "Deployed with the Monkeymaxxing Stack.", as your first release.  It proves that a new
   version goes live the way every later release will.  Your users see nothing.

   Tests: I did not run your app's tests.  This laptop has no podman or docker,
   so your app's tests run at GitHub, automatically, when I push.

   Backup: your server settings also get a private backup copy at GitHub, beside your app.
   If you already have an empty private repository for it, tell me its address exactly as
   you push to it.  Otherwise I make one, or show you how, in part 2.

   Say "yes" and I push them.  Or say "show" to see the details, or tell me what to change.
   ```

   The "Backup:" lines ask for the backup repository's address once,
   here, together with the app's repository, so no later part asks again.
   Record the address exactly as the person gives it, such as
   `git@github.com:OWNER/example_systems.git` or an SSH host alias from the
   person's `~/.ssh/config`, such as `github-backup:OWNER/example_systems.git`.
   Leave the lines out when the person already named it.

   "show" gives, per file, what changed in more words and the terms the
   person needs, such as the primary database server or R2, then the same
   question; "show" and a file's name shows that file's change.

   Write the app's test command so it runs as written on a clean
   machine, and check it against the test runner's own rules before the
   screen, because without a container tool nothing runs it before CI
   does. For example, Node's `node --test` finds the `test/` folder by
   itself, while `node --test test/` makes Node 22 look for a file named
   `test/` and fail. Reason: in a newcomer test run, that one word failed
   CI and cost the person a second "yes".

   Make the "Tests:" line true. When a container tool exists and you ran
   the tests, say that they passed or which failed. When the laptop has
   no podman or docker, keep the line above: the app's tests run in CI
   for that reason. Never ask the person to install a container tool.
   Never say or imply that tests passed when you did not run them.

   One "yes" approves the set, and the README line of the first release
   with it: chapter 9's step 3 pushes that line and asks nothing. Reason:
   "Your servers" and "Live" tell the person there is nothing to do, and
   in a newcomer test run a question about that line, asked there, waited
   unseen for over 9 minutes. When the person asks for a change, make it
   and show the screen again. When the person strikes the README line,
   ask on this screen which small change the first release may use
   instead, or offer an empty commit, which changes no file.

   After "yes", commit the changes in the app's folder with a message that
   says what changed and why, and push `main` with the person's own Git
   login. Then read CI's result yourself, from what you can read, never
   from the person: never ask the person to sign in to the Git host or to
   look at a CI page. Reason: a private repository's CI page says "Page
   not found" to a browser that is not signed in, and in a newcomer test
   the person could not sign in there at all. The routes, none of which
   needs the person:

   - **The image at the registry:**
     `./server_management_scripts/wait_for_the_app_image IMAGE:FULL_APP_COMMIT_ID`
     in the systems repository, as a background command. Exit 0 means CI
     built and pushed the image. Exit 3 means the image is private and
     this laptop has no registry login, so it cannot tell. From chapter 4
     on, the Git host token screen also reads the image with the new
     token, and the results file's `container_image_found` says whether
     CI built it.
   - **CI's report on the `ci-report` branch,** which step 6's workflow
     pushes on every run, success or failure: `git fetch origin ci-report`
     in the app's folder, then `git show origin/ci-report:result.txt` and
     `git show origin/ci-report:test.log`. The report names the commit,
     so check that it is the one you pushed. This route works with the
     Git login you already push with, and it also shows why a run
     failed.
   - **`gh run watch`** on the pushed commit's run, when `gh` is signed in
     on the laptop.

   Record the pushed commit's full ID, 40 characters, as the app's tag in
   production's `deployed_image_tags` in the laptop's copy, and commit
   there. Chapter 7 starts the app with that image.

   **Tell the person after:** the end of part 1, "Your app", with
   [chapter 0's compact map](00_before_you_start_what_we_build_and_how_long_it_takes.md#the-compact-map),
   whose first line gives the result, such as:

   ```text
   Your app is ready: my changes are on main, and GitHub is building your app.  That changes no server yet.

     ✓ 1. Your app
     → 2. Your accounts            now, about 25 minutes
       3. Your keys locked away
       4. Your servers
       5. Live
       Later: phone alerts.  Your site has none yet.
   ```

   Then, in the same reply, chapter 3's account screen follows as the
   reply's last text, as the skill's "Now and next" rule says. Never end
   the reply with "chapter 3 is next", or name a chapter at all.

   **Check:** the push succeeded, and `deployed_image_tags` holds the
   pushed commit's full ID, and you read CI's result from the registry,
   the `ci-report` branch, or `gh`. When none of them could tell yet,
   chapter 4 checks the image.

8. **An app requirement in the checklist that the app cannot meet** is a
   deviation, recorded with the reason. For example, a job queue in Redis,
   a separate data store that holds waiting background jobs, differs from
   the stack's requirement to keep the queue in Postgres.

   **Tell the person:** one line in step 7's screen, above the file lines, such
   as "Your app keeps its waiting jobs in Redis. The Stack keeps them in
   Postgres. I record the difference in the checklist." So the person
   reads every difference before the one "yes".

   **Check:** each such item is `deviated`, with `deviation:` saying what
   differs and why.

## If something is different

- **The app needs no change** (step 7): say so in one line, push nothing,
  and go on. An app that already has CI records the tag of its newest
  green build of `main`.
- **A bigger change, such as SQLite to Postgres, or uploads to R2**
  (step 5): show that change on its own screen first, in the same form,
  with what it means for the person's data. Such a change can take days.
  The setup then waits, and the day's plan moves with it.
- **The person names "no CI"** (step 6): test and build in a container
  on the laptop, with `podman build --platform linux/amd64 --build-arg RELEASE=IMAGE_TAG --tag IMAGE_NAME:IMAGE_TAG /Users/alex/code/shop`
  (or `docker build` with the same options, whichever the laptop has for
  the tests above) from a clean checkout, with the commit that
  `git rev-parse HEAD` prints written out as `IMAGE_TAG`. Push with
  the person's own registry login on the laptop. The servers still use
  only the read-only token of chapter 4.
- **Another CI service** (step 6): it follows the same six steps. Only the
  registry host, the login command, and the name of the publish-only token
  change.
- **GHCR refuses the first push of a brand-new package with `denied`**
  (step 7). The workflow's image label links the package to the
  repository, which normally prevents it. If it happens, rerun the failed
  job with `gh run rerun --failed` when `gh` is signed in; otherwise push
  an empty commit (`git commit --allow-empty`) after the person's "yes",
  and record its ID as the tag. Never send the person to the Actions
  tab. A second `denied` is a real permission problem.

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

**The app's code is the person's.** The person approves every change to
the app, in one set, before you push.

**The container.** The app's packages are the one piece of code here that
nobody on the team wrote. A container keeps that code away from the
laptop's open desk login.

**One tag names one image.** The playbooks refuse any tag other than the
full commit, so that one tag always names one image.

**The old-password check.** The database entries in
`playbooks/end_connections_that_use_an_old_database_password.yml` let
rotation check the current password without requiring staging secrets on a
production-only system.

**Images from CI.** CI builds on a clean machine. No password that can
publish an image sits on the systems desk. A release to production waits
for the person's approval by default
(`production_releases_wait_for_a_persons_approval` in `mmx_project_settings.yml`).

**Test data comes from the seed command.** "Production data stays on the
production servers" in [The rules](../AGENTS.md#the-rules) gives the
whole rule and its reasons.

Next, in the same reply, as the skill's "Now and next" rule says: [Chapter 3: Make your server account and your systems desk](03_make_your_server_account_and_your_systems_desk.md).
