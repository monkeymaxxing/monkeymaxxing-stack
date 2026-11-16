# Recover from a lost phone

**When to use this page:** the phone that gets the alerts and shows the
desk's phone code is lost, stolen, or stops working.

**What this page does:** the alerts reach the person's new phone again, and
a new phone code replaces the old phone's codes for logging in to the desk.

**Who acts:** the person does every step below, on the new phone, at
websites, and in the person's own terminals on the laptop and the desk. The
coding agent says what comes next and what to look for. The coding agent
never reads or handles the phone-code secret or the recovery codes.

**Terms:** this page uses the Stack's terms, such as phone code, systems
desk, MMHotline, and SOS. [Technical terms](../talking_with_the_team.md#technical-terms)
explains each term. Pushover is the push app that puts the alerts on the
phone.

## Tell the person before you start

> First we put the alerts on your new phone and send a test alert, so an urgent alert reaches you again.
> Then you log in to the desk without the old phone and make a new phone code.
> The new phone code stops the old phone's codes from working, even if someone else has the old phone.

## Before you start

- **The new phone is in the person's hands.** The steps install Pushover
  and an authenticator app on the new phone.
- **The person can open the team's password manager.** The person's
  Pushover login is there, and so are the phone-code secret and the
  recovery codes, which the person saved when the person set up the phone
  code.

## Put the alerts on the new phone

1. **Install Pushover on the new phone and sign in** with the person's
   Pushover account, whose login is in the team's password manager.
   **Check:** step 4's test alert checks this step, because only a phone
   signed in to the person's account receives the test.
2. **Allow alerts to sound in Silent Mode** (Critical Alerts on iOS), as
   [chapter 4 (sign up for the outside services the Stack uses)](../initial_setup/04_sign_up_for_the_outside_services_the_stack_uses.md#chapter-4-sign-up-for-the-outside-services-the-stack-uses)
   describes for the first phone.
   **Check:** step 5's test SOS rings the phone in Silent Mode. Step 5 runs
   only when the person is on call now. MMHotline's dashboard shows who
   is on call.
3. **When the old phone may be in someone else's hands, delete the old
   phone from Pushover.** The person signs in at
   [pushover.net](https://pushover.net/), finds the old phone in the
   account's list of devices, and deletes it.
   Reason: alerts name the servers and the faults, and a deleted device
   receives no more alerts.
   **Check:** the account's list of devices no longer shows the old phone.
4. **Send a test alert to the new phone.** **Warn the person first:** the
   test rings like an alarm. It is an emergency-priority Pushover message
   that repeats every 30 seconds, for up to 10 minutes, until the person
   acknowledges it on the phone. It is only a test, and nothing is wrong.
   The person opens MMHotline's page, such as `https://ops.example.com`.
   The team's address is in the system's `README.md`, under "Operating
   links", and in `util01_private_page_host_names.mmhotline` in
   `mmx_project_settings.yml`. The person signs in through Access, opens **Contact methods**, and sends a test to
   the Pushover contact method.
   **Check:** the new phone shows the test, and the person acknowledges the
   test in Pushover. The contact method's card saying "Accepted by
   Pushover" does not prove that the phone received the test.
5. **When the person is on call now, send the test SOS** of
   [chapter 8 (check that alerts reach your phone and backups restore)](../initial_setup/08_check_that_alerts_reach_your_phone_and_backups_restore.md#chapter-8-check-that-alerts-reach-your-phone-and-backups-restore),
   part 2 (each person on call signs in and adds a phone), with the new
   phone in Silent Mode. The test SOS wakes whoever is on call, so send the
   test SOS only to a person who is on call and expects it. MMHotline's
   dashboard shows who is on call now.
   **Check:** the phone must ring. Then the person claims the test SOS in
   MMHotline and resolves the test incident on the incident's MMHotline
   page, as part 2 of chapter 8 says.

## Log in to the desk without the old phone

The person needs a desk session for the next section. Try these ways in
this order, and use the first way that works:

| Way in | What the person does |
| --- | --- |
| A desk session that is still open | Use the session, such as a Rex session on the laptop. Go to [Make a new phone code](#make-a-new-phone-code) in that session. |
| A recovery code | From the enrolled laptop, run `ssh desk01` and type one recovery code at the code prompt. Each recovery code works once. |
| The saved phone-code secret | Add the saved secret to an authenticator app on the new phone. Then run `ssh desk01` and enter a code from the new phone. |

The recovery codes come from `set-up-the-phone-code`, which showed them when
the person set up the phone code. The person saved the recovery codes in the
password manager with the phone-code secret.

For the saved secret, the phone needs the correct time, but the
authenticator app needs no network. Never paste the secret into agent chat,
a repository, or a terminal transcript.

**Check:** `ssh desk01` ends at the person's prompt on the desk. A wrong
code counts toward the lockout in [If something is different](#if-something-is-different).

When none of the three ways works, follow
[Rebuild a systems desk](rebuild_a_systems_desk.md). The desk has no console
password, so a new desk with a new phone code is the way back. The
production servers keep running meanwhile.

## Make a new phone code

Replacing the phone-code secret is the default.
Reason: the old secret still makes valid codes on the old phone, so
restoring the saved secret on the new phone leaves the old phone able to
log in with the laptop's key.

The person works in the desk session from
[Log in to the desk without the old phone](#log-in-to-the-desk-without-the-old-phone),
as the person.

1. **Move the old phone-code file aside and start the setup:**

   ```sh
   mv ~/.google_authenticator ~/.google_authenticator.lost
   /usr/local/bin/set-up-the-phone-code
   ```

   Between the `mv` and the confirmed code in step 4, the desk admits the
   laptop's key without a code. Keep that time short.
   **Check:** `set-up-the-phone-code` shows a QR code. MMWatchdog on the
   desk warns that the phone-code file is missing, which is expected. The
   warning closes once the new file exists. If `set-up-the-phone-code`
   says "Your phone code is already set up", the `mv` did not move the old
   file: run the `mv` again.
2. **Scan the new QR code with the new phone.**
   **Check:** the new phone's authenticator app shows a code for the desk.
3. **Save the new secret and the new recovery codes in the password
   manager,** and replace the old entries there.
   **Check:** none on the desk, because the password manager is outside
   the desk. The person looks at the saved entries before step 4, because
   step 4 clears the screen.
4. **Confirm one code:** type one code from the new phone at the prompt.
   **Check:** `set-up-the-phone-code` says "Your phone code is ready." If
   the command says "That code did not match. No phone-code file was kept.
   Run set-up-the-phone-code again.", run `/usr/local/bin/set-up-the-phone-code`
   again, without a new `mv`, then scan the new QR code (step 2) and save
   the new secret and recovery codes (step 3). The failed run kept no
   phone-code file, and each run makes a new secret.
   [If something is different](#if-something-is-different) says what
   stays the same until the code matches.
5. **Log in a second time.** Keep the first desk session open. In a second laptop
   terminal, run `ssh desk01` with a fresh code from the new phone.
   **Check:** the second login works. Each code works once, so after a
   failed login wait for the phone's next code.
6. **When the second login works, remove the old file:**

   ```sh
   rm -f ~/.google_authenticator.lost
   ```

   `-f`, because the file is read-only to you (mode 0400), and plain `rm`
   would stop to ask.
   **Check:** `ls ~/.google_authenticator.lost` says the file does not
   exist.
7. **If the authenticator app on the new phone still holds the old secret**
   from [Log in to the desk without the old phone](#log-in-to-the-desk-without-the-old-phone),
   delete the old secret's entry.
   **Check:** the authenticator app shows only the new desk entry.

## Record

1. **Record in `systems_desk_recovery` in the checklist,
   `monkeymaxxing_stack_checklist.yml`:** the date, that
   the test alert reached the new phone, that the new phone code logged in,
   and whether the old phone was removed from Pushover.
   **Check:** none, because the record is the last step.

## If something is different

- **If the new phone is of another kind,** such as Android after an
  iPhone, the new phone needs its own Pushover licence after the free
  trial.
- **If step 4's test alert never arrives on the new phone:** check that
  the new phone is signed in to the team's Pushover account, with the login
  from the password manager. Then, in MMHotline, remove the person's
  Pushover contact method and add it again, and send the test again.
  Reason: the contact method holds the Pushover user key, and a new
  contact method makes MMHotline send to the account as it is now.
- **If the person is not on call now,** skip the test SOS in step 5 of
  [Put the alerts on the new phone](#put-the-alerts-on-the-new-phone).
- **If the desk locks the laptop out:** 5 wrong codes within ten minutes
  lock the laptop out of the desk for 5 minutes, and a wrong recovery code
  counts as a wrong code. The numbers are `phone_code_lockout.wrong_codes_before_lockout`
  and `phone_code_lockout.lockout_minutes` in `mmx_project_settings.yml`,
  5 and 5 in the template. Wait until the lockout ends, then try again
  with a fresh code.
- **If `set-up-the-phone-code` fails after the `mv`:** the old file stays
  as `~/.google_authenticator.lost`, and no new phone-code file exists. So
  the desk still admits the laptop's key without a code, and MMWatchdog's
  warning that the phone-code file is missing stays open. Keep the desk
  session open and run the command again, as step 4 of
  [Make a new phone code](#make-a-new-phone-code) says. A desk review in
  that time stops with "The phone code is missing."
- **If no way into the desk works,** follow
  [Rebuild a systems desk](rebuild_a_systems_desk.md).

## How the alerts reach the new phone

Nothing changes in the systems repository or the vault. Pushover sends to
the person's account, by the person's Pushover user key, and from the
account to each phone signed in to the account. MMHotline's contact method
holds the person's user key, and the Pushover group holds the account, so
the new phone receives the alerts once the new phone is signed in.
