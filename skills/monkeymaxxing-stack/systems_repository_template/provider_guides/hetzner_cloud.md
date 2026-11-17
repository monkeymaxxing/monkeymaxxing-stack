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


The five provider scripts use `curl` and `jq` against `https://api.hetzner.cloud/v1/`, on the laptop with
`SERVER_PROVIDER_API_TOKEN` read from the key file, on the desk through the API proxy (no token), and on `util01`
with `util01`'s own token. No Hetzner command-line tool (`hcloud`) is installed anywhere, so there is no saved
login to remove. Write one `hetzner_request METHOD PATH [BODY_FILE]` function that sends the request and
the bearer token (`Authorization: Bearer TOKEN`, from standard input with `curl -H @-`, never on a command
line), and prints the answer's body or the provider's own error message. Read the current
[API reference](https://docs.hetzner.cloud/) and
[cloud-init documentation](https://cloudinit.readthedocs.io/en/latest/reference/modules.html#ssh)
before writing the team's scripts. The provider script contract is in the
[helper guide](../server_management_scripts/README.md#write-the-teams-provider-scripts).

1. Register each initial public key with `POST /ssh_keys` and the body
   `{"name": NAME, "public_key": "PUBLIC_KEY_TEXT"}`; compare an existing key (`GET /ssh_keys?name=NAME`)
   before reusing the existing key's name. On `util01`, the token is
   `SERVER_PROVIDER_API_TOKEN` too, for the restore drill's jobs.
2. Render the first-boot data with
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
3. Create with `POST /servers` and the body `{"name": NAME, "server_type": TYPE, "location": LOCATION,
   "image": IMAGE, "ssh_keys": [KEY_ID, ...], "user_data": "FIRST_BOOT_FILE_TEXT",
   "labels": {"stack-create-id": TOKEN}, "start_after_create": true}`, built with `jq` from files so no value
   goes on a command line. List every initial key's numeric `id`, from `GET /ssh_keys?name=KEY_NAME` (the
   `ssh_keys[0].id` field). Include a key on every create: a create without a key enables password
   provisioning. Look keys up by their names one request each: a name with a comma, such as
   `util01, the mmhotline user`, is no problem in a JSON body.
4. Give each create attempt a unique label `stack-create-id=TOKEN` (the body above).
   `POST /servers` answers before the server runs, with an `action`; poll `GET /actions/ID` every 5 seconds
   until its `status` is `success`. While the create runs, list servers by the unique selector
   (`GET /servers?label_selector=stack-create-id%3DTOKEN`) and write the discovered ID to the
   receipt. On failure or a handled stop, repeat the ownership lookup
   before returning. Never recover ownership by name alone. Retry only a
   temporary capacity refusal known to have created no server. `curl` never repeats a request on its own.
5. List with `GET /servers?per_page=50`, following `meta.pagination.next_page`; normalize the JSON to the
   provider script contract, with `power_state` `running` for Hetzner's
   `status` `running` and `stopped` for `off`; any other `status`, such as
   `starting`, passes through as it is. Delete an owned drill server by the receipt's
   ID with `DELETE /servers/ID` and confirm the ID is absent from the list.
6. `power_off_a_server_at_the_provider` sends `POST /servers/ID/actions/poweroff`,
   which cuts the power, when `GET /servers/ID` shows a `status` other than `off`, then polls that `status`
   every 5 seconds until `off`, for at most 5 minutes, and prints
   `{"id": ID, "power_state": "stopped"}`. A server the request cannot find
   is an error. For failure tests, use the script, then
   `POST /servers/ID/actions/poweron`, and check the list script's `power_state`:
   `stopped`, then `running`. `util01`'s project token is read and write,
   so it may power off.
7. Prices: `GET http://127.0.0.1:8081/server_types` gives each server type's
   `prices`, per location, hourly and monthly, and `GET http://127.0.0.1:8081/pricing`
   gives the public IPv4 address's charge in `primary_ips`, as
   [chapter 6](../initial_setup/06_create_your_three_production_servers.md) shows.
   `read_the_monthly_price_at_the_provider` makes the same two requests to
   `https://api.hetzner.cloud/v1/` with `curl` and
   `SERVER_PROVIDER_API_TOKEN` as the bearer token, adds the type's
   monthly price in the location to the public IPv4 address's monthly
   charge there, and returns the sum as `monthly_price` with the currency
   the answer names.

Reason: `curl` calls the one API the same way in all three places, so the scripts run unchanged on the laptop,
the desk and `util01` without a program to install, and `curl` never repeats a create whose answer was lost
(a repeat could create a second server).
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
