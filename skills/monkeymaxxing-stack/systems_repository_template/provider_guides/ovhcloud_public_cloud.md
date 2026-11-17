# OVHcloud

OVHcloud calls a server an **instance** and a size a **flavor**. Follow the shared
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts),
[enrollment contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run),
and [initial setup](../initial_setup/).

## VPS or Public Cloud: by how long the server stays

OVHcloud sells two kinds of server. Choose by how long the server will run:

- **A server meant to stay is a VPS,** billed by the month: the first
  servers (`app001`, `db01`, `util01`), a systems desk at OVHcloud, and any
  later server the team keeps, such as a second app server.
- **A server the Stack creates and removes again is a Public Cloud
  instance,** billed by the hour: `restore01` for the restore drill and row
  recovery, a replacement built during a repair, and app servers added for
  the load.

Prices in the US, month to month, read on 2026-11-17. A VPS includes the
daily backup that OVHcloud requires with it:

| Size | VPS | Public Cloud | A VPS is cheaper after |
| --- | --- | --- | --- |
| 2 vCPU, 4 GB | VPS-1, $5.85 a month | d2-4, $0.0256 an hour | about 9.5 days |
| 4 vCPU, 8 GB, the app server | VPS-2, $10.60 a month | b2-15, $0.1663 an hour | about 2.7 days |

Before you create a server, show the person both prices, and say which
kind you chose and why.

Two things to know about a VPS:

- **It is billed by the month,** so a VPS for a server that lives for
  minutes, such as `restore01`, costs a whole month.
- **Only the person can end it.** Ending a VPS takes a token that OVHcloud
  emails to the account's admin contact. Your destroy script requests the
  termination (`POST /vps/NAME/terminate`) and tells the person to confirm
  it from that email; it never reports the server as gone.

How you make a VPS, through the API proxy with the person's credential and
after the person approves the price:

1. Pick a datacenter with stock. The public, credential-free
   `GET /vps/order/rule/datacenter?ovhSubsidiary=US&planCode=PLAN` lists
   each datacenter as available or out of stock; the US has two,
   `US-EAST-VA` and `US-WEST-OR`.
   Order it with the order cart: `POST /order/cart`, then
   `POST /order/cart/CART_ID/vps` with the plan, such as `vps-2027-model1`,
   the cart's required configuration, and the plan's required options:
   the Standard automated backup (`automatedBackup`), the operating system
   (`os`) and the storage (`storage`), as the public catalog's
   `addonFamilies` mark them `mandatory`; then
   `POST /order/cart/CART_ID/checkout`. The first month's backup is free.
   If checkout cannot pay
   by API, the person places the same order in the console.
2. Rebuild it with `POST /vps/NAME/rebuild`: the newest Debian 13
   `imageId`, the desk's `publicSshKey`, `doNotSendPassword: true`, and a
   `postInstallScript`. That script runs once, as a shell script, after the
   install, so it cannot be the first-boot data itself, which is
   cloud-init's settings. The script saves the first-boot data as
   cloud-init's local data, `/var/lib/cloud/seed/nocloud/user-data` with an
   empty `meta-data` beside it, and runs `cloud-init clean --reboot`, so
   cloud-init applies the data at the next boot as on a Public Cloud
   instance.
3. Until that reboot, public SSH accepts only the desk's key, with no
   password. Check on the first VPS that after the reboot public TCP 22 is
   closed and the server has joined WireGuard. Then record the server in
   the inventory as usual.

**The desk stays outside production's location,** so a production
outage leaves the team's tools working. When that location has no VPS in
stock, make the desk a Public Cloud `d2-4` there, billed by the hour, and
move it to a VPS with
[Rebuild a systems desk](../operating_procedures/rebuild_a_systems_desk.md)
once stock returns. Never put the desk in production's location to save
money.

Your provider scripts keep creating Public Cloud instances, because the
servers they create are temporary. When `create_a_server_at_the_provider`
is given a VPS's server type, such as for the replacement of a failed VPS,
it creates a Public Cloud flavor at least as large: `d2-4` for VPS-1,
`b2-15` for VPS-2. After the repair, recommend moving the replacement back
to a VPS with [Replace a server](../operating_procedures/replace_a_server.md):
it is permanent now.

## The provider's web console

The person sees the servers in the OVHcloud Control Panel of the account's region:
<https://manager.us.ovhcloud.com/> for OVHcloud US, <https://manager.eu.ovhcloud.com/> for Europe, and
<https://manager.ca.ovhcloud.com/> for Canada. Open **Public Cloud**, the system's project, then **Instances**.

## Credentials on the systems desk

OVHcloud's API signs each request with a secret, not with a token in a header. The desk's
**API proxy** does the signing: it listens on
`http://127.0.0.1:8081/`, the same address as at the other providers, signs each request
with the person's credential, and sends it to OVHcloud. The coding agent uses the credential without reading it.

Set both settings in `mmx_project_settings.yml`, with the address of the OVHcloud site where the account was made:

```yaml
systems_desk_provider_api_url: https://api.us.ovhcloud.com/1.0/
systems_desk_provider_api_authentication: ovhcloud_signed_requests
```

