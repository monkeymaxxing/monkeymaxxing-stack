# Vultr Cloud Compute

Vultr calls a server an **instance** and a server type a **plan**. Follow the shared
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts),
[enrollment contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run),
and [initial setup](../initial_setup/): accounts in
[chapter 4 (sign up for the outside services the Stack uses)](../initial_setup/04_sign_up_for_the_outside_services_the_stack_uses.md),
servers in [chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md).

## The provider's web console

The person sees the servers in Vultr's customer portal, <https://my.vultr.com/>,
under **Compute**.

## Credentials on the systems desk

The person owns the provider token; the coding agent reaches the provider
through the desk's API proxy, as
[Credentials on the systems desk](README.md#credentials-on-the-systems-desk)
says.

Set `systems_desk_provider_api_url: https://api.vultr.com/v2/` in `mmx_project_settings.yml`, including the trailing slash.
The person saves the token with `set-up-outside-services personal-token server-provider --server-listing-path instances`.
A server listing uses `http://127.0.0.1:8081/instances`.

The five provider scripts use `curl` and `jq` with the request function below, on the desk through the
proxy and on `util01` with `util01`'s own API key, so neither needs Vultr's command-line tool. Reason:
`vultr-cli` retries a request through its library with no way to turn retries off, and a repeated create
whose answer was lost makes a second server; `curl` sends each request once.

### The person's API key

The person's API key is the account's own, from **Account → API**. It has every right, so it stays in the
person's protected desk files.

### util01's API key

`util01` creates, lists, powers off and deletes instances with its own API key, which belongs to an
[API-only service user](https://docs.vultr.com/platform/iam/service-user/how-to-create-a-service-user),
not to a person: the weekly restore drill creates and deletes `restore01`, the daily leftover check lists
the instances, and the triage agent's server replacements power a failed server off, create its replacement
and delete the failed one. The person creates the service user `example-systems-util01` with an IAM policy
that allows exactly these [IAM actions](https://docs.vultr.com/platform/iam/policies/iam-policy-actions-map/compute-actions),
on resources `*`:

| IAM action | Why `util01` needs it, and which script's call |
| --- | --- |
| `compute.instance.Create` | Create a server: `create_a_server_at_the_provider`, `POST /v2/instances` |
| `compute.instance.List` | List servers: every script but the price script, `GET /v2/instances` |
| `compute.instance.Read` | Read one server while it starts: `create_a_server_at_the_provider`, `GET /v2/instances/ID` |
| `compute.instance.Update` | Power a server off for the triage agent's replacements: `power_off_a_server_at_the_provider`, `POST /v2/instances/ID/halt` |
| `compute.instance.Delete` | Delete a server: `destroy_a_server_at_the_provider`, `DELETE /v2/instances/ID` |
| `compute.sshkey.List` | Find the SSH key the create names: `create_a_server_at_the_provider`, `GET /v2/ssh-keys` |
| `compute.sshkey.Read` | Read the keys that listing returns: `create_a_server_at_the_provider`, `GET /v2/ssh-keys` |

Vultr's action map (checked 2026-11-12) names no separate action for halt, start or reboot:
`compute.instance.Update` ("Update instance") covers the halt, as a real round showed (below). The policy
allows both `compute.sshkey.List` and `compute.sshkey.Read`, the rights with which the create's key
listing passed on a real account. The price script and the operating systems' listing read
public listings that need no key, so they need no action. Resources stay `*` because a future instance's
ID is unknown: the key can delete any instance of the account, so keep other systems in another Vultr
account. `set-up-outside-services secrets` asks for the service user's API key at a hidden prompt and saves
it in the vault as `util01_provider_api_token`; the scripts read it from `SERVER_PROVIDER_API_TOKEN`.
`util01` needs no other setting and no program beyond Debian's `curl` and `coreutils` and the Stack's `jq`.

A policy made before this Stack version, for the restore drill only, lacks `compute.instance.Update`, so
`replace_failed_servers` cannot power a failed server off, and may lack `compute.sshkey.Read`. To widen it,
the person adds both to the service user's policy in Vultr's IAM; the API key stays the same, so
nothing changes in the vault. To replace the key after a leak, the person makes a new key for the service
user, runs `set-up-outside-services secrets --replace util01_provider_api_token`, the coding agent runs
`every_server`, and the person deletes the old key.

### Vultr's address list for API keys

In the service user's **API Access → Access Control List**, allow `util01`'s actual public IPv4 address as
a `/32`, and its IPv6 address as a `/128` when API calls use IPv6. Apply the same restriction to the
person's key, with the desk's public address. Reopen the saved list and test from each caller. Update
`util01`'s entry after `util01` is replaced, before its provider jobs run. A refused address answers HTTP
401 (`Unauthorized IP address`) and created nothing: check the caller's address against the saved list and
correct the list. A systems desk with more than one outgoing address can alternate between allowed and
refused requests. Reason: a valid key still fails from an unlisted address, and calls can prefer IPv6.
When the team turns on the access list for `util01`'s key, put both of `util01`'s addresses on it, its
IPv4 address and its IPv6 address: `util01` has both, and a server with both may call over either, so with
one missing, `util01`'s calls fail with `Unauthorized IP address` from time to time.
Vultr answers HTTP 401 `Unauthorized IP address` also for a call that the key's user is not allowed to make,
as a real round on 2026-11-12 showed: before the service user had all seven actions above, its key was
refused the SSH-key listing and the halt with that answer. So for that answer check the service user's
policy against the table above as well as the address list.

## The provider scripts' request function

Put the function, with the value above it, at the top of each script, after `#!/bin/bash` and
`set -euo pipefail`. It goes through the API proxy where `SERVER_PROVIDER_API_TOKEN` is empty (the
coding agent on a desk) and sends the key itself where it is set (`util01`'s jobs, and the person's own
terminal during the first desk's bootstrap). It works in Debian's `bash` and in macOS's `bash` 3.2.

```bash
vultr_api_address=https://api.vultr.com/v2/   # systems_desk_provider_api_url

# vultr_request METHOD PATH [BODY_FILE]
# Sends one request to PATH under the API address, such as "instances",
# prints the answer's body, and fails on an answer that is not 2xx,
# without printing the body.
vultr_request() {
  local method=$1 path=$2 body_file=${3:-} answer http_status_code
  local -a body_arguments=()
  [ -z "$body_file" ] || body_arguments=(--header 'Content-Type: application/json' --data-binary "@$body_file")
  answer=$(mktemp)
  if [ -z "${SERVER_PROVIDER_API_TOKEN:-}" ]; then
    http_status_code=$(curl --silent --show-error --connect-timeout 10 --max-time 120 \
      --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' \
      "http://127.0.0.1:8081/$path") || true
  else
    # The key goes through standard input, never the command line, which
    # other accounts on the server can read.
    http_status_code=$(printf 'Authorization: Bearer %s\n' "$SERVER_PROVIDER_API_TOKEN" |
      curl --silent --show-error --connect-timeout 10 --max-time 120 --header @- \
        --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' \
        "$vultr_api_address$path") || true
  fi
  case "$http_status_code" in
    2??) cat -- "$answer"; rm -f -- "$answer" ;;
    *) printf 'Vultr answered %s %s with HTTP %s (body withheld)\n' "$method" "${path%%\?*}" "$http_status_code" >&2
       rm -f -- "$answer"; return 1 ;;
  esac
}

# vultr_list PATH KEY
# Prints every page of a listing as one JSON list, such as
# vultr_list instances instances. A failed page fails the whole listing.
vultr_list() {
  local path=$1 key=$2 cursor='' answer pages=''
  while :; do
    answer=$(vultr_request GET "$path?per_page=500${cursor:+&cursor=$cursor}") || return 1
    # Each page is one line; jq joins the lines at the end. A growing list is
    # never a command-line argument: it can pass the 131,072 bytes Linux
    # allows for one.
    pages+=$(jq -c --arg key "$key" '.[$key]' <<< "$answer")$'\n'
    cursor=$(jq -r '.meta.links.next // empty | @uri' <<< "$answer")
    [ -n "$cursor" ] || break
  done
  printf '%s' "$pages" | jq -cs 'add'
}
```

The time limits are 10 seconds to connect and 120 seconds for an answer. The function withholds an error's
body, and the scripts print only selected fields, because an instance's answer holds its
`default_password`. Never pass the key or first-boot data as command-line arguments.

## The five provider scripts

Each script is `#!/bin/bash`, `set -euo pipefail`, the value and the functions above, then its own part
below, in `server_management_scripts/` under the contract's names.

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
# Vultr's plan listing needs no key, so it is read without one: util01's
# key then needs no right for it, and its address list does not apply.
# Each page's plans are one line of $pages, joined by jq: the whole listing is
# over the 131,072 bytes Linux allows for one command-line argument.
pages='' cursor=''
while :; do
  page=$(curl --silent --show-error --fail --connect-timeout 10 --max-time 120 \
    "${vultr_api_address}plans?type=all&per_page=500${cursor:+&cursor=$cursor}") || { echo "Vultr's plan listing did not answer" >&2; exit 1; }
  pages+=$(jq -c '.plans' <<< "$page")$'\n'
  cursor=$(jq -r '.meta.links.next // empty | @uri' <<< "$page")
  [ -n "$cursor" ] || break
done
plan=$(printf '%s' "$pages" | jq -cs --arg p "$server_type" 'add | [.[] | select(.id == $p)] | if length == 1 then .[0] else empty end')
[ -n "$plan" ] || { echo "Vultr lists no plan $server_type" >&2; exit 1; }
jq -e --arg l "$location" '.locations | index($l)' <<< "$plan" > /dev/null || { echo "plan $server_type is not offered in region $location" >&2; exit 1; }
echo "Vultr's plan price; Vultr's answer does not say whether tax or the public IPv4 address is included" >&2
jq --arg l "$location" '{server_type: .id, location: $l, monthly_price: (.monthly_cost | tostring), currency: "USD"}' <<< "$plan"
```

`list_the_servers_at_the_provider`:

```bash
vultr_list instances instances | jq '{servers: [.[] | {id, name: .label,
    public_ipv4_address: (if .main_ip == "0.0.0.0" then "" else .main_ip end),
    power_state: .power_status}]}'
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
[ "${#ssh_key_names[@]}" -ge 1 ] || { echo "give at least one --ssh-key-name" >&2; exit 2; }
keys=$(vultr_list ssh-keys ssh_keys)
ssh_key_ids='[]'
for key_name in "${ssh_key_names[@]}"; do
  # A name can repeat at Vultr: accept exactly one key by that name.
  key_id=$(jq -r --arg n "$key_name" '[.[] | select(.name == $n) | .id] | if length == 1 then .[0] else empty end' <<< "$keys")
  [ -n "$key_id" ] || { echo "expected exactly one SSH key named $key_name" >&2; exit 1; }
  ssh_key_ids=$(jq -c --arg id "$key_id" '. + [$id]' <<< "$ssh_key_ids")
done
# The image is the operating system's exact name, such as "Debian 13 x64 (trixie)":
# Vultr's numeric OS IDs are not release aliases.
os_id=$(vultr_list os os | jq -r --arg n "$image" '[.[] | select(.name == $n) | .id] | if length == 1 then .[0] else empty end')
[ -n "$os_id" ] || { echo "expected exactly one operating system named $image" >&2; exit 1; }
# Vultr takes the first-boot data base64-encoded, read from the file, never an argument.
base64 < "$first_boot_data" | tr -d '\n' |
  jq -Rs --arg label "$server_name" --arg region "$location" --arg plan "$server_type" --argjson os_id "$os_id" \
    --argjson sshkey_id "$ssh_key_ids" \
    '{label: $label, hostname: $label, region: $region, plan: $plan, os_id: $os_id, sshkey_id: $sshkey_id,
      user_data: ., enable_ipv6: true, backups: "disabled", enable_vpc: false}' > "$body_file"
