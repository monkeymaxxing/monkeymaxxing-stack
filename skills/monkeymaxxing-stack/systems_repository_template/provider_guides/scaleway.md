# Scaleway Instances

Scaleway calls a server an **Instance**, a server type a **commercial type**, and a location a **zone**.
Follow the shared [script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts),
[enrollment contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run),
and [initial setup](../initial_setup/): accounts in
[chapter 4 (set up your accounts and lock your systems desk)](../initial_setup/04_set_up_your_accounts_and_lock_your_desk.md),
servers in [chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md).

## The provider's web console

The person sees the servers in the Scaleway console, at the Instances list:
<https://console.scaleway.com/instance/servers>.

## Credentials on the systems desk

The person owns the provider token; the coding agent reaches the provider
through the desk's API proxy, as
[Credentials on the systems desk](README.md#credentials-on-the-systems-desk)
says.

Set `systems_desk_provider_api_url: https://api.scaleway.com/` in `mmx_project_settings.yml`, including the trailing slash.
The person types the secret key on the laptop with the laptop key command below, and you move it
to the desk right after the bootstrap. To replace the key later, the person runs
`ssh -t desk01 set-up-outside-services personal-token server-provider --server-listing-path instance/v1/zones/fr-par-1/servers --token-header X-Auth-Token`.
A server listing uses `http://127.0.0.1:8081/instance/v1/zones/fr-par-1/servers`.

### The laptop key command

The values for [The laptop key command](README.md#the-laptop-key-command):

- **Script:** `~/example-setup/enter-the-scaleway-key`.
- **Values:** one, the API key's **secret key** of "The person's API key" below. The access key is not needed.
- **Shape:** a UUID: 36 characters, 8-4-4-4-12 hexadecimal digits with hyphens.
- **Read-only call:** `GET https://api.scaleway.com/instance/v1/zones/fr-par-1/servers?per_page=1` with `X-Auth-Token: SECRET_KEY`. HTTP 200 accepts the key.
- **Key file line:** the secret key.


Scaleway authenticates with the API key's secret key in `X-Auth-Token`, rather than an Authorization
bearer header. `--token-header X-Auth-Token` makes the command check the token with that header and write
the root-owned provider token file, which only the API proxy reads, as one line:

```
proxy_set_header X-Auth-Token "TOKEN";
```

See [Scaleway authentication](https://www.scaleway.com/en/developers/api). The five provider scripts use
`curl` and `jq` with the request function below, on the desk through the proxy and on `util01` with
`util01`'s own secret key, so neither needs Scaleway's command-line tool `scw`. Reason: an API request
needs only the secret key, while `scw` also needs the access key, the Organization's ID and a zone, which
`util01`'s jobs do not have.

### The person's API key

The person makes an API key for an IAM application `example-systems-alex`, with the person's desk account
name in place of `alex`, scoped to the system's Project, with the permission sets `InstancesFullAccess`,
`SSHKeysFullAccess` and `BlockStorageReadOnly`. The secret key goes into the proxy as above.

### util01's API key

`util01` creates, lists, powers off and deletes Instances with its own API key, for an IAM application
`example-systems-util01` that belongs to the Organization and not to a person: the weekly restore drill
creates and deletes `restore01`, the daily leftover check lists the Instances, and the triage agent's
server replacements power a failed server off, create its replacement and delete the failed one. Its
policy grants, in the system's Project only:

| Permission set | Why `util01` needs it |
| --- | --- |
| `InstancesFullAccess` | Create, list, power off and delete Instances, and their disks, flexible IPs and first-boot data |
| `SSHKeysReadOnly` | Read the public key the create names |

The price script reads Scaleway's public product catalog, which needs no key, so it needs no permission set.

Scaleway's [permission sets](https://www.scaleway.com/en/docs/iam/reference-content/permission-sets/)
(checked 2026-11-12 in the page's source, `pages/iam/reference-content/permission-sets.mdx` in Scaleway's
`docs-content` repository) describe `InstancesFullAccess` as "Full access to create, read, list, edit and delete
Instances", `SSHKeysReadOnly` as "Read access to SSH keys", and offer `InstancesServerStop` and
`InstancesServerStart` for stopping and starting alone; nothing narrower than `InstancesFullAccess` creates
and deletes, so `InstancesFullAccess` is the smallest set for the scripts, and it already includes the
power-off. A policy rule scoped to one Project is the smallest scope Scaleway offers: keep other systems in
another Project. `set-up-outside-services secrets` asks for the secret key at a hidden prompt and saves it in
the vault as `util01_provider_api_token`; the scripts read it from `SERVER_PROVIDER_API_TOKEN`. `util01`
needs no other setting and no program beyond Debian's `curl` and the Stack's `jq`. A key made before this
Stack version had these two sets already, so a running system widens nothing.

To replace the key after a leak, the person makes a new API key for the same application, runs
`set-up-outside-services secrets --replace util01_provider_api_token`, the coding agent runs
`every_server`, and the person deletes the old key in **IAM → API keys**.

## The provider scripts' request function

Put the function, with the values above it, at the top of each script, after `#!/bin/bash` and
`set -euo pipefail`. Copy the Project's ID from the Scaleway console's **Project settings** into
`scaleway_project_id`. The function goes through the API proxy where `SERVER_PROVIDER_API_TOKEN` is
empty (the coding agent on a desk) and sends the secret key itself where it is set (`util01`'s jobs, and
the person's own terminal during the first desk's bootstrap). It works in Debian's `bash` and in macOS's
`bash` 3.2.

```bash
scaleway_api_address=https://api.scaleway.com/   # systems_desk_provider_api_url
scaleway_project_id=00000000-0000-4000-8000-000000000000   # the Project's ID
# Every zone that has Scaleway Instances (checked 2026-11-12). The list
# script lists all of them, and the create refuses any other zone.
scaleway_zones='fr-par-1 fr-par-2 fr-par-3 nl-ams-1 nl-ams-2 nl-ams-3 pl-waw-1 pl-waw-2 pl-waw-3 it-mil-1'

# scaleway_request METHOD PATH [BODY_FILE [CONTENT_TYPE]]
# Sends one request to PATH under the API address, such as
# "instance/v1/zones/fr-par-1/servers", prints the answer's body, and fails
# on an answer that is not 2xx, without printing the body.
scaleway_request() {
  local method=$1 path=$2 body_file=${3:-} content_type=${4:-application/json} answer http_status_code
  local -a body_arguments=()
  [ -z "$body_file" ] || body_arguments=(--header "Content-Type: $content_type" --data-binary "@$body_file")
  answer=$(mktemp)
  if [ -z "${SERVER_PROVIDER_API_TOKEN:-}" ]; then
    http_status_code=$(curl --silent --show-error --connect-timeout 10 --max-time 120 \
      --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' \
      "http://127.0.0.1:8081/$path") || true
  else
    # The secret key goes through standard input, never the command line,
    # which other accounts on the server can read.
    http_status_code=$(printf 'X-Auth-Token: %s\n' "$SERVER_PROVIDER_API_TOKEN" |
      curl --silent --show-error --connect-timeout 10 --max-time 120 --header @- \
        --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' \
        "$scaleway_api_address$path") || true
  fi
  case "$http_status_code" in
    2??) cat -- "$answer"; rm -f -- "$answer" ;;
    *) printf 'Scaleway answered %s %s with HTTP %s (body withheld)\n' "$method" "${path%%\?*}" "$http_status_code" >&2
       rm -f -- "$answer"; return 1 ;;
  esac
}

# scaleway_list PATH KEY
# Prints every page of a listing, such as
# scaleway_list "instance/v1/zones/fr-par-1/servers?project=$scaleway_project_id" servers,
# as one JSON list, or one object for a listing that answers an object.
# A failed page fails the whole listing.
scaleway_list() {
  local path=$1 key=$2 separator='?' page=1 answer pages=''
  case "$path" in *\?*) separator='&' ;; esac
  while :; do
    answer=$(scaleway_request GET "$path${separator}per_page=100&page=$page") || return 1
    # Each page is one line; jq joins the lines at the end. A growing list is
    # never a command-line argument: it can pass the 131,072 bytes Linux
    # allows for one.
    pages+=$(jq -c --arg key "$key" '.[$key]' <<< "$answer")$'\n'
    [ "$(jq --arg key "$key" '.[$key] | length' <<< "$answer")" -eq 100 ] || break
    page=$((page + 1))
  done
  printf '%s' "$pages" | jq -cs 'if (.[0] | type) == "array" then add else .[0] end'
}

# scaleway_servers: every server of the Project, in every zone, as one JSON list.
scaleway_servers() {
  local zone servers all=''
  for zone in $scaleway_zones; do
    servers=$(scaleway_list "instance/v1/zones/$zone/servers?project=$scaleway_project_id" servers) || return 1
    all+=$servers$'\n'
  done
  printf '%s' "$all" | jq -cs 'add'
}
```

The time limits are 10 seconds to connect and 120 seconds for an answer. The function withholds an error's
body because an error can repeat the request's first-boot data. Never pass the secret key or first-boot
data as command-line arguments.

## The five provider scripts

Each script is `#!/bin/bash`, `set -euo pipefail`, the values and the functions above, then its own part
below, in `server_management_scripts/` under the contract's names.

`list_the_servers_at_the_provider`:

```bash
scaleway_servers | jq '{servers: [.[] | {id, name,
    public_ipv4_address: ([.public_ips[]? | select(.family == "inet") | .address][0] // .public_ip.address // ""),
    power_state: ({"running": "running", "stopped": "stopped", "stopped in place": "stopped"}[.state] // .state)}]}'
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
body_file=$(mktemp); user_data_file=$(mktemp); chmod 600 "$body_file" "$user_data_file"
# Clear the first-boot data after reading it, also on failure.
trap ': > "$first_boot_data"; rm -f -- "$body_file" "$user_data_file"' EXIT
[ "${#ssh_key_names[@]}" -ge 1 ] || { echo "give at least one --ssh-key-name" >&2; exit 2; }
case " $scaleway_zones " in *" $location "*) ;; *) echo "$location is not in scaleway_zones" >&2; exit 2 ;; esac
z="instance/v1/zones/$location"
# Scaleway's metadata can hand every key of the Project to cloud-init, so
# the first-boot data turns that off and names the keys for root itself.
if grep -Eq '^(users|allow_public_ssh_keys):' "$first_boot_data"; then
  echo "the first-boot data already sets users or allow_public_ssh_keys" >&2; exit 1
fi
{ cat -- "$first_boot_data"; printf 'allow_public_ssh_keys: false\nusers:\n  - name: root\n    ssh_authorized_keys:\n'; } > "$user_data_file"
for key_name in "${ssh_key_names[@]}"; do
  # A name can repeat at Scaleway: accept exactly one key by that name.
  public_key=$(scaleway_request GET "iam/v1alpha1/ssh-keys?project_id=$scaleway_project_id&page_size=100&name=$(jq -rn --arg n "$key_name" '$n | @uri')" |
    jq -r --arg n "$key_name" '[.ssh_keys[] | select(.name == $n) | .public_key] | if length == 1 then .[0] else empty end')
  [ -n "$public_key" ] || { echo "expected exactly one SSH key named $key_name" >&2; exit 1; }
  jq -rn --arg k "$public_key" '"      - \($k | tojson)"' >> "$user_data_file"
done
# The root disk is the commercial type's whole local disk. Types without a
# local disk need block storage, which these scripts do not create.
disk_bytes=$(scaleway_list "$z/products/servers" servers | jq -r --arg t "$server_type" \
  '.[$t] | select(.per_volume_constraint.l_ssd.max_size > 0) | [.volumes_constraint.max_size, .per_volume_constraint.l_ssd.max_size] | min')
[ -n "$disk_bytes" ] || { echo "$server_type in $location has no local disk; choose a type with one" >&2; exit 1; }
jq -n --arg name "$server_name" --arg commercial_type "$server_type" --arg image "$image" --arg project "$scaleway_project_id" \
  --argjson size "$disk_bytes" \
  '{name: $name, commercial_type: $commercial_type, image: $image, project: $project, dynamic_ip_required: false,
    volumes: {"0": {size: $size, volume_type: "l_ssd"}}}' > "$body_file"
write_receipt() {  # write_receipt JSON: replaces the ownership file in one step
  [ -z "$ownership_file" ] || { printf '%s\n' "$1" > "$ownership_file.new" && mv -- "$ownership_file.new" "$ownership_file"; }
}
# The IDs before the create tell a lost answer's server apart. Never send the POST again.
ids_before=$(scaleway_list "$z/servers?project=$scaleway_project_id" servers | jq -c '[.[].id]')
if created=$(scaleway_request POST "$z/servers" "$body_file"); then
  server_id=$(jq -r '.server.id' <<< "$created")
else
  echo "the create's answer failed; looking for a new server named $server_name" >&2
  sleep 30  # time for Scaleway to list a create it accepted
  server_id=$(scaleway_list "$z/servers?project=$scaleway_project_id" servers | jq -r --argjson before "$ids_before" --arg n "$server_name" \
    '[.[] | select(.name == $n and (.id as $id | $before | index($id) | not)) | .id] | if length == 1 then .[0] else empty end')
  [ -n "$server_id" ] || { echo "no single new server named $server_name appeared; check the listing before any retry" >&2; exit 1; }
fi
write_receipt "$(jq -n --arg id "$server_id" --arg name "$server_name" '{id: $id, name: $name}')"
# Scaleway creates the server stopped: the first-boot data and the address
# go on before the first boot.
scaleway_request PATCH "$z/servers/$server_id/user_data/cloud-init" "$user_data_file" text/plain > /dev/null
# The flexible IPv4 address carries the server's ID as a tag, so the destroy
# finds it even when this answer is lost.
jq -n --arg project "$scaleway_project_id" --arg server "$server_id" \
  '{project: $project, type: "routed_ipv4", server: $server, tags: ["server-\($server)"]}' > "$body_file"
scaleway_request POST "$z/ips" "$body_file" > /dev/null
printf '{"action": "poweron"}\n' > "$body_file"
scaleway_request POST "$z/servers/$server_id/action" "$body_file" > /dev/null
for _ in $(seq 1 90); do
  detail=$(scaleway_request GET "$z/servers/$server_id")
  address=$(jq -r '[.server.public_ips[]? | select(.family == "inet") | .address][0] // empty' <<< "$detail")
  if [ "$(jq -r .server.state <<< "$detail")" = running ] && [ -n "$address" ]; then
    result=$(jq -n --arg id "$server_id" --arg name "$server_name" --arg a "$address" --arg t "$server_type" --arg l "$location" \
      --arg w "$wireguard_public_key" --arg i "$private_ip" \
      '{id: $id, name: $name, public_ipv4_address: $a, server_type: $t, location: $l, wireguard_public_key: $w, private_ip: $i}')
    write_receipt "$result"
    printf '%s\n' "$result"
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not running with a public IPv4 address after 15 minutes" >&2
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
listing=$(scaleway_servers)
# Never fall back from a missing ID to a matching name.
if [ -z "$server_id" ]; then
  [ -n "$server_name" ] || { echo "give --server-id or --server-name" >&2; exit 2; }
  server_id=$(jq -r --arg n "$server_name" '[.[] | select(.name == $n) | .id] | if length == 1 then .[0] else empty end' <<< "$listing")
  [ -n "$server_id" ] || { echo "expected exactly one server named $server_name" >&2; exit 1; }
fi
server=$(jq -c --arg i "$server_id" '[.[] | select(.id == $i)][0] // empty' <<< "$listing")
# The server's flexible IPs, by its tag or its attachment, in every zone:
# an IP whose server is already gone still costs money.
ips='[]'
for zone in $scaleway_zones; do
  ips=$(scaleway_list "instance/v1/zones/$zone/ips?project=$scaleway_project_id" ips | jq -c --argjson all "$ips" --arg i "$server_id" --arg zone "$zone" \
    '$all + [.[] | select((.tags | index("server-\($i)")) or .server.id == $i) | {id, zone: $zone}]')
done
if [ -n "$server" ]; then
  zone=$(jq -r .zone <<< "$server"); z="instance/v1/zones/$zone"
  volumes=$(jq -c '[.volumes[]? | .id]' <<< "$server")
  body_file=$(mktemp); trap 'rm -f -- "$body_file"' EXIT
  case "$(jq -r .state <<< "$server")" in
    running | 'stopped in place')
      # terminate deletes the server with its local disks; Scaleway refuses
      # a plain DELETE of a server stopped in place.
      printf '{"action": "terminate"}\n' > "$body_file"
      scaleway_request POST "$z/servers/$server_id/action" "$body_file" > /dev/null ;;
    stopped)
      scaleway_request DELETE "$z/servers/$server_id" > /dev/null ;;
    *) echo "server $server_id is $(jq -r .state <<< "$server"); run the destroy again once it has stopped or started" >&2; exit 1 ;;
  esac
  # Deletion accepted is not deletion finished: wait until a whole listing
  # lacks the ID. A failed listing stops the script; it never counts as "gone".
  for attempt in $(seq 1 61); do
    [ "$attempt" -le 60 ] || { echo "server $server_id is still listed after 10 minutes" >&2; exit 1; }
    scaleway_list "$z/servers?project=$scaleway_project_id" servers | jq -e --arg i "$server_id" 'any(.[]; .id == $i)' > /dev/null || break
    sleep 10
  done
  # A disk a stopped server's delete leaves behind.
  for volume_id in $(jq -r '.[]' <<< "$volumes"); do
    if scaleway_list "$z/volumes?project=$scaleway_project_id" volumes | jq -e --arg v "$volume_id" 'any(.[]; .id == $v)' > /dev/null; then
      scaleway_request DELETE "$z/volumes/$volume_id" > /dev/null
    fi
  done
else
  echo "no server with ID $server_id: nothing to destroy but its addresses" >&2
fi
for ip in $(jq -r '.[] | "\(.zone)/\(.id)"' <<< "$ips"); do
  # terminate can release the address itself: delete only what is still listed.
  if scaleway_list "instance/v1/zones/${ip%%/*}/ips?project=$scaleway_project_id" ips | jq -e --arg i "${ip#*/}" 'any(.[]; .id == $i)' > /dev/null; then
    scaleway_request DELETE "instance/v1/zones/${ip%%/*}/ips/${ip#*/}" > /dev/null
  fi
done
jq -n --arg i "$server_id" '{id: $i, deleted: true}'
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
zone=$(scaleway_servers | jq -r --arg i "$server_id" '[.[] | select(.id == $i) | .zone][0] // empty')
[ -n "$zone" ] || { echo "no server with ID $server_id" >&2; exit 1; }
state_of() {  # the server's state from a whole listing of its zone
  scaleway_list "instance/v1/zones/$zone/servers?project=$scaleway_project_id" servers | jq -r --arg i "$server_id" '[.[] | select(.id == $i) | .state][0] // empty'
}
body_file=$(mktemp); trap 'rm -f -- "$body_file"' EXIT
printf '{"action": "stop_in_place"}\n' > "$body_file"
case "$(state_of)" in
  stopped | 'stopped in place') ;;
  *) scaleway_request POST "instance/v1/zones/$zone/servers/$server_id/action" "$body_file" > /dev/null ;;
esac
# The contract's 5 minutes.
for _ in $(seq 1 30); do
  case "$(state_of)" in
    stopped | 'stopped in place') jq -n --arg i "$server_id" '{id: $i, power_state: "stopped"}'; exit 0 ;;
  esac
  sleep 10
done
echo "server $server_id is not stopped after 5 minutes" >&2
exit 1
```

The list script's `power_state` is `running` for a server's `state` `running`, and `stopped` for `stopped`
and `stopped in place`; `starting`, `stopping` and `locked` pass through as they are. IDs are Scaleway's
server UUIDs; the server's zone comes from the listing, so the scripts need nothing beyond the ID. Names
can repeat, so every lifecycle action uses the ID, and the create records the zone's server IDs before the
POST: when the POST's answer is lost or refused, it looks once more after 30 seconds and accepts only
exactly one new ID with the exact name; otherwise it stops without a retry. Reason: another POST could
duplicate an accepted create. Scaleway's exact answer for a type a zone has run out of is not verified, so
the script retries no error as a capacity refusal.

The create makes the server stopped, uploads the first-boot data as the `cloud-init` key, attaches a new
flexible IPv4 address tagged `server-ID`, and only then powers the server on. Reason: first boot consumes
the first-boot data, and a flexible address keeps the server's public address across a stop, which the
dynamic address would not. The power-off is `stop_in_place`, which keeps the server on its machine with its
disk: the replacement needs the failed server stopped and its disk kept, not the machine released.
The destroy terminates the server, which deletes it with its local disks but keeps its flexible IPs
(Scaleway refuses a plain delete of a server stopped in place), then deletes every flexible IP tagged with
its ID or attached to it. A rerun after a failure finds the leftover addresses by the tag.

The four scripts above, with `util01`'s path (a shell with `SERVER_PROVIDER_API_TOKEN` set), created a `DEV1-S`
server in `nl-ams-1` with first-boot data in 24 seconds (root SSH with the named key and the first-boot
data worked 29 seconds later), stopped it in place in 24 seconds and destroyed it with its disk and address
in 17 seconds, on a real Project (2026-11-12). A rerun of the destroy for a server already gone removed its
leftover address. The same create in `fr-par-1` was refused with HTTP 403 `quotas_exceeded`: quotas are
per zone. Deleting a fully `stopped` server (stopped from the console, not by the script) is not yet proved.

The Stack's tests (`tests/scaleway_provider_scripts_test.py`) run these blocks, with each `bash` on the
test machine, against a stand-in for Scaleway's API, through the proxy and with the secret key, including a
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
case " $scaleway_zones " in *" $location "*) ;; *) echo "unknown zone $location" >&2; exit 1 ;; esac
# The public catalog needs no key, so it is read without one: util01's key
# then needs no permission set for it.
price='' page=1
while [ -z "$price" ]; do
  answer=$(curl --silent --show-error --fail --connect-timeout 10 --max-time 120 \
    "${scaleway_api_address}product-catalog/v2alpha1/public-catalog/products?product_types=instance&zone=$location&page_size=100&page=$page") ||
    { echo "Scaleway's product catalog did not answer" >&2; exit 1; }
  price=$(jq -c --arg t "$server_type" '[.products[] | select(.product == $t and (.unit_of_measure | tostring | test("hour")))
      | .price.retail_price] | if length == 1 then .[0] else empty end' <<< "$answer")
  [ -n "$price" ] || [ "$(jq '.products | length' <<< "$answer")" -eq 100 ] || break
  page=$((page + 1))
done
[ -n "$price" ] || { echo "Scaleway's catalog has no hourly price for $server_type in $location" >&2; exit 1; }
hourly=$(jq -r '((.units | tonumber) + (.nanos // 0) / 1000000000) | tostring' <<< "$price")
echo "Scaleway's catalog gives an hourly price only: $hourly an hour times 730 hours, an average month; it does not say whether VAT is included, and the flexible IPv4 address is priced apart and left out" >&2
jq --arg t "$server_type" --arg l "$location" \
  '{server_type: $t, location: $l, monthly_price: (((.units | tonumber) + (.nanos // 0) / 1000000000) * 730 * 100 | round / 100 | tostring),
    currency: .currency_code}' <<< "$price"
