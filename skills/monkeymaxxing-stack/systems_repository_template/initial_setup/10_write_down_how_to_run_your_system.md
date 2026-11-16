# Chapter 10: Write down how to run your system

**When:** after chapter 9 (go live).

**What this chapter does:** the break-in response page is prepared, the
checklist is reviewed, and the operating guide is saved in the systems
repository's `README.md`, with the links, the test results, what happens if
each server fails, and the person's next actions.

**Who acts:** you, the coding agent, write the pages and check the
results. The person corrects the break-in response page, checks a private
page when their login is necessary, and agrees who does each next action
and when.

**Tell the person when the chapter starts:**

> I save your operating guide in the systems repository's README, so that you, or a new session of your coding agent, can find it later without this conversation.
> The guide holds your links, test results, and next steps.
> The guide shows what works, what still needs attention, and what happens if each of your servers fails.

## Before you start

- **The messages to the person.** Each step says what to tell or ask the
  person, in quote blocks: "Tell the person first" before the step, "Ask
  the person" when the person must act or approve, and "Tell the person
  after" with the result and its link. Say each message when its step
  comes, in your own words, with the team's own names and links.
- **Do not read the full checklist aloud.** Link its evidence and answer the
  person's questions. The saved README must agree with the final explanation.

## Steps

