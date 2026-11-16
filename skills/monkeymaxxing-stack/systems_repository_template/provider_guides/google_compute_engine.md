# Google Compute Engine

Compute Engine calls a server an **instance**, a size a **machine type**, and a location a **zone**, such as
`europe-west4-a` in the Netherlands. Follow the shared
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts),
[enrollment contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run),
and [initial setup](../initial_setup/). Use a dedicated Google Cloud project for the system, so its
credentials reach nothing else.

## The provider's web console

The person sees the servers in the Google Cloud console, at the VM instances list:
<https://console.cloud.google.com/compute/instances>, with the system's project selected at the top.

## Credentials on the systems desk

Google Cloud takes a short-lived access token, which a program makes from a service account's key, not a fixed
token in a header. The desk's
**API proxy** does that: it listens on `http://127.0.0.1:8081/`, the same address as
at the other providers, makes an access token from the key, keeps it until a minute before it expires, adds it
to each request, and sends the request to Compute Engine. The coding agent uses the credential without
reading it.

Set both settings in `mmx_project_settings.yml`:

```yaml
systems_desk_provider_api_url: https://compute.googleapis.com/compute/v1/
systems_desk_provider_api_authentication: google_cloud_service_account_tokens
```

A Google Cloud credential is a service account's **key file**, JSON that Google gives once.
`SERVER_PROVIDER_API_TOKEN` holds the file's text in base64, on one line. The proxy asks Google for tokens with
two scopes only: Compute Engine's (`https://www.googleapis.com/auth/compute`) and the price catalog's
read-only scope (`https://www.googleapis.com/auth/cloud-billing.readonly`); the service account's roles decide
what the token may do inside them. Paths under `http://127.0.0.1:8081/cloudbilling/` go to the price catalog,
`https://cloudbilling.googleapis.com/`; every other path goes to Compute Engine.

### The person's credential

The person does the project's one-time steps in the Google Cloud console, with their own Google login, and in
**Cloud Shell**, the console's browser terminal, which has Google's `gcloud` already: nothing is installed on
the laptop.

1. The person makes the Google Cloud account, saves the login and its two-step codes in the team's password
   manager, creates the project, links a billing account, and gives the coding agent the project's ID, such as
   `example-systems-123456`. The ID is not a secret; the coding agent writes it at the top of the provider
   scripts as `google_project_id`.