```

The price script reads the same catalog as the [Prices](#commercial-type-zone-and-image) paragraph below,
and turns the hourly price into a monthly estimate with the hours of an average month, as the
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts) says.

## Commercial type, zone, and image

Use x86_64 types with a local disk, because the create makes the root disk on the type's local disk:
`DEV1-M` (3 vCPUs, 4 GB RAM, 40 GB) for the ordinary roles and `DEV1-L` (4 vCPUs, 8 GB, 80 GB) for
`app001`, as [chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md)
asks. `DEV1-S`'s 2 GB of RAM and 20 GB of disk are too small. Check stock with
`GET http://127.0.0.1:8081/instance/v1/zones/fr-par-1/products/servers/availability`, in `nl-ams-1`,
`fr-par-1` or `pl-waw-1`. ARM types need different images, tools and containers.

**Prices.** Scaleway's public product catalog gives each type's price per hour, and needs no credential:

```sh
curl -sS 'https://api.scaleway.com/product-catalog/v2alpha1/public-catalog/products?product_types=instance&zone=fr-par-1&page_size=100&page=1' |
  jq '.products[] | select(.product == "DEV1-M") | {product, description, price: .price.retail_price, unit_of_measure}'
```

Read `page=2` too when the type is not on the first page. `retail_price` is `units` plus `nanos`
billionths of the `currency_code` (euros), per `unit_of_measure` (one hour); the catalog gives no monthly
price, so show the person the hourly price and 730 times it as a month's estimate. The answer does not say
whether VAT is included: show the number as Scaleway's catalog price and point the person to the
[price page](https://www.scaleway.com/en/pricing/virtual-instances/) for tax. The flexible IPv4 address
is priced apart from the server: the same catalog's product `Zonal Flexible IPv4` (without
`product_types`) answered 0.005 euros with `unit_of_measure` `ip`, which does not name the period. On
2026-11-12 the catalog answered `DEV1-S` in `fr-par-1` at 0.008976 euros an hour, on page 2, and the
Instance API's own `hourly_price` and `monthly_price` in `products/servers` answered `0.0` for every type:
never show those to the person.

