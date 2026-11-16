# Steps shared by the programs of the triage agent's server work on util01:
# read_the_fleet_hub_for_server_replacement, replace_failed_servers and
# destroy_replaced_servers (playbooks/replace_failed_servers.yml and
# playbooks/destroy_replaced_servers.yml), and add_an_app_server_for_the_load
# and remove_an_app_server_for_the_load (playbooks/add_an_app_server_for_the_load.yml
# and playbooks/remove_server.yml run without server_name). Sourced from Bash
# with set -euo pipefail.
#
# Nothing of the server work is stored on util01. Its state comes from three
# places a later run reads again: the Git trailers of the commits on main,
# the provider's list, and the fleet hub. So a run that dies half way, or a
# rebuilt util01, loses nothing, and every playbook can be requested again.
# Every commit of the server work carries Server-pool, so
# `git log --grep '^Server-pool: '` lists every change to the pools.

state_dir=/var/lib/replace_failed_servers
fleet_file=$state_dir/fleet.json

# The fleet hub's answer for one node, as the programs see it. A node is:
#   reporting, waiting_for_first_report: never a target. A node waits for its
#     first report for up to 90 seconds after it joins or the hub starts, so
#     right after a util01 restart a dead server shows this before it turns
#     silent.
#   silent: no report within three report intervals, and no whole-server
#     MMWatchdog maintenance window that lasts now.
#   silent_in_planned_maintenance: silent inside a whole-server window
#     (report.maintenance.every_check_group, whose until is later than now),
#     such as a person's planned work. Never a target.
#   silent_during_its_reboot: silent inside the window that
#     reboot_servers_after_updates opens, while that run may still wait for
#     the server to come back. Not a target yet.
#   silent_after_a_failed_reboot: silent inside that window, longer than the
#     run waits for the server to come back plus 2 minutes, so the run's
#     wait has certainly ended. A target: the server did not come back.
# The reboot playbook's reason reads "reboot_servers_after_updates: waits
# 3m for the server to come back", with the wait it used. The 2 minutes,
# fixed: the node may send one more report, 30 seconds apart, between the
# hub's acceptance of the window and the reboot, and the run then needs a
# few seconds to start the reboot.
# Times: the hub's RFC 3339 times; until is the node's clock, compared with
# util01's.
fleet_classes_jq='
  def seconds: sub("\\.[0-9]+"; "") | sub("\\+00:00$"; "Z") | fromdateiso8601;
  def class($now):
    (.report.maintenance.every_check_group // null) as $window |
    if .state != "silent" then {class: .state}
    elif $window == null or ($window.until | seconds) <= $now then {class: "silent"}
    else
      ((($window.reason // "") | capture("^reboot_servers_after_updates: waits (?<minutes>[0-9]+)m for the server to come back$")? | .minutes | tonumber) // null) as $wait |
      if $wait == null then {class: "silent_in_planned_maintenance", reason: ($window.reason // "")}
      else (((.last_report_received_at | seconds) + ($wait + 2) * 60) | floor) as $failed_at |
        if $now >= $failed_at then {class: "silent_after_a_failed_reboot", reboot_wait_minutes: $wait}
        else {class: "silent_during_its_reboot", reboot_wait_minutes: $wait, counts_as_failed_at: $failed_at}
        end
      end
    end;
'

# A copy of the systems repository of this run's own, at origin/main of the
# Git host. Commits go there and never into util01's shared copy, which
# MMHotline keeps at the judged commit.
clone_main() {
  local clone=$1
  git clone --quiet --no-hardlinks --local "$repository" "$clone"
  git -C "$clone" remote set-url origin "$SYSTEMS_REPOSITORY_SSH_URL"
  fetch_main "$clone"
}
fetch_main() {
  git -C "$1" fetch --quiet origin main
  git -C "$1" checkout --quiet --detach FETCH_HEAD
}

# Every commit on main with a Server-pool trailer, as one JSON list of
# {commit, time, trailers: {KEY: [VALUE, ...]}}, newest first.
replacement_history() {
  local clone=$1 commit time
  git -C "$clone" log HEAD --grep='^Server-pool: ' --format='%H %ct' | while read -r commit time; do
    git -C "$clone" show -s --format='%(trailers:only,unfold)' "$commit" | jq -Rn --arg commit "$commit" --argjson time "$time" '
      {commit: $commit, time: $time,
       trailers: ([inputs | capture("^(?<key>[A-Za-z-]+): (?<value>.*)$")?] |
         group_by(.key) | map({key: .[0].key, value: map(.value)}) | from_entries)}'
  done | jq -s .
}

# The replacements whose failed servers no cleanup commit destroyed yet,
# newest first: {commit, pool, replaced, replaced_id, replacement,
# replacement_id, try}. A server name is never used twice, so a name
# identifies a server across the whole history.
pending_replacements() {
  jq -c '
    ([.[] | .trailers["Destroyed-server"][]?]) as $destroyed |
    [.[] | select(.trailers["Replacement-server"]) | .trailers as $t |
      {commit, pool: $t["Server-pool"][0], replaced: $t["Replaced-server"][0],
       replaced_id: $t["Replaced-server-provider-id"][0], replacement: $t["Replacement-server"][0],
       replacement_id: $t["Replacement-server-provider-id"][0], try: ($t["Replacement-try"][0] | tonumber)} |
      select(.replaced as $name | $destroyed | index($name) | not)]' <<< "$1"
}

# The private address of a server name, for example app012 is 10.20.1.12 inside its
# pool's block in private_ip_ranges.
address_of() {
  local name=$1 pool=$2 number
  number=$((10#${name##*[a-z]}))
  jq -nr --argjson ranges "$PRIVATE_IP_RANGES" --arg pool "$pool" --argjson number "$number" \
    '$ranges[$pool] | split("/")[0] | split(".")[0:3] + [($number | tostring)] | join(".")'
}

# The highest number a pool's prefix, such as app, ever used: in the
# inventory's Git history in CLONE, in the provider's list PROVIDER_SERVERS
# (which also holds a desk's server created and not yet committed), in the
# replacement trailers of HISTORY (replacement_history), and in the names
# NAMES_GIVEN, one a line, that this run gave already.
highest_number_used() {
  local clone=$1 prefix=$2 provider_servers=$3 history=$4 names_given=$5
  { git -C "$clone" log -p HEAD -- inventories/servers.yml | sed -nE "s/^[-+ ]  ($prefix[0-9]+):.*/\1/p"
    jq -r '.servers[].name' <<< "$provider_servers"
    jq -r '.[] | .trailers | (.["Replaced-server"], .["Replacement-server"]) | .[]?' <<< "$history"
    printf '%s' "$names_given"
  } | sed -nE "s/^$prefix([0-9]+)$/\1/p" | awk 'BEGIN {highest = 0} {if ($1 + 0 > highest) highest = $1 + 0} END {print highest}'
}

# Changes one pool in inventories/servers.yml of the current directory:
#   OLD and NEW: NEW takes OLD's place (a replacement): OLD's node block
#     becomes NEW's, and NEW takes OLD's place in the pool's nodes list;
#   NEW alone, OLD "": NEW's node block goes after the block of the pool's
#     last server, and NEW to the end of the pool's nodes list (an add);
#   OLD alone, NEW "": OLD's node block and its name in the list go (a
#     removal); ADDRESS and the rest are then "".
# NEW's block holds ADDRESS, PUBLIC_IPV4_ADDRESS, the WireGuard PUBLIC_KEY,
# SERVER_TYPE and LOCATION. Returns 1, changing nothing, when OLD's block or
# the pool's one-line nodes list is not found, or NEW is there already.
change_the_pool_in_the_inventory() {
  local old=$1 new=$2 pool=$3 address=$4 public_ipv4_address=$5 public_key=$6 server_type=$7 location=$8
  if [ -n "$new" ] && grep -q "^  $new:\$" inventories/servers.yml; then return 1; fi
  awk -v old="$old" -v new="$new" -v pool="$pool" -v address="$address" -v public_ipv4_address="$public_ipv4_address" \
    -v public_key="$public_key" -v server_type="$server_type" -v location="$location" '
    function print_the_new_block() {
      print "  " new ":"
      print "    address: " address
      print "    https_address: https://" address ":7443"
      print "    ssh_user: root"
      print "    ssh_known_hosts: ssh/known_hosts"
      print "    ssh_config: ssh/config"
      print "    vars:"
      print "      public_ipv4_address: " public_ipv4_address
      print "      server_type: " server_type
      print "      location: " location
      print "      private_ip: " address
      print "      wireguard_public_key: \"" public_key "\""
      found_block = 1
    }
    # The first reading of the file finds the pool'\''s last server, after
    # whose block an added server goes.
    NR == FNR {
      if ($0 ~ /^groups:/) first_groups = 1
      if (first_groups && $0 == "  " pool ":") first_pool = 1
      else if (first_pool && /^  [^ ]/) first_pool = 0
      if (first_pool && /^    nodes: \[[^]]*\]$/) {
        list = $0; sub(/^    nodes: \[/, "", list); sub(/\]$/, "", list)
        count = split(list, names, ","); last = names[count]; gsub(/ /, "", last)
      }
      next
    }
    FNR == 1 { anchor = (old == "" ? last : "") }
    /^groups:/ {
      in_groups = 1
      if (old == "" && !found_block) { print_the_new_block(); print "" }
    }
    !in_groups && old != "" && $0 == "  " old ":" {
      in_old = 1; found_old = 1
      if (new != "") print_the_new_block()
      next
    }
    in_old {
      if ($0 ~ /^    /) next
      in_old = 0
      if (new == "" && $0 == "") next
    }
    !in_groups && anchor != "" && $0 == "  " anchor ":" { in_anchor = 1; print; next }
    in_anchor {
      if ($0 ~ /^    /) { print; next }
      in_anchor = 0; print ""; print_the_new_block()
    }
    in_groups && $0 == "  " pool ":" { in_pool = 1; print; next }
    in_pool && /^  [^ ]/ { in_pool = 0 }
    in_pool && /^    nodes: \[[^]]*\]$/ {
      list = $0; sub(/^    nodes: \[/, "", list); sub(/\]$/, "", list)
      count = split(list, names, ",")
      line = ""
      for (i = 1; i <= count; i++) {
        name = names[i]; gsub(/ /, "", name)
        if (name == "") continue
        if (old != "" && name == old) { found_list = 1; if (new == "") continue; name = new }
        line = line (line != "" ? ", " : "") name
      }
      if (old == "") { line = line (line != "" ? ", " : "") new; found_list = 1 }
      print "    nodes: [" line "]"
      next
    }
    { print }
    END { exit !((old == "" ? found_block : found_old) && found_list) }
  ' inventories/servers.yml inventories/servers.yml > inventories/servers.yml.new || { rm -f inventories/servers.yml.new; return 1; }
  mv inventories/servers.yml.new inventories/servers.yml
}

# One line with the monthly price of SERVER_TYPE in LOCATION, with its public
# address, from the provider script read_the_monthly_price_at_the_provider,
# for the report of an added or removed server NAME. A price that cannot be
# read says so: the price is the person's information, never a reason to
# stop.
monthly_price_line() {
  local name=$1 server_type=$2 location=$3 price
  if price=$("$repository/server_management_scripts/read_the_monthly_price_at_the_provider" \
       --server-type "$server_type" --location "$location" 2> /dev/null) &&
     jq -e '(.monthly_price | tostring | length > 0) and (.currency | length > 0)' <<< "$price" > /dev/null 2>&1; then
    printf "%s, %s in %s, costs %s %s a month with its public address, at the provider's price now\n" \
      "$name" "$server_type" "$location" "$(jq -r '.monthly_price | tostring' <<< "$price")" "$(jq -r .currency <<< "$price")"
  else
    printf "%s is %s in %s; its monthly price could not be read (server_management_scripts/read_the_monthly_price_at_the_provider)\n" \
      "$name" "$server_type" "$location"
  fi
}

# Runs check-that-this-server-does-its-work on a server over WireGuard and
# SSH, from the clone, whose ssh/known_hosts holds the server's key. Prints
# what fails.
the_server_does_its_work() {
  local clone=$1 address=$2
  (cd "$clone" && ssh -F ssh/config -o ConnectTimeout=10 "root@$address" /usr/local/bin/check-that-this-server-does-its-work < /dev/null)
}

# Pushes the clone's commit to main. When the push is refused, such as
# because a desk pushed meanwhile, fetches main and runs the function named
# by $2 again on the new main, up to 3 pushes in all. The function makes the
# change and the commit, and returns 1 when the change no longer applies.
# 3 pushes, fixed: a desk pushes a few times an hour at most, so a third
# refusal in a row means a cause that retrying does not fix.
push_to_main() {
  local clone=$1 make_the_commit=$2 push
  for push in 1 2 3; do
    "$make_the_commit" || return 1
    if git -C "$clone" push --quiet origin HEAD:main; then
      return 0
    fi
    printf 'the Git host refused push %s of 3 to main; fetching main again\n' "$push"
    fetch_main "$clone" || return 1
  done
  return 1
}