2. In Cloud Shell, the person turns on the two APIs the scripts use and makes their own service account,
   named after them, with the roles Compute Instance Admin (v1) and Compute Security Admin, and its key:

   ```sh
   gcloud services enable compute.googleapis.com cloudbilling.googleapis.com --project=PROJECT_ID
   gcloud iam service-accounts create alex-systems-desk --project=PROJECT_ID --display-name="alex's systems desk"
   gcloud projects add-iam-policy-binding PROJECT_ID --role=roles/compute.instanceAdmin.v1 \
     --member=serviceAccount:alex-systems-desk@PROJECT_ID.iam.gserviceaccount.com
   gcloud projects add-iam-policy-binding PROJECT_ID --role=roles/compute.securityAdmin \
     --member=serviceAccount:alex-systems-desk@PROJECT_ID.iam.gserviceaccount.com
   gcloud iam service-accounts keys create alex-systems-desk.json --iam-account=alex-systems-desk@PROJECT_ID.iam.gserviceaccount.com
   ```

   with the person's desk account name in place of `alex`. Reason for the role: it creates, powers and deletes
   servers and their disks and reads the images, and its `compute.instances.delete` reaches every server of the
   project, which is why the project holds nothing else. Reason for Compute Security Admin: Compute Instance
   Admin (v1) cannot create or delete firewall rules, and the network's WireGuard rule
   ([Sizes, network and quotas](#sizes-network-and-quotas)) needs both. When the key's creation is refused because of the
   organization policy `iam.disableServiceAccountKeyCreation`, an administrator of the organization turns the
   policy off for this project first.
3. During the first desk's bootstrap (chapter 2), the person puts the key into the laptop's temporary token
   file, in the person's own laptop terminal, after downloading the key file from Cloud Shell (**More**,
   **Download**):

   ```sh
   export SERVER_PROVIDER_API_TOKEN="$(openssl base64 -A < ~/Downloads/alex-systems-desk.json)"
   ```

4. On the desk, the person runs, in the person's own terminal, in the systems repository:

   ```sh
   . ~/.config/monkeymaxxing-stack/example_systems.env && set-up-outside-services personal-token server-provider --server-listing-path 'projects/PROJECT_ID/aggregated/instances?maxResults=1'
   ```

   The command asks for the key file's whole text at one hidden prompt: in Cloud Shell the person runs
   `cat alex-systems-desk.json` and pastes everything from `{` to `}`. It checks the key with a listing of the
   project's servers, and only then writes `/etc/systems-desk/provider-api-signing-credential.json`, root:root,
   mode `0600`, restarts the API proxy, checks the same listing through `http://127.0.0.1:8081/`, and
   saves the key in base64 in the person's token file as `SERVER_PROVIDER_API_TOKEN`. When a check fails, the
   proxy keeps its old credential. Then the person deletes the key file in Cloud Shell and on the laptop:
   `rm alex-systems-desk.json`.

The proxy forwards each request only to Compute Engine's address and the price catalog's, refuses a whole
address in place of a path, and a path with `..`, and passes a redirect back without following it. It sends
the signed request for a token only to `https://oauth2.googleapis.com/token`, and refuses a key file that names
another token address.

### util01's credential

`util01` creates, lists, powers off and destroys servers with its own service account, which belongs to the
project and not to a person: the weekly restore drill creates and destroys `restore01`, the daily leftover check
lists the servers, and the triage agent's server replacements run the same scripts there. The person makes a
custom role with exactly the permissions the scripts use, and the service account with that role, in Cloud
Shell:

```sh
gcloud iam roles create util01CreatesAndDestroysServers --project=PROJECT_ID \
  --title="util01 creates and destroys servers" \
  --permissions=compute.instances.create,compute.instances.list,compute.instances.stop,compute.instances.delete,compute.instances.setMetadata,compute.instances.setLabels,compute.disks.create,compute.images.useReadOnly,compute.subnetworks.use,compute.subnetworks.useExternalIp,compute.zoneOperations.get
gcloud iam service-accounts create util01-restore-drill --project=PROJECT_ID --display-name="util01 creates and destroys servers"
gcloud projects add-iam-policy-binding PROJECT_ID --role=projects/PROJECT_ID/roles/util01CreatesAndDestroysServers \
  --member=serviceAccount:util01-restore-drill@PROJECT_ID.iam.gserviceaccount.com
gcloud iam service-accounts keys create util01-restore-drill.json --iam-account=util01-restore-drill@PROJECT_ID.iam.gserviceaccount.com
```

`set-up-outside-services secrets` asks for the key file's whole text at one hidden prompt (`cat
util01-restore-drill.json` in Cloud Shell, then paste), saves it in base64 in the vault as
`util01_provider_api_token`, and the person deletes the file. The restore drill and the leftover check already
give that key to the scripts as `SERVER_PROVIDER_API_TOKEN`, so `util01` needs no other setting and no program
beyond Debian's `curl` and `openssl` and the Stack's `jq`.

| Permission | Why `util01` needs it |
| --- | --- |
| `compute.instances.list` | List servers, every zone in one listing |
| `compute.instances.create`, `compute.disks.create`, `compute.images.useReadOnly` | Create a server with its boot disk from the system's image |
| `compute.instances.setMetadata`, `compute.instances.setLabels` | Give the new server its first-boot data, SSH key and `stack-system-id` label |
| `compute.subnetworks.use`, `compute.subnetworks.useExternalIp` | Put the new server on the network with a public IPv4 address |
| `compute.zoneOperations.get` | Wait for the create to finish |
| `compute.instances.stop` | Power a failed server off, for the triage agent's replacements |
| `compute.instances.delete` | Destroy a server |

The names are Google's, from [Create and start a VM instance](https://docs.cloud.google.com/compute/docs/instances/create-start-instance)
("Required permissions") and the [Compute Engine API reference](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances).
A custom role is the smallest scope Compute Engine offers here: `util01` can power off and destroy any server of
the project, which holds only this system. The price request reads Google's public price catalog, which needs
no IAM permission, only the project's Cloud Billing API turned on (step 2 above). A team whose `util01` service
account has an older role adds the missing permissions to it in IAM (**Roles**, the role, **Edit role**); the
key stays the same.

**Proved at Compute Engine: the weekly restore drill, once.** On 2026-11-13, in `europe-west4-a`, a `util01`
of type `e2-small` from the imported Debian 13 image ran the real weekly restore drill against a real system's
backups at Backblaze B2, with `util01`'s service account. The drill made and destroyed `restore01` by itself and
passed: 4 minutes 46 seconds from the drill's start to its end, `restore_duration_seconds` 256, `util01` created
in 13 seconds, the destroy 24 seconds, and no instance, disk or address left. The four server scripts are
proved on a real project, run as `util01` runs them, the desk's API proxy is proved with a listing, and
the price script is proved on the real catalog ("[Proved on a real project](#proved-on-a-real-project)" below).
A Debian 13 image made with "[The Debian image](#the-debian-image)" was imported and booted with these scripts on
2026-11-12: create 12 seconds, root login with the first-boot marker 31 seconds later, power-off 24 seconds,
destroy 12 seconds. cloud-init ignores `root:` lines in the `ssh-keys` metadata, so the create script writes
`cloudinit:` lines.

**Not yet proved at Compute Engine:** the custom role above exactly as written (the test's service account had
other, wider rights, and the drill's run showed that its role cannot create the firewall rule, which `util01`
never needs); the setup chapters end to end on a Compute Engine project (the 2026-11-13 drill ran on a copy of
a system set up at another provider); the Compute Security Admin role's firewall calls through the API signing
proxy; and the triage agent's server replacement. A drill at setup is still watched:
after setup the coding agent starts the drill once by hand, as
[Start or stop a drill now](../operating_procedures/run_the_weekly_database_restore_drill.md#start-or-stop-a-drill-now)
says, and checks its result as [Read the result](../operating_procedures/run_the_weekly_database_restore_drill.md#read-the-result)
says: `passed` in `latest_result.json`, and no `restore01` left in the list script's output. It records the
result in the checklist item `backups_restore_every_week`. Reason: the weekly drill is the system's proof that
backups restore, and at setup it also proves that `restore01` reaches `util01` through the firewall rule.

### Replacing a credential, and a person who leaves

To replace the person's key, such as after a lost laptop, the person makes a new key for their service account
in Cloud Shell, runs the `personal-token` command again, and then deletes the old key on the service account's
**Keys** tab; the proxy keeps the old key until the new one passed its check. To replace `util01`'s, the person
makes a new key for `util01-restore-drill`, runs `set-up-outside-services secrets --replace
util01_provider_api_token`, the coding agent runs `every_server`, and the person deletes the old key. When a
person leaves, the person who stays deletes the leaving person's service account; `util01`'s key keeps working.

When the team moves its servers away from Compute Engine, the desk review that changes
`systems_desk_provider_api_authentication` deletes `/etc/systems-desk/provider-api-signing-credential.json` from
the desk, and once the project holds no server of the system, the person deletes every service account of the
system, or the whole project ([Move the servers to another provider](../operating_procedures/move_the_servers_to_another_provider.md), step 6).

## The provider scripts' request function

The scripts use Compute Engine's REST API with `curl` and `jq`, through one function. The function goes through
the API proxy on a desk, where the coding agent has no credential, and where `SERVER_PROVIDER_API_TOKEN`
is set, on `util01` and in the person's own terminal on the laptop during the first desk's bootstrap, it makes
its own access token from the key with `openssl` once per script. It needs `bash`, `curl`, `openssl` and `jq`,
and works in Debian's `bash` and in the older `bash` 3.2 that macOS has. Reason for `curl` over Google's own
`gcloud`: `gcloud` is a download of several hundred megabytes with its own Python, to pin and review on
`util01`, the desk and the laptop, while the token takes three `openssl` and `curl` steps.

Put it, with the values above it, at the top of each script, after `#!/bin/bash` and `set -euo pipefail`:

```bash
google_api_address=https://compute.googleapis.com/compute/v1/  # systems_desk_provider_api_url
google_project_id=example-systems-123456                        # the project's ID
google_network=default                                          # the VPC network the servers use
google_stack_system_id=example_systems                          # every server's stack-system-id label

# google_boot_disk_gib MACHINE_TYPE: the boot disk's size, from chapter 6's
# sizes: 80 GiB for the app server's type, 40 GiB for the others.
google_boot_disk_gib() {
  case "$1" in e2-custom-4-8192) echo 80 ;; *) echo 40 ;; esac
}

base64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

# google_access_token_from_the_key: trades a JWT, signed with the private key
# of the key file in SERVER_PROVIDER_API_TOKEN, for an access token that lasts
# an hour. The key and the signed JWT pass only through pipes.
google_access_token_from_the_key() {
  local key_file header claims signature
  key_file=$(printf '%s' "$SERVER_PROVIDER_API_TOKEN" | openssl base64 -d -A)
  header=$(printf '{"alg":"RS256","typ":"JWT"}' | base64url)
  claims=$(printf '%s' "$key_file" | jq -c --argjson now "$(date +%s)" '{iss: .client_email,
    scope: "https://www.googleapis.com/auth/compute https://www.googleapis.com/auth/cloud-billing.readonly",
    aud: "https://oauth2.googleapis.com/token", iat: $now, exp: ($now + 3600)}' | base64url)
  signature=$(printf '%s.%s' "$header" "$claims" |
    openssl dgst -sha256 -sign <(printf '%s' "$key_file" | jq -r .private_key) | base64url)
  printf 'grant_type=urn%%3Aietf%%3Aparams%%3Aoauth%%3Agrant-type%%3Ajwt-bearer&assertion=%s' "$header.$claims.$signature" |
    curl --silent --show-error --fail --connect-timeout 10 --max-time 30 --data-binary @- https://oauth2.googleapis.com/token |
    jq -er .access_token
}
google_access_token=''
[ -z "${SERVER_PROVIDER_API_TOKEN:-}" ] || google_access_token=$(google_access_token_from_the_key)

# google_request METHOD PATH [BODY_FILE]
# Sends one request to PATH under the API address, such as
# "projects/$google_project_id/aggregated/instances", or under the price
# catalog's for a PATH that starts with cloudbilling/, prints the answer's
# body, and fails on an answer that is not 2xx with Google's error status,
# without printing the body.
google_request() {
  local method=$1 path=$2 body_file=${3:-} url answer http_status_code status
  local -a body_arguments=()
  [ -z "$body_file" ] || body_arguments=(--header 'Content-Type: application/json' --data-binary "@$body_file")
  answer=$(mktemp)
  if [ -z "${SERVER_PROVIDER_API_TOKEN:-}" ]; then
    http_status_code=$(curl --silent --show-error --connect-timeout 10 --max-time 120 --request "$method" \
      ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' "http://127.0.0.1:8081/$path")
  else
    case "$path" in
      cloudbilling/*) url="https://cloudbilling.googleapis.com/${path#cloudbilling/}" ;;
      *) url="$google_api_address$path" ;;
    esac
    # The token goes through standard input, never the command line, which
    # other accounts on the server can read.
    http_status_code=$(printf 'Authorization: Bearer %s\n' "$google_access_token" |
      curl --silent --show-error --connect-timeout 10 --max-time 120 --header @- --request "$method" \
        ${body_arguments[@]+"${body_arguments[@]}"} --output "$answer" --write-out '%{http_code}' "$url")
  fi
  case "$http_status_code" in
    2??) cat -- "$answer"; rm -f -- "$answer" ;;
    *) status=$(jq -r '[.error.status // empty, (.error.errors[]?.reason // empty), (.error.details[]?.reason // empty)] | unique | join(" ")' \
         < "$answer" 2> /dev/null || true)
       printf 'Google answered %s %s with HTTP %s %s (body withheld)\n' "$method" "${path%%\?*}" "$http_status_code" "$status" >&2
       rm -f -- "$answer"; return 1 ;;
  esac
}

# google_instances: every instance of the project, in every zone, as a JSON
# array of Compute Engine's instance objects, from every page of the listing.
# A zone that does not answer fails the listing (returnPartialSuccess is off).
google_instances() {
  local pages='' page next_page_token=''
  while :; do
    page=$(google_request GET "projects/$google_project_id/aggregated/instances?maxResults=500${next_page_token:+&pageToken=$next_page_token}")
    # Each page's instances are one line; jq joins the lines at the end. A
    # growing list is never a command-line argument: a whole project's
    # instances can pass the 131,072 bytes Linux allows for one argument.
    pages+=$(printf '%s' "$page" | jq -c '[.items[]?.instances[]?]')$'\n'
    next_page_token=$(printf '%s' "$page" | jq -r '.nextPageToken // empty')
    [ -n "$next_page_token" ] || break
  done
  printf '%s' "$pages" | jq -cs 'add'
}
```

For example, the coding agent's own reads use the same paths through the proxy, such as
`curl -sS http://127.0.0.1:8081/projects/PROJECT_ID/zones/europe-west4-a/machineTypes/e2-custom-2-4096`.

The time limits are the guide's defaults: 10 seconds to connect and 120 seconds for an answer. Never pass
credentials or first-boot data as command-line arguments. Keep first-boot files mode `0600` and clear them after
reading, including on failure. Use the [Compute Engine API reference](https://docs.cloud.google.com/compute/docs/reference/rest/v1)
for request fields.

## The provider scripts

Each script is `#!/bin/bash`, `set -euo pipefail`, the values and the request function above, then its own part
below, in `server_management_scripts/` under the contract's names. They follow the
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts), and the rules after
them say why.

`list_the_servers_at_the_provider`:

```bash
google_instances | jq '{servers: [.[] | {id, name,
    public_ipv4_address: (.networkInterfaces[0].accessConfigs[0].natIP // ""),
    power_state: ({"RUNNING": "running", "TERMINATED": "stopped"}[.status] // .status)}]}'
```

`create_a_server_at_the_provider`:

```bash
# Compute Engine keeps no SSH keys of its own: each --ssh-key-name is a line
# here, the name, a "|", then the public key, as root_ssh_public_keys has it.
# The create script sends each key in the `ssh-keys` metadata as a line that
# starts with `cloudinit:`: cloud-init's Compute Engine data source installs
# the keys only from lines that start with `cloudinit:` or the default
# user's name, `debian:`. With `disable_root: false` in the first-boot data,
# `root` gets them too.
google_ssh_public_keys='
desk01, alex|ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExampleExampleExampleExampl alex@desk01
util01, the mmhotline user|ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExampleExampleExampleExampm mmhotline@util01
'
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
body_file=$(mktemp); errors=$(mktemp); chmod 600 "$body_file"
# Clear the first-boot data after reading it, also on failure.
trap ': > "$first_boot_data"; rm -f -- "$body_file" "$errors"' EXIT
[ "${#ssh_key_names[@]}" -ge 1 ] || { echo "give at least one --ssh-key-name" >&2; exit 2; }
ssh_keys=''
for key_name in "${ssh_key_names[@]}"; do
  key=$(printf '%s\n' "$google_ssh_public_keys" | awk -F'|' -v n="$key_name" '$1 == n { print $2; exit }')
  [ -n "$key" ] || { echo "no line for the SSH key $key_name in google_ssh_public_keys" >&2; exit 2; }
  ssh_keys="${ssh_keys}cloudinit:$key"$'\n'
done
z="projects/$google_project_id/zones/$location"
jq -n --arg name "$server_name" --arg zone "$location" --arg type "$server_type" --arg image "$image" \
  --arg network "$google_network" --arg keys "$ssh_keys" --arg system "$google_stack_system_id" \
  --argjson disk "$(google_boot_disk_gib "$server_type")" --rawfile userData "$first_boot_data" \
  '{name: $name, machineType: ("zones/" + $zone + "/machineTypes/" + $type),
    disks: [{boot: true, autoDelete: true, initializeParams: {sourceImage: $image, diskSizeGb: ($disk | tostring),
             diskType: ("zones/" + $zone + "/diskTypes/pd-balanced")}}],
    networkInterfaces: [{network: ("global/networks/" + $network), stackType: "IPV4_ONLY",
                         accessConfigs: [{type: "ONE_TO_ONE_NAT", name: "External NAT"}]}],
    metadata: {items: [{key: "user-data", value: $userData}, {key: "ssh-keys", value: $keys},
                       {key: "block-project-ssh-keys", value: "TRUE"}, {key: "enable-oslogin", value: "FALSE"}]},
    labels: {"stack-system-id": $system}, serviceAccounts: []}' > "$body_file"
: > "$first_boot_data"
write_receipt() {  # write_receipt JSON: replaces the ownership file in one step
  [ -z "$ownership_file" ] || { printf '%s\n' "$1" > "$ownership_file.new" && mv -- "$ownership_file.new" "$ownership_file"; }
}
new_request_id() { od -An -N16 -tx1 /dev/urandom | tr -d ' \n' | sed -E 's/^(.{8})(.{4})(.{4})(.{4})(.{12})$/\1-\2-\3-\4-\5/'; }
# The same requestId makes a repeated create return the first one's
# operation, so a lost answer is sent again with it. A refusal for capacity
# created nothing, so its retry takes a new ID.
request_id=$(new_request_id)
capacity_deadline=$(( $(date +%s) + 300 )) resent_after_a_lost_answer=''
while :; do
  if operation=$(google_request POST "$z/instances?requestId=$request_id" "$body_file" 2> "$errors"); then
    server_id=$(jq -r '.targetId' <<< "$operation")
    write_receipt "$(jq -n --arg id "$server_id" --arg name "$server_name" '{id: $id, name: $name}')"
    operation_name=$(jq -r '.name' <<< "$operation")
    for _ in $(seq 1 60); do
      [ "$(jq -r '.status' <<< "$operation")" = DONE ] && break
      sleep 5
      operation=$(google_request GET "$z/operations/$operation_name")
    done
    # DONE can mean failed: the operation's error names why.
    reasons=$(jq -r '[.error.errors[]?.code] | join(" ")' <<< "$operation")
    [ -z "$reasons" ] && break
    echo "the create failed: $reasons" >&2
  else
    cat -- "$errors" >&2
    reasons=$(cat -- "$errors")
    if grep -qE 'with HTTP (000|5)' "$errors" && [ -z "$resent_after_a_lost_answer" ]; then
      sleep 30; resent_after_a_lost_answer=yes; continue
    fi
  fi
  if [[ "$reasons" =~ ZONE_RESOURCE_POOL_EXHAUSTED ]] && [ "$(date +%s)" -lt "$capacity_deadline" ]; then
    sleep 20; request_id=$(new_request_id); continue
  fi
  exit 1
done
for _ in $(seq 1 90); do
  detail=$(google_instances | jq -c --arg i "$server_id" '[.[] | select(.id == $i)][0] // {}')
  address=$(jq -r '.networkInterfaces[0].accessConfigs[0].natIP // empty' <<< "$detail")
  if [ "$(jq -r '.status // empty' <<< "$detail")" = RUNNING ] && [ -n "$address" ]; then
    result=$(jq -n --arg id "$server_id" --arg name "$server_name" --arg a "$address" --arg t "$server_type" --arg l "$location" \
      --arg w "$wireguard_public_key" --arg i "$private_ip" \
      '{id: $id, name: $name, public_ipv4_address: $a, server_type: $t, location: $l, wireguard_public_key: $w, private_ip: $i}')
    write_receipt "$result"
    printf '%s\n' "$result"
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not RUNNING with a public IPv4 address after 15 minutes" >&2
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
listing=$(google_instances)
if [ -n "$server_id" ]; then
  # Never fall back from a missing ID to a matching name.
  if ! jq -e --arg i "$server_id" 'any(.[]; .id == $i)' <<< "$listing" > /dev/null; then
    echo "no server with ID $server_id: nothing to destroy" >&2
    jq -n --arg i "$server_id" '{id: $i, deleted: true}'
    exit 0
  fi
elif [ -n "$server_name" ]; then
  # Names repeat across zones, so a name must match exactly one server.
  server_id=$(jq -r --arg n "$server_name" '[.[] | select(.name == $n) | .id] | if length == 1 then .[0] else empty end' <<< "$listing")
  [ -n "$server_id" ] || { echo "expected exactly one server named $server_name" >&2; exit 1; }
else
  echo "give --server-id or --server-name" >&2; exit 2
fi
zone=$(jq -r --arg i "$server_id" '[.[] | select(.id == $i) | .zone | split("/") | last][0]' <<< "$listing")
google_request DELETE "projects/$google_project_id/zones/$zone/instances/$server_id" > /dev/null
# Deletion accepted is not deletion finished: wait until a whole listing lacks
# the ID. A failed listing stops the script; it never counts as "gone".
for _ in $(seq 1 60); do
  if ! google_instances | jq -e --arg i "$server_id" 'any(.[]; .id == $i)' > /dev/null; then
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
detail_of() {  # detail_of: "STATUS ZONE" of the server from a whole listing, or nothing when it is not listed
  google_instances | jq -r --arg i "$server_id" '[.[] | select(.id == $i) | "\(.status) \(.zone | split("/") | last)"][0] // empty'
}
detail=$(detail_of)
[ -n "$detail" ] || { echo "no server with ID $server_id" >&2; exit 1; }
# Compute Engine has no power cut: stop shuts the operating system down, and
# noGracefulShutdown skips the instance's own graceful-shutdown wait.
case "${detail%% *}" in TERMINATED|STOPPING) ;; *)
  google_request POST "projects/$google_project_id/zones/${detail#* }/instances/$server_id/stop?noGracefulShutdown=true" > /dev/null ;;
esac
for _ in $(seq 1 30); do
  detail=$(detail_of)
  if [ "${detail%% *}" = TERMINATED ]; then
    jq -n --arg i "$server_id" '{id: $i, power_state: "stopped"}'
    exit 0
  fi
  sleep 10
done
echo "server $server_id is not stopped after 5 minutes" >&2
exit 1
```

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
machine=$(google_request GET "projects/$google_project_id/zones/$location/machineTypes/$server_type")
# A shared-core type bills a fraction of a core that Google's catalog does not
# name; the setup's sizes are whole cores.
[ "$(jq -r '.isSharedCpu // false' <<< "$machine")" = false ] ||
  { echo "$server_type shares a CPU core; price it on Google's page https://cloud.google.com/compute/vm-instance-pricing" >&2; exit 1; }
family=$(printf '%s' "${server_type%%-*}" | tr '[:lower:]' '[:upper:]')
# Compute Engine's SKUs in the public price catalog, every page. Compute
# Engine's service ID in the catalog is 6F81-5844-456A.
# Each page's kept SKUs are one line of $skus, and jq reads the lines from
# standard input: the real catalog keeps about 1.5 MB, more than the 131,072
# bytes Linux allows for one command-line argument.
skus='' next_page_token=''
while :; do
  page=$(google_request GET "cloudbilling/v1/services/6F81-5844-456A/skus?pageSize=5000${next_page_token:+&pageToken=$next_page_token}")
  skus+=$(printf '%s' "$page" | jq -c --arg region "${location%-*}" \
    '[.skus[] | select(.category.usageType == "OnDemand" and ((.serviceRegions | index($region)) or (.serviceRegions | index("global"))))]')$'\n'
  next_page_token=$(printf '%s' "$page" | jq -r '.nextPageToken // empty')
  [ -n "$next_page_token" ] || break
done
printf '%s' "$skus" | jq -s --argjson machine "$machine" --arg family "$family" --argjson disk "$(google_boot_disk_gib "$server_type")" '
  add as $skus |
  def price(prefix): [$skus[] | select(.description | startswith(prefix))] |
    if length == 1 then .[0].pricingInfo[0].pricingExpression.tieredRates[-1].unitPrice
    else error("no single price for \(prefix)") end;
  def amount: (.units | tonumber) + .nanos / 1e9;
  (price($family + " Instance Core running in")) as $core | (price($family + " Instance Ram running in")) as $ram |
  (price("Balanced PD Capacity in")) as $balanced | (price("External IP Charge on a Standard VM")) as $address |
  {monthly_price: (((($core | amount) * $machine.guestCpus + ($ram | amount) * $machine.memoryMb / 1024 + ($address | amount)) * 730
                    + ($balanced | amount) * $disk) * 100 | round / 100),
   currency: $core.currencyCode}'
```

These scripts, with an access token made in the shell as on `util01`, are proved on a real project, the price
script on Google's real catalog ("[Proved on a real project](#proved-on-a-real-project)" below). The Stack's tests
(`tests/google_compute_engine_provider_scripts_test.py`) run these blocks, with each `bash` on the test machine,
macOS's 3.2 included, against a stand-in for Compute Engine, its price catalog and Google's token address that
checks each JWT's signature with the key's public key, with the token in the shell and through the proxy,
including a create whose answer is lost and a capacity refusal.

**Rules.** The list script's `power_state` is `running` for the status `RUNNING` and `stopped` for `TERMINATED`,
which at Compute Engine means stopped; `PROVISIONING`, `STAGING`, `STOPPING`, `SUSPENDING`, `SUSPENDED` and
`REPAIRING` pass through as they are. IDs are strings: they can exceed the largest whole number `jq` keeps
exactly, so the scripts never turn them into numbers. Names repeat across zones, so every later step uses the
ID, and finds its zone in the complete listing. The create writes its receipt as soon as Compute Engine accepts
the create, from the operation's `targetId`, then waits for the operation to be `DONE` and checks its `error`,
because `DONE` can mean failure. Its `requestId` makes a create whose answer was lost safe to send once more:
Compute Engine returns the first create's operation instead of making a second. A refusal with
`ZONE_RESOURCE_POOL_EXHAUSTED` created nothing, so the create tries again every 20 seconds, with a new
`requestId`, for at most 5 minutes, as the contract says. The destroy script treats an ID the complete listing
does not show as destroyed. Compute Engine has no power cut: the power-off script's stop shuts the operating
system down ([stop](https://docs.cloud.google.com/compute/docs/instances/stop-start-instance)), so a power-failure
test at Compute Engine tests a clean shutdown, as at OVHcloud.

The price is the machine type's cores and memory, its public IPv4 address for 730 hours and its boot disk for a
month, before any tax, from the [Cloud Billing Catalog API](https://docs.cloud.google.com/billing/docs/how-to/get-pricing-information-api),
which needs no IAM permission but the project's Cloud Billing API turned on. For example,
`read_the_monthly_price_at_the_provider --server-type e2-custom-2-4096 --location europe-west4-a` prints
`{"monthly_price": ..., "currency": "USD"}`. Data sent out to the internet is priced separately, per GB.

## The Debian image

Google's own Debian 13 image has no cloud-init, so it ignores first-boot data. The person imports Debian's
[Debian 13 genericcloud amd64 image](https://cloud.debian.org/images/cloud/trixie/latest/) once, in Cloud Shell,
following Google's [manual import guide](https://docs.cloud.google.com/compute/docs/import/import-existing-image),
with `PROJECT`, `BUCKET` and `IMAGE` set to the project, a new unique bucket name and an image name such as
`debian-13-genericcloud-20261110`:

```sh
base=https://cloud.debian.org/images/cloud/trixie/latest
curl -fLO "$base/SHA512SUMS"
curl -fLO "$base/debian-13-genericcloud-amd64.tar.xz"
expected=$(awk '$2 == "debian-13-genericcloud-amd64.tar.xz" {print $1}' SHA512SUMS)
test -n "$expected"
printf '%s  debian-13-genericcloud-amd64.tar.xz\n' "$expected" | sha512sum -c -
tar -xJf debian-13-genericcloud-amd64.tar.xz
expected=$(awk '$2 == "debian-13-genericcloud-amd64.raw" {print $1}' SHA512SUMS)
test -n "$expected"
printf '%s  disk.raw\n' "$expected" | sha512sum -c -
tar --format=oldgnu -Sczf disk.tar.gz disk.raw
gcloud --project="$PROJECT" storage buckets create "gs://$BUCKET" \
  --location=europe-west4 --uniform-bucket-level-access \
  --public-access-prevention --soft-delete-duration=0
gcloud --project="$PROJECT" storage cp disk.tar.gz "gs://$BUCKET/disk.tar.gz"
gcloud --project="$PROJECT" compute images create "$IMAGE" \
  --source-uri="gs://$BUCKET/disk.tar.gz" --architecture=X86_64 \
  --guest-os-features=UEFI_COMPATIBLE,VIRTIO_SCSI_MULTIQUEUE,GVNIC \
  --licenses=projects/debian-cloud/global/licenses/debian-13-trixie
gcloud --project="$PROJECT" compute images describe "$IMAGE" --format='value(status,selfLink)'
gcloud --project="$PROJECT" storage rm "gs://$BUCKET/disk.tar.gz"
gcloud --project="$PROJECT" storage buckets delete "gs://$BUCKET" --quiet
```

The extracted file is `disk.raw` while `SHA512SUMS` names it `debian-13-genericcloud-amd64.raw`, so the second
check names the file. Google requires a GNU-format gzip tar holding only `disk.raw`. Wait for `READY`, then set
`server_image` in `mmx_project_settings.yml` to the image's path, `projects/PROJECT/global/images/IMAGE`. Reason
for a fixed image name rather than a family: a family picks a changing image, and replacements and restores
must boot the same one. The disposable bucket has soft delete off, so deleting its object keeps no billable
copy. The download address, `.../trixie/latest/`, has no date, so record in the checklist the `Last-Modified`
header of the download (`curl -fsI "$base/debian-13-genericcloud-amd64.tar.xz"`) or the image's creation date,
and both hashes. A person who imports the image through the REST API writes `rawDisk.source` as
`https://storage.googleapis.com/BUCKET/disk.tar.gz`; `gcloud` accepts `gs://BUCKET/disk.tar.gz`.

Debian's genericcloud image has cloud-init with the
[GCE datasource](https://docs.cloud-init.io/en/latest/reference/datasources/gce.html), reads the `user-data`
metadata the create sends, and installs the `ssh-keys` metadata's keys only from lines that start with
`cloudinit:` or the default user's name, `debian:`; the create script writes `cloudinit:`; with
`disable_root: false` in the first-boot data, `root` gets them too. It has no Google guest agent, so nothing
else reads the metadata. Debian genericcloud 13's `ssh.service` has `After=cloud-init-network.service`; its
`ssh.socket` does not, so keep socket activation off. Prove first boot through authenticated WireGuard SSH or the
serial console; public SSH is closed on purpose.

## Sizes, network and quotas

E2 [custom types](https://docs.cloud.google.com/compute/docs/instances/creating-instance-with-custom-machine-type)
that meet the setup's sizes are `e2-custom-4-8192` with an 80 GiB boot disk for `app001`, and `e2-custom-2-4096`
with 40 GiB for `db01`, `util01` and `staging01`, as `google_boot_disk_gib` gives. `e2-small` has only 2 GiB and
a shared core. ARM families need ARM images and programs, so use x86 E2. Check
[quotas](https://docs.cloud.google.com/compute/resource-usage) for regional E2 CPUs, instances, disks, external
addresses and a new account's `CPUs (All Regions)`, and leave room for `restore01` and a replacement.

The project's `default` network has [auto-mode subnets](https://docs.cloud.google.com/vpc/docs/subnets#ip-ranges)
in `10.128.0.0/9`, which do not overlap `10.20.0.0/16`. Compute Engine's
[VPC firewall](https://docs.cloud.google.com/firewall/docs/firewalls) filters before the server's own firewall,
and a new project's `default` network admits SSH, RDP and ICMP from anywhere. Once, at setup, before the first
server is created, the coding agent makes the network admit WireGuard from outside and removes the rules that
admit SSH, RDP and ICMP (ping) from outside. It uses the
person's credential through the API proxy (the person's service account above, which has Compute
Security Admin); the person clicks nothing in the console:

```sh
curl -sS -X POST http://127.0.0.1:8081/projects/PROJECT/global/firewalls -H 'Content-Type: application/json' \
  -d '{"name":"allow-wireguard","network":"global/networks/default","direction":"INGRESS","allowed":[{"IPProtocol":"udp","ports":["443","51820"]}],"sourceRanges":["0.0.0.0/0"]}'
for rule in default-allow-ssh default-allow-rdp default-allow-icmp; do
  curl -sS -X DELETE "http://127.0.0.1:8081/projects/PROJECT/global/firewalls/$rule"
done
sleep 15
curl -sS http://127.0.0.1:8081/projects/PROJECT/global/firewalls | jq -r '.items[].name'
```

Each call returns an operation that Google finishes a few seconds later, so the listing waits 15 seconds;
a listing taken at once can still show a deleted rule (seen in a real run on 2026-11-13). The coding agent deletes `default-allow-icmp` as well, because it admits ping from
anywhere, which the Stack has no use for. The project's `default-allow-internal` rule stays: it admits traffic
only from the network's own addresses, `10.128.0.0/9`, which no outside host can use, and UFW still filters each
server. A team that has no other machines on the network may delete `default-allow-internal` the same way; we
recommend that, and the Stack works either way. From outside, the network then admits only WireGuard.

The person sees the coding agent's message that it made the rule `allow-wireguard`, and the rule's name in the
listing, which has no `default-allow-ssh`, `default-allow-rdp` or `default-allow-icmp`. The person knows it worked when the
listing shows `allow-wireguard` and, later, when the restore drill at setup reaches `restore01`. `util01`'s own
service account cannot make this rule: its custom role has no firewall permission, and Google refused the
call with HTTP 403 in a real run on 2026-11-13, on a project that had no rule, so `restore01` could not reach
`util01` until a wider credential made it. That is intended: `util01` never changes the network. A project that
has no `allow-wireguard` rule gets it from the coding agent the same way.

UFW still does the Stack's filtering on each server. The create gives no server a service account
(`serviceAccounts: []`), because a service account's token comes from the metadata address, which the Stack
blocks; it sets `block-project-ssh-keys` and turns OS Login off, because the Stack manages root's keys. Delete
an instance's boot disk with it (`autoDelete`), so nothing billable is left; an address the team reserved stays
until deleted.

For power-cycle checks, the coding agent powers a server off with the script and on through the proxy:

```sh
./server_management_scripts/power_off_a_server_at_the_provider --server-id SERVER_ID
curl -sS -X POST http://127.0.0.1:8081/projects/PROJECT_ID/zones/ZONE/instances/SERVER_ID/start
./server_management_scripts/list_the_servers_at_the_provider | jq '.servers[] | select(.id == "SERVER_ID")'
```

Wait for `power_state` `stopped` after the power-off and `running` after the start. An ephemeral public address
can change on a stop and start: update `public_ipv4_address` in the inventory and run `every_server`, so
WireGuard's endpoints follow.

## Proved on a real project

On 2026-11-12, in `europe-west4-a`, the guide's scripts, with the access token made in the shell as on `util01`,
on the project's `default` network, from Ubuntu's `ubuntu-2404-noble-amd64-v20261105` image, which has cloud-init:

| Step | Result | Seconds |
| --- | --- | --- |
| Create an `e2-micro`, with first-boot data | `STAGING`, then `RUNNING` with a public IPv4 address; the first-boot file was cleared | 12 |
| SSH as `root` with the `ssh-keys` key | read the marker the first-boot data wrote | 40 |
| Power off (`noGracefulShutdown`) | `STOPPING`, then `TERMINATED` (`stopped`); the ephemeral public address went with the stop | 56 |
| Power off again, and a nonexistent ID | done at once; `no server with ID ...`, exit 1 | 2, 0 |
| Destroy | left out of the complete listing | 13 |
| Destroy again | `no server with ID ...: nothing to destroy`, done | 1 |
| Price | refused: the project's Cloud Billing API was off (`SERVICE_DISABLED`) | 1 |

The price script then ran on 2026-11-12, from a Linux server, against Google's real Cloud Billing Catalog, with
a narrow test service account key. The catalog keeps 1,984 SKUs (1.5 MB) for the region, more than Linux allows
in one command-line argument (131,072 bytes, `jq: Argument list too long`), so the scripts give `jq` every page on
standard input. The script answered, with exit code 0 and nothing on standard error, `{"monthly_price": 61.9, "currency": "USD"}` for
`e2-standard-2` and `{"monthly_price": 86.1, "currency": "USD"}` for `n2-standard-2` in `europe-west4-a`, which
are the hand calculation from the same catalog's rates (61.90 and 86.10 USD a month). The price was not compared
with Google's pricing page, whose tables load by script.

Afterwards the project held no instance, disk or address. The desk's API proxy made a token from the key
and listed the project's servers with no credential in the caller's environment.

## Console and rescue access

Set instance metadata `serial-port-enable=TRUE` through the proxy, check that the organization's policy permits
serial access, and enable `serial-getty@ttyS0.service` on the imported image through MMX. Open **Connect to
serial console**, port 1, following Google's
[serial-console guide](https://docs.cloud.google.com/compute/docs/troubleshooting/troubleshooting-using-serial-console).
Test root login with the shared root console password while WireGuard is stopped, before completing
`provider_console_and_backup_mmhotline_logins`, because browser SSH and serial output do not prove independent
access.

Compute Engine has no rescue boot. For an unbootable server, follow Google's
[rescue VM procedure](https://docs.cloud.google.com/compute/docs/troubleshooting/rescue-vm): snapshot the disk,
attach a recovery copy to a temporary repair VM, and identify the disk before repair. Track the recovery
resources' IDs for cleanup, because snapshots, disks and repair VMs are billed separately.
