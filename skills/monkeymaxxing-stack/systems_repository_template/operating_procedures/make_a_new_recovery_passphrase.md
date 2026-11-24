# Make a new recovery passphrase

**When to use this page:** nobody can find the recovery passphrase, while
the systems desk still works.

**What this page does:** the person's desk makes a new recovery bundle,
`recovery_bundle.age`, with a new recovery passphrase, and puts it in
place of the old bundle in the systems repository and in the locked backup
bucket. The new bundle holds every item the old one held, read from where
each lives on the desk. Two items the desk cannot read back come another
way: the person types the servers' current shared root console password
from the password manager, and the command makes new emergency codes for
the phone code. The console password and the servers stay as they are.
The phone keeps working: nobody scans a new QR code.

**Who acts:**

- **The person** runs one command in their own terminal on the desk,
  types the console password from the team's password manager, and saves
  the new recovery passphrase there. The passphrase shows once, on the
  person's screen only.
- **The coding agent,** on the laptop, gives the command and checks the
  result.

**Terms:** this page uses the Stack's terms, such as systems desk,
recovery bundle, recovery passphrase, phone code and emergency code.
[Technical terms](../talking_with_the_team.md#technical-terms) explains
each term.

**Which desk runs it:** the desk the bundle covers, whose SSH and
WireGuard keys the bundle holds, so a rebuild keeps giving that desk
back. "Which desk this page rebuilds" in
[Rebuild a systems desk](rebuild_a_systems_desk.md) says how to find its
name; the examples below call it `desk01`. A new bundle covers the desk
that makes it, and its passphrase screen names that desk.

**When the desk is lost too,** this page cannot help: a new bundle needs
the desk's keys. Without the recovery passphrase, a lost desk cannot be
rebuilt from the bundle.

**When nobody has the current console password either,** the password
manager lacks the item `Shared root console password` or holds an old
one: replace the password first, as
[The shared root console password](rotate_a_secret.md#the-shared-root-console-password)
says. That works without the old password, while `util01` reaches the
servers over SSH. Then follow this page.

## Tell the person before you start

> Your recovery bundle needs a new passphrase, because nobody can open the old one.
> You run one command on your systems desk. You type your servers' console password from your password manager, and it shows you a new recovery passphrase.
> You save the passphrase in your password manager, in place of the old one, and type it back.
> Your console password and your phone code keep working. Your servers keep running.

## Make the new bundle

1. **The person of the desk the bundle covers runs the command,** with
   that desk's name in place of `desk01`. Tell the person:

   > Please type this in your terminal, with a code from your phone:
   >
   > `ssh -t desk01 set-up-outside-services make-a-new-recovery-bundle`
   >
   > It asks two things, one at a time:
   >   1. Your servers' console password. Type it from the item  Shared root console password  in your password manager.
   >   2. Your new recovery passphrase, six words, shown once, exactly as it shows: small letters, one space between words. Save it in your password manager as your company's recovery passphrase, in place of the old one, then type it back.
   > Then it saves the new recovery bundle by itself. Tell me "done" when it says  Go back to your coding agent.

   Ask for "done" here: `wait-for-the-setup` ends at once on a desk whose
   lock is done, so no wait reads this command's end.

   The command refuses a desk that is not locked, and names the step it
   needs. It checks every item first. It checks the typed console password
   against its hash in the vault; after two wrong ones it stops and
   changes nothing, and points to the rotation above. Then it shows the
   passphrase screen, builds the new bundle, and copies it into the locked
   backup bucket with the database backups' write key from the vault. Only
   then does it give the phone code new emergency codes, and commit and
   push the bundle. It never changes the vault. One run at a time: a
   second terminal is refused.
   **Check:** on the desk,
   `jq '{steps, stopped_with, desk: .for_the_coding_agent.recovery_bundle_systems_desk_name}' /var/lib/monkeymaxxing-stack/setup_results.json`
   shows the step `new_recovery_bundle` as `done`, no `stopped_with`, and
   the desk's name.
   With a stop, say in one plain sentence what `stopped_with` says, fix
   the cause, and ask the person to run the command again:
   - **A stop before the person typed the passphrase back** changed
     nothing on the desk. The rerun makes a new passphrase, so the person
     saves the newest one.
   - **A stop after it** says the rerun finishes that bundle. The rerun
     shows no screen and makes no new passphrase: it copies the bundle
     into the backup bucket unless the bucket holds it already, gives the
     phone code its emergency codes unless it has them already, and
     commits and pushes it.
2. **The person checks that the new passphrase opens the new bundle,**
   in their own laptop terminal, after you pull `main` into the laptop's
   clone, and after loading `with_recovery_passphrase` as
   [Read an item from the recovery bundle](rebuild_a_systems_desk.md#read-an-item-from-the-recovery-bundle)
   says:

   ```sh
   # On the laptop, in your own terminal. It asks for the recovery passphrase.
   cd ~/code/example_systems && with_recovery_passphrase ~/.local/bin/mmx secrets list-keys --vault recovery_bundle.age
   ```

   **Check:** the person says it listed key names, among them
   `phone_code_emergency_codes` and `shared_root_console_password`, and no
   error.
3. **Push the backup** at the Git host, as
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
- **Everything else is unchanged:** the vault, its passphrase, the
  servers' console password, the production key, the WireGuard keys, and
  every outside key.