write_receipt() {  # write_receipt JSON: replaces the ownership file in one step
  [ -z "$ownership_file" ] || { printf '%s\n' "$1" > "$ownership_file.new" && mv -- "$ownership_file.new" "$ownership_file"; }
}
# The IDs before the create tell a lost answer's server apart. Never send the POST again.
ids_before=$(vultr_list instances instances | jq -c '[.[].id]')
if created=$(vultr_request POST instances "$body_file"); then
  server_id=$(jq -r '.instance.id' <<< "$created")
else
  echo "the create's answer failed; looking for a new server named $server_name" >&2
  sleep 30  # time for Vultr to list a create it accepted
  server_id=$(vultr_list instances instances | jq -r --argjson before "$ids_before" --arg n "$server_name" \
    '[.[] | select(.label == $n and (.id as $id | $before | index($id) | not)) | .id] | if length == 1 then .[0] else empty end')
  [ -n "$server_id" ] || { echo "no single new server named $server_name appeared; check the listing before any retry" >&2; exit 1; }
fi
write_receipt "$(jq -n --arg id "$server_id" --arg name "$server_name" '{id: $id, name: $name}')"
for _ in $(seq 1 90); do
  detail=$(vultr_request GET "instances/$server_id" | jq -c '.instance | {status, power_status, main_ip}')
  address=$(jq -r 'select(.main_ip != "0.0.0.0") | .main_ip // empty' <<< "$detail")
  if [ "$(jq -r '"\(.status) \(.power_status)"' <<< "$detail")" = "active running" ] && [ -n "$address" ]; then
    result=$(jq -n --arg id "$server_id" --arg name "$server_name" --arg a "$address" --arg t "$server_type" --arg l "$location" \
      --arg w "$wireguard_public_key" --arg i "$private_ip" \
      '{id: $id, name: $name, public_ipv4_address: $a, server_type: $t, location: $l, wireguard_public_key: $w, private_ip: $i}')
    write_receipt "$result"
    printf '%s\n' "$result"
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not active and running with a public IPv4 address after 15 minutes" >&2
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
listing=$(vultr_list instances instances)
if [ -n "$server_id" ]; then
  # Never fall back from a missing ID to a matching name.
  if ! jq -e --arg i "$server_id" 'any(.[]; .id == $i)' <<< "$listing" > /dev/null; then
    echo "no server with ID $server_id: nothing to destroy" >&2
    jq -n --arg i "$server_id" '{id: $i, deleted: true}'
    exit 0
  fi