Use Debian 13: `server_image: debian_trixie`, the Marketplace image label, which the create passes as it
is, and Scaleway resolves to the zone's current image. Scaleway's Debian image includes cloud-init and uses
[root for SSH](https://www.scaleway.com/en/docs/instances/how-to/connect-to-instance/).

Check [Organization quotas](https://www.scaleway.com/en/docs/organizations-and-projects/organization/organization-quotas/)
for the type, total Instances, disks, and IPs, allowing a replacement and `restore01` at the same time.
Validate identity and payment before requesting increases. Quotas do not reserve stock.

## Network and metadata

Attach no Private Network. Scaleway [Private Networks](https://www.scaleway.com/en/docs/vpc/how-to/create-private-network/)
support custom ranges and automatically generated /22 subnets, which can overlap WireGuard's `10.20.0.0/16`.
Leave the automatically assigned [security group](https://www.scaleway.com/en/docs/instances/how-to/use-security-groups/)
permissive, so UFW owns the restrictions. Reason: provider filters can block WireGuard or hide broken guest rules.

Scaleway's [metadata addresses](https://docs.cloud-init.io/en/latest/reference/datasources/scaleway.html)
are `169.254.42.42` and `fd00:42::42`, not the EC2 addresses the template blocks. In the copied
`server_management_scripts/server_first_boot.cloud-config.yml`, replace `169.254.169.254` with
`169.254.42.42` and `fd00:ec2::254` with `fd00:42::42` in the metadata deny commands, and list both
addresses in every applicable UFW rule list in `roles/every_server/main.yml`: MMX removes outgoing rules
absent from the managed list. The create script adds `allow_public_ssh_keys: false` and root's keys to
the rendered data itself.

After first boot, manage `scw-fetch-ssh-keys.service`, `scw-generate-ssh-keys.service`, and
`scw-signal-booted.service` as stopped, disabled, and masked in `every_server`, and clear only those units'
failed states. Reason: blocked metadata makes them fail after a reboot. MMX owns the authorized keys;
preserve host keys. Check that `/etc/cloud/cloud-init.disabled` exists and read the WireGuard public key to
confirm enrollment; `cloud-init status` reports `disabled` after the Stack creates the marker.

## Keys and lifecycle

The coding agent registers a key from the desk, through the proxy, with the person's key:

```sh
jq -n --arg name 'util01, the mmhotline user' --arg public_key 'ssh-ed25519 AAAA... mmhotline@util01' \
  --arg project_id PROJECT_ID '{name: $name, public_key: $public_key, project_id: $project_id}' |
  curl -sS --fail-with-body -X POST -H 'Content-Type: application/json' --data-binary @- \
  http://127.0.0.1:8081/iam/v1alpha1/ssh-keys | jq '{id, name, fingerprint}'
```

Compare the listed `public_key` with the key's line before using the name, and give each key a name no
other key has: the create accepts exactly one key per name. Register `util01`'s key before the first
drill, because `util01`'s key can read keys but not add them.

For a power test, the coding agent stops and starts the server from the desk:

```sh
./server_management_scripts/power_off_a_server_at_the_provider --server-id SERVER_ID
printf '{"action": "poweron"}' | curl -sS --fail-with-body -X POST -H 'Content-Type: application/json' \
  --data-binary @- http://127.0.0.1:8081/instance/v1/zones/ZONE/servers/SERVER_ID/action
./server_management_scripts/list_the_servers_at_the_provider | jq '.servers[] | select(.id == "SERVER_ID")'
```

Wait for `power_state` `stopped`, then `running`. Whether `stop_in_place` cuts the power or shuts the
operating system down is not checked, so keep the sudden-power-loss test unproved until it is. A server
stopped in place is still billed.

Use the shared [replacement](../operating_procedures/replace_a_server.md),
[removal](../operating_procedures/remove_a_server.md), and
[restore-drill](../operating_procedures/run_the_weekly_database_restore_drill.md) procedures.

## Console and rescue access

Scaleway's [serial console](https://www.scaleway.com/en/docs/instances/how-to/use-serial-console/)
needs a guest password set beforehand. Apply the Stack's shared root console password,
then open **CPU & GPU Instances**, select the zone and server, and click **Console**.
Prove root login before marking `provider_console_and_backup_mmhotline_logins` complete.
Reason: serial access survives guest network failure.

For a failed boot, power off, select **Advanced settings → Use rescue image**,
save, and power on. Follow [boot modes](https://www.scaleway.com/en/docs/instances/how-to/use-boot-modes/).
Inspect the original disk read-only first. Rescue has separate network and firewall
settings, so check rescue access before handling protected data.
After repair, power off and select **Use local boot** before starting the server.
Reason: rescue boots a separate operating system rather than the installed disk.
