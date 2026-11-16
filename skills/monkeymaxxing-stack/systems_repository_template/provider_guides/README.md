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

## Credentials on the systems desk

The person owns the provider token. The coding agent runs as `coding-agent`
and uses the local API proxy, so the coding agent never holds the
token. Each guide gives its provider's values: the API address for
`systems_desk_provider_api_url` in `mmx_project_settings.yml`, the
`set-up-outside-services personal-token server-provider` command, a server
listing's path, and the provider CLI's credential store. At OVHcloud, AWS EC2
and Google Compute Engine the API proxy signs the requests with the credential instead, as
each guide's "Credentials on the systems desk" says.

- `set-up-outside-services personal-token server-provider` writes
  `/etc/systems-desk/provider-api-token.conf`, root:root, mode `0600`, and
  the person's token file. The token file lives outside Git. Never give the
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
- During first-desk bootstrap, record and clear every laptop credential
  file after the desk works. Use environment-only authentication where
  supported, so no saved personal CLI context remains. The person may keep
  personal CLI credentials only in the person's protected desk account.
  `util01` keeps separate account-owned restore credentials.