elif [ -n "$server_name" ]; then
  server_id=$(jq -r --arg n "$server_name" '[.[] | select(.label == $n) | .id] | if length == 1 then .[0] else empty end' <<< "$listing")
  [ -n "$server_id" ] || { echo "expected exactly one server named $server_name" >&2; exit 1; }
else
  echo "give --server-id or --server-name" >&2; exit 2
fi
vultr_request DELETE "instances/$server_id" > /dev/null
# Deletion accepted is not deletion finished: wait until a whole listing lacks
# the ID. A failed listing stops the script; it never counts as "gone".
for _ in $(seq 1 60); do
  listing=$(vultr_list instances instances)
  if ! jq -e --arg i "$server_id" 'any(.[]; .id == $i)' <<< "$listing" > /dev/null; then
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
power_status_of() {  # the instance's power_status from a whole listing, or nothing when it is not listed
  vultr_list instances instances | jq -r --arg i "$server_id" '[.[] | select(.id == $i) | .power_status][0] // empty'
}
power_status=$(power_status_of)
[ -n "$power_status" ] || { echo "no server with ID $server_id" >&2; exit 1; }
[ "$power_status" = stopped ] || vultr_request POST "instances/$server_id/halt" > /dev/null
# The contract's 5 minutes; a halt took seconds on a real account.
for _ in $(seq 1 30); do
  if [ "$(power_status_of)" = stopped ]; then
    jq -n --arg i "$server_id" '{id: $i, power_state: "stopped"}'
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not stopped after 5 minutes" >&2
exit 1
```

The list script maps an instance's `label` to the contract's name, `main_ip` to its public IPv4 address
(`0.0.0.0`, before Vultr assigns one, to an empty address), and `power_status` to `power_state`: Vultr's
`running` and `stopped` are the contract's words. IDs are Vultr's instance UUIDs. Labels can repeat, so
every lifecycle action uses the ID, and the create records the account's instance IDs before the POST:
when the POST's answer is lost or refused, it looks once more after 30 seconds and accepts only exactly one
new ID with the exact label; otherwise it stops without a retry. Reason: another POST could duplicate an
accepted create. Vultr's exact answer for a plan a region has run out of is not verified, so the script
retries no error as a capacity refusal. The create asks for public networking with IPv6, no VPC
(`enable_vpc: false`), no automatic backups and no firewall group, and returns once the instance is
`active` and `running` with an address: that does not mean cloud-init and WireGuard have finished.

The list, create, destroy and power-off scripts above, with `util01`'s path (a shell with `SERVER_PROVIDER_API_TOKEN`
set) and a key whose service user had exactly the seven IAM actions in the table above, created a
`vc2-1c-1gb` instance in `ams` with first-boot data in 46 seconds (Debian 13; root SSH with the named key
and the first-boot data worked about 40 seconds later), listed it with `power_state` `running` and then
`stopped`, powered it off in 3 seconds and again, on the stopped server, at once, and deleted it in 1
second, on a real account (2026-11-12). A rerun of the destroy for the deleted ID counted as done. Before
the user had all seven actions, the same key was refused the SSH-key listing and the halt with HTTP 401
`Unauthorized IP address`. The price request answered `monthly_cost` 5 for `vc2-1c-1gb`, in US dollars:
the answer has no currency field.

The Stack's tests (`tests/vultr_provider_scripts_test.py`) run these blocks, with each `bash` on the test
machine, against a stand-in for Vultr's API, through the proxy and with the key, including a create whose
answer is lost and a listing of more than one page.

## Plan, region, and image

For the [server setup in chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md),
the smallest matching regular plans are `vc2-4c-8gb` for `app001` and `vc2-2c-4gb` for `db01`, `util01` and
`staging01`: 4 vCPUs/8 GB/160 GB and 2 vCPUs/4 GB/80 GB. The cheapest 1 GB and 2 GB plans fall below the
Stack's starting requirements. Use x64 plans, because the template's downloads are AMD64. Read
`GET http://127.0.0.1:8081/regions` and `GET http://127.0.0.1:8081/regions/REGION/availability?type=vc2`
before creation; Amsterdam is `ams`. Catalog presence does not reserve capacity.

