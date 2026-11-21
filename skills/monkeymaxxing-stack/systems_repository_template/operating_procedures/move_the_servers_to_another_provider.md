# Move the servers to another provider

**When:** the team chooses a cheaper or closer provider, or chooses to leave the current provider.

**What this page does:** every server of the system, the systems desks
included, is replaced by a server at the new provider, one stage at a time,
and the old provider keeps no server and no API token of the system.

**Who acts:** you, the coding agent, write the provider scripts, change the
settings, and do the replacements. Only a person:

- creates the API tokens at the new provider, and deletes the old ones on
  the old provider's website (steps 1 and 6);
- runs the desk review, `set-up-outside-services`, and the vault commands
  in the person's own terminal (step 1);
- rebuilds the person's own desk with you, and approves its first desk
  review (step 5).

## Before you start

- **Use [Add a server](add_a_server.md) whenever a
  replacement below calls for adding a server.** The linked instructions cover
  names, addresses, creation, inventory, SSH trust, MMX setup, WireGuard,
  reboots, and verification.
- **Move the servers in stages. Start a new app server before changing the database servers.**
  Adding or removing a database server changes the server list in each app's
  `DATABASE_URL`. The list comes from `database_servers` in
  `inventories/servers.yml`. MMX then restarts web containers, one app server
  at a time. Adding the new app server first keeps requests working while
  the existing app server's web containers restart.

## Steps