| OVHcloud site | `systems_desk_provider_api_url` | The page that makes a credential |
| --- | --- | --- |
| OVHcloud US (`us.ovhcloud.com`) | `https://api.us.ovhcloud.com/1.0/` | `https://api.us.ovhcloud.com/createToken/` |
| OVHcloud Europe (`ovhcloud.com`) | `https://eu.api.ovh.com/1.0/` | `https://www.ovh.com/auth/api/createToken` |
| OVHcloud Canada (`ca.ovhcloud.com`) | `https://ca.api.ovh.com/1.0/` | `https://ca.ovh.com/auth/api/createToken` |

An OVHcloud credential has three values, which OVHcloud's page shows once: the **Application Key**, the
**Application Secret**, and the **Consumer Key**. The access rules on the page limit the credential to one
Public Cloud project. `SERVER_PROVIDER_API_TOKEN` holds the three values joined with colons, in that order:
`APPLICATION_KEY:APPLICATION_SECRET:CONSUMER_KEY`.

### The person's credential

1. The person makes the OVHcloud account on the site for the team's region, and saves the login and its
   two-step codes in the team's password manager. The whole team uses this one account; each person makes
   their own credential in it, named after them.
2. The person creates the Public Cloud project: in OVHcloud's Control Panel, **Public Cloud**, then
   **Create a project**. The coding agent asks the person for the project's ID, the 32 letters and digits
   under the project's name. The ID is not a secret. The coding agent writes it at the top of each
   provider script as `ovhcloud_project_id`.
3. The coding agent gives the person the link below, with the site's page from the table and the
   project's ID in place of `PROJECT_ID`. The link fills in the access rules: everything inside the one
   project, plus ordering, rebuilding and ending VPS servers (`/order/cart` and `/vps`), and nothing else
   in the account. The laptop uses the same credential to make the first desk.

   ```text
   https://api.us.ovhcloud.com/createToken/?GET=/cloud/project/PROJECT_ID&GET=/cloud/project/PROJECT_ID/*&POST=/cloud/project/PROJECT_ID/*&PUT=/cloud/project/PROJECT_ID/*&DELETE=/cloud/project/PROJECT_ID/*&GET=/order/cart/*&POST=/order/cart&POST=/order/cart/*&GET=/vps&GET=/vps/*&POST=/vps/*
   ```

   The createToken page has its own sign-in form and ignores a browser that is already signed in to the
   Control Panel, so the person types the OVHcloud login and password on that page.
   On the page the person logs in, sets **Application name** to `example_systems: alex's systems desk`,
   with the person's desk account name in place of `alex`, **Application description** to
   `The systems desk creates, lists and deletes servers`, and **Validity** to **Unlimited**, and presses
   **Create keys**. Reason for Unlimited: the page's default is one day, and the proxy would stop working
   the next day. The person replaces the credential instead, below.
4. OVHcloud shows the three values once, so the person types them at once into the laptop key command
   below. You move them to the desk right after the bootstrap.

5. To replace the credential later, the person runs
   `ssh -t desk01 set-up-outside-services personal-token server-provider --server-listing-path cloud/project/PROJECT_ID/instance`.
   The command asks for the Application Key, the Application Secret and the Consumer Key, each at a hidden
   prompt, checks them with a signed listing of the project's servers at OVHcloud, and only then writes
   `/etc/systems-desk/provider-api-signing-credential.json`, root:root, mode `0600`, restarts the API signing
   proxy, and checks the same listing through `http://127.0.0.1:8081/`. When a check fails, the proxy keeps its
   old credential.

### The laptop key command

