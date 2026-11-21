# Post to the status page

**When to use this page:** customers need to hear about a problem, such as
an outage, a recovery or a break-in, and later that the problem is over.

**What this page does:** this page posts a notice on the public status
page, updates the notice, corrects or deletes it, and resolves the notice,
through MMHotline while `util01` runs, or from a systems desk with the
person's own R2 key while `util01` is down.

**Who acts:** the coding agent writes each message for the incident at
hand and gives the person the command. The person posts: in MMHotline in
the browser, or, while `util01` is down, in their own desk terminal. The
desk commands read the person's own R2 key from their token file on the
desk, `~/.config/monkeymaxxing-stack/example_systems.env`, which you never
read.

**Terms:** this page uses the Stack's terms, such as status page, token
file, link token, R2 and `util01`.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term. Read [The MMHotline-down alarm and the status page](test_the_alarm_for_a_silent_mmhotline.md#the-mmhotline-down-alarm-and-the-status-page)
for how the two services keep working while the servers are down.

## Find your situation

| Situation | Follow |
| --- | --- |
| `util01` runs | [Post through MMHotline while util01 runs](#post-through-mmhotline-while-util01-runs) |
| `util01` is down, and your systems desk works (your phone-code SSH login to the desk works) | [Post from a systems desk while util01 is down](#post-from-a-systems-desk-while-util01-is-down) |
| Your systems desk is lost, whether `util01` runs or not | [When the desk is also lost](#when-the-desk-is-also-lost) |

## Before you start

- **Write plain-text messages for customers.** Say what customers notice
  and what the team is doing. Never include a server's name or a secret.
- **The public status page's link** is in
  [the README](../README.md#operating-links). Each route below ends by
  checking that page.
- **Times on the page.** A visitor's browser shows each time in the
  visitor's own time zone. The page's raw HTML, and a browser without
  JavaScript, show the times in UTC. Write a time inside a message in UTC,
  such as "13:30 UTC", or leave it out.

## What a notice has

A **notice** is one problem or one planned job, with its updates. Each
notice has these parts:

| Part | What it is | The command's flag |
| --- | --- | --- |
| Title | A short name for the notice, 1 to 140 characters on one line, such as "Sign-in delays". The page and the feed show it. Required | `--title "..."` |
| Message | What customers notice and what the team is doing. Required with every post | `--message "..."` |
| Impact | `outage` (the default), `degraded` (slow, or some customers affected) or `maintenance` (planned work). An outage makes the page's banner red, a degraded notice amber, and a maintenance notice blue | `--impact outage`, `--impact degraded` or `--impact maintenance` |
| Affected components | The parts of the service the notice names, from the `components` list in `mmhotline_settings.yml`. Leave this out when the list is empty. Repeat the flag for more than one | `--component website --component api` |
| Stage | The notice's step, which labels each update. Optional. For `outage` and `degraded`: `investigating`, `identified`, `monitoring` or `resolved`. For `maintenance`: `scheduled`, `in_progress` or `completed` | `--stage identified` |
| Planned window | When planned work starts and ends, as UTC times in the form `2026-12-05T02:00:00Z`. Only for `maintenance`; the end must come after the start | `--scheduled-start ...` and `--scheduled-end ...` |

A stage labels an update. It does not close the notice: only
`mmhotline status-page resolve` closes it. A closed `outage` or `degraded`
notice shows as "Resolved", and a closed `maintenance` notice shows as
"Completed".

**Planned maintenance.** Post the notice ahead of time with
`--impact maintenance` and `--stage scheduled`. The page shows a blue
"Scheduled maintenance" banner, and each affected component stays
"Operational". When the work starts, post an update with
`--stage in_progress`: each affected component then shows "Maintenance".
When the work ends, resolve the notice, which shows as "Completed" and
returns the components to "Operational". The page never closes a
maintenance notice at the planned end time, so a person always does.

## Post through MMHotline while util01 runs

1. **Open the "Alerts and correction approvals" link** in
   [the README](../README.md#operating-links).
   **Check:** none here; step 3 checks the public page.
2. **Open the incident for the problem, then select "Post to the status
   page".** The button posts an outage notice titled "Service disruption",
   which the person can then update and rename, as the paragraph below says.
   Or, when the person asks you to post, run it on `util01`
   through the desk:
   `ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 "mmhotline status-page post --title \"...\" --message \"...\""'`.
   The command passes through two shells, so keep the quotes exactly as
   shown: the `\"` marks keep each multi-word title and message in one
   piece. Text sent this way must not contain `'`, `"`, `$`, or a
   backtick. For such text, post in MMHotline's browser screen, or from the
   desk as [Post from a systems desk while util01 is down](#post-from-a-systems-desk-while-util01-is-down)
   says.
   Add `--impact`, `--component`, `--stage`, `--scheduled-start` and
   `--scheduled-end` as [What a notice has](#what-a-notice-has) says.
   **Check:** none here; step 3 checks the public page.

   To update a notice that is already open, add `--notice-id N` and leave
   out `--title` and `--impact`. To close it, run `mmhotline status-page resolve --notice-id N --closing-message "..."`.
   To fix a typo or the notice's details, or to remove a mistaken or test
   notice or update, use `mmhotline status-page edit` or
   `mmhotline status-page delete` the same way
   ([Correct a notice](#correct-a-notice-or-delete-a-mistaken-one)).
   MMHotline's status page screen does the same in the browser: each open
   notice has an "Add an update" form, and folded sections to resolve, edit
   or delete.
3. **Check the public status page,** linked in
   [the README](../README.md#operating-links).
   **Check:** the page shows the notice under its title, or lists a
   resolved notice under "Recently resolved".

## Post from a systems desk while util01 is down

While `util01` is down, each person posts from their own systems desk with
their own R2 key for the page's bucket
([A person's own R2 key for posting from a systems desk](#a-persons-own-r2-key-for-posting-from-a-systems-desk)).
Every command here runs in the person's own desk terminal. The person
opens it on the laptop with `ssh desk01` and a phone code.

1. **Check that the desk can post:**
   `. ~/.config/monkeymaxxing-stack/example_systems.env && mmhotline status-page show`.
   **Check:** the command lists the page's notices. An empty list is fine: a successful read verifies the
   desk's bucket address and R2 key
   ([chapter 8](../initial_setup/08_check_that_alerts_reach_your_phone_and_backups_restore.md)). When the token file
   lacks the three lines below, such as on a new person's desk or a rebuilt
   desk, do step 2 first.

   ```sh
   # Posting to the status page from this systems desk while util01 is down: this person's own R2 key for the page's bucket.
   export MMHOTLINE_STATUS_PAGE_R2_BUCKET_URL='...'      # status_page.r2_bucket_url; not a secret
   export MMHOTLINE_STATUS_PAGE_R2_ACCESS_KEY_ID='...'   # not a secret
   export MMHOTLINE_STATUS_PAGE_R2_SECRET_ACCESS_KEY='...'
   ```

2. **Only when the token file lacks those lines: make the person's key,**
   in the person's own desk terminal:

   ```sh
   set-up-outside-services cloudflare
   ```

   The command asks for a link token, made from the link it prints, makes
   the person's key, and deletes the link token. The command needs the
   status page's domain to be Active at Cloudflare.
   **Check:** step 1's command lists the page's notices.

3. **Post the first notice.** The examples below show an initial post, a
   later update, and a resolution after recovery. Write each title and
   message for the incident at hand. Add `--impact`, `--component` and
   `--stage` as [What a notice has](#what-a-notice-has) says.

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page post --json --title "Our site is down" --impact outage --stage investigating --message "Our site is down. We are working to bring it back."
   ```

   For planned work, post the notice ahead of time:

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page post --json --title "Database upgrade" --impact maintenance --stage scheduled --scheduled-start 2026-12-05T02:00:00Z --scheduled-end 2026-12-05T03:00:00Z --message "We upgrade our database. The site may be slow for a few minutes."
   ```

   **Check:** the first post prints the notice's `notice_id`, and the
   public status page shows the notice under its title. Use the printed
   `notice_id` when updating, correcting or resolving the notice. The
   later examples use `1` as the notice ID.

4. **Post each later update.** An update has a message and, when you wish,
   a stage. It takes no title or impact: [step 6](#correct-a-notice-or-delete-a-mistaken-one)
   changes those.

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page post --notice-id 1 --stage monitoring --message "The site works again for most customers."
   ```

   For planned work, post `--stage in_progress` when the work starts: the
   affected components then show "Maintenance".

   **Check:** the public status page shows the update.

5. **Resolve the notice after recovery:**

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page resolve --notice-id 1 --closing-message "Everything works again."
   ```

   A closing message takes the stage `resolved`, or `completed` for a
   maintenance notice, unless you add `--stage`.

   **Check:** the public status page lists the resolved notice under
   "Recently resolved". `mmhotline status-page show` lists the open
   notices, with each update's `update_id` and stage.

6. **Correct or delete a notice when needed,** as
   [Correct a notice or delete a mistaken one](#correct-a-notice-or-delete-a-mistaken-one)
   says.

## Correct a notice or delete a mistaken one

Use `edit` to fix a typo, or to change a notice's title, impact, components
or planned window, or an update's message or stage. Use `delete` to remove
a mistaken or test notice, or one mistaken update. An edited update shows
"(edited)" on the page. Both commands rewrite the page's three files at
once.

Find the IDs first. `mmhotline status-page show` lists the open notices
with their `notice_id` and each update's `update_id`. It lists only the
three most recent resolved notices, without their updates.
`mmhotline status-page show --json` lists the full notice history with
every `notice_id` and `update_id`, resolved notices included. A notice that
is already resolved can be edited or deleted too.

**While `util01` runs,** run the command on `util01` through the desk, or
use the folded "Edit" and "Delete" sections of MMHotline's status page
screen. The commands below use `1` as the notice ID and `2` as the update
ID:

```sh
# On the laptop. Fix a notice's title:
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 "mmhotline status-page edit --notice-id 1 --title \"Sign-in delays\""'

# Fix an update's message:
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 "mmhotline status-page edit --notice-id 1 --update-id 2 --message \"We found the cause and are rolling out a fix.\""'

# Delete one update, or the whole notice:
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 "mmhotline status-page delete --notice-id 1 --update-id 2"'
ssh desk01-agent 'cd systems_repository && ssh -F ssh/config root@10.20.0.1 "mmhotline status-page delete --notice-id 1"'
```

Text sent through these nested lines must not contain `'`, `"`, `$`, or a
backtick; use MMHotline's browser screen for such text.

**While `util01` is down,** the person runs the same commands from their
own systems desk terminal, with their own R2 key:

```sh
. ~/.config/monkeymaxxing-stack/example_systems.env &&
  mmhotline status-page edit --notice-id 1 --title "Sign-in delays"

. ~/.config/monkeymaxxing-stack/example_systems.env &&
  mmhotline status-page edit --notice-id 1 --update-id 2 --message "We found the cause and are rolling out a fix."

. ~/.config/monkeymaxxing-stack/example_systems.env &&
  mmhotline status-page delete --notice-id 1 --update-id 2

. ~/.config/monkeymaxxing-stack/example_systems.env &&
  mmhotline status-page delete --notice-id 1
```

Each `edit` changes only the flags you give, and needs at least one:

- **A notice:** `--title`, `--impact`, `--component` (repeat it for more
  than one component), `--clear-components`, `--scheduled-start`, `--scheduled-end` and
  `--clear-schedule`. Changing the impact away from `maintenance` clears
  the planned window.
- **An update** (with `--update-id`): `--message`, `--stage` and
  `--clear-stage`.

`delete --notice-id N` removes the whole notice. With `--update-id U` it
removes one update, and refuses to remove the notice's only update: delete
the notice instead. A deleted notice's ID is never used again.

**Check:** `mmhotline status-page show` lists the corrected notice, or no
longer lists the deleted one, and the public status page shows the same.
`https://status.example.com/feed.xml`, which the page's footer links as the
"Atom feed", shows the corrected title too.

## When the desk is also lost

**When `util01` still works:**

1. **Post through MMHotline in a browser on a trusted laptop,** as
   [Post through MMHotline while util01 runs](#post-through-mmhotline-while-util01-runs)
   says. The browser sign-in uses Cloudflare Access; the lost desk is not
   needed.
   **Check:** verify the public status page after posting.

**When `util01` and the desk are lost:**

1. **Follow [Rebuild a systems desk](rebuild_a_systems_desk.md).** Do not
   wait for a complete production rebuild to post.
   **Check:** the checks of Rebuild a systems desk.
2. **The rebuild's Cloudflare step made the person's new R2 key.**
   [Rebuild a systems desk](rebuild_a_systems_desk.md)'s step 17 runs
   `set-up-outside-services cloudflare`, which writes the key and the
   page's bucket address into the new desk's token file, and deletes the
   lost desk's key, which has the same name. The desk role installs
   MMHotline's command-line program, at the release pinned by
   `stack_software.mmhotline.version` in `mmx_project_settings.yml`.
   **Check:** `. ~/.config/monkeymaxxing-stack/example_systems.env && mmhotline status-page show`,
   in the person's own desk terminal, lists the page's notices.
3. **Use the posting commands above** (steps 3 to 5 of
   [Post from a systems desk while util01 is down](#post-from-a-systems-desk-while-util01-is-down),
   and [Correct a notice or delete a mistaken one](#correct-a-notice-or-delete-a-mistaken-one)).
   The replacement desk can post directly to R2 before joining monitoring
   or rebuilding `util01`.
   **Check:** the public status page shows the notice.
4. **Record the tested desk-loss posting path in `systems_desk_recovery`.**
   **Check:** none, because the record is the last step.

Reason: the public status page lives outside the production servers, and a replacement desk needs no working MMHotline service to write R2.

## If something is different

- **If the token file lacks the three R2 lines,** run
  `set-up-outside-services cloudflare` (step 2 of
  [Post from a systems desk while util01 is down](#post-from-a-systems-desk-while-util01-is-down)).
- **If a person leaves the team,**
  [Add or remove a team member](add_or_remove_a_team_member.md#adding-or-removing-a-person)
  deletes the leaving person's key by its name.

## A person's own R2 key for posting from a systems desk

While `util01` is down, each person posts from their own systems desk with
their own R2 key for the page's bucket. `set-up-outside-services cloudflare`
makes the key, an account token named after the person, such as
`example_systems: alex posts to the status page`, with Workers R2 Storage
Bucket Item Write on the page's bucket only. It writes the key into the
desk's token file, `~/.config/monkeymaxxing-stack/example_systems.env`,
beside the page's bucket address.

The `systems_desk` role installs MMHotline's command-line program on the
systems desk, at the release pinned by `stack_software.mmhotline.version` in
`mmx_project_settings.yml`. With the three R2 settings above,
`mmhotline status-page post`, `resolve`, `edit` and `delete` write
directly to the page's bucket, and rewrite `index.html`, `status.json` and
`feed.xml` there. The MMHotline service does not run on the
systems desk.
