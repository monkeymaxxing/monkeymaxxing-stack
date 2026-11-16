# The one check of the provider's list before a program on util01 believes
# that the provider does not list a server. Sourced from Bash by
# replace_failed_servers, destroy_replaced_servers,
# add_an_app_server_for_the_load, remove_an_app_server_for_the_load, the
# weekly restore drill and util01's check for a leftover restore01, with
# UTIL01_PUBLIC_IPV4_ADDRESS in the env.
#
# An empty or partial answer, such as from a filter in
# list_the_servers_at_the_provider that matches nothing, or from a token of
# another project, would otherwise count a failed server as gone (neither
# powered off nor destroyed, and still paid for), or a leftover restore01 as
# absent. So a list is believed only when it holds util01, the machine these
# programs run on, by its name and public address, as the programs match
# the other servers.

# Exit 0 when the provider's list ($1) holds util01.
the_provider_list_holds_util01() {
  jq -e --arg address "$UTIL01_PUBLIC_IPV4_ADDRESS" \
    '.servers | any(.name == "util01" and .public_ipv4_address == $address)' <<< "$1" > /dev/null
}
not_this_systems_list="the provider's list does not hold util01, the server this program runs on, so it is not this system's whole list: most likely the filter in server_management_scripts/list_the_servers_at_the_provider leaves servers out, or the provider API token belongs to another project"
