# Hetzner Cloud

## The provider's web console

The person sees the servers in the Hetzner Console, <https://console.hetzner.com/>:
open the system's project, then **Servers** in the left menu.

## Credentials on the systems desk

The person owns the provider token; the coding agent reaches the provider
through the desk's API proxy, as
[Credentials on the systems desk](README.md#credentials-on-the-systems-desk)
says.

Set `systems_desk_provider_api_url: https://api.hetzner.cloud/v1/` in `mmx_project_settings.yml`, including the trailing slash.
The person types the token on the laptop with the laptop key command below, and you move it to
the desk right after the bootstrap. To replace the token later, the person runs
`ssh -t desk01 set-up-outside-services personal-token server-provider --server-listing-path servers`.
A server listing uses `http://127.0.0.1:8081/servers`.

### The laptop key command

The values for [The laptop key command](README.md#the-laptop-key-command):

- **Script:** `~/example-setup/enter-the-hetzner-key`.
- **Values:** one, the project's **API token**, Read & Write.
- **Shape:** 64 letters and digits.
- **Read-only call:** `GET https://api.hetzner.cloud/v1/servers?per_page=1` with `Authorization: Bearer TOKEN`. HTTP 200 accepts the token.
- **Key file line:** the token.


The CLI's credential store is `~/.config/hcloud/cli.toml`, unless `--config` selects another file.
Check the [provider's configuration documentation](https://github.com/hetznercloud/cli/blob/main/docs/reference/manual/hcloud.md) for overridden paths.

Use Hetzner's `hcloud` command-line tool. Read the current
[CLI documentation](https://github.com/hetznercloud/cli) and
[cloud-init documentation](https://cloudinit.readthedocs.io/en/latest/reference/modules.html#ssh)
before writing the team's scripts. Check `hcloud help` for the installed
release's options. The provider script contract is in the
[helper guide](../server_management_scripts/README.md#write-the-teams-provider-scripts).

1. Install `hcloud` on the systems desk and add the pinned installation to the
   utility role. The coding agent on the desk uses the API proxy and
   never holds a token. Only `util01` maps `SERVER_PROVIDER_API_TOKEN` to
   `HCLOUD_TOKEN`, for the restore drill's jobs. A person who runs a plain
   `hcloud` command in the person's own terminal sets
   `export HCLOUD_TOKEN=$SERVER_PROVIDER_API_TOKEN` there.
2. Register each initial public key with `hcloud ssh-key create --name NAME
   --public-key-from-file PUBLIC_KEY_FILE`; compare an existing key before
   reusing the existing key's name.
3. Render the first-boot data with
   `server_management_scripts/render_server_first_boot`, using the new
   server's WireGuard private key, private address, and structured `peers`
   list from the [renderer contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run).
   Never supply wg-quick directives as peer input.
   Pass the rendered file to the provider once, outside Git with mode
   `0600`, then discard the rendered file and the setup machine's private
   key copy. Store only the WireGuard public key in the inventory.
   Generate no SSH host key on the setup machine. Record the SSH host key
   after the first connection over WireGuard succeeds.

   Reason: the first WireGuard handshake authenticates the new server
   through the public key recorded before creation. SSH host-key trust
   therefore needs no provider console output or generated SSH host key.
4. Create with `hcloud server create --name NAME --type TYPE --location
   LOCATION --image IMAGE --ssh-key KEY_ID --user-data-from-file FILE
   --output json`. Repeat `--ssh-key` for every initial key. Include a key
   on every create: a create without a key enables password provisioning.
   Pass each key by its numeric ID, from
   `hcloud ssh-key describe KEY_NAME --output json` (the `id` field).
   `--ssh-key` reads a comma-separated list, so a name with a comma, such
   as `util01, the mmhotline user`, would split into two names that match
   no key.
5. Give each create attempt a unique `--label stack-create-id=TOKEN`.
   The CLI waits for actions before returning JSON. While the create runs,
   list servers by the unique selector and write the discovered ID to the
   receipt. On failure or a handled stop, repeat the ownership lookup
   before returning. Never recover ownership by name alone. Retry only a
   temporary capacity refusal known to have created no server.
6. List with `hcloud server list --output json`; normalize the JSON to the
   provider script contract, with `power_state` `running` for Hetzner's
   `status` `running` and `stopped` for `off`; any other `status`, such as
   `starting`, passes through as it is. Delete an owned drill server by the receipt's
   ID with `hcloud server delete ID` and confirm the ID is absent.
7. `power_off_a_server_at_the_provider` runs `hcloud server poweroff ID`,
   which cuts the power, when `hcloud server describe ID --output json`
   shows a `status` other than `off`, then polls that `status` every 5
   seconds until `off`, for at most 5 minutes, and prints
   `{"id": ID, "power_state": "stopped"}`. A server `describe` cannot find
   is an error. For failure tests, use the script, then
   `hcloud server poweron ID`, and check the list script's `power_state`:
   `stopped`, then `running`. `util01`'s project token is read and write,
   so it may power off.
8. Prices: `GET http://127.0.0.1:8081/server_types` gives each server type's
   `prices`, per location, hourly and monthly, and `GET http://127.0.0.1:8081/pricing`
   gives the public IPv4 address's charge in `primary_ips`, as
   [chapter 6](../initial_setup/06_create_your_three_production_servers.md) shows.
   `read_the_monthly_price_at_the_provider` makes the same two requests to
   `https://api.hetzner.cloud/v1/` with `curl` and
   `SERVER_PROVIDER_API_TOKEN` as the bearer token, adds the type's
   monthly price in the location to the public IPv4 address's monthly
   charge there, and returns the sum as `monthly_price` with the currency
   the answer names.

Reason: the official tool owns API authentication and action handling.
The WireGuard first-boot key lets an unattended restore authenticate the
new server before sending backup credentials. Keep public TCP 22 closed
on IPv4 and IPv6. Attach no Hetzner firewall; ufw owns the firewall.

## Console and rescue access

Hetzner Cloud needs no separate console activation. Open the server in
Cloud Console and select the console icon. Log in as `root` with the
shared root console password, the password manager item
`Shared root console password`. Test a root
console login before marking `provider_console_and_backup_mmhotline_logins` complete.

Reason: the browser console reaches the server without SSH or WireGuard,
so the console can repair failed SSH or WireGuard settings.

For a server that cannot boot, enable Hetzner's rescue system, reboot into
the rescue system, and inspect or repair the installed disk. Follow
[Hetzner's rescue-system guide](https://docs.hetzner.com/cloud/servers/getting-started/rescue-system/).
A server replacement remains the normal recovery for a failed server.
