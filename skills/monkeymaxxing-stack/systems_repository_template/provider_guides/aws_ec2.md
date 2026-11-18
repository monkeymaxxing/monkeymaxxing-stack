# AWS EC2

EC2 calls a server an **instance**, a size an **instance type**, and a boot image an **AMI**. Follow the shared
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts),
[enrollment contract](../server_management_scripts/README.md#enroll-a-server-before-the-first-mmx-run),
and [initial setup](../initial_setup/). Use a dedicated AWS account for the system, so its access keys reach
nothing else.

## The provider's web console

The person sees the servers in the EC2 console, <https://console.aws.amazon.com/ec2/>:
choose the system's region in the top bar, then **Instances**.

## Credentials on the systems desk

AWS signs each request with the secret access key (Signature Version 4), not with a token in a header. The desk's
**API proxy** does the signing: it listens on
`http://127.0.0.1:8081/`, the same address as at the other providers, signs each request
with the person's access key, and sends it to EC2 in the system's region. The coding agent uses the credential
without reading it.

Set both settings in `mmx_project_settings.yml`, with the system's region in the address:

```yaml
systems_desk_provider_api_url: https://ec2.eu-north-1.amazonaws.com/
systems_desk_provider_api_authentication: aws_signed_requests
```

The proxy takes the region and the service it signs for from the address: `ec2.eu-north-1.amazonaws.com` is
EC2 in Stockholm. `set-up-outside-services` sends the credential only to an address of that form,
`https://ec2.REGION.amazonaws.com/`. An AWS credential has two values, which AWS shows once: the **Access key
ID** and the **Secret access key**. `SERVER_PROVIDER_API_TOKEN` holds them joined with a colon:
`ACCESS_KEY_ID:SECRET_ACCESS_KEY`.

### The person's credential

1. The person makes the AWS account, saves the root login and its two-step codes in the team's password
   manager, and turns on two-step sign-in for the root login.
2. In the IAM console (`https://console.aws.amazon.com/iam/home#/users`), the person creates a user named
   after themselves, such as `alex`, with no console access, and attaches the AWS managed policy
   `AmazonEC2FullAccess`. Reason: the person's credential also prepares the network, the security group and
   the keys below, and the account holds nothing but this system.
3. On the user's **Security credentials** tab, **Create access key**, use case **Command Line Interface
   (CLI)**. AWS shows the Secret access key once.
4. AWS shows the Secret access key once, so the person types both values at once into the laptop key
   command below. You move them to the desk right after the bootstrap.

5. To replace the credential later, the person runs
   `ssh -t desk01 set-up-outside-services personal-token server-provider --server-listing-path '?Action=DescribeInstances&Version=2016-11-15'`.
   The command asks for the Access key ID and the Secret access key, each at a hidden prompt, checks them with
   a signed listing of the region's servers, and only then writes
   `/etc/systems-desk/provider-api-signing-credential.json`, root:root, mode `0600`, restarts the API signing
   proxy, and checks the same listing through `http://127.0.0.1:8081/`. When a check fails, the proxy keeps its
   old credential.

### The laptop key command

The values for [The laptop key command](README.md#the-laptop-key-command):

- **Script:** `~/example-setup/enter-the-aws-key`.
- **Values:** two, in this order: **Access key ID**, **Secret access key**.
- **Shape:** `AKIA` followed by 16 capital letters and digits, then 40 characters of letters, digits, `/` and `+`.
- **Read-only call:** a signed `DescribeInstances` in the system's region, with the guide's `aws_ec2_request` function below, and the two values in the script's memory only.
- **Key file line:** `ACCESS_KEY_ID:SECRET_ACCESS_KEY`.


The proxy forwards each request only to the address in the credential file, refuses a whole address in place
of a path, and a path with `..`, and passes a redirect back without following it.

### util01's credential

`util01` creates, lists, powers off and destroys servers with its own credential, which belongs to the account
and not to a person: the weekly restore drill creates and destroys `restore01`, the daily leftover check
lists the servers, and the triage agent's server replacements run the same scripts there. The person creates
a second IAM user, `util01-restore-drill`, with no console access, gives it the policy below as an inline
policy named `util01-creates-and-destroys-this-systems-servers`, with the region, the account's 12-digit ID
and the system's `stack-system-id` value in place of the examples, and creates its access key as above.
`set-up-outside-services secrets` asks for the two values, each at a hidden prompt, and saves the joined form in
the vault as `util01_provider_api_token`. The restore drill and the leftover check already give that key to the
scripts as `SERVER_PROVIDER_API_TOKEN`, so `util01` needs no other setting and no program beyond Debian's
`curl`, `awk` and `openssl` and the Stack's `jq`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListServersAndImages",
      "Effect": "Allow",
      "Action": ["ec2:DescribeInstances", "ec2:DescribeImages"],
      "Resource": "*"
    },
    {
      "Sid": "LaunchFromTheseResources",
      "Effect": "Allow",
      "Action": "ec2:RunInstances",
      "Resource": [
        "arn:aws:ec2:eu-north-1::image/*",
        "arn:aws:ec2:eu-north-1:111122223333:subnet/*",
        "arn:aws:ec2:eu-north-1:111122223333:network-interface/*",
        "arn:aws:ec2:eu-north-1:111122223333:security-group/*",
        "arn:aws:ec2:eu-north-1:111122223333:key-pair/*"
      ]
    },
    {
      "Sid": "LaunchOnlyThisSystemsServers",
      "Effect": "Allow",
      "Action": "ec2:RunInstances",
      "Resource": [
        "arn:aws:ec2:eu-north-1:111122223333:instance/*",
        "arn:aws:ec2:eu-north-1:111122223333:volume/*"
      ],
      "Condition": {"StringEquals": {"aws:RequestTag/stack-system-id": "example_systems"}}
    },
    {
      "Sid": "TagOnlyWhileLaunching",
      "Effect": "Allow",
      "Action": "ec2:CreateTags",
      "Resource": "arn:aws:ec2:eu-north-1:111122223333:*/*",
      "Condition": {"StringEquals": {"ec2:CreateAction": "RunInstances"}}
    },
    {
      "Sid": "PowerOffAndDestroyOnlyThisSystemsServers",
      "Effect": "Allow",
      "Action": ["ec2:StopInstances", "ec2:TerminateInstances"],
      "Resource": "arn:aws:ec2:eu-north-1:111122223333:instance/*",
      "Condition": {"StringEquals": {"aws:ResourceTag/stack-system-id": "example_systems"}}
    }
  ]
}
```

| Permission | Why `util01` needs it |
| --- | --- |
| `ec2:DescribeInstances` | List servers |
| `ec2:DescribeImages` | Read the AMI's root disk name before a create |
| `ec2:RunInstances`, only with the tag `stack-system-id` on the new instance and disk | Create a server |
| `ec2:CreateTags`, only inside `RunInstances` | Tag the new server and its disk |
| `ec2:StopInstances`, only on a server tagged `stack-system-id` | Power a failed server off, for the triage agent's replacements |
| `ec2:TerminateInstances`, only on a server tagged `stack-system-id` | Destroy a server |

The statements follow AWS's [example policies](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html)
("Tag instances and volumes on creation with specific tags", "Describe all instances, and stop, start, and
terminate only particular instances"). The tag condition is the smallest scope EC2 offers here: `util01` can
power off and destroy any server of this system, and no other instance of the account. `util01` cannot import
SSH keys: the coding agent imports `util01`'s key from the desk before the first drill, as
[Keys](#keys-first-boot-and-the-network) says. The price request reads AWS's public price list, which needs
no credential. A team whose `util01` policy predates this Stack version replaces it with this one in IAM;
the access key stays the same.

**Proved at EC2: the weekly restore drill, once.** On 2026-11-13, in `eu-north-1`, a `util01` of type
`t3.small` ran the real weekly restore drill against a real system's backups at Backblaze B2, with a narrow
IAM user and its tagged security group. The drill made and destroyed `restore01` by itself and passed: 3 minutes
13 seconds from the drill's start to its end, `restore_duration_seconds` 167, `util01` created in 11 seconds,
the destroy 21 seconds, and no running or stopped instance, volume, network interface, address or snapshot left.

**Not yet proved at EC2:** the setup chapters end to end on an EC2 account (the 2026-11-13 drill ran on a copy
of a system set up at another provider), and the narrow policy exactly as this guide gives it (see the test
user's wider rights below). The five
scripts are proved on a real AWS account, run as `util01` runs them, signed in the shell with an IAM user's access
key, and the desk's API proxy is proved with signed listings ("[Proved on a real account](#proved-on-a-real-account)"
below). The narrow credential's power-off is proved too (2026-11-12): with a narrow test user, after a
tag-scoped `ec2:StopInstances` statement was added as this guide gives it, the power-off script stopped a tagged
server in 11 seconds (a repeat on the stopped server took 1 second, and the script refused a nonexistent ID), and
for an instance without the `stack-system-id` tag EC2 refused the same call with HTTP 403 `UnauthorizedOperation`
("no identity-based policy allows the ec2:StopInstances action"), so the tag scope holds. Create took 12 seconds and
destroy 11 seconds with the same user. The test user's other rights are wider than this guide's list: its
`ec2:RunInstances` is not limited to the tag. After setup the coding agent starts the drill once by hand, as
[Start or stop a drill now](../operating_procedures/run_the_weekly_database_restore_drill.md#start-or-stop-a-drill-now)
says, and checks its result as [Read the result](../operating_procedures/run_the_weekly_database_restore_drill.md#read-the-result)
says: `passed` in `latest_result.json`, and no `restore01` left in the list script's output. It records the
result in the checklist item `backups_restore_every_week`. Reason: the weekly drill is the system's proof that
backups restore, so its first run at a new system gets watched.

### Replacing a credential, and a person who leaves

To replace the person's access key, such as after a lost laptop, the person creates a second access key on
the same user, runs the `personal-token` command again, and then deletes the old key on the user's
**Security credentials** tab; the proxy keeps the old key until the new one passed its check. To replace
`util01`'s, the person creates a new key for `util01-restore-drill`, runs
`set-up-outside-services secrets --replace util01_provider_api_token`, the coding agent runs `every_server`,
and the person deletes the old key. When a person leaves, the person who stays deletes the leaving person's
IAM user; `util01`'s key keeps working.

When the team moves its servers away from EC2, the desk review that changes
`systems_desk_provider_api_authentication` deletes `/etc/systems-desk/provider-api-signing-credential.json`
from the desk, and once EC2 holds no server of the system, the person deletes every IAM user of the system
([Move the servers to another provider](../operating_procedures/move_the_servers_to_another_provider.md), step 6).

## The provider scripts' request function

EC2's API is a query API that answers in XML. The scripts send each request with `curl` and read the answer
with a short `awk` reader that turns EC2's XML into JSON for `jq`, through one function. The function goes
through the API proxy on a desk, where the coding agent has no credential, and signs the request with
`curl --aws-sigv4` where `SERVER_PROVIDER_API_TOKEN` is set: `util01`'s jobs, and the person's own terminal on
the laptop during the first desk's bootstrap. It needs `bash`, `curl` 7.75 or newer, `awk`, `openssl` and
`jq`, and works in Debian's `bash` and in the older `bash` 3.2 that macOS has. Reason for `curl` over AWS's own
command-line tool: the tool is a separate download of about 60 MB, with its own version to pin and review on
`util01`, the desk and the laptop, while `curl` already signs requests and every machine has it.

Put it, with the values above it, at the top of each script, after `#!/bin/bash` and `set -euo pipefail`:

