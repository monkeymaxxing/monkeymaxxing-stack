# Steps shared by the programs on util01 that create a server and own it
# until their own cleanup or a pushed commit: the weekly restore drill
# (playbooks/weekly_database_restore_drill.yml), the row recovery
# (playbooks/recover_rows_from_a_restored_copy.yml) and replace_failed_servers.
# Both source this file from Bash with set -euo pipefail, as the mmhotline
# user, with repository set to util01's copy of the systems repository and
# SERVER_IMAGE, UTIL01_SSH_KEY_NAME, UTIL01_PRIVATE_IP,
# UTIL01_PUBLIC_IPV4_ADDRESS and UTIL01_WIREGUARD_PUBLIC_KEY in the env.
# The SSH and WireGuard commands read ssh/config and ssh/known_hosts from the
# current directory, a copy of the systems repository, as MMX does.
# README.md, "Enroll a server before the first MMX run", gives the reasons
# for each step.

# Makes a new WireGuard key pair in memory and writes the first-boot data for
# a server at PRIVATE_IP that peers with PEERS_JSON (a JSON list of peer
# objects) to FIRST_BOOT_FILE, mode 0600, and the public key to
# PUBLIC_KEY_FILE. The private key leaves memory only inside the first-boot
# data, which the caller removes right after the create.
write_the_first_boot_data() {
  local private_ip=$1 peers_json=$2 first_boot_file=$3 public_key_file=$4 private_key
  ( umask 077
    private_key=$(wg genkey)
    printf '%s\n' "$private_key" | wg pubkey > "$public_key_file"
    printf '%s\n' "$private_key" | jq -Rs --arg private_ip "$private_ip" --argjson peers "$peers_json" \
      '{private_key:rtrimstr("\n"),private_ip:$private_ip,peers:$peers}' | \
      "$repository/server_management_scripts/render_server_first_boot" > "$first_boot_file" )
}

# The port WireGuard listens on, inventory vars.wireguard_listen_port: the
# port servers and desks send to (not the laptops' redirected UDP 443).
wireguard_listen_port() {
  sed -nE 's/^  wireguard_listen_port: *([0-9]+) *(#.*)?$/\1/p' "$repository/inventories/servers.yml"
}

# The peer object for util01, which every new server needs.
util01_as_a_peer() {
  jq -nc --arg public_key "$UTIL01_WIREGUARD_PUBLIC_KEY" --arg allowed_ip "$UTIL01_PRIVATE_IP/32" \
    --arg endpoint "$UTIL01_PUBLIC_IPV4_ADDRESS:$(wireguard_listen_port)" \
    '{public_key:$public_key,allowed_ips:[$allowed_ip],endpoint:$endpoint,persistent_keepalive:25}'
}

# Creates the server NAME and writes the provider's receipt to RECEIPT as
# soon as the provider accepts, so cleanup can destroy the server by its ID.
create_the_owned_server() {
  local name=$1 server_type=$2 location=$3 private_ip=$4 public_key=$5 first_boot_file=$6 receipt=$7
  "$repository/server_management_scripts/create_a_server_at_the_provider" \
    --server-name "$name" --server-type "$server_type" --location "$location" \
    --image "$SERVER_IMAGE" --ssh-key-name "$UTIL01_SSH_KEY_NAME" \
    --wireguard-public-key "$public_key" --wireguard-private-ip "$private_ip" \
    --first-boot-data "$first_boot_file" \
    --ownership-file "$receipt"
}

# Destroys the server that RECEIPT records, by its provider ID, and only when
# the receipt names NAME: a damaged receipt never selects another server.
# Without a receipt, the provider accepted nothing, and nothing is destroyed.
destroy_the_owned_server() {
  local receipt=$1 name=$2 server_id
  [ -f "$receipt" ] || return 0
  server_id=$(jq -er --arg name "$name" 'select(.name == $name) | .id | strings | select(length > 0)' "$receipt") || return 1
  "$repository/server_management_scripts/destroy_a_server_at_the_provider" --server-id "$server_id"
}

# A runtime WireGuard peer on util01, so util01 reaches the new server before
# every_server writes the peer into util01's settings. The outer MMX job
# holds util01's node lock, so root SSH makes only this one change, without
# nesting an MMX job on util01.
add_a_runtime_peer_on_util01() {
  ssh -F ssh/config "root@$UTIL01_PRIVATE_IP" wg set wg0 peer "$1" allowed-ips "$2/32"
}
remove_the_runtime_peer_on_util01() {
  ssh -F ssh/config "root@$UTIL01_PRIVATE_IP" wg set wg0 peer "$1" remove
}

# Records the new server's SSH host key in ./ssh/known_hosts over the
# authenticated WireGuard tunnel, retrying every 2 seconds for up to 5
# minutes. Fixed, with its reason: boot plus the first-boot setup took about
# a minute on test servers, and a server that needs five times as long is a bad
# server. Strict checking resumes for every later connection.
accept_the_host_key_over_wireguard() {
  local address=$1 attempt
  for ((attempt=0; attempt<150; attempt++)); do
    if ssh -F ssh/config -o StrictHostKeyChecking=accept-new -o ConnectTimeout=2 "root@$address" true; then
      return 0
    fi
    [ "$attempt" -lt 149 ] || return 1
    sleep 2
  done
}

# The steps of the two programs that own restore01: the weekly restore drill
# and the row recovery. restore01 lives only in a throwaway clone of util01's
# copy, never in Git, util01's copy or a desk's copy.

# Refuses, before anything is created, when restore01 exists at the provider
# or the inventory holds a restore server. Needs
# steps_for_reading_the_providers_list.bash, and runs in util01's copy.
refuse_when_a_restore_server_exists() {
  local servers
  servers=$("$repository/server_management_scripts/list_the_servers_at_the_provider")
  the_provider_list_holds_util01 "$servers" || { echo "$not_this_systems_list; nothing created" >&2; return 1; }
  jq -e '[.servers[] | select(.name == "restore01")] | length == 0' <<< "$servers" >/dev/null || { echo 'restore01 already exists at the provider; nothing created' >&2; return 1; }
  mmx nodes --json | jq -e '([.nodes[] | select(.name == "restore01")] | length == 0) and ((.groups.database_restore_servers // []) | length == 0)' >/dev/null || { echo 'the inventory has a restore server; nothing created' >&2; return 1; }
}

# Adds restore01, at ADDRESS with PUBLIC_IPV4_ADDRESS and the WireGuard
# PUBLIC_KEY, to the inventory of the throwaway clone in the current
# directory, in database_restore_servers. The group keeps every group var
# and keeps restore01 out of the normal roles.
add_restore01_to_the_inventory_of_this_clone() {
  local address=$1 public_ipv4_address=$2 public_key=$3
  awk -v address="$address" -v public_ipv4_address="$public_ipv4_address" -v public_key="$public_key" '
    /^groups:/ {
      print "  restore01:"
      print "    address: " address
      print "    ssh_user: root"
      print "    connection: ssh_only"
      print "    ssh_known_hosts: ssh/known_hosts"
      print "    ssh_config: ssh/config"
      print "    vars:"
      print "      private_ip: " address
      print "      public_ipv4_address: " public_ipv4_address
      print "      wireguard_public_key: \"" public_key "\""
      print ""
    }
    /^  database_restore_servers:/ { in_restore=1 }
    in_restore && /^    nodes: \[\]/ { sub(/nodes: \[\]/,"nodes: [restore01]"); in_restore=0 }
    { print }
  ' inventories/servers.yml > inventories/servers.yml.new
  mv inventories/servers.yml.new inventories/servers.yml
}
