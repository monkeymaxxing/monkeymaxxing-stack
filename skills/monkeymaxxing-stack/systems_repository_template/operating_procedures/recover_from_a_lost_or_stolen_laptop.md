# Recover from a lost or stolen laptop

**When to use this page:** a laptop is lost, stolen, or suspected of
leaking the desk-login keys. The same steps fit a compromised laptop, where
a program that you do not trust ran as the person and may have copied the
files in the home directory.

**What this page does:** a replacement systems desk, built from a trusted
new laptop, takes the old desk's place, and the old desk is deleted, so the
stolen laptop's keys reach no desk. The credentials that the laptop held
are replaced too.

**Who acts:** the person works on the new laptop, at websites, and in the
password manager. The coding agent, on the new laptop, does the work that
[Rebuild a systems desk](rebuild_a_systems_desk.md) gives it.

**Terms:** this page uses the Stack's terms, such as systems desk, phone
code, and personal provider token. [Technical terms](../talking_with_the_team.md#technical-terms)
explains each term.

## Before you start

- **Work from a clean laptop:** a new laptop, or this laptop after the
  laptop's operating system is reinstalled. Reason: on a compromised
  laptop, the untrusted program may still be running.
- **Build a replacement desk from a trusted new laptop.** Do not enroll the
  new laptop on the old desk and keep the old desk.
  Reason: deleting the old desk revokes the stolen laptop's entire door
  without needing access through the stolen laptop.
  [Why a replacement desk, not a wait](#why-a-replacement-desk-not-a-wait)
  explains why waiting is not enough.
- **The person can open the team's password manager.** It holds the
  recovery passphrase, which opens the recovery bundle: the old desk's
  production SSH key, desk WireGuard key and vault passphrase.
- **The stolen laptop's own desk login may still be open.** Your shared
  login, `desk01-agent`, stays open for up to one unused hour, and ten
  hours at most. Build the replacement and delete the old desk without
  waiting.

## Steps

1. **Create fresh desk-only login keys on the new laptop:** SSH and
   WireGuard, as
   [chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md)
   describes. Never restore the stolen laptop's desk-login private keys.
   **Check:** chapter 3's commands print the new public keys. The new keys
   go into the replacement desk's `allowed_laptops` in step 2.
2. **Make a new personal provider token** at the provider's website, with
   the same permissions as in chapter 3. Do this before the rebuild, so
   the rebuild uses the new token, not the old one.
   Reason: the laptop held the old token during setup, in
   `~/example-setup/provider-key` and, at some providers, the provider's
   command-line tool, and a backup of the laptop can still hold the old
   token. The old token creates and deletes servers
   without a desk or a phone code.
   **Check:** the provider's website shows the new token.
3. **Build the replacement desk:** for the desk the recovery bundle
   covers, whose keys are in the bundle, follow
   [Rebuild a systems desk](rebuild_a_systems_desk.md). "Which desk this
   page rebuilds" there says how to find that desk's name. For any other
   desk, add a new desk, as "Joining" in
   [Add or remove a team member](add_or_remove_a_team_member.md#joining)
   says, and remove the old one, as "Leaving" steps 2 and 3 say. Use the next desk
   name, such as `desk02` when the team's only desk was `desk01`. The next
   desk name takes the next number above every desk number the team has
   used, never a lost desk's name, by the same rule as a new server in a pool
   ([Server names and private addresses](../AGENTS.md#server-names-and-private-addresses))
   and as step 6 of Rebuild a systems desk explains. In Rebuild a systems
   desk:
   - the person types the new personal provider token from step 2 into the
     laptop key command (step 3), and step 14 moves it to the desk;
   - the old desk's production SSH key, desk WireGuard key and vault
     passphrase come from the recovery bundle;
   - the replacement desk's `allowed_laptops` contains only the new
     laptop's keys;
   - power off the old desk before activating the restored WireGuard
     identity on the replacement desk;
   - step 22 deletes the old desk by the old
     desk's verified provider ID, and a fresh provider listing confirms
     that the old desk is gone. The stolen laptop's keys reach no existing
     desk after deletion.

   **Check:** the checks of Rebuild a systems desk.
4. **Verify the replacement desk:** a fresh phone-code login and
   production access from the replacement desk.
   **Check:** both work. Rebuild a systems desk lists the checks.
5. **Revoke and replace the stolen laptop's other credentials:** the app
   Git credential, registry publishing token, coding-agent login, and
   staging test token, where present.
   **Check:** each service's credentials page lists only the new
   credential. The pages are the Git host's list of keys and tokens (at
   GitHub, `https://github.com/settings/keys` and
   `https://github.com/settings/tokens`), the registry's tokens page, the
   coding agent provider's sessions or keys page, and the staging test
   token where the app keeps it.
6. **Delete the old personal provider token** at the provider's website.
   **Check:** the provider's token list shows only the new token.
7. **Review app releases and systems Git history** for unexpected changes.
   Run `git log` on the systems repository's `main`, and on the app's
   repository, from the earliest date the compromise could have started.
   Read each commit that the team's coding agents and `util01` did not
   make. For a commit nobody knows, `util01`'s journal names the key that
   pushed it, as
   [An unknown commit in the systems repository](respond_to_a_break_in.md#an-unknown-commit-in-the-systems-repository)
   says. Also compare the registry's list of image
   tags, on the registry's package page that the person opens signed in,
   or with `gh` when it is signed in, with `deployed_image_tags` in
   `inventories/servers.yml`.
   **Check:** every commit and image tag is known. Each unknown commit or
   tag goes to the person before anything else, as
   [Respond to a break-in](respond_to_a_break_in.md) says.
8. **Complete chapter 3 (make your server account and your systems desk)'s
   cleanup on the new laptop.**
   **Check:** the checks in chapter 3's cleanup.
9. **Record the tested result in `systems_desk_recovery`,** in the
   checklist, `monkeymaxxing_stack_checklist.yml`.
   **Check:** none, because the record is the last step.

## If something is different

- **If evidence shows use through an open desk session,** rotate
  production secrets ([Rotate a secret](rotate_a_secret.md)).
- **If the laptop was compromised rather than lost,** do every step from a
  clean laptop, as [Before you start](#before-you-start) says.
- **If the program could have read the person's password manager** (a
  browser extension or desktop app that was unlocked on that laptop),
  the person changes the password manager's master password from the
  clean laptop.

## Why a replacement desk, not a wait

The phone code protects the old desk until the old desk is deleted. But a
thief can trigger the lockout again each time the lockout ends
(`phone_code_lockout.lockout_minutes` in `mmx_project_settings.yml`,
5 minutes in the template). The lockout also stops the person's own laptop
for that time. Waiting for a lockout is not recovery from stolen keys.

## Which keys change

Production SSH public keys stay unchanged when the desk's production
identity was restored. A lost laptop does not require rotating every
production key merely because the laptop's desk-login key was stolen.
The personal provider token is the exception, because the laptop held the
personal provider token during setup (step 2).