```bash
aws_ec2_address=https://ec2.eu-north-1.amazonaws.com/  # systems_desk_provider_api_url
aws_region=eu-north-1                                  # the region in that address
aws_subnet_id=subnet-0123456789abcdef0                 # the subnet the servers use
aws_security_group_id=sg-0123456789abcdef0             # the group that admits UDP 443 and 51820 only
aws_stack_system_id=example_systems                    # every server's stack-system-id tag

# aws_root_disk_gib SERVER_TYPE: the root disk's size, from chapter 6's sizes:
# 80 GiB for the app server's type, 40 GiB for the others.
aws_root_disk_gib() {
  case "$1" in t3.xlarge) echo 80 ;; *) echo 40 ;; esac
}

# ec2_xml_to_json: reads one EC2 answer's XML on standard input and prints it as
# JSON. An element with children is an object, one whose children are all
# <item> is an array, and any other element is a string.
ec2_xml_to_json() {
  awk '
    function replace_all(text, from, to,   out, i) {
      out = ""
      while ((i = index(text, from)) > 0) { out = out substr(text, 1, i - 1) to; text = substr(text, i + length(from)) }
      return out text
    }
    function json_string(text) {
      text = replace_all(text, "&lt;", "<"); text = replace_all(text, "&gt;", ">")
      text = replace_all(text, "&quot;", "\""); text = replace_all(text, "&apos;", "\047")
      text = replace_all(text, "&amp;", "&"); text = replace_all(text, "\\", "\\\\")
      text = replace_all(text, "\"", "\\\""); text = replace_all(text, "\n", "\\n")
      text = replace_all(text, "\r", "\\r"); text = replace_all(text, "\t", "\\t")
      return "\"" text "\""
    }
    function close_element(   value, piece) {
      if (kind[depth] == "array") value = "[" buffer[depth] "]"
      else if (kind[depth] == "object") value = "{" buffer[depth] "}"
      else value = json_string(texts[depth])
      piece = (kind[depth - 1] == "array") ? value : json_string(names[depth]) ":" value
      depth--
      buffer[depth] = buffer[depth] (buffer[depth] == "" ? "" : ",") piece
    }
    BEGIN { RS = "<"; depth = 0; kind[0] = "object"; buffer[0] = "" }
    NR == 1 { next }
    {
      end = index($0, ">"); tag = substr($0, 1, end - 1); text = substr($0, end + 1)
      if (tag ~ /^[?!]/) next
      if (tag ~ /^\//) { close_element(); next }
      empty = (tag ~ /\/$/); sub(/\/$/, "", tag); split(tag, words, /[ \t\r\n]/)
      if (depth > 0 && kind[depth] == "") kind[depth] = (words[1] == "item") ? "array" : "object"
      depth++; names[depth] = words[1]; kind[depth] = ""; buffer[depth] = ""; texts[depth] = empty ? "" : text
      if (empty) close_element()
    }
    END { print "{" buffer[0] "}" }'
}

# aws_ec2_request ACTION [NAME=VALUE ...]
# Sends one EC2 action with its parameters, prints the answer as JSON, and
# fails on an answer that is not 2xx with EC2's error code, without printing
# the answer.
aws_ec2_request() {
  local action=$1 pair body answer http_status_code code
  shift
  body=$(mktemp); answer=$(mktemp); chmod 600 "$body" "$answer"
  printf 'Action=%s&Version=2016-11-15' "$action" > "$body"
  # Values reach jq through standard input, never a command line, which other
  # accounts on the server can read: a create's UserData holds a private key.
  for pair in "$@"; do
    printf '&%s=%s' "${pair%%=*}" "$(printf '%s' "${pair#*=}" | jq -sRr @uri)" >> "$body"
  done
  if [ -z "${SERVER_PROVIDER_API_TOKEN:-}" ]; then
    http_status_code=$(curl --silent --show-error --connect-timeout 10 --max-time 120 \
      --header 'Content-Type: application/x-www-form-urlencoded' --data-binary "@$body" \
      --output "$answer" --write-out '%{http_code}' http://127.0.0.1:8081/)
  else
    # The access key goes through standard input, never the command line.
    http_status_code=$(printf 'user = "%s"\n' "$SERVER_PROVIDER_API_TOKEN" |
      curl --config - --aws-sigv4 "aws:amz:$aws_region:ec2" --silent --show-error --connect-timeout 10 --max-time 120 \
        --header 'Content-Type: application/x-www-form-urlencoded' --data-binary "@$body" \
        --output "$answer" --write-out '%{http_code}' "$aws_ec2_address")
  fi
  rm -f -- "$body"
  case "$http_status_code" in
    2??) ec2_xml_to_json < "$answer"; rm -f -- "$answer" ;;
    *) code=$(ec2_xml_to_json < "$answer" | jq -r '.Response.Errors.Error.Code? // empty' 2> /dev/null || true)
       printf 'EC2 answered %s with HTTP %s %s (body withheld)\n' "$action" "$http_status_code" "$code" >&2
       rm -f -- "$answer"; return 1 ;;
  esac
}

# aws_instances: every instance of the region that is not terminated, as a
# JSON array of EC2's instance objects, from every page of the listing.
aws_instances() {
  local pages='' page next_token=''
  while :; do
    page=$(aws_ec2_request DescribeInstances MaxResults=1000 ${next_token:+"NextToken=$next_token"})
    # Each page's instances are one line; jq joins the lines at the end. A
    # growing list is never a command-line argument: a region's instances can
    # pass the 131,072 bytes Linux allows for one argument.
    pages+=$(printf '%s' "$page" | jq -c \
      '[.DescribeInstancesResponse.reservationSet[]?.instancesSet[]? | select(.instanceState.name != "terminated")]')$'\n'
    next_token=$(printf '%s' "$page" | jq -r '.DescribeInstancesResponse.nextToken? // empty')
    [ -n "$next_token" ] || break
  done
  printf '%s' "$pages" | jq -cs 'add'
}
```

