# DigitalOcean

DigitalOcean calls a server a **Droplet** and a server type a **size**. Follow the shared
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts),
[enrollment contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run),
and [initial setup](../initial_setup/): accounts in
[chapter 4 (set up your accounts and lock your desk)](../initial_setup/04_set_up_your_accounts_and_lock_your_desk.md),
servers in [chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md).

## The provider's web console

The person sees the servers in DigitalOcean's control panel, at the Droplets list:
<https://cloud.digitalocean.com/droplets>.

## Credentials on the systems desk

The person owns the provider token; the coding agent reaches the provider
through the desk's API proxy, as
[Credentials on the systems desk](README.md#credentials-on-the-systems-desk)
says.

Set `systems_desk_provider_api_url: https://api.digitalocean.com/v2/` in `mmx_project_settings.yml`, including the trailing slash.
The person types the token on the laptop with the laptop key command below, and the bootstrap moves it to
the desk. To replace the token later, the person runs
`ssh -t desk01 set-up-outside-services personal-token server-provider --server-listing-path droplets`.
A server listing uses `http://127.0.0.1:8081/droplets`.

### The laptop key command

The values for [The laptop key command](README.md#the-laptop-key-command):

- **Script:** `~/example-setup/enter-the-digitalocean-key`.
- **Values:** one, the **personal access token** of "The person's token" below.
- **Shape:** `dop_v1_` followed by 64 hexadecimal characters.
- **Read-only call:** `GET https://api.digitalocean.com/v2/droplets?per_page=1` with `Authorization: Bearer TOKEN`. HTTP 200 accepts the token.
- **Key file line:** the token.


The five provider scripts use `curl` and `jq` with the request function below, on the desk through the
proxy and on `util01` with `util01`'s own token, so neither needs DigitalOcean's command-line tool `doctl`.
Reason: the scripts then run unchanged in both places, and `curl` never repeats a create on its own
(`doctl` retries a request whose answer was lost, which can create a second Droplet).

### The person's token

The person makes the token in DigitalOcean's control panel, **API**, **Generate New Token**, with
**Custom Scopes**, no expiry, named `example_systems: alex's systems desk` with the person's desk account
name in place of `alex`. Its scopes are `util01`'s list below, plus `ssh_key:create` and `ssh_key:delete`
to register and remove keys, and `account:read` to read the account's Droplet limit. A token without
`ssh_key:delete` cannot remove a key it registered (HTTP 403 on a real account). Keep this token off `util01`.

### util01's token

`util01` creates, lists, powers off and deletes Droplets with its own token, which belongs to the account
and not to a person: the weekly restore drill creates and deletes `restore01`, the daily leftover check
lists the Droplets, and the triage agent's server replacements power a failed server off, create its
replacement and delete the failed one. The person makes it the same way, named
`example_systems: util01 creates and deletes servers`, with exactly these custom scopes:

| Scope | Why `util01` needs it |
| --- | --- |
| `droplet:create` | Create a server |
| `droplet:read` | List servers and read one |
| `droplet:update` | Power a server off (the `power_off` Droplet action) |
| `droplet:delete` | Delete a server |
| `ssh_key:read` | Find the SSH key the create names |
| `regions:read`, `sizes:read`, `image:read`, `snapshot:read`, `actions:read`, `vpc:read` | DigitalOcean requires these beside `droplet:create`, `droplet:update` and `droplet:delete`; `sizes:read` also lets `read_the_monthly_price_at_the_provider` read a size's price |

Sources: DigitalOcean's [scopes](https://docs.digitalocean.com/reference/api/scopes/) list, its pages for
[`droplet:create`](https://docs.digitalocean.com/reference/api/scopes/droplet/create/),
[`droplet:update`](https://docs.digitalocean.com/reference/api/scopes/droplet/update/) and
[`droplet:delete`](https://docs.digitalocean.com/reference/api/scopes/droplet/delete/), which name the
required scopes beside each, and the [Droplet actions](https://docs.digitalocean.com/reference/api/reference/droplet-actions/)
reference, which names `droplet:update` for `power_off` (checked 2026-11-12). These custom scopes are the
smallest DigitalOcean offers: a scope covers every Droplet of the team, not one project, so keep other
systems in another DigitalOcean team. `set-up-outside-services secrets` asks for the token at a hidden
prompt and saves it in the vault as `util01_provider_api_token`; the scripts read it from
`SERVER_PROVIDER_API_TOKEN`. `util01` needs no other setting and no program beyond Debian's `curl` and the
Stack's `jq`.

A token made before this Stack version, for the restore drill only, lacks `droplet:update`, so
`replace_failed_servers` cannot power a failed server off with it. To widen it, the person makes a new
token with the list above, runs `set-up-outside-services secrets --replace util01_provider_api_token`, the
coding agent runs `every_server`, and the person deletes the old token on the **API** page. The same steps
replace the token after a leak. When a person leaves, the person who stays deletes the leaving person's
token by its name; `util01`'s token keeps working.

## The provider scripts' request function

Put the function, with the value above it, at the top of each script, after `#!/bin/bash` and
`set -euo pipefail`. It goes through the API proxy where `SERVER_PROVIDER_API_TOKEN` is empty (the
coding agent on a desk) and sends the token itself where it is set (`util01`'s jobs, and the person's own
terminal during the first desk's bootstrap). It works in Debian's `bash` and in macOS's `bash` 3.2.

```bash
digitalocean_api_address=https://api.digitalocean.com/v2/   # systems_desk_provider_api_url

# digitalocean_request METHOD PATH [BODY_FILE]
# Sends one request to PATH under the API address, such as "droplets",
# prints the answer's body, and fails on an answer that is not 2xx,
# without printing the body.
digitalocean_request() {
  local method=$1 path=$2 body_file=${3:-} answer http_status_code
  local -a body_arguments=()
  [ -z "$body_file" ] || body_arguments=(--header 'Content-Type: application/json' --data-binary "@$body_file")
  answer=$(mktemp)
  if [ -z "${SERVER_PROVIDER_API_TOKEN:-}" ]; then
    http_status_code=$(curl --silent --show-error --connect-timeout 10 --max-time 120 \
      --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' \
      "http://127.0.0.1:8081/$path") || true
  else
    # The token goes through standard input, never the command line, which
    # other accounts on the server can read.
    http_status_code=$(printf 'Authorization: Bearer %s\n' "$SERVER_PROVIDER_API_TOKEN" |
      curl --silent --show-error --connect-timeout 10 --max-time 120 --header @- \
        --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' \
        "$digitalocean_api_address$path") || true
  fi
  case "$http_status_code" in
    2??) cat -- "$answer"; rm -f -- "$answer" ;;
    *) printf 'DigitalOcean answered %s %s with HTTP %s (body withheld)\n' "$method" "${path%%\?*}" "$http_status_code" >&2
       rm -f -- "$answer"; return 1 ;;
  esac
}

# digitalocean_list PATH KEY
# Prints every page of a listing as one JSON list, such as
# digitalocean_list droplets droplets. A failed page fails the whole listing.
digitalocean_list() {
  local path=$1 key=$2 separator='?' page=1 answer pages=''
  case "$path" in *\?*) separator='&' ;; esac
  while :; do
    answer=$(digitalocean_request GET "$path${separator}per_page=200&page=$page") || return 1
    # Each page is one line; jq joins the lines at the end. A growing list is
    # never a command-line argument: it can pass the 131,072 bytes Linux
    # allows for one.
    pages+=$(jq -c --arg key "$key" '.[$key]' <<< "$answer")$'\n'
    jq -e '.links.pages.next' <<< "$answer" > /dev/null || break
    page=$((page + 1))
  done
  printf '%s' "$pages" | jq -cs 'add'
}
```

The time limits are 10 seconds to connect and 120 seconds for an answer, which a create answers well
within. The function withholds an error's body because an error can repeat the request's `user_data`.
Never pass the token or first-boot data as command-line arguments.

## The five provider scripts

Each script is `#!/bin/bash`, `set -euo pipefail`, the value and the functions above, then its own part
below, in `server_management_scripts/` under the contract's names.

`list_the_servers_at_the_provider`:

```bash
# DigitalOcean lists Droplets with GPUs only when asked for them, so two listings.
droplets=$(digitalocean_list droplets droplets)
gpu_droplets=$(digitalocean_list 'droplets?type=gpus' droplets)
printf '%s\n%s\n' "$droplets" "$gpu_droplets" | jq -s '{servers: [.[0] + .[1] | unique_by(.id)[] | {
    id: (.id | tostring), name,
    public_ipv4_address: ([.networks.v4[]? | select(.type == "public") | .ip_address][0] // ""),
    power_state: ({"active": "running", "off": "stopped"}[.status] // .status)}]}'
```

`create_a_server_at_the_provider`:

```bash
server_name='' server_type='' location='' image='' first_boot_data='' wireguard_public_key='' private_ip='' ownership_file=''
ssh_key_names=()
while [ $# -gt 0 ]; do
  case "$1" in
    --server-name) server_name=$2 ;; --server-type) server_type=$2 ;; --location) location=$2 ;;
    --image) image=$2 ;; --ssh-key-name) ssh_key_names+=("$2") ;; --first-boot-data) first_boot_data=$2 ;;
    --wireguard-public-key) wireguard_public_key=$2 ;; --wireguard-private-ip) private_ip=$2 ;;
    --ownership-file) ownership_file=$2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift 2
done
body_file=$(mktemp); chmod 600 "$body_file"
# Clear the first-boot data after reading it, also on failure.
trap ': > "$first_boot_data"; rm -f -- "$body_file"' EXIT
[ "${#ssh_key_names[@]}" -ge 1 ] || { echo "give at least one --ssh-key-name: without a key DigitalOcean emails a root password" >&2; exit 2; }
keys=$(digitalocean_list account/keys ssh_keys)
ssh_key_ids='[]'
for key_name in "${ssh_key_names[@]}"; do
  # A name can repeat at DigitalOcean: accept exactly one key by that name.
  key_id=$(jq -r --arg n "$key_name" '[.[] | select(.name == $n) | .id] | if length == 1 then .[0] else empty end' <<< "$keys")
  [ -n "$key_id" ] || { echo "expected exactly one SSH key named $key_name" >&2; exit 1; }
  ssh_key_ids=$(jq -c --argjson id "$key_id" '. + [$id]' <<< "$ssh_key_ids")
done
jq -n --arg name "$server_name" --arg region "$location" --arg size "$server_type" --arg image "$image" \
  --argjson ssh_keys "$ssh_key_ids" --rawfile user_data "$first_boot_data" \
  '{name: $name, region: $region, size: $size, image: $image, ssh_keys: $ssh_keys, user_data: $user_data,
    ipv6: true, monitoring: false, with_droplet_agent: false}' > "$body_file"
write_receipt() {  # write_receipt JSON: replaces the ownership file in one step
  [ -z "$ownership_file" ] || { printf '%s\n' "$1" > "$ownership_file.new" && mv -- "$ownership_file.new" "$ownership_file"; }
}
# The IDs before the create tell a lost answer's server apart. Never send the POST again.
ids_before=$(digitalocean_list droplets droplets | jq -c '[.[].id]')
if created=$(digitalocean_request POST droplets "$body_file"); then
  server_id=$(jq -r '.droplet.id' <<< "$created")
else
  echo "the create's answer failed; looking for a new server named $server_name" >&2
  sleep 30  # time for DigitalOcean to list a create it accepted
  server_id=$(digitalocean_list droplets droplets | jq -r --argjson before "$ids_before" --arg n "$server_name" \
    '[.[] | select(.name == $n and (.id as $id | $before | index($id) | not)) | .id] | if length == 1 then .[0] else empty end')
  [ -n "$server_id" ] || { echo "no single new server named $server_name appeared; check the listing before any retry" >&2; exit 1; }
fi
write_receipt "$(jq -n --arg id "$server_id" --arg name "$server_name" '{id: $id, name: $name}')"
for _ in $(seq 1 90); do
  detail=$(digitalocean_request GET "droplets/$server_id")
  address=$(jq -r '[.droplet.networks.v4[]? | select(.type == "public") | .ip_address][0] // empty' <<< "$detail")
  if [ "$(jq -r .droplet.status <<< "$detail")" = active ] && [ -n "$address" ]; then
    result=$(jq -n --arg id "$server_id" --arg name "$server_name" --arg a "$address" --arg t "$server_type" --arg l "$location" \
      --arg w "$wireguard_public_key" --arg i "$private_ip" \
      '{id: $id, name: $name, public_ipv4_address: $a, server_type: $t, location: $l, wireguard_public_key: $w, private_ip: $i}')
    write_receipt "$result"
    printf '%s\n' "$result"
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not active with a public IPv4 address after 15 minutes" >&2
exit 1
```

`destroy_a_server_at_the_provider`:

```bash
server_id='' server_name=''
while [ $# -gt 0 ]; do
  case "$1" in
    --server-id) server_id=$2 ;; --server-name) server_name=$2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift 2
done
listing=$(digitalocean_list droplets droplets)
if [ -n "$server_id" ]; then
  # Never fall back from a missing ID to a matching name.
  if ! jq -e --arg i "$server_id" 'any(.[]; (.id | tostring) == $i)' <<< "$listing" > /dev/null; then
    echo "no server with ID $server_id: nothing to destroy" >&2
    jq -n --arg i "$server_id" '{id: $i, deleted: true}'
    exit 0
  fi
elif [ -n "$server_name" ]; then
  server_id=$(jq -r --arg n "$server_name" '[.[] | select(.name == $n) | .id | tostring] | if length == 1 then .[0] else empty end' <<< "$listing")
  [ -n "$server_id" ] || { echo "expected exactly one server named $server_name" >&2; exit 1; }
else
  echo "give --server-id or --server-name" >&2; exit 2
fi
digitalocean_request DELETE "droplets/$server_id" > /dev/null
# Deletion accepted is not deletion finished: wait until a whole listing lacks
# the ID. A failed listing stops the script; it never counts as "gone".
for _ in $(seq 1 60); do
  listing=$(digitalocean_list droplets droplets)
  if ! jq -e --arg i "$server_id" 'any(.[]; (.id | tostring) == $i)' <<< "$listing" > /dev/null; then
    jq -n --arg i "$server_id" '{id: $i, deleted: true}'
    exit 0
  fi
  sleep 10
done
echo "server $server_id is still listed after 10 minutes" >&2
exit 1
```

`power_off_a_server_at_the_provider`:

```bash
server_id=''
while [ $# -gt 0 ]; do
  case "$1" in
    --server-id) server_id=$2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift 2
done
[ -n "$server_id" ] || { echo "give --server-id" >&2; exit 2; }
status_of() {  # status_of: the Droplet's status from a whole listing, or nothing when it is not listed
  digitalocean_list droplets droplets | jq -r --arg i "$server_id" '[.[] | select((.id | tostring) == $i) | .status][0] // empty'
}
status=$(status_of)
[ -n "$status" ] || { echo "no server with ID $server_id" >&2; exit 1; }
body_file=$(mktemp); trap 'rm -f -- "$body_file"' EXIT
printf '{"type": "power_off"}\n' > "$body_file"
# power_off cuts the power, as a power cut does.
[ "$status" = off ] || digitalocean_request POST "droplets/$server_id/actions" "$body_file" > /dev/null
# The contract's 5 minutes; a power-off took seconds on a real account.
for _ in $(seq 1 30); do
  if [ "$(status_of)" = off ]; then
    jq -n --arg i "$server_id" '{id: $i, power_state: "stopped"}'
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not stopped after 5 minutes" >&2
exit 1
```

The list script's `power_state` is `running` for a Droplet's `status` `active` and `stopped` for `off`;
`new` and `archive` pass through as they are. IDs are DigitalOcean's numeric Droplet IDs, as strings.
Names can repeat at DigitalOcean, so every lifecycle action uses the ID, and the create, which has no
ownership label, records the account's Droplet IDs before the POST: when the POST's answer is lost or
refused, it looks once more after 30 seconds and accepts only exactly one new ID with the exact name;
otherwise it stops without a retry. Reason: another POST could duplicate an accepted create. DigitalOcean's
exact answer for a size a region has run out of is not verified, so the script retries no error as a
capacity refusal. The create sends the rendered first-boot file as `user_data`, as it is (at most 64 KiB),
with `ipv6`, without DigitalOcean's monitoring agent and without the Droplet Agent: the Stack supplies its
own monitoring and uses the Recovery Console below.

The four scripts above, with `util01`'s path (a shell with `SERVER_PROVIDER_API_TOKEN` set), created an
`s-1vcpu-512mb-10gb` Droplet in `ams3` with first-boot data in 38 seconds (root SSH with the named key and
the first-boot data worked 15 seconds later), powered it off in 12 seconds and deleted it in 12 seconds,
on a real account (2026-11-12). A token without `droplet:update` was refused the power-off with HTTP 403.
The Stack's tests (`tests/digitalocean_provider_scripts_test.py`) run these blocks, with each `bash` on the
test machine, against a stand-in for DigitalOcean's API, through the proxy and with the token, including a
create whose answer is lost and a listing of more than one page.

`read_the_monthly_price_at_the_provider`:

```bash
server_type='' location=''
while [ $# -gt 0 ]; do
  case "$1" in
    --server-type) server_type=$2 ;; --location) location=$2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift 2
done
[ -n "$server_type" ] && [ -n "$location" ] || { echo "give --server-type and --location" >&2; exit 2; }
size=$(digitalocean_list sizes sizes | jq -c --arg s "$server_type" '[.[] | select(.slug == $s)] | if length == 1 then .[0] else empty end')
[ -n "$size" ] || { echo "DigitalOcean lists no size $server_type" >&2; exit 1; }
jq -e --arg l "$location" '.regions | index($l)' <<< "$size" > /dev/null || { echo "size $server_type is not offered in region $location" >&2; exit 1; }
echo "DigitalOcean's monthly price, without the tax it adds in some countries; it includes the Droplet's public IPv4 address" >&2
jq --arg l "$location" '{server_type: .slug, location: $l, monthly_price: (.price_monthly | tostring), currency: "USD"}' <<< "$size"
```

The price script reads `price_monthly` of the size, in US dollars, the same number the
[Prices](#region-size-and-image) paragraph below shows the person: DigitalOcean charges the hourly price
until it reaches the monthly price within a month, and a Basic size includes its public IPv4 address.
DigitalOcean's sizes cost the same in every region, so the region only has to offer the size.

## Region, size, and image

Select the official [`debian-13-x64` image](https://docs.digitalocean.com/products/droplets/details/images/)
(`server_image: debian-13-x64`; the create sends the slug, which follows image refreshes). DigitalOcean's
Debian 13 image includes cloud-init and installs the selected SSH keys for `root`. Use x86-64 sizes,
because the Stack's server binaries and container images are x86-64, also with an ARM systems desk.

Check `GET http://127.0.0.1:8081/sizes` and `GET http://127.0.0.1:8081/regions` for availability in the
chosen region, and use the full region slug, such as `ams3`. Basic `s-4vcpu-8gb` for `app001` and
`s-2vcpu-4gb` for the remaining ordinary roles meet the shared setup's minimums.

**Prices.** `curl -sS 'http://127.0.0.1:8081/sizes?per_page=200' | jq '.sizes[] | select(.slug == "s-2vcpu-4gb") | {slug, price_monthly, price_hourly, disk, regions}'`
gives each size's `price_monthly` and `price_hourly` in US dollars, without the tax DigitalOcean adds in
some countries; the hourly price stops at the monthly price within a month. A Basic size (`s-...`)
includes its public IPv4 address and its outbound transfer allowance
([prices](https://www.digitalocean.com/pricing/droplets), checked 2026-11-12: the API answered `4` and
`0.00595` for `s-1vcpu-512mb-10gb`, the page's $4.00 a month and $0.00595 an hour). Compare disk sizes and [current prices](https://www.digitalocean.com/pricing/droplets)
before choosing, because equal-memory plans can have different disks.

Check `GET http://127.0.0.1:8081/account` for `status` `active` and `droplet_limit`, because new accounts
have account-specific limits. Allow a temporary slot for the restore drill and another for a replacement.
DigitalOcean [blocks SMTP ports 25, 465 and 587](https://docs.digitalocean.com/products/droplets/details/limits/):
send app email through an email service's HTTPS API.

## Network

DigitalOcean automatically creates a regional default VPC with the first Droplet when no VPC exists. A VPC
is DigitalOcean's private network, separate from WireGuard; the automatic default needs no `vpc:create`.
Check an existing [default VPC](https://docs.digitalocean.com/products/networking/vpc/how-to/set-default-vpc/)
before the first create, and after it read the Droplet's `vpc_uuid` and `GET /vpcs/UUID` for its
`ip_range`. If that range overlaps `10.20.0.0/16`, or the team's chosen WireGuard range, stop and report the
overlap before creating more servers, and resolve the address plan through
[chapter 3 (make your server account and your systems desk)](../initial_setup/03_make_your_server_account_and_your_systems_desk.md).
Reason: a provider subnet overlapping WireGuard sends private traffic to the wrong interface.

Attach no Cloud Firewall: UFW enforces the Stack's firewall.

Handle DigitalOcean's metadata-reading services in `roles/every_server/main.yml` before the first reboot.
Keep the metadata HTTP block, including `169.254.169.254`. When the team uses no VPC peering, stop, disable
and mask `vpc-peering.service`: the provider's
[route-injection service](https://docs.digitalocean.com/products/networking/vpc/how-to/update-peering-routes/)
queries metadata and fails after the block. If the unit is a regular file under `/etc/systemd/system`,
remove the stopped unit before masking, because systemd cannot replace a regular local unit with a mask.
Preserve the VPC interface and routes. Inspect `droplet-agent.service` and `do-agent.service`, if present,
for metadata dependencies. Reboot and check failed units as well as private access, because first-boot
success misses the peering service's failure.

## Keys, first boot, and lifecycle

The coding agent registers a key from the desk, through the proxy, with the person's token:

```sh
jq -n --arg name 'util01, the mmhotline user' --arg public_key 'ssh-ed25519 AAAA... mmhotline@util01' \
  '{name: $name, public_key: $public_key}' |
  curl -sS --fail-with-body -X POST -H 'Content-Type: application/json' --data-binary @- \
  http://127.0.0.1:8081/account/keys | jq '.ssh_key | {id, name, fingerprint}'
```

Compare the listed `public_key` (`GET /account/keys`) with the key's line before using the name, and give
each key a name no other key has: the create accepts exactly one key per name. Register `util01`'s key
before the first drill, because `util01`'s token can read keys but not add them. Include a key on every
create: without one DigitalOcean emails a root password.

For a power-failure test, the coding agent cuts the power and powers on from the desk:

```sh
./server_management_scripts/power_off_a_server_at_the_provider --server-id SERVER_ID
printf '{"type": "power_on"}' | curl -sS --fail-with-body -X POST -H 'Content-Type: application/json' \
  --data-binary @- http://127.0.0.1:8081/droplets/SERVER_ID/actions | jq '.action | {id, status}'
./server_management_scripts/list_the_servers_at_the_provider | jq '.servers[] | select(.id == "SERVER_ID")'
```

Wait for `power_state` `stopped` after the power-off and `running` after the power-on. `power_off` is a hard
power-off, "similar to cutting the power on a server", in DigitalOcean's
[Droplet actions](https://docs.digitalocean.com/reference/api/reference/droplet-actions/) reference, so the
test is a sudden power loss. Both tokens allow these requests. A stopped Droplet is still billed until it
is destroyed.

Use the shared [replacement](../operating_procedures/replace_a_server.md),
[removal](../operating_procedures/remove_a_server.md) and
[restore-drill](../operating_procedures/run_the_weekly_database_restore_drill.md) procedures for the
remaining steps.

## Console and rescue access

DigitalOcean needs no separate Recovery Console activation. Open the Droplet's
**Settings → Recovery console → Launch Console**. Use the shared root console password from the password manager.
The [Recovery Console](https://docs.digitalocean.com/products/droplets/how-to/recovery/recovery-console/)
works without SSH or WireGuard. The ordinary Droplet Console uses SSH, so the Droplet Console cannot prove independent recovery.

For an unbootable server, power off and select **Settings → Recovery mode → Boot from Recovery ISO**.
Power on and open the Recovery Console to repair the installed disk.
The [Recovery ISO](https://docs.digitalocean.com/products/droplets/how-to/recovery/recovery-iso/)
enables networking and SSH automatically, outside the installed disk's UFW rules.
Close rescue SSH through the console before handling backup data.
Return to **Boot from Hard Drive** and verify private access, original host keys and public SSH closure.