**Prices.** `curl -sS 'http://127.0.0.1:8081/plans?type=vc2&per_page=500' | jq '.plans[] | select(.id == "vc2-2c-4gb") | {id, monthly_cost, hourly_cost, disk, locations}'`
gives the plan's `monthly_cost` and `hourly_cost` in US dollars (on 2026-11-12, `5` and `0.007` for
`vc2-1c-1gb`; the plan listing answers without a key too). Vultr bills a Cloud Compute server by the hour,
up to 672 hours a month. Neither the answer nor Vultr's billing page says whether tax or the public IPv4
address is included: show the person the numbers as Vultr's plan price and point to Vultr's price page for
tax. Show the current price before creation. Vultr's
[billing unit](https://docs.vultr.com/support/platform/billing/how-am-i-billed-for-my-servers) is at
least one hour, even for a shorter test, and
[stopped servers stay billed](https://docs.vultr.com/support/platform/billing/are-stopped-instances-still-billed-on-vultr)
until destroyed.

Use Debian 13 x64, which includes cloud-init and permits the first key login as `root`
(`server_image: Debian 13 x64 (trixie)`, the name in `GET http://127.0.0.1:8081/os`). The create script
resolves the name to Vultr's numeric `os_id` before each create, because an OS ID is not a release alias.
It passes the renderer's cloud-config base64-encoded as `user_data`
([cloud-init on Vultr](https://docs.vultr.com/how-to-deploy-a-vultr-server-with-cloudinit-userdata)).

Check [Account → Billing → Limits](https://docs.vultr.com/platform/billing/manage-account-limits/) for
instance and cost limits, allowing a replacement and `restore01` at the same time. Limits vary by account.

## First boot

In the copied `server_management_scripts/server_first_boot.cloud-config.yml`, insert these commands before `ufw default deny incoming`:

```sh
ufw --force delete allow 22
ufw --force delete allow 22/tcp
ufw --force delete allow OpenSSH
```

Move `systemctl enable --now wg-quick@wg0` before the two commands that remove the early INPUT guards.
Before removing those guards, check both `ufw-user-input` and `ufw6-user-input` for inherited public SSH accepts.
For example, this check covers the image's unrestricted single-port SSH rules:

```sh
for rules_command in iptables-save ip6tables-save; do
  if "$rules_command" | grep -E -- '-A ufw6?-user-input' |
    grep -- '--dport 22' | grep -- '-j ACCEPT' | grep -v -- '-i wg0'; then
    echo 'Unrestricted SSH rule remains' >&2
    exit 1
  fi
done
```

Keep the early guards until WireGuard runs and both chains reject public SSH. The same file is the
template that `util01`'s create renders, so the restore drill and the replacements get the correction too.
Pass the renderer's result, without further changes, to the create. After boot, connect over WireGuard.
Check `cloud-init status --wait --long`. Verify the expected WireGuard public key and address, and
`/etc/cloud/cloud-init.disabled`. The marker can make cloud-init report `disabled`; the status alone then
does not prove first boot finished. Check public TCP 22 from outside the server. Inspect first-boot service
ordering over the private connection. Never print the private key or cloud-init user data while collecting
proof. Reason: the Debian image can keep blanket SSH allows despite UFW's default-deny policy.

Run the first MMX configuration before any reboot or power test. If an earlier restart leaves private SSH
refused, destroy and recreate the Vultr server (the cause was not isolated; the failure was not seen after
the first MMX run).

Vultr's [VPC ranges](https://docs.vultr.com/support/products/network/can-i-specify-a-custom-network-address-range-for-my-vpc-network)
are configurable and can overlap `10.20.0.0/16`: inspect existing attachments before keeping the WireGuard
range. The [Vultr cloud-init datasource](https://docs.cloud-init.io/en/latest/reference/datasources/vultr.html)
reads HTTP at `169.254.169.254`. Keep cloud-init disabled after enrollment and keep the metadata HTTP block.
No other metadata-dependent agent was found on the checked Debian image; recheck failed units after a
reboot when changing images. Reason: provider-network routes must not compete with WireGuard, and metadata
keeps first-boot secrets.

## Keys and lifecycle

The coding agent registers a key from the desk, through the proxy, with the person's key:

```sh
jq -n --arg name 'util01, the mmhotline user' --arg ssh_key 'ssh-ed25519 AAAA... mmhotline@util01' \
  '{name: $name, ssh_key: $ssh_key}' |
  curl -sS --fail-with-body -X POST -H 'Content-Type: application/json' --data-binary @- \
  http://127.0.0.1:8081/ssh-keys | jq '.ssh_key | {id, name}'
```

Compare the listed `ssh_key` (`GET /ssh-keys`) with the key's line before using the name, and give each key
a name no other key has: the create accepts exactly one key per name. Register `util01`'s key before the
first drill, because `util01`'s key can list SSH keys but not add them.

For a power test, the coding agent stops and starts the instance from the desk:

```sh
./server_management_scripts/power_off_a_server_at_the_provider --server-id SERVER_ID
curl -sS --fail-with-body -X POST http://127.0.0.1:8081/instances/SERVER_ID/start
./server_management_scripts/list_the_servers_at_the_provider | jq '.servers[] | select(.id == "SERVER_ID")'
```

Wait for `power_state` `stopped` after the halt and `running` after the start. Vultr's
[CLI reference](https://docs.vultr.com/reference/vultr-cli/instance/stop) describes its stop, the same
`/halt`, as a graceful shutdown: confirm abrupt-cut behavior before counting a stop and start as a
sudden-power-loss test. Before stopping, record the enabled and active states of `ssh.service` and
`ssh.socket` over WireGuard, and check whether each active SSH unit starts after
`cloud-init-network.service`. After starting, require a new key-checked SSH connection over WireGuard, no
failed units, `wg0`, and `/etc/cloud/cloud-init.disabled`: `power_status` `running` alone does not pass.

Keep the shared [replacement](../operating_procedures/replace_a_server.md),
[removal](../operating_procedures/remove_a_server.md) and
[restore-drill](../operating_procedures/run_the_weekly_database_restore_drill.md) procedures.

## Console and rescue access

Open **Products → the instance → View Console**. No separate console activation is required.
Allow the console window to open, then test `root` with the shared root console password from the password manager.
The [web console](https://docs.vultr.com/vultr-web-console-faq) works without SSH or WireGuard, so a person can repair broken networking.

For a server that cannot boot, choose **Settings → Custom ISO → SystemRescue x64 → Attach ISO and Reboot**.
Follow [Vultr's rescue guide](https://docs.vultr.com/troubleshoot-your-vps-with-bootable-isos), using View Console to identify and repair the installed disk.
The rescue system has a separate firewall and starts SSH, so stop rescue SSH before mounting sensitive data.
Detach the ISO and reboot from disk after repair.