The values for [The laptop key command](README.md#the-laptop-key-command):

- **Script:** `~/example-setup/enter-the-ovhcloud-key`.
- **Values:** three, in this order: **Application Key**, **Application Secret**, **Consumer Key**.
- **Shape:** 16, 32 and 32 letters and digits.
- **Read-only call:** a signed `GET cloud/project/PROJECT_ID/instance`, with the guide's `ovhcloud_request` function below, and the three values in the script's memory only.
- **Key file line:** `APPLICATION_KEY:APPLICATION_SECRET:CONSUMER_KEY`.


The API proxy is `provider-api-proxy.service`. systemd runs it under an account of its own
and hands it a copy of the credential file that only that account reads, so neither the coding agent nor any
other account on the desk reads the credential. It forwards each request only to the API address in the
credential file, and that address is one of the three in the table: `set-up-outside-services` refuses any
other. Reason: the coding agent can push `mmx_project_settings.yml`, so an address taken from it as it is
could send the credential to any host. The proxy refuses a whole address in place of a path, and a path with
`..`, and passes a redirect back without following it, so the signed request never leaves OVHcloud's API.

### util01's credential

`util01` creates, lists, stops and deletes servers with its own credential, which belongs to the account and not to a
person: the weekly restore drill creates and deletes `restore01`, the daily leftover check lists the servers,
and the triage agent's server replacements run the same scripts there, with `power_off_a_server_at_the_provider`. The person makes it from a second
link, with the narrower rules `util01` needs:

```text
https://api.us.ovhcloud.com/createToken/?GET=/cloud/project/PROJECT_ID/*&POST=/cloud/project/PROJECT_ID/instance&POST=/cloud/project/PROJECT_ID/instance/*&DELETE=/cloud/project/PROJECT_ID/instance/*
```

On that page too the person types the OVHcloud login and password, because the page ignores a signed-in
browser. **Application name** `example_systems: util01 creates and deletes servers`, **Validity** **Unlimited**.
`set-up-outside-services secrets` asks for its three values, each at a hidden prompt, and saves the joined
form in the vault as `util01_provider_api_token`. The restore drill and the leftover check already give that
key to the scripts as `SERVER_PROVIDER_API_TOKEN`, so `util01` needs no other setting and no program beyond
Debian's `curl` and `sha1sum` and the Stack's `jq`.

| Methods | Paths under `/cloud/project/PROJECT_ID` | Why `util01` needs them |
| --- | --- | --- |
| GET | `/*` | List servers, keys, flavors and images; the price script reads a flavor's plan codes |
| POST | `/instance` | Create a server |
| POST | `/instance/*` | Start, stop or reboot a server, for the triage agent's replacements |
| DELETE | `/instance/*` | Delete a server |

The price script reads OVHcloud's public order catalog, outside the project, without the credential, so
`util01`'s credential needs no rule for it. `util01`'s credential cannot register SSH keys: the coding agent registers `util01`'s key from the desk
before the first drill. The replacement's create names that one key (`util01_ssh_key_name_at_the_provider`),
and its power-off is `POST /instance/ID/stop`, which `POST /instance/*` covers: a rule's `*` matches the rest
of the path, several segments deep (a credential with `POST /cloud/project/PROJECT_ID/*` was allowed
`POST /cloud/project/PROJECT_ID/instance/ID/stop` on a real project, 2026-11-12). DELETE permits removing any server of the project, so keep other systems in
other projects.

**Proved at OVHcloud: the weekly restore drill, and `util01`'s four access rules.** On 2026-11-13, in
`US-EAST-VA-1`, a `util01` of type `d2-4` ran the real weekly restore drill against a real system's backups at
Backblaze B2. The drill made and destroyed `restore01` by itself and passed: 3 minutes 59 seconds from the
drill's start to its end, `restore_duration_seconds` 218, `util01` created in 57 seconds, the destroy 16
seconds, and no instance, volume, snapshot or address left. The desk's server work through the API proxy is
proved on a real OVHcloud project too: list, create with first-boot data, stop, start, delete.

The same day a credential with exactly this guide's four rules (its `GET /auth/currentCredential` answer showed
those four rules and no expiry) was enough for everything `util01` does: the list script, the create with
first-boot data (56 seconds), the power-off, `POST /instance/ID/stop` (16 seconds, `stopped`), the destroy (15
seconds), and the whole weekly restore drill, which passed (`restore_duration_seconds` 206) and left no
`restore01`. A call outside the four rules, such as `GET /me`, `POST .../volume` or `PUT .../instance/ID`, got
HTTP 403 with "This call has not been granted", so the rules are also not wider than needed. The first drill at
setup still runs once by hand after setup, as
[Start or stop a drill now](../operating_procedures/run_the_weekly_database_restore_drill.md#start-or-stop-a-drill-now)
says, and the coding agent checks its result as [Read the result](../operating_procedures/run_the_weekly_database_restore_drill.md#read-the-result)
says: `passed` in `latest_result.json`, and no `restore01` left in the list script's output. It records the
result in the checklist item `backups_restore_every_week`. Reason: the weekly drill is the system's proof that
backups restore. A systems desk was set up at OVHcloud US with the desk chapter on 2026-11-13, and its API proxy signed
requests through `http://127.0.0.1:8081/` with the person's credential (HTTP 200).

### Replacing a credential, and a person who leaves

To replace the person's credential, such as after a lost laptop, the person makes a new one from the same
link and runs the `personal-token` command again; the proxy keeps the old one until the new one passed its
check. Then the person deletes the old application in OVHcloud's Control Panel, under the account's
**API keys** page, by its name. To replace `util01`'s, the person makes a new one from `util01`'s link, runs
`set-up-outside-services secrets --replace util01_provider_api_token`, the coding agent runs `every_server`,
and the person deletes the old application. When a person leaves, the person who stays deletes the leaving
person's application by its name on the same page; `util01`'s credential keeps working.

A person can also end a credential at once, without the Control Panel: `POST /auth/logout`, signed with that
credential, makes OVHcloud refuse it. The call needs no access rule, so `util01`'s four rules already cover it,
and it answers HTTP 200 with `null`. Proved on 2026-11-13: one request right after the call still worked, and
about 20 seconds later every call answered HTTP 403 with "This credential is not valid". The application's
entry stays on the **API keys** page until the person deletes it there, so delete it too.

When the team moves its servers away from OVHcloud, the desk review that changes
`systems_desk_provider_api_authentication` to `token_in_a_header` deletes
`/etc/systems-desk/provider-api-signing-credential.json` from the desk, `personal-token server-provider` for
the new provider fills the API proxy's token file, and `secrets --replace
util01_provider_api_token` replaces `util01`'s. Once OVHcloud holds no server of the system, the person deletes
every application of the system on the **API keys** page: each person's and `util01`'s
([Move the servers to another provider](../operating_procedures/move_the_servers_to_another_provider.md), step 6).

## The provider scripts' request function

OVHcloud's own command-line tool mixes API versions, and its newer listing of SSH keys can leave out keys
that the v1 API made, so the five scripts use v1 requests with `curl` and `jq` instead, through one
function. The function goes through the API proxy on a desk, where the coding agent has no
credential, and signs the request itself where `SERVER_PROVIDER_API_TOKEN` is set: `util01`'s jobs, and
the person's own terminal on the laptop during the first desk's bootstrap. It needs `bash`, `curl`, `jq`,
and `sha1sum`, or on macOS `shasum`, and works in Debian's `bash` and in the older `bash` 3.2 that macOS
has. Check `jq --version` on the laptop; a macOS without `/usr/bin/jq` needs `jq` installed first. Put it,
with the two values above it, at the top of each script, after `#!/bin/bash` and `set -euo pipefail`:

```bash
ovhcloud_api_address=https://api.us.ovhcloud.com/1.0/   # systems_desk_provider_api_url
ovhcloud_project_id=0123456789abcdef0123456789abcdef    # the project's ID
command -v sha1sum >/dev/null || sha1sum() { shasum -a 1; }   # macOS, during the bootstrap

# ovhcloud_request METHOD PATH [BODY_FILE]
# Sends one request to PATH under the API address, such as
# "cloud/project/$ovhcloud_project_id/instance", prints the answer's body,
# and fails on an answer that is not 2xx, without printing the body, except
# for an order (order/...): its error names the cause, such as no stock, and
# holds no secret.
ovhcloud_request() {
  local method=$1 path=$2 body_file=${3:-} body='' url timestamp signature answer http_status_code
  local -a body_arguments=()
  if [ -n "$body_file" ]; then
    # The signature covers the exact bytes curl sends, trailing newline
    # included, which a plain $(cat) would drop.
    body=$(cat -- "$body_file"; printf x); body=${body%x}
    body_arguments=(--header 'Content-Type: application/json' --data-binary "@$body_file")
  fi
  answer=$(mktemp)
  if [ -z "${SERVER_PROVIDER_API_TOKEN:-}" ]; then
    url="http://127.0.0.1:8081/$path"
    http_status_code=$(curl --silent --show-error --connect-timeout 10 --max-time 120 \
      --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' "$url")
  else
    url="$ovhcloud_api_address$path"
    local application_key application_secret consumer_key
    IFS=: read -r application_key application_secret consumer_key <<< "$SERVER_PROVIDER_API_TOKEN"
    timestamp=$(curl --silent --show-error --fail --max-time 30 "${ovhcloud_api_address}auth/time")
    [[ "$timestamp" =~ ^[0-9]+$ ]] || { rm -f -- "$answer"; return 1; }
    signature="\$1\$$(printf '%s' "$application_secret+$consumer_key+$method+$url+$body+$timestamp" | sha1sum | cut -d' ' -f1)"
    # The headers go through standard input, never the command line, which
    # other accounts on the server can read.
    http_status_code=$(printf 'X-Ovh-Application: %s\nX-Ovh-Consumer: %s\nX-Ovh-Timestamp: %s\nX-Ovh-Signature: %s\n' \
        "$application_key" "$consumer_key" "$timestamp" "$signature" |
      curl --silent --show-error --connect-timeout 10 --max-time 120 --header @- \
        --request "$method" ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' "$url")
  fi
  case "$http_status_code" in
    2??) cat -- "$answer"; rm -f -- "$answer" ;;
    *) if [[ "$path" == order/* ]]; then
         printf 'OVHcloud answered %s %s with HTTP %s: %s\n' "$method" "$path" "$http_status_code" "$(head -c 500 -- "$answer")" >&2
       else
         printf 'OVHcloud answered %s %s with HTTP %s (body withheld)\n' "$method" "$path" "$http_status_code" >&2
       fi
       rm -f -- "$answer"; return 1 ;;
  esac
}
```

For example, the list script's request is
`ovhcloud_request GET "cloud/project/$ovhcloud_project_id/instance"`, and the coding agent's own reads
use the same paths, such as `curl http://127.0.0.1:8081/cloud/project/PROJECT_ID/flavor?region=US-EAST-VA-1`.

The signature joins the application secret, the consumer key, the method, the whole URL with its query, the
exact body sent, and OVHcloud's own time from `/auth/time`, with `+`, and is the SHA-1 digest in hexadecimal
after the literal `$1$` (OVHcloud's [first steps with the API](https://docs.ovhcloud.com/en/guides/manage-and-operate/api/first-steps)).
The time limits are the guide's defaults: 10 seconds to connect and 120 seconds for an answer, which a
create answers well within. Never pass credential headers or first-boot data as command-line arguments.
Keep first-boot files mode `0600` and clear them after reading, including on failure. Select the fields to
print with `jq`: a create answer can hold `rescuePassword`, and an error can repeat the request's `userData`.
Use the [v1 schema](https://api.us.ovhcloud.com/1.0/cloud.json) for request fields.

## The five provider scripts

Each script is `#!/bin/bash`, `set -euo pipefail`, the two values and the request function above, then its
own part below, in `server_management_scripts/` under the contract's names. They follow the
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts), and the rules
after them say why.

`list_the_servers_at_the_provider`:

```bash
# One request lists the whole project: v1 pages an answer only when asked.
ovhcloud_request GET "cloud/project/$ovhcloud_project_id/instance" |
  jq '{servers: [.[] | {id, name,
        public_ipv4_address: ([.ipAddresses[]? | select(.version == 4 and .type == "public") | .ip][0] // ""),
        power_state: ({"ACTIVE": "running", "SHUTOFF": "stopped"}[.status] // .status)}]}'
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
# OVHcloud's v1 create takes one SSH key. Reason: the first MMX run writes
# root's whole key list from root_ssh_public_keys.
[ "${#ssh_key_names[@]}" -eq 1 ] || { echo "give exactly one --ssh-key-name: OVHcloud's create takes one SSH key" >&2; exit 2; }
p="cloud/project/$ovhcloud_project_id"
flavor_id=$(ovhcloud_request GET "$p/flavor?region=$location" | jq -r --arg n "$server_type" '[.[] | select(.name == $n and .available) | .id][0] // empty')
image_id=$(ovhcloud_request GET "$p/image?osType=linux&region=$location" | jq -r --arg n "$image" '[.[] | select(.name == $n and .status == "active") | .id][0] // empty')
ssh_key_id=$(ovhcloud_request GET "$p/sshkey?region=$location" | jq -r --arg n "${ssh_key_names[0]}" '[.[] | select(.name == $n) | .id][0] // empty')
network_id=$(ovhcloud_request GET "$p/network/public" | jq -r --arg r "$location" '[.[] | .regions[]? | select(.region == $r and .status == "ACTIVE") | .openstackId][0] // empty')
for v in flavor_id image_id ssh_key_id network_id; do [ -n "${!v}" ] || { echo "could not resolve $v in $location" >&2; exit 1; }; done
jq -n --arg name "$server_name" --arg region "$location" --arg flavorId "$flavor_id" --arg imageId "$image_id" \
  --arg sshKeyId "$ssh_key_id" --arg networkId "$network_id" --rawfile userData "$first_boot_data" \
  '{name: $name, region: $region, flavorId: $flavorId, imageId: $imageId, sshKeyId: $sshKeyId,
    monthlyBilling: false, networks: [{networkId: $networkId}], userData: $userData}' > "$body_file"
write_receipt() {  # write_receipt JSON: replaces the ownership file in one step
  [ -z "$ownership_file" ] || { printf '%s\n' "$1" > "$ownership_file.new" && mv -- "$ownership_file.new" "$ownership_file"; }
}
# The IDs before the create tell a lost answer's server apart: v1 has no
# ownership label. Never send the POST again.
ids_before=$(ovhcloud_request GET "$p/instance" | jq -c '[.[].id]')
if created=$(ovhcloud_request POST "$p/instance" "$body_file"); then
  server_id=$(jq -r '.id' <<< "$created")
else
  echo "the create's answer failed; looking for a new server named $server_name" >&2
  sleep 30  # time for OVHcloud to list a create it accepted
  server_id=$(ovhcloud_request GET "$p/instance" | jq -r --argjson before "$ids_before" --arg n "$server_name" \
    '[.[] | select(.name == $n and (.id as $id | $before | index($id) | not)) | .id] | if length == 1 then .[0] else empty end')
  [ -n "$server_id" ] || { echo "no single new server named $server_name appeared; check the listing before any retry" >&2; exit 1; }
fi
write_receipt "$(jq -n --arg id "$server_id" --arg name "$server_name" '{id: $id, name: $name}')"
for _ in $(seq 1 90); do
  detail=$(ovhcloud_request GET "$p/instance/$server_id")
  address=$(jq -r '[.ipAddresses[]? | select(.version == 4 and .type == "public") | .ip][0] // empty' <<< "$detail")
  if [ "$(jq -r .status <<< "$detail")" = ACTIVE ] && [ -n "$address" ]; then
    result=$(jq -n --arg id "$server_id" --arg name "$server_name" --arg a "$address" --arg t "$server_type" --arg l "$location" \
      --arg w "$wireguard_public_key" --arg i "$private_ip" \
      '{id: $id, name: $name, public_ipv4_address: $a, server_type: $t, location: $l, wireguard_public_key: $w, private_ip: $i}')
    write_receipt "$result"
    printf '%s\n' "$result"
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not ACTIVE with a public IPv4 address after 15 minutes" >&2
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
p="cloud/project/$ovhcloud_project_id"
listing=$(ovhcloud_request GET "$p/instance")
if [ -n "$server_id" ]; then
  # Never fall back from a missing ID to a matching name.
  if ! jq -e --arg i "$server_id" 'any(.[]; .id == $i)' <<< "$listing" > /dev/null; then
    echo "no server with ID $server_id: nothing to destroy" >&2
    jq -n --arg i "$server_id" '{id: $i, deleted: true}'
    exit 0
  fi
elif [ -n "$server_name" ]; then
  server_id=$(jq -r --arg n "$server_name" '[.[] | select(.name == $n) | .id] | if length == 1 then .[0] else empty end' <<< "$listing")
  [ -n "$server_id" ] || { echo "expected exactly one server named $server_name" >&2; exit 1; }
else
  echo "give --server-id or --server-name" >&2; exit 2
fi
ovhcloud_request DELETE "$p/instance/$server_id" > /dev/null
# Deletion accepted is not deletion finished: wait until a whole listing lacks
# the ID. A failed listing stops the script; it never counts as "gone".
for _ in $(seq 1 60); do
  listing=$(ovhcloud_request GET "$p/instance")
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
p="cloud/project/$ovhcloud_project_id"
status_of() {  # status_of: the server's OVHcloud status from a whole listing, or nothing when it is not listed
  ovhcloud_request GET "$p/instance" | jq -r --arg i "$server_id" '[.[] | select(.id == $i) | .status][0] // empty'
}
status=$(status_of)
[ -n "$status" ] || { echo "no server with ID $server_id" >&2; exit 1; }
# OVHcloud has no power cut: stop asks the operating system to shut down.
[ "$status" = SHUTOFF ] || ovhcloud_request POST "$p/instance/$server_id/stop" > /dev/null
# A stop took up to 40 seconds on a real project; 5 minutes leave room.
for _ in $(seq 1 30); do
  if [ "$(status_of)" = SHUTOFF ]; then
    jq -n --arg i "$server_id" '{id: $i, power_state: "stopped"}'
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not stopped after 5 minutes" >&2
exit 1
```

These scripts, signed in the shell as on `util01`, created a `d2-2` server in `US-EAST-VA-1` with first-boot data
in 56 seconds, stopped it in 16 seconds with the power-off script and deleted it in 16 seconds, on a real
project (2026-11-12). Through the API proxy they created a `d2-4` server in `US-EAST-VA-1` with first-boot data
in 75 seconds, stopped and started it, and deleted it, on a real OVHcloud project (2026-11-12, with the list
script's earlier form). The Stack's tests (`tests/ovhcloud_provider_scripts_test.py`) run these blocks, with
each `bash` on the test machine, macOS's 3.2 included, against a stand-in for OVHcloud, signed and through the
proxy, including a create whose answer is lost.

`read_the_monthly_price_at_the_provider`:

```bash
ovhcloud_subsidiary=US   # the catalog's country: US for the US site; for the others the account's, such as FR, DE, GB or CA
server_type='' location=''
while [ $# -gt 0 ]; do
  case "$1" in
    --server-type) server_type=$2 ;; --location) location=$2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift 2
done
[ -n "$server_type" ] && [ -n "$location" ] || { echo "give --server-type and --location" >&2; exit 2; }
flavors=$(ovhcloud_request GET "cloud/project/$ovhcloud_project_id/flavor?region=$location") ||
  { echo "OVHcloud does not offer the region $location to this project (or its flavors could not be read: see the line above)" >&2; exit 1; }
# The create script bills by the hour (monthlyBilling: false), so the price is the hourly plan's.
plan=$(jq -r --arg t "$server_type" '[.[] | select(.name == $t) | .planCodes.hourly // empty] | unique | if length == 1 then .[0] else empty end' <<< "$flavors")
[ -n "$plan" ] || { echo "OVHcloud lists no hourly plan for the flavor $server_type in $location" >&2; exit 1; }
# The public catalog needs no credential and lies outside the project, so it
# is read without one: util01's credential then needs no rule for it.
catalog=$(curl --silent --show-error --fail --connect-timeout 10 --max-time 120 \
  "${ovhcloud_api_address}order/catalog/public/cloud?ovhSubsidiary=$ovhcloud_subsidiary") || { echo "OVHcloud's catalog did not answer" >&2; exit 1; }
micro_cents=$(jq -r --arg plan "$plan" '[.addons[] | select(.planCode == $plan) | .pricings[] | .price] | first // empty' <<< "$catalog")
[ -n "$micro_cents" ] || { echo "OVHcloud's catalog has no hourly price for $plan" >&2; exit 1; }
echo "OVHcloud's catalog price for $ovhcloud_subsidiary, billed by the hour: the hourly price times 730 hours, with the tax its locale states (0 on the US site); the public IPv4 address is priced apart and left out" >&2
jq --arg t "$server_type" --arg l "$location" --argjson price "$micro_cents" \
  '{server_type: $t, location: $l, monthly_price: ($price / 100000000 * 730 * 100 | round / 100 | tostring), currency: .locale.currencyCode}' <<< "$catalog"
```

The price script makes the [Prices](#region-image-and-network) paragraph's two requests below: the flavor's
hourly plan code through the project, then the plan's hourly price in the public catalog, in hundred-millionths
of the account's currency, which it multiplies by 730 hours. The servers are billed by the hour, because the
create script sets `monthlyBilling: false`: a replaced server or `restore01` lives for minutes, and a monthly
plan charges the whole month and cannot be switched back.

## Region, image, and network

Query regional catalogs before creation; `US-EAST-VA-1` is Virginia in the US service.
`d2-4` has 2 vCPUs, 4 GB RAM, and 50 GB disk, meeting the database,
utility, and staging sizes in [chapter 6 (create your three production servers: app, database, and tools)](../initial_setup/06_create_your_three_production_servers.md).
For the app server, `b2-15` has 4 vCPUs, 15 GB RAM, and 100 GB disk.
`d2-8` has only 50 GB disk, below the app requirement. Choose x86-64 because ARM needs matching binaries
and images. Use hourly billing for temporary servers; stopping a server does not end billing.

**Prices.** Two requests give a flavor's price (OVHcloud's v1 schema: `cloud.json`, the flavor's
`planCodes`; `order.json`, `/order/catalog/public/cloud`, which needs no credential). First the flavor's
plan codes, through the proxy:

```sh
curl -sS 'http://127.0.0.1:8081/cloud/project/PROJECT_ID/flavor?region=US-EAST-VA-1' |
  jq '.[] | select(.name == "d2-4") | {name, region, planCodes}'
```

Then the public catalog, straight from the API address, with `ovhSubsidiary=US` for the US site, or the
account's country, such as `FR`, `DE`, `GB` or `CA`, for the others:

```sh
curl -sS 'https://api.us.ovhcloud.com/1.0/order/catalog/public/cloud?ovhSubsidiary=US' |
  jq --arg plan HOURLY_PLAN_CODE '.addons[] | select(.planCode == $plan) |
    {planCode, invoiceName, pricings: [.pricings[] | {price, intervalUnit, capacities, description}]}'
```

`price` is in micro-cents of the account's currency (100000000 is one unit, such as one dollar), and
`description` says per what for the hourly plan ("hourly prices", with `intervalUnit` `none`). `tax` is the tax
within `price`: 0 on the US site, whose catalog's `locale.taxRate` is 0, so show the price as before any tax. The
servers are billed by the hour (`monthlyBilling: false`), so show the person the hourly price and the hourly price
times 730 hours as the monthly cost, not the cheaper monthly plan (`planCodes.monthly`), which the servers do not
use. Show the person the
public IPv4 charge too: the catalog's line `publicip.ip.hour.consumption`, which was 0 on a real project on
2026-11-12, or OVHcloud's [price page](https://us.ovhcloud.com/public-cloud/prices/) when the catalog has no
line for it.

Select active `Debian 13` from the regional catalog, as the create script does with `--image "Debian 13"`
(`server_image: Debian 13`). Image IDs change, so the script resolves the ID before each creation. The
Debian image has cloud-init and default user `debian`; the first-boot data sets `disable_root: false`, so
cloud-init installs the selected key for `root` as well.
On Debian 13, inspect `cloud-init-network.service`, rather than assuming
the unit is `cloud-init.service`, when proving the enrollment contract's SSH ordering.
Require the network stage before `ssh.service` and `sysinit.target`, with `ssh.socket` after `sysinit.target`.
That ordering also puts the network stage before socket activation. Recheck the dependencies on the selected image.
Prove first boot through authenticated WireGuard SSH or the provider's VNC console.
Public SSH is deliberately closed, so do not wait for public SSH as a readiness check.
VNC can show only a login prompt after boot, without cloud-init's completion message.
Inspect `/var/log/cloud-init-output.log` and the WireGuard public key through authenticated access before marking enrollment complete.
Never print `/etc/wireguard/wg0.conf` or the private-key file.

Select only the existing active public `Ext-Net` in the region.
Query `GET /network/public` beneath the project path. Select `regions[].openstackId`
where `region` matches the requested location and `status` is `ACTIVE`.
Use that regional ID as `networks[].networkId`, rather than the catalog object's top-level `id`.
Do not inherit wizard private networks, gateways, floating IPs, or backups.
WireGuard needs no provider private network. Inspect existing private-network
subnets and systems desk routes before choosing `10.20.0.0/16`, because a vRack
subnet can overlap the WireGuard plan.

Leave OVHcloud's default [security group](https://docs.ovhcloud.com/en/guides/public-cloud/compute/setup-security-group)
unchanged and attach no custom provider firewall. The default permits traffic
and OVHcloud can reset the default rules. UFW enforces the Stack's firewall. So nobody makes a rule that admits
UDP 443: the default already admits it, and the 2026-11-13 drill's `restore01` reached `util01` with no rule made.

The checked Debian 13 image had no metadata-agent failure after the metadata
block and reboot. Keep cloud-init enabled for enrollment. Check
`systemctl --failed` after rebooting a new image. Disable only identified,
unneeded metadata-dependent agents through MMX. Keep the metadata block
because metadata can expose first-boot secrets.

Check regional instance, vCPU, RAM, and flavor quotas in **Quota and Regions**.
Allow replacements and a simultaneous restore. Request an
[increase](https://support.us.ovhcloud.com/hc/en-us/articles/22188629448339-How-to-increase-Public-Cloud-quotas)
before provisioning. Catalog availability does not reserve physical capacity.

## Keys, first boot, and lifecycle

The coding agent registers a key from the desk, through the proxy, with v1 `POST /sshkey` beneath the
project path and `name`, `publicKey` and `region`, such as `util01`'s `mmhotline` key from its line in
`root_ssh_public_keys`:

```sh
body=$(mktemp)
jq -n --arg name 'util01, the mmhotline user' --arg publicKey 'ssh-ed25519 AAAA... mmhotline@util01' \
  --arg region US-EAST-VA-1 '{name: $name, publicKey: $publicKey, region: $region}' > "$body"
curl -sS --fail-with-body -X POST -H 'Content-Type: application/json' --data-binary "@$body" \
  http://127.0.0.1:8081/cloud/project/PROJECT_ID/sshkey | jq '{id, name, regions}'
curl -sS 'http://127.0.0.1:8081/cloud/project/PROJECT_ID/sshkey?region=US-EAST-VA-1' | jq '.[] | {id, name, publicKey}'
rm -f -- "$body"
```

Compare the listed `publicKey` with the key's line before using the name. An empty v2 listing does not
prove a key is absent. v1 accepts one `sshKeyId`, so the create script takes exactly one `--ssh-key-name`:
the key of the machine that runs the first MMX run on the server. The first MMX run writes root's whole key
list from `root_ssh_public_keys`.

The create script reads the rendered first-boot file into the v1 create body's `userData` string, without
additional base64 encoding, with `monthlyBilling: false` and `networks[].networkId` set to the public network
ID. `ACTIVE` with a public IPv4 address does not mean cloud-init and WireGuard have finished.

Create with the final requested name. A later v1 rename can revert during
power operations, so do not use a temporary ownership name.
v1 creation has no ownership label, so the create script records the project's server IDs before the POST.
When the POST's answer is lost or refused, it looks once more after 30 seconds and accepts only exactly one
new ID with the exact name; otherwise it stops without a retry. Reason: another POST could duplicate an
accepted create. The exact OVHcloud capacity-error response remains unverified, so the script does not
retry a quota error, an HTTP 5xx, or a lost answer as a capacity refusal.

List the whole project in one request: v1 pages an answer only when the request asks for pages with
`X-Pagination-Mode`, so send no such header. (Checked 2026-11-12: the project's flavor listing, 179
entries, came back whole, with and without the header.)
The list script's `power_state` is `running` for OVHcloud's `ACTIVE` and `stopped` for `SHUTOFF`; any other
`status`, such as `BUILD` or `REBOOT`, passes through as it is.
After deletion, the destroy script polls complete listings until the recorded ID disappears.
Deletion acceptance alone does not end cleanup. Use the shared
[replacement](../operating_procedures/replace_a_server.md),
[removal](../operating_procedures/remove_a_server.md), and
[restore drill](../operating_procedures/run_the_weekly_database_restore_drill.md) procedures.

For power-cycle checks, the coding agent stops and starts a server from the desk:

```sh
./server_management_scripts/power_off_a_server_at_the_provider --server-id SERVER_ID
curl -sS --fail-with-body -X POST http://127.0.0.1:8081/cloud/project/PROJECT_ID/instance/SERVER_ID/start
./server_management_scripts/list_the_servers_at_the_provider | jq '.servers[] | select(.id == "SERVER_ID")'
```

Wait for `power_state` `stopped` after the stop and `running` after the start; each took up to 40 seconds on
a real project. Stop and start ask the operating system to shut down and boot; they are not an abrupt power
cut. Keep the sudden-power-loss test unproved until an action that cuts power is verified. Both credentials'
rules allow these requests.

## Console and rescue access

In Manager, select **Public Cloud**, the project, **Instances**, the instance,
then **VNC console**. No separate console activation is documented.
v1 `POST /instance/INSTANCE_ID/vnc` beneath the project path returns a temporary console URL; the person's
credential allows it. Keep the console URL out of logs and command-line arguments.
The [console](https://docs.ovhcloud.com/en/guides/public-cloud/compute/getting-started#54-vnc-console-access)
needs a configured Linux password. Test root login with the Stack's saved
shared root console password before marking break-glass access complete, because VNC
must work when WireGuard fails.

For a server that cannot boot, choose **Reboot in rescue mode** in the
instance's action menu. Follow the [rescue guide](https://docs.ovhcloud.com/en/guides/public-cloud/compute/put-an-instance-in-rescue-mode).
The temporary password appears in VNC, and the installed disk becomes an
additional disk. Identify the disk with `lsblk` before mounting.
v1 `POST /instance/INSTANCE_ID/rescueMode` beneath the project path accepts `{"rescue":true}`; the person's
credential allows it. Wait for `RESCUE` and the rescue login prompt.
The POST response's `adminPassword` can be null. Read `rescuePassword` from protected v1 instance detail after boot.
Never print the response. Clear the temporary credential file after login.

Rescue has separate SSH and firewall settings. Installed Debian's UFW does not protect rescue.
The rescue image may lack `iptables` and `ip6tables`. Stop `ssh.service` from VNC and verify public TCP 22 refuses connections.
Close public SSH before handling backup credentials or protected disk contents.
For ext4 inspection, mount the installed partition read-only with `mount -o ro,noload DEVICE /mnt`.
Inspect `/mnt/var/log/cloud-init.log` for boot completion. Never display a WireGuard private-key file.
Unmount the disk after inspection. Send `{"rescue":false}` to leave rescue through the API, then wait for normal boot.
Verify private SSH and public-port closure after leaving rescue.