1. **Prepare access if the new provider is another company.**
   For a move between locations at the current provider, continue with step 2.
   Read the new provider's [Stack guide](../provider_guides/) (Hetzner Cloud and
   OVHcloud), or its guide in the `providers/` folder of
   [monkeymaxxing-recipes](https://github.com/monkeymaxxing/monkeymaxxing-recipes/tree/main/providers) (DigitalOcean, Vultr,
   Scaleway, AWS EC2, Google Compute Engine; fetch it as
   [Using a recipe](../AGENTS.md#using-a-recipe) says), or the new
   provider's documentation when no guide exists. Write the create,
   destroy, and list scripts as the guide says: with the provider's own
   command-line tool, or with the guide's request function.
   Follow the [provider contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).
   Create two API tokens at the new provider, the person's and `util01`'s, as the guide's
   "Credentials on the systems desk" says. Set `systems_desk_provider_api_url` and
   `systems_desk_provider_api_authentication` in `mmx_project_settings.yml` to the guide's values,
   push, and have each person run a desk review, which points `http://127.0.0.1:8081/` at the new
   provider. Tell the person before the review that when `systems_desk_provider_api_authentication`
   changes, the review also deletes the desk's copy of the old provider's token:
   `/etc/systems-desk/provider-api-signing-credential.json` on a move to `token_in_a_header`, and
   `/etc/systems-desk/provider-api-token.conf` on a move to a provider the API proxy serves
   (OVHcloud, AWS EC2, Google Compute Engine); between two such providers, the `personal-token` command
   below replaces the credential file.
   After a review that moved the desk to `token_in_a_header`, nothing answers at
   `http://127.0.0.1:8081/` or at Cloudflare's `http://127.0.0.1:8082/` until the person gives the
   new provider's token in the next sentence's command.
   Each person then types the guide's `set-up-outside-services personal-token server-provider`
   command on the laptop, as `ssh -t desk01 set-up-outside-services personal-token server-provider ...`,
   with their own desk name and a phone code. It replaces the old provider's token in the desk's
   proxy, the provider token's only place on the desk. The person saves `util01`'s own token with
   `ssh -t desk01 set-up-outside-services secrets --replace util01_provider_api_token`.
   After these steps neither the vault nor a file that the Stack writes on a desk holds the old
   provider's tokens; the tokens still work at the old provider until step 6 deletes them there.
   The new scripts reach only the new provider, so during the
   replacements below, destroy old servers through the old provider's
   console, when the linked replacement procedure directs.
   **Check:** the new scripts list the servers at the new provider, and
   each person's `http://127.0.0.1:8081/` reaches the new provider.
2. **Register the utility server's SSH key at the new provider.**
   Use `util01`'s `mmhotline` key from its line in `root_ssh_public_keys`.
   Register `util01`'s `mmhotline` key under the name
   `util01, the mmhotline user` at the new provider.
   Supply the registration name through `--ssh-key-name`.
   Use the key registration the provider guide gives, a command or a
   request, and verify the registered public key.
   Each new server at the provider then starts with `util01`'s `mmhotline` key.
   **Check:** the registered public key matches `util01`'s `mmhotline`
   line in `root_ssh_public_keys`.
3. **Move the restore drill's settings.**
   Set `restore_drill_location` and `restore_drill_server_type` in
   `mmx_project_settings.yml` to the new provider's location and database
   server size.
   Use the Debian release from
   [The server image in chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md#the-server-image).
   Set `server_image` to the new provider's name for the chosen
   Debian release (`debian-13` at Hetzner for Debian 13).
   The weekly drill will then create `restore01` at the
   new provider, in the location named by `restore_drill_location`.
   **Check:** the next weekly restore drill creates `restore01` at the
   new provider and passes.
4. **Replace the servers in the order listed below.**
   Follow [Replacing a server](replace_a_server.md#replacing-a-server), including its checks, for each replacement:
   - Add a new app server in a commit of its own. Let the new app server
     serve before changing the database servers (step 8 of [Add a
     server](add_a_server.md)).
   - Replace a database server. When the old server is the primary,
     [Replacing a server](replace_a_server.md#replacing-a-server) makes the
     new server the primary before removing the old server. When the old
     server was a replica, run `switch_database_primary` with
     `--var server_name=` set to the new database server, so the primary
     moves to the new provider.
     Once the primary is at the new provider, replace the remaining database servers one at a time.
   - Replace the app servers that existed before the new app server.
   - Replace any jobs and load-balancer servers, one at a time.
     Use the instructions for jobs servers and load-balancer servers in
     [Replacing a server](replace_a_server.md#replacing-a-server).
   - Replace `staging01`.
   - Replace `util01` last.

   **Check:** the checks of each replacement in
   [Replacing a server](replace_a_server.md#replacing-a-server).
5. **Rebuild each systems desk at the new provider.** The desks are servers of
   the system too, and the steps above leave them at the old provider.
   Do this after `util01` is replaced, so that each new desk can reach the new
   `util01` and join the MMWatchdog fleet. Set `systems_desk_provider_api_url`
   in `mmx_project_settings.yml` to the new provider's address, as the new
   provider's guide gives it. Then move the desks one at a time, at the new
   provider and in a location different from production:
   - **The first desk,** whose keys are in the recovery bundle: rebuild it with
     [Rebuild a systems desk](rebuild_a_systems_desk.md). It keeps its old
     private address, its WireGuard key and its person, so the servers still
     recognize it. Only its public address changes, and that change reaches
     the servers' peers in the `WireGuard peers` item below.
   - **Each teammate's desk:** add a new desk for that teammate, as "Joining"
     in [Add or remove a team member](add_or_remove_a_team_member.md#joining)
     says, then remove the old desk, as "Leaving" steps 2 and 3 say.
   - **The old first desk** is powered off before its rebuild starts, because
     two desks must not run one WireGuard identity at once. It stays powered
     off, and is not destroyed, until the rebuilt desk passes that
     procedure's verification. Then the procedure's step 22 destroys it by
     its verified provider ID. Until then the person has no
     desk, so rebuild the desk of the person who drives the move last, and
     keep that desk until every other desk works.
   - **The WireGuard peers.** The rebuilt desk starts at a new public
     address. Its first `every_server` run, through that desk (step 19 of
     that procedure), applies the new address to every server's peers; until that run
     finishes, the servers still hold the old address.
     Record the new address as the desk's `public_ipv4_address` in
     `inventories/servers.yml` first.
   - **The lock-out button's reviewed record.** Each new desk's bootstrap
     records its first desk review. The old desks, while they last, ask the person to approve the changed
     inventory the next time the button or a desk review runs; that is expected.
     Do not press the lock-out button to test it.

   **Check:** the checks of [Rebuild a systems desk](rebuild_a_systems_desk.md)
   pass for the first desk, and the checks of "Joining" for each teammate's
   desk.
6. **Delete the old provider's API tokens.** Once the old provider holds no server of the system,
   the old desks included, the person deletes, on the old provider's website, every API token of the
   system there: each person's and `util01`'s, where the old provider's guide says: at OVHcloud the
   **API keys** page, at AWS the IAM users, at Google Cloud the service accounts. For a move between locations at the current provider, skip this step:
   the tokens stay in use.
   Reason: a token for an account the team has left still creates and deletes servers in that account,
   and nobody would look for it.
   **Check:** the old provider's token page lists no token of the system.
7. **Verify** with the `verification` of the checklist item
   `move_to_another_provider`, then mark the item done.
   The old provider must hold no server of the system, the old desks included, and no API token of the system.

## If something is different

- **A move between locations at the current provider:** skip step 1's
  access work and continue with step 2, and skip step 6: the tokens stay
  in use.
- **The old provider's console:** the new scripts reach only the new
  provider, so destroy old servers through the old provider's console, as
  step 1 says.
