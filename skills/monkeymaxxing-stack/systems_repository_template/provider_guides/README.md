# Provider guides

The coding agent reads the selected provider's guide before writing the
team's scripts. The guides explain provider choices and link to the
provider's own command-line documentation. Each guide covers only what
differs at that provider; the shared steps stay in the
[provider script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts)
and the [initial setup](../initial_setup/).

Each guide's "The provider's web console" section gives the address where the person sees the servers.

Setup offers these seven. The coding agent reaches each at `http://127.0.0.1:8081/` on
the desk, through the API proxy, which adds the person's token or, for OVHcloud and
AWS EC2, whose APIs need each request signed, and Google Compute Engine, whose API takes tokens
made from a key, signs the request:

- [Hetzner Cloud](hetzner_cloud.md)
- [DigitalOcean](digitalocean.md)
- [OVHcloud Public Cloud](ovhcloud_public_cloud.md)
- [Vultr](vultr.md)
- [Scaleway](scaleway.md)
- [AWS EC2](aws_ec2.md)
- [Google Compute Engine](google_compute_engine.md)

Not tested:

- **Azure Linux Virtual Machines:** account signup failed (2026-11), before
  any server could be created.
- **Akamai/Linode:** the account was rejected at review with no reason given
  (2026-11), before any server could be created.

The Stack may still work on these providers with the provider script
contract and the provider's own documentation. Expect the same signup
problem, and check that an account can be created before planning around
the provider.

For another provider, use the provider's current documentation and follow
the [provider script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts).

## The laptop key command

Before the desk exists, the person types the provider key on the laptop,
once. The Stack ships no program for this step. You write a small Bash
script from the rule below, with the selected guide's values from its own
"The laptop key command" section. The script is
`~/example-setup/enter-the-hetzner-key`: `example` is the company's name in
lowercase with hyphens, and `hetzner` is the provider's short name. The
script must work with the Bash that the laptop has, Bash 3.2 on a Mac.

The script does six things, in order:

1. **A hidden prompt for each value,** with `read -rs`, named as the
   provider's page names the value, such as `Hetzner API token (hidden): `.
   It removes spaces, line breaks and quotes that came with a paste.
2. **A shape check of each value,** with the guide's shape, before any
   request. A wrong shape prints what the value must look like, such as
   "The token has 64 letters and digits. Copy it again.", and asks again.
3. **One read-only API call** with the values: the guide's listing
   request. A refusal prints the provider's own reason and asks again. The
   script sends each value only in the request's header or signature,
   never on a command line, so other programs cannot read it in the
   process list: `curl` reads the header from standard input with
   `-H @-`.
4. **The key file, `~/example-setup/provider-key`, mode `0600`,** written
   with `umask 077` so the file is private from its first byte. The file
   holds one line in the form of `SERVER_PROVIDER_API_TOKEN`, as the
   guide's "Key file line" names it: the token itself at most providers;
   at OVHcloud the three values joined with colons,
   `APPLICATION_KEY:APPLICATION_SECRET:CONSUMER_KEY`; at AWS the two
   joined with a colon, `ACCESS_KEY_ID:SECRET_ACCESS_KEY`; at Google Cloud
   the key file's text in base64 on one line, as `openssl base64 -A`
   writes it. The desk's API proxy reads exactly this form.
5. **One line to the person:** `Hetzner accepted the key.`, with the
   provider's name. The script never prints a value.
6. **It stays open and starts the desk's setup by itself.** After the
   line, it prints `Leave this window open.  Your coding agent orders your
   systems desk next.` and waits for the file
   `~/example-setup/desk-ordered`, which your `create-desk01` script makes
   only after the provider accepted the desk's order (chapter 3, step 2 of
   "Create desk01 through WireGuard"). Then it prints `Your systems desk
   is ordered.  Building it takes about 10 minutes.` and waits for the
   file `~/example-setup/desk-ready`, which you make when the desk is
   ready (chapter 4, step 2). It checks every 5 seconds. It gives up after
   90 minutes without `desk-ordered`, with `Your systems desk was not
   ordered.  Ask your coding agent.`, and after 90 minutes without
   `desk-ready`, with `Your systems desk is not ready.  Ask your coding
   agent.` Reason for 90: the desk takes about 10 minutes, so a longer
   wait means your own work failed, and a window must not wait for ever.
   Reason for the two lines: a build time printed before the order
   succeeded is false when the order fails, such as when the size is sold
   out. When `desk-ready` is there, it runs `exec ssh desk01-setup`, so
   the person types no second command and the setup runs in this window.

Right after the bootstrap in
[chapter 3](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#create-desk01-through-wireguard),
you move the key file to the desk's API proxy, over the bootstrap's root
SSH, on standard input, and delete the laptop file. The bootstrap cannot
do this itself: MMX keeps every laptop file a run reads in the run's
history, and the key must not stay on the laptop. The person does
nothing for it. The command is in `playbooks/systems_desk.yml`'s header;
chapter 3, step 4 of "Create desk01 through WireGuard", gives it with the
guide's values: the guide's server listing path, Scaleway's
`--token-header X-Auth-Token`, and, at a provider whose requests the proxy
signs, `--provider-api-authentication` and `--provider-api-address` from
`systems_desk_provider_api_authentication` and
`systems_desk_provider_api_url`. In the first part of the setup `util01` uses the
same key. A narrower key for `util01`, as each guide's `util01` section
describes, is a later choice of the team.

## Credentials on the systems desk

The person owns the provider token. The coding agent runs as `coding-agent`
and uses the local API proxy, so the coding agent never holds the
token. Each guide gives its provider's values: the API address for
`systems_desk_provider_api_url` in `mmx_project_settings.yml`, the
`set-up-outside-services personal-token server-provider` command, a server
listing's path, and the provider CLI's credential store. At OVHcloud, AWS EC2
and Google Compute Engine the API proxy signs the requests with the credential instead, as
each guide's "Credentials on the systems desk" says.

- The bootstrap, and later `set-up-outside-services personal-token server-provider`
  when the person replaces the key, write
  `/etc/systems-desk/provider-api-token.conf`, root:root, mode `0600`, which
  only the API proxy reads. The token lives outside Git. Never give the
  real token to the coding agent.
- The proxy listens on `http://127.0.0.1:8081/` and replaces the matching
  authentication header. Provider requests use the path relative to the
  configured upstream base URL, such as `http://127.0.0.1:8081/servers` for
  Hetzner's server listing.
- Verify the selected location and API path before creating resources.
- The person checks that the installed provider CLI can select the local
  API endpoint before using the CLI as `coding-agent`. When endpoint
  selection is unavailable, the coding agent uses curl and jq through the
  local API proxy. Do not fall back to exposing a real token to the
  coding agent.
- A guide's lifecycle commands describe provider operations for the person
  or account-owned restore jobs. Run coding-agent operations through the
  proxy, with the same ownership, first-boot, pagination, and deletion
  checks.
- During the first desk's bootstrap, the laptop holds only the key file
  of "The laptop key command", which you delete when you move the key to
  the desk. Clear any
  provider tool's saved login on the laptop after the desk works. Use environment-only authentication where
  supported, so no saved personal CLI context remains. The person may keep
  personal CLI credentials only in the person's protected desk account.
  `util01` keeps separate account-owned restore credentials.
