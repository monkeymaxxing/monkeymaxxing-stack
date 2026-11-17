# Recover from a lost phone

**When to use this page:** the phone that gets the alerts and shows the
desk's phone code is lost, stolen, or stops working.

**What this page does:** the alerts reach the person's new phone again, and
a new phone code replaces the old phone's codes for logging in to the desk.

**Who acts:** the person does the steps on the new phone, at websites, and
in their own terminals on the laptop and the desk. The coding agent, on the
laptop, says what comes next and what to look for. The coding agent never
reads the phone code's secret or an emergency code.

**Terms:** this page uses the Stack's terms, such as phone code, emergency
code, recovery bundle, systems desk, MMHotline, and SOS.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term. Pushover is the push app that puts the alerts on the phone.

## Tell the person before you start

> First we put the alerts on your new phone and send a test alert, so an urgent alert reaches you again.
> Then you log in to your desk with an emergency code and make a new phone code.
> The new phone code stops the old phone's codes from working, even if someone else has the old phone.

## Before you start

- **The new phone is in the person's hands.** The steps install Pushover
  and an authenticator app on it.
- **The person can open the team's password manager.** It holds the
  Pushover login and the recovery passphrase. The recovery passphrase
  opens the recovery bundle, which holds the desk's emergency codes.
- **Your own desk login is closed too.** You reach the desk through
  `desk01-agent`, which needs a phone code. Until the new phone code works,
  you can do nothing on the desk.

## Put the alerts on the new phone

1. **Install Pushover on the new phone and sign in** with the person's
   Pushover account, whose login is in the team's password manager.
   **Check:** step 4's test alert checks this step, because only a phone
   signed in to the person's account receives the test.
2. **Allow alerts to sound in Silent Mode** (Critical Alerts on iOS), as
   [chapter 8 (check that alerts reach your phone and backups restore)](../initial_setup/08_check_that_alerts_reach_your_phone_and_backups_restore.md#part-2-each-person-on-call-signs-in-and-adds-a-phone)
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

1. **Find an emergency code.** Each code works once, in place of a phone
   code.
   - For the first desk, `desk01`: the codes are in the recovery bundle, as
     `phone_code_emergency_codes`. The person prints them in their own
     terminal with `mmx secrets show --vault recovery_bundle.age phone_code_emergency_codes`,
     in the systems repository, as
     [Read an item from the recovery bundle](rebuild_a_systems_desk.md#read-an-item-from-the-recovery-bundle)
     says.
   - For a desk added later, such as `desk02`: the codes are in the team's
     password manager, as "desk02 phone code emergency codes".

   **Check:** the person has one unused code.
2. **Log in with it.** Tell the person:

   > Please type `ssh desk01` in your terminal. At the code prompt, type one emergency code.

   **Check:** `ssh desk01` ends at the person's prompt on the desk. A wrong
   code counts toward the lockout in
   [If something is different](#if-something-is-different).

When no emergency code works, follow
[Rebuild a systems desk](rebuild_a_systems_desk.md). The servers keep
running meanwhile.

## Make a new phone code

The person works in the desk login from
[Log in to the desk without the old phone](#log-in-to-the-desk-without-the-old-phone).
Keep that login open until step 4.

1. **Move the old phone code aside and make a new one:**

   ```sh
   # On the desk, as the person:
   sudo mv /etc/systems-desk/phone-code /etc/systems-desk/phone-code.lost
   sudo set-up-the-phone-code --emergency-codes-to ~/phone-code-emergency-codes
   ```

   THE DESK OPENS WITH THE LAPTOP KEY ALONE UNTIL THE NEW CODE MATCHES. DO BOTH LINES AT ONCE.

   **Check:** `set-up-the-phone-code` shows a QR code. If it says the phone
   code is already set up, the `mv` did not work: run the `mv` again.
2. **Scan the QR code with the new phone, and type the 6 digits it
   shows.**
   **Check:** the command says "Your phone code is ready." After "That code
   did not match", type the phone's next code. The command asks until one
   matches.
3. **Save the new emergency codes.**
   - For the first desk, in the recovery bundle: the person follows
     [Change an item in the recovery bundle](rebuild_a_systems_desk.md#change-an-item-in-the-recovery-bundle)
     with `phone_code_emergency_codes` and the file
     `~/phone-code-emergency-codes`, and you publish the bundle once your
     login works again (step 5).
   - For a desk added later: the person replaces the password manager's
     entry "desk02 phone code emergency codes" with the file's codes, then
     deletes the file: `rm ~/phone-code-emergency-codes`.

   **Check:** `ls ~/phone-code-emergency-codes` says the file does not
   exist.
4. **Log in a second time.** Keep the first login open. In a second laptop
   terminal, the person types `ssh desk01` and a code from the new phone.
   **Check:** the second login works. Each code works once, so after a
   failed login wait for the phone's next code.
5. **Open your own login again.** Ask the person for one code in the chat,
   as "Your login on the desk" in
   [`AGENTS.md`](../AGENTS.md#your-login-on-the-desk) says.

   WAIT FOR A NEW CODE. THE CODE FROM STEP 4 WORKS ONLY ONCE.

   For the first desk, commit `recovery_bundle.age` in the desk's checkout
   and publish it, as [Making a change](../AGENTS.md#making-a-change) says.
   **Check:** `~/code/example_systems/ssh/open-the-desk-login --check` says the login is open, and the
   publishing step names the bundle's commit.
6. **Remove the old phone code:**

   ```sh
   # On the desk, as the person:
   sudo rm /etc/systems-desk/phone-code.lost
   ```

   **Check:** `sudo ls /etc/systems-desk/phone-code.lost` says the file
   does not exist.
7. **If the authenticator app on the new phone holds an old desk entry,**
   delete it.
   **Check:** the app shows only the new desk entry.

## Record

1. **Record in `systems_desk_recovery` in the checklist,
   `monkeymaxxing_stack_checklist.yml`:** the date, that
   the test alert reached the new phone, that the new phone code logged in,
   and whether the old phone was removed from Pushover. Publish it, as
   [Making a change](../AGENTS.md#making-a-change) says.
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
  lock the laptop out of the desk for 5 minutes, and a wrong emergency code
  counts as a wrong code. The numbers are `phone_code_lockout.wrong_codes_before_lockout`
  and `phone_code_lockout.lockout_minutes` in `mmx_project_settings.yml`,
  5 and 5 in the template. Wait until the lockout ends, then try again.
- **If `set-up-the-phone-code` fails after the `mv`:** no phone-code file
  exists, so the desk opens with the laptop key alone, and a desk review
  stops with "This desk is locked, but its phone code … is missing". Run
  `sudo set-up-the-phone-code --emergency-codes-to ~/phone-code-emergency-codes`
  again at once, in the open login.
- **If no way into the desk works,** follow
  [Rebuild a systems desk](rebuild_a_systems_desk.md).

## How the alerts reach the new phone

Nothing changes in the vault. Pushover sends to
the person's account, by the person's Pushover user key, and from the
account to each phone signed in to the account. MMHotline's contact method
holds the person's user key, and the Pushover group holds the account, so
the new phone receives the alerts once the new phone is signed in.
