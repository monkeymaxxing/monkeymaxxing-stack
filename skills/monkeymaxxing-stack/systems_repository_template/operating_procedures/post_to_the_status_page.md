# Post to the status page

**When to use this page:** customers need to hear about a problem, such as
an outage, a recovery or a break-in, and later that the problem is over.

**What this page does:** this page posts a notice on the public status
page, updates the notice, and resolves the notice, through MMHotline while
`util01` runs, or from a systems desk with the person's own R2 key while
`util01` is down.

**Who acts:** the coding agent writes each message for the incident at
hand and gives the person the command. The person posts: in MMHotline in
the browser, in a terminal on `util01`, or in the person's own desk
terminal. Commands that source the person's token file,
`~/.config/monkeymaxxing-stack/example_systems.env`, run only in the
person's own desk terminal, as the secrets rule in
[The rules](../AGENTS.md#the-rules) says.

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

## Post through MMHotline while util01 runs

1. **Open the "Alerts and correction approvals" link** in
   [the README](../README.md#operating-links).
   **Check:** none here; step 3 checks the public page.
2. **Open the incident for the problem, then select "Post to the status
   page".** Alternatively, run `sudo mmhotline status-page post --message "..."`
   in a terminal on `util01`.
   **Check:** none here; step 3 checks the public page.
3. **Check the public status page,** linked in
   [the README](../README.md#operating-links).
   **Check:** the page shows the notice, or lists a resolved notice under
   "Recently resolved".

## Post from a systems desk while util01 is down

While `util01` is down, each person posts from their own systems desk with
their own R2 key for the page's bucket
([A person's own R2 key for posting from a systems desk](#a-persons-own-r2-key-for-posting-from-a-systems-desk)).
Every command here runs in the person's own desk terminal.

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
   in the person's own desk terminal, in the systems repository:

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services cloudflare
   ```

   The command asks for a link token, made from the link it prints, makes
   the person's key, and deletes the link token. The command needs the
   status page's domain to be Active at Cloudflare.
   **Check:** step 1's command lists the page's notices.

3. **Post the first notice.** The examples below show an initial post, a
   later update, and a resolution after recovery. Write each message for the
   incident at hand.

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page post --json --message "Our site is down. We are working to bring it back."
   ```

   **Check:** the first post prints the notice's `notice_id`, and the
   public status page shows the notice. Use the printed `notice_id` when
   updating or resolving the notice. The update and resolution examples
   use `1` as the notice ID.

4. **Post each later update:**

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page post --notice-id 1 --message "The site works again for most customers."
   ```

   **Check:** the public status page shows the update.

5. **Resolve the notice after recovery:**

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env &&
     mmhotline status-page resolve --notice-id 1 --closing-message "Everything works again."
   ```

   **Check:** the public status page lists the resolved notice under
   "Recently resolved". `mmhotline status-page show` lists the open
   notices.

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
2. **On the replacement desk, the person runs `set-up-outside-services cloudflare`,**
   as [step 2 of posting from a systems desk](#post-from-a-systems-desk-while-util01-is-down)
   shows, in the person's own desk terminal. The run makes a new personal
   R2 key, writes it and the page's bucket address into the token file,
   and deletes the lost desk's key, which has the same name.
   **Check:** the token file holds the three lines.
3. **Install the pinned MMHotline CLI on the replacement desk.** The
   `systems_desk` role installs it, at the release pinned by
   `stack_software.mmhotline.version` in `mmx_project_settings.yml`.
   **Check:** `. ~/.config/monkeymaxxing-stack/example_systems.env && mmhotline status-page show`
   lists the page's notices.
4. **Use the posting commands above** (steps 3 to 5 of
   [Post from a systems desk while util01 is down](#post-from-a-systems-desk-while-util01-is-down)).
   The replacement desk can post directly to R2 before joining monitoring
   or rebuilding `util01`.
   **Check:** the public status page shows the notice.
5. **Record the tested desk-loss posting path in `systems_desk_recovery`.**
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
`mmhotline status-page post` and `mmhotline status-page resolve` write
directly to the page's bucket. The MMHotline service does not run on the
systems desk.