For example, the coding agent's own reads use the same requests through the proxy, such as
`curl -sS http://127.0.0.1:8081/ --data 'Action=DescribeInstanceTypeOfferings&Version=2016-11-15&LocationType=region'`,
which answers in XML.

The time limits are the guide's defaults: 10 seconds to connect and 120 seconds for an answer. Never pass
credentials or first-boot data as command-line arguments. Keep first-boot files mode `0600` and clear them after
reading, including on failure. Use the [EC2 API reference](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/)
for request parameters.

## The provider scripts

Each script is `#!/bin/bash`, `set -euo pipefail`, the values and the request function above, then its own part
below, in `server_management_scripts/` under the contract's names. They follow the
[script contract](../server_management_scripts/README.md#write-the-teams-provider-scripts), and the rules after
them say why.

`list_the_servers_at_the_provider`:

```bash
aws_instances | jq '{servers: [.[] | {id: .instanceId,
    name: ([.tagSet[]? | select(.key == "Name") | .value][0] // ""),
    public_ipv4_address: (.ipAddress // ""),
    power_state: ({"running": "running", "stopped": "stopped"}[.instanceState.name] // .instanceState.name)}]}'
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
errors=$(mktemp)
# Clear the first-boot data after reading it, also on failure.
trap ': > "$first_boot_data"; rm -f -- "$errors"' EXIT
# EC2's create takes one key pair. Reason: the first MMX run writes root's
# whole key list from root_ssh_public_keys.
[ "${#ssh_key_names[@]}" -eq 1 ] || { echo "give exactly one --ssh-key-name: EC2's create takes one key pair" >&2; exit 2; }
[ "$location" = "$aws_region" ] || { echo "--location must be $aws_region, the region of $aws_ec2_address" >&2; exit 2; }
user_data=$(openssl base64 -A < "$first_boot_data")
root_device=$(aws_ec2_request DescribeImages ImageId.1="$image" | jq -r '.DescribeImagesResponse.imagesSet[0].rootDeviceName // empty')
[ -n "$root_device" ] || { echo "no AMI $image in $aws_region" >&2; exit 1; }
credit_arguments=()
case "$server_type" in t*) credit_arguments=(CreditSpecification.CpuCredits=standard) ;; esac
launch() {  # launch CLIENT_TOKEN: one RunInstances; prints the new instance's ID
  aws_ec2_request RunInstances ClientToken="$1" ImageId="$image" InstanceType="$server_type" MinCount=1 MaxCount=1 \
    KeyName="${ssh_key_names[0]}" UserData="$user_data" MetadataOptions.HttpTokens=required \
    NetworkInterface.1.DeviceIndex=0 NetworkInterface.1.SubnetId="$aws_subnet_id" \
    NetworkInterface.1.SecurityGroupId.1="$aws_security_group_id" NetworkInterface.1.AssociatePublicIpAddress=true \
    NetworkInterface.1.DeleteOnTermination=true \
    BlockDeviceMapping.1.DeviceName="$root_device" BlockDeviceMapping.1.Ebs.VolumeSize="$(aws_root_disk_gib "$server_type")" \
    BlockDeviceMapping.1.Ebs.VolumeType=gp3 BlockDeviceMapping.1.Ebs.Encrypted=true BlockDeviceMapping.1.Ebs.DeleteOnTermination=true \
    TagSpecification.1.ResourceType=instance TagSpecification.1.Tag.1.Key=Name TagSpecification.1.Tag.1.Value="$server_name" \
    TagSpecification.1.Tag.2.Key=stack-system-id TagSpecification.1.Tag.2.Value="$aws_stack_system_id" \
    TagSpecification.2.ResourceType=volume TagSpecification.2.Tag.1.Key=Name TagSpecification.2.Tag.1.Value="$server_name" \
    TagSpecification.2.Tag.2.Key=stack-system-id TagSpecification.2.Tag.2.Value="$aws_stack_system_id" \
    ${credit_arguments[@]+"${credit_arguments[@]}"} |
    jq -r '.RunInstancesResponse.instancesSet[0].instanceId'
}
write_receipt() {  # write_receipt JSON: replaces the ownership file in one step
  [ -z "$ownership_file" ] || { printf '%s\n' "$1" > "$ownership_file.new" && mv -- "$ownership_file.new" "$ownership_file"; }
}
# The same ClientToken makes a repeated create return the first one's
# instance, so a lost answer is sent again with it. A refusal for capacity
# created nothing, so its retry takes a new token.
client_token="$server_name-$(date +%s)-$RANDOM"
capacity_deadline=$(( $(date +%s) + 300 )) resent_after_a_lost_answer=''
until server_id=$(launch "$client_token" 2> "$errors"); do
  cat -- "$errors" >&2
  if grep -q 'InsufficientInstanceCapacity' "$errors" && [ "$(date +%s)" -lt "$capacity_deadline" ]; then
    sleep 20; client_token="$server_name-$(date +%s)-$RANDOM"
  elif grep -qE 'with HTTP (000|5)' "$errors" && [ -z "$resent_after_a_lost_answer" ]; then
    sleep 30; resent_after_a_lost_answer=yes
  else
    exit 1
  fi
done
write_receipt "$(jq -n --arg id "$server_id" --arg name "$server_name" '{id: $id, name: $name}')"
for _ in $(seq 1 90); do
  detail=$(aws_instances | jq -c --arg i "$server_id" '[.[] | select(.instanceId == $i)][0] // {}')
  address=$(jq -r '.ipAddress // empty' <<< "$detail")
  if [ "$(jq -r '.instanceState.name // empty' <<< "$detail")" = running ] && [ -n "$address" ]; then
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
listing=$(aws_instances)
if [ -n "$server_id" ]; then
  # Never fall back from a missing ID to a matching name.
  if ! jq -e --arg i "$server_id" 'any(.[]; .instanceId == $i)' <<< "$listing" > /dev/null; then
    echo "no server with ID $server_id: nothing to destroy" >&2
    jq -n --arg i "$server_id" '{id: $i, deleted: true}'
    exit 0
  fi
elif [ -n "$server_name" ]; then
  server_id=$(jq -r --arg n "$server_name" '[.[] | select(any(.tagSet[]?; .key == "Name" and .value == $n)) | .instanceId]
    | if length == 1 then .[0] else empty end' <<< "$listing")
  [ -n "$server_id" ] || { echo "expected exactly one server named $server_name" >&2; exit 1; }
else
  echo "give --server-id or --server-name" >&2; exit 2
fi
aws_ec2_request TerminateInstances InstanceId.1="$server_id" > /dev/null
# Termination accepted is not termination finished: wait until a whole listing
# shows the ID terminated, which the listing leaves out. A failed listing stops
# the script; it never counts as "gone".
for _ in $(seq 1 60); do
  if ! aws_instances | jq -e --arg i "$server_id" 'any(.[]; .instanceId == $i)' > /dev/null; then
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
state_of() {  # state_of: the server's EC2 state from a whole listing, or nothing when it is not listed
  aws_instances | jq -r --arg i "$server_id" '[.[] | select(.instanceId == $i) | .instanceState.name][0] // empty'
}
state=$(state_of)
[ -n "$state" ] || { echo "no server with ID $server_id" >&2; exit 1; }
# SkipOsShutdown cuts the power without asking the operating system to shut down.
case "$state" in stopped|stopping) ;; *)
  aws_ec2_request StopInstances InstanceId.1="$server_id" Force=true SkipOsShutdown=true > /dev/null ;;
esac
for _ in $(seq 1 30); do
  if [ "$(state_of)" = stopped ]; then
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
offers=https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws
# price_rows OFFER TEXT...: the region's public price list for OFFER, only its
# header and the rows that contain one of the quoted TEXTs, as one JSON object
# per row. The lists need no credential; EC2's is about 180 MB, read as it arrives.
price_rows() {
  local offer=$1 pattern
  local -a patterns=(-e '"SKU",')
  shift
  for pattern in "$@"; do patterns+=(-e "\"$pattern\""); done
  curl --silent --show-error --fail --connect-timeout 10 --max-time 900 "$offers/$offer/current/$location/index.csv" |
    { grep -F "${patterns[@]}" || true; } |
    awk '
      function field_list(line,   n, i, c, value, quoted) {
        n = 0; value = ""; quoted = 0
        for (i = 1; i <= length(line); i++) {
          c = substr(line, i, 1)
          if (quoted && c == "\"" && substr(line, i + 1, 1) == "\"") { value = value c; i++ }
          else if (c == "\"") quoted = !quoted
          else if (c == "," && !quoted) { fields[++n] = value; value = "" }
          else value = value c
        }
        fields[++n] = value
        return n
      }
      function replace_all(text, from, to,   out, i) {
        out = ""
        while ((i = index(text, from)) > 0) { out = out substr(text, 1, i - 1) to; text = substr(text, i + length(from)) }
        return out text
      }
      function json_string(text) {
        return "\"" replace_all(replace_all(text, "\\", "\\\\"), "\"", "\\\"") "\""
      }
      { sub(/\r$/, "") }
      /^"SKU",/ { columns = field_list($0); for (i = 1; i <= columns; i++) name[i] = fields[i]; next }
      columns {
        field_list($0); row = ""
        for (i = 1; i <= columns; i++) row = row (i > 1 ? "," : "") json_string(name[i]) ":" json_string(fields[i])
        print "{" row "}"
      }'
}
ec2_rows=$(price_rows AmazonEC2 "$server_type" gp3)
on_demand='select(.TermType == "OnDemand")'
instance_hourly=$(printf '%s\n' "$ec2_rows" | jq -rs --arg t "$server_type" "[.[] | $on_demand | select(.[\"Instance Type\"] == \$t
  and .Tenancy == \"Shared\" and .[\"Operating System\"] == \"Linux\" and .[\"Pre Installed S/W\"] == \"NA\"
  and .CapacityStatus == \"Used\" and .operation == \"RunInstances\" and .Unit == \"Hrs\")] | if length == 1 then .[0].PricePerUnit else empty end")
disk_monthly_per_gib=$(printf '%s\n' "$ec2_rows" | jq -rs "[.[] | $on_demand | select(.[\"Volume API Name\"] == \"gp3\" and .Unit == \"GB-Mo\")]
  | if length == 1 then .[0].PricePerUnit else empty end")
ipv4_hourly=$(price_rows AmazonVPC 'Hourly charge for In-use Public IPv4 Addresses' | jq -rs "[.[] | $on_demand] | if length == 1 then .[0].PricePerUnit else empty end")
for v in instance_hourly disk_monthly_per_gib ipv4_hourly; do
  [ -n "${!v}" ] || { echo "no single on-demand price for $v of $server_type in $location" >&2; exit 1; }
done
# AWS counts 730 hours in a month. The price is the server, its root disk as
# the create script makes it, and its public IPv4 address, before any tax.
jq -n --argjson h "$instance_hourly" --argjson d "$disk_monthly_per_gib" --argjson i "$ipv4_hourly" \
  --argjson g "$(aws_root_disk_gib "$server_type")" \
  '{monthly_price: ((($h + $i) * 730 + $d * $g) * 100 | round / 100), currency: "USD"}'
```

These scripts, signed in the shell as on `util01`, and the request through the API proxy are proved on
a real AWS account; the round's steps and times are in [Proved on a real account](#proved-on-a-real-account).
The Stack's tests (`tests/aws_ec2_provider_scripts_test.py`) run these blocks, with each `bash` on the test
machine, macOS's 3.2 included, against a stand-in for EC2 that checks each request's Signature Version 4,
signed and through the proxy, including a create whose answer is lost and a capacity refusal.

**Rules.** The list script's `power_state` is `running` for the instance state `running` and `stopped` for
`stopped`; `pending`, `stopping` and `shutting-down` pass through as they are, and `terminated` records,
which EC2 keeps for about an hour, are left out. The destroy script treats an ID the listing does not show as
destroyed. The create returns once the instance is `running` with a public IPv4 address; `running` does not
mean cloud-init and WireGuard have finished. The create names the server only by its `Name` tag, which EC2
neither requires to be unique nor keeps from being changed, so every later step uses the instance ID. Its
`ClientToken` makes a create whose answer was lost safe to send once more: EC2 returns the first create's
instance instead of making a second ([idempotency](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html)).
A refusal with `InsufficientInstanceCapacity` created nothing, so the create tries again every 20 seconds, with a
new token, for at most 5 minutes, as the contract says. The power-off script sends `StopInstances` with
`SkipOsShutdown`, which cuts the power without a shutdown of the operating system
([stop methods](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-stop-methods.html)); a server
already `stopped` or `stopping` needs no request. The listing asks for 1000 instances a page and follows
`nextToken` to the end.

## Region, image, sizes and prices

Use a region, such as Stockholm `eu-north-1`, as the scripts' location: `--location` must be the region of
`aws_ec2_address`. An AMI is EC2's boot image. Debian publishes its AMIs from account `136693071363`
([Debian's page](https://wiki.debian.org/Cloud/AmazonEC2Image/Trixie)); image IDs differ by region and change
with each release, so the coding agent reads the newest Debian 13 AMI through the proxy and sets its ID as
`server_image` in `mmx_project_settings.yml`:

```sh
curl -sS http://127.0.0.1:8081/ --data 'Action=DescribeImages&Version=2016-11-15&Owner.1=136693071363&Filter.1.Name=name&Filter.1.Value.1=debian-13-amd64-*'
```

Pick the image with the newest `creationDate` from the answer. Debian's AMI includes cloud-init and defaults
to the user `admin`; the first-boot data sets `disable_root: false`, so cloud-init installs the key pair for
`root` as well. Verify that `cloud-init-network.service` runs before `ssh.service` and `ssh.socket` on the
chosen image, because Debian 13 renamed the network stage.

Within [T3](https://aws.amazon.com/ec2/instance-types/t3/), `t3.medium` supplies 2 vCPUs and 4 GiB for the
database, utility and staging servers, and `t3.xlarge` 4 vCPUs and 16 GiB for the app server, with root disks
of 40 GiB and 80 GiB of gp3, as `aws_root_disk_gib` gives. Reason: smaller T3 sizes fail the shared initial
requirements, and EC2 disks are separate purchases. T3 is x86; Graviton (T4g) needs ARM images and programs
throughout. The create sets T3's `CpuCredits=standard`, which never charges for extra CPU credits and slows
the server once its credits run out.

`read_the_monthly_price_at_the_provider --server-type t3.medium --location eu-north-1` prints, for example,
`{"monthly_price": 41.04, "currency": "USD"}`: the server, its root disk and its public IPv4 address for 730
hours, before any tax, from AWS's public [price list files](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api.html),
which need no credential. Data sent out to the internet is priced separately, per GB. Reason for the files over
AWS's Price List Query API: the query API needs `pricing:GetProducts` on every credential that asks, and
answers at a different address than EC2, while the files are public.

[Standard On-Demand quotas](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-on-demand-instances.html)
count vCPUs, and a new account can start at five. The sizes above need twelve with staging and `restore01`, plus
room for a replacement: ask for more under **Service Quotas** before provisioning. A quota does not guarantee
stock in an Availability Zone.

**Stock:** no public route; AWS shows it only with the credential, and for certain only at the create. With the
credential, before any order, `Action=DescribeInstanceTypeOfferings&LocationType=availability-zone` lists the
Availability Zones that offer a type: on the laptop in chapter 3 with the guide's signed request and the key file,
and through `http://127.0.0.1:8081/` on the desk. Chapter 3 reads it, for the desk and every server of the plan, before its one price screen, as
[the real price, approved once](../initial_setup/03_make_your_server_account_and_your_systems_desk.md#the-real-price-approved-once) says.

## Keys, first boot and the network

Every server needs a VPC subnet. AWS's [default VPC](https://docs.aws.amazon.com/vpc/latest/userguide/default-vpc-components.html),
`172.31.0.0/16`, does not overlap WireGuard's default `10.20.0.0/16`; check a custom VPC for overlaps. AWS's
private addresses are separate from the inventory's `private_ip`. Pick a subnet of the default VPC whose
route table sends `0.0.0.0/0` to an internet gateway, and that assigns no IPv6 address by itself, and set its
ID as `aws_subnet_id`.

EC2 requires a [security group](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html).
Once, at setup, before the first server is created, the coding agent creates one that admits only UDP 443 and UDP 51820 (servers and desks send to 51820 directly) from
anywhere, with the person's credential through the proxy (`AmazonEC2FullAccess` covers both calls; `util01`'s
policy has no security group permission and never needs one), and sets its ID as `aws_security_group_id`.
The person sees the coding agent's message with the group's name, `example_systems-wireguard`, and its ID, and
knows it worked when the agent's `DescribeSecurityGroups` check shows the UDP 443 and UDP 51820 rules and, later, when the
restore drill at setup reaches `restore01`. Reason: EC2 has no server without a security group, an
exception to the shared rule of no provider firewall; UFW and the early SSH guard still do the Stack's
filtering.

```sh
curl -sS http://127.0.0.1:8081/ --data 'Action=CreateSecurityGroup&Version=2016-11-15&GroupName=example_systems-wireguard&GroupDescription=WireGuard+UDP+443+and+51820+only&VpcId=VPC_ID'
curl -sS http://127.0.0.1:8081/ --data 'Action=AuthorizeSecurityGroupIngress&Version=2016-11-15&GroupId=GROUP_ID&IpPermissions.1.IpProtocol=udp&IpPermissions.1.FromPort=443&IpPermissions.1.ToPort=443&IpPermissions.1.IpRanges.1.CidrIp=0.0.0.0/0&IpPermissions.2.IpProtocol=udp&IpPermissions.2.FromPort=51820&IpPermissions.2.ToPort=51820&IpPermissions.2.IpRanges.1.CidrIp=0.0.0.0/0'
```

A new group allows all outbound traffic. The coding agent imports each key pair from the desk, through the
proxy, such as `util01`'s `mmhotline` key from its line in `root_ssh_public_keys`, with the public key in base64:

```sh
key=$(printf '%s' 'ssh-ed25519 AAAA... mmhotline@util01' | openssl base64 -A | jq -sRr @uri)
curl -sS http://127.0.0.1:8081/ --data "Action=ImportKeyPair&Version=2016-11-15&KeyName=util01-mmhotline&PublicKeyMaterial=$key"
curl -sS http://127.0.0.1:8081/ --data 'Action=DescribeKeyPairs&Version=2016-11-15&KeyName.1=util01-mmhotline&IncludePublicKey=true'
```

Compare the listed public key's type and base64 data with the key's line before using the name; EC2 can add a
trailing newline or drop the comment. EC2 accepts one key pair per create, so the create script takes exactly
one `--ssh-key-name`: the key of the machine that runs the first MMX run on the server. Import `util01`'s key
again after rebuilding `util01`.

The create sends the rendered first-boot file as `UserData`, in base64, which EC2's query API requires; EC2
allows at most [16 KB](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html) before encoding.
It requires IMDSv2, the metadata service's token form, during boot; the shared firewall rules block the
metadata address afterwards, because the user data holds the WireGuard private key. If the image has
[`amazon-ssm-agent`](https://docs.aws.amazon.com/systems-manager/latest/userguide/ssm-agent-technical-details.html#imds),
disable it through MMX. The root disk and the network interface go with the server when it is destroyed
(`DeleteOnTermination`). Prove first boot through authenticated WireGuard SSH or the serial console; public SSH
is closed on purpose. For a disposable check, `GetConsoleOutput` with `Latest=true` shows what the first boot
wrote to the console; never print the rendered data or a private key.

For power-cycle checks, the coding agent powers a server off with the script and on through the proxy:

```sh
./server_management_scripts/power_off_a_server_at_the_provider --server-id SERVER_ID
curl -sS http://127.0.0.1:8081/ --data 'Action=StartInstances&Version=2016-11-15&InstanceId.1=SERVER_ID'
./server_management_scripts/list_the_servers_at_the_provider | jq '.servers[] | select(.id == "SERVER_ID")'
```

Wait for `power_state` `stopped` after the power-off and `running` after the start. A server's
[automatic public address changes](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html) on a stop
and start: update `public_ipv4_address` in the inventory and run `every_server`, so WireGuard's endpoints follow.

## Proved on a real account

On 2026-11-12, in `eu-north-1`, the guide's scripts, signed in the shell with `curl --aws-sigv4` as on `util01`,
with the default VPC's subnet and a security group that admitted UDP 443 and SSH from the testing machine:

| Step | Result | Seconds |
| --- | --- | --- |
| Create a `t3.nano` from Debian's `debian-13-amd64-20261111-2659`, with first-boot data | `running` with a public IPv4 address; the first-boot file was cleared | 12 |
| SSH as `root` with the key pair's key | read the marker the first-boot data wrote | 15 |
| Power off (`SkipOsShutdown`) | `stopped`; the automatic public address went with the stop | 21 |
| Power off again, and a nonexistent ID | done at once; `no server with ID ...`, exit 1 | 0 |
| Destroy | `shutting-down`, then left out of the listing | 21, 11 |
| Destroy again | `no server with ID ...: nothing to destroy`, done | 0 |
| Price of `t3.nano` | `{"monthly_price": 10.94, "currency": "USD"}` from the public price files | 3 |

Afterwards no instance but two `terminated` records, no volume, network interface or elastic address was left.
The desk's API proxy answered a signed `DescribeRegions` and `DescribeInstances` from EC2 with no
credential in the caller's environment.

## Console and rescue access

Turn on the [EC2 Serial Console](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-access-to-serial-console.html)
for the account and region, with the person's login in the AWS console. T3 is a
[supported Nitro type](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-serial-console-prerequisites.html).
Check `serial-getty@ttyS0` and the Stack's shared root console password. Open **Connect**, then **EC2 Serial
Console**, while the instance is running. Test an interactive root login before completing
`provider_console_and_backup_mmhotline_logins`, because serial access bypasses the network. Console log
output proves no password login.

For an unbootable root disk, stop the instance before [detaching the root volume](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-detaching-volume.html).
Attach the disk to a temporary rescue server in the [same Availability Zone](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-attaching-volume.html).
Preserve data before repair. Unmount and reattach the repaired disk with the original root-device name.
Check `DeleteOnTermination` before removing rescue resources, because an attached disk can otherwise be lost.