1. **Prepare the break-in response page.** Before handover, prepare [the break-in response page](../operating_procedures/respond_to_a_break_in.md#0-prepare-the-response-page).
   You propose the page, with an answer to each question from what the
   systems repository and the setup already know, and the person corrects
   it; the person asks no question first. A question the team has not decided yet is answered "not decided yet", with
   the name of the person who will decide and a date; the page still counts as
   prepared.
   The two-desk staging drill and the yearly drill are optional practice: they are in the checklist's
   `growth_and_improvement_items`, and the setup does not run them.

   **Ask the person:**

   > Here is your break-in response page, filled in from what your systems repository already knows: [the page].
   > The page says what to do first if someone breaks in. Please correct any answer that is wrong.
   > For a question your team has not decided yet, tell me who decides, and by when.

   **Check:** record the proof in `break_in_response_page` in the checklist.

2. **Check the results.** Review the checklist against the results from each
   chapter. Each chapter marked the items it proved. Keep recorded deviations as
   `deviated`. Every item in the checklist's "Setup" part must be `done` or
   `deviated` with its reason. An item in the "Later, when it happens" part
   stays `open`, with its `waits_for` saying what must happen first. An item
   in `growth_and_improvement_items` stays `waits_for_its_trigger`, such as
   `second_database_server`, whose trigger is the first paying customers.
   Do not mark a scheduled test as complete.

   **Tell the person:** no message, because step 5 says what is complete.

   **Check:** every "Setup" item is `done`, or `deviated` with its reason.

3. **Save the operating handover in `README.md`.** Use the sections of
   `README.md`, copied from the systems repository template. Replace every
   example value with this system's actual value or a clear statement that
   the value is not available.
   Include:
   - The first page, from "What the Monkeymaxxing Stack builds" to "What
     the system does not survive", with the current servers: the
     production servers in point 2 of "The system in seven points", and
     the servers in "What happens when a server fails at night?". Keep the
     first page's other sentences. With the fuller system, say that the
     system has `app002` and `staging01`.
   - The app, alert dashboard, MMX history location, and status page links.
   - The app repository, image-build instructions, optional CI link, and
     systems repository link.
   - The test-app link, if the test server exists.
   - The common requests and their procedure links.
   - The effect of each server failure with the current inventory.
   - The restore measurements recorded in `monkeymaxxing_stack_checklist.yml`,
     under `backups_restore_every_week`, and reviewed in
     [chapter 8 (check that alerts reach your phone and backups restore)](08_check_that_alerts_reach_your_phone_and_backups_restore.md). Include the measurement
     dates and what each measurement covers and does not measure.
   - The person's next actions, at most five, in order, each with its
     responsible person and its date or starting event. Group related
     work into one action, such as the account protection still to add. Leave
     the later checks and the growth and improvement items, such as
     `second_database_server`, to the checklist, and say that the weekly
     review checks whether a trigger arrived.

   Keep a missing measurement marked as not measured. If a person or date
   is not agreed, record that fact. Do not replace an unknown result with
   the design target. Check the links that are available to this session.

   **Ask the person,** only when the person's login is necessary to check
   a private page:

   > Please open [the private page] and tell me whether the page opens. I cannot sign in there myself.

   **Tell the person:** no other message, because step 4 explains the
   saved failure behavior, and step 5 gives the README's path.

   **Check:** no example value remains in `README.md`, and every link
   available to this session opens.

4. **Explain the current failure behavior.** Use the inventory and the
   measured results. For the initial system with one app server, one
   database server, and `util01`, explain:

   > If db01 fails, your site stops until a replacement database is restored
   > from the backups and the app reconnects. There is no second database
   > server to become the primary automatically and accept database writes.
   > The database restore drill on [recorded date] took [measured time].
   > The newest restored transaction was [age] old when the drill began.
   > No test measured the time to recover the whole site.
   > [Say what the drill's check established about missing data, or that
   > the drill did not measure missing data.]
   >
   > If app001 fails, your site stops until a new app server replaces it.
   >
   > If util01 fails, your site keeps running. But scheduled checks and utility-server MMX runs stop,
   > and MMHotline is down until your coding agent rebuilds util01 from
   > the systems repository, using your systems desk. Two alarms reach your
   > phone: the hub-outage alerters alert everyone who can be on call,
   > directly through Pushover, and the MMHotline-down alarm in your
   > Cloudflare account wakes the person on call.

   If the restore drill did not pass, state that result instead of a
   restore time. The hub-outage alerters' sentence stands. Their outage test on this system is
   an optional check that the person can ask for
   ([Check my system's protections](../operating_procedures/assess_a_running_system_and_recommend_changes.md#check-my-systems-protections)); offer it, and assign it to nobody.

   Then explain what protects the site from an app001 or db01 failure:

   > Two operating procedures in your systems repository add servers to
   > keep the site running after an app server or database server fails.
   > [Add a second database server](../operating_procedures/add_a_second_database_server.md)
   > adds `db02` as a replica, so the database fails over to it by itself.
   > [Add an app server](../operating_procedures/add_an_app_server.md)
   > adds `app002`. The checklist says when: both at your first paying
   > customers. `db02` comes sooner once a restore takes longer than your
   > business can stay down, and `app002` once your business cannot stay
   > down while an app server is replaced. Once
   > db02 and app002 are added, I test that the site stays up when an app
   > server or a database server fails. The tests allow brief request failures
   > during a database switchover or after an app server fails.
   > Until db02 and app002 are added, an app001 or db01 failure takes the
   > site down.

   The two quote blocks above are this step's "Tell the person" messages.
   They are longer than other messages, because the README saves the same
   text.

   **Check:** the explanation agrees with the inventory, the measured
   results, and `README.md`.

5. **Show how to return.** Give the README path and the actual operating
   links. Explain how to start a new coding-agent session in the systems
   repository as `coding-agent` on the desk with `start-the-coding-agent`.
   Show `ssh desk01`, the phone-code prompt, and the desk's own recovery procedures.
   Show where the person updates the desk's inventory and manages the desk with `review-and-apply-the-systems-desk-settings`.
   Confirm the desk can test, build, and publish app images when CI does not perform those tasks.
   The laptop can keep app development and local tests.
   Use one relevant request from the README as an example.
   Show the alert acknowledgment and approval actions. Identify the status
   posting procedure and the recovery procedure table.

   **Tell the person first:**

   > Your operating guide is in [the README's link]. To come back later, run `ssh desk01`, type your phone code, then run `start-the-coding-agent`.
   > Then ask me in plain words, such as "[a request from the README]". The README lists the common requests.

   **Check:** the person can name where the README is and how to start a
   new session.

6. **State what is complete,** name the items that wait for a later
   event, offer the optional check of the system's protections, and
   confirm who will do the next actions and when. If responsibility
   or timing for a next action is not agreed, state that the handover still
   has unassigned work.

   **Ask the person:**

   > Your setup is complete: your site is live, alerts reach your phone, and your backups are proven to restore.
   > These items wait for a later event: [the items]. Your next actions are [the actions]. Who does each one, and when?
   > Want extra confidence? Ask me to check your system's protections. The check tests the protections on your own servers, some checks wait for a quiet time, and the Stack's own tests already proved how the software behaves.

   Mark `operating_handover_saved` only after its verification passes.
   Commit and push the README and checklist together. Then run
   `./server_management_scripts/run_mmx_on_util01 validate`, so MMHotline's
   dashboard shows the final checklist
   ([AGENTS.md, "Making a change"](../AGENTS.md#making-a-change), step 7).

   **Tell the person after:**

   > Your guide and checklist are saved, and MMHotline's dashboard shows the final checklist: [MMHotline's link].

   **Check:** `operating_handover_saved` is `done` after its verification
   passed, and the push reached the Git host.

## If something is different

- **The restore drill did not pass** (step 4): state that result instead
  of a restore time.
- **A next action has no agreed person or date** (step 6): state that the
  handover still has unassigned work, and record that fact in `README.md`.

## Why the chapter works this way

**The hub-outage alerters' sentence stands without a test here.** The
Stack's own tests prove how the hub-outage alerters behave, so their outage
test on this system is an optional check, assigned to nobody.

Next: follow the system's [operating procedures](../AGENTS.md#when-this-happens-follow-this-operating-procedure).
