# Make a new recovery passphrase

**When to use this page:** nobody can find the recovery passphrase, while
the systems desk still works. Also when the password manager lacks the
item `Shared root console password` and nobody can open the recovery
bundle to read it.

**What this page does:** the person's desk makes a new recovery bundle,
`recovery_bundle.age`, with a new recovery passphrase, and puts it in
place of the old bundle in the systems repository and in the locked backup
bucket. The new bundle holds every item the old one held, read from where
each lives on the desk. Two items the desk cannot read back get new
values: a new shared root console password for the servers, and new
emergency codes for the phone code. The phone keeps working: nobody scans
a new QR code.

**Who acts:**

- **The person** runs one command in their own terminal on the desk, and
  saves two new values in the team's password manager: the console
  password and the recovery passphrase. Both show once, on the person's
  screen only.
- **The coding agent,** on the laptop, checks for `restore01` first, then
  gives the servers the new console password and checks the result.

**Terms:** this page uses the Stack's terms, such as systems desk,
recovery bundle, recovery passphrase, phone code and emergency code.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

**When the desk is lost too,** this page cannot help: a new bundle needs
the desk's keys. Without the recovery passphrase, a lost desk cannot be
rebuilt from the bundle.

## Tell the person before you start

> Your recovery bundle needs a new passphrase, because nobody can open the old one.
> You run one command on your systems desk. It shows a new password for your servers' consoles and a new recovery passphrase, one at a time.
> You save each one in your password manager, in place of the old one, and type it back.
> Your phone code keeps working. Your servers keep running.

## Make the new bundle

1. **Check for a running `restore01`,** as step 1 of
   [The shared root console password](rotate_a_secret.md#the-shared-root-console-password)
   says.
   Reason: the command gives the servers a new console password, and
   `every_server` skips a restore server.
   **Check:** the provider lists no `restore01`.
2. **The person runs the command.** Tell the person:

   > Please type this in your terminal, with a code from your phone:
   >
   > `ssh -t desk01 set-up-outside-services make-a-new-recovery-bundle`
   >
   > It shows two things, one at a time:
   >   1. A new password for your servers' consoles. Save it in your password manager as  Shared root console password,  in place of the old one, then type it back.
   >   2. Your new recovery passphrase, six words. Save it in your password manager as your company's recovery passphrase, in place of the old one, then type it back.
   > Then it saves the new recovery bundle by itself. Tell me "done" when it says  Go back to your coding agent.

   Ask for "done" here: `wait-for-the-setup` ends at once on a desk whose
   lock is done, so no wait reads this command's end.

   The command refuses a desk whose lock is not done, and names the step
   it needs. It then reads each item from the desk, makes new emergency
   codes for the phone code, copies the new bundle into the locked backup
   bucket with the database backups' write key from the vault, and commits
   and pushes the bundle and the vault.
   **Check:** on the desk,
   `jq '{steps, stopped_with}' /var/lib/monkeymaxxing-stack/setup_results.json`
   shows the step `new_recovery_bundle` as `done` and no `stopped_with`.
   With a stop, say in one plain sentence what `stopped_with` says, fix
   the cause, and ask the person to run the command again. Each run makes
   a new passphrase, so the person saves the newest one.
3. **The person checks that the new passphrase opens the new bundle,**
   in their own laptop terminal, after you pull `main` into the laptop's
   clone:

   ```sh
   # On the laptop, in your own terminal. It asks for the recovery passphrase.
   cd ~/code/example_systems && ~/.local/bin/mmx secrets list-keys --vault recovery_bundle.age
   ```

   **Check:** the person says it listed key names, among them
   `phone_code_emergency_codes` and `shared_root_console_password`, and no
   error.
4. **Give the servers the new console password:** run `every_server` on
   `util01`, as steps 3 and 4 of
   [The shared root console password](rotate_a_secret.md#the-shared-root-console-password)
   say, and have the person log in at one server's provider console with
   the new password.
   **Check:** the run passes, and the console login works.
5. **Push the backup** at the Git host, as
   ["The main copy and the backup at the Git host"](../AGENTS.md#the-main-copy-and-the-backup-at-the-git-host)
   says.
   **Check:** `git ls-remote backup main` shows the same commit as `main`
   in the clone.

## What changed and what stays

- **The old bundle** stays in the systems repository's history and in the
  locked backup bucket until its lock ends. Only the old passphrase opens
  it, so it is harmless.
- **The old emergency codes** no longer work. The new ones are only in the
  new bundle.
- **The old console password** stops working on each server at
  `every_server`'s next run there.
- **Everything else is unchanged:** the vault, its passphrase, the
  production key, the WireGuard keys, and every outside key.
