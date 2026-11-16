#!/usr/bin/env python3
"""Revoke sessions of this Stack's private Access applications, using the desk token."""
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request


def revoke(account, host_names, token):
    def request(path, method='GET'):
        url = 'https://api.cloudflare.com/client/v4/accounts/' + account + '/access/apps' + path
        with urllib.request.urlopen(urllib.request.Request(url, method=method, headers={'Authorization': 'Bearer ' + token}), timeout=30) as response:
            result = json.load(response)
        if result.get('success') is not True:
            raise RuntimeError('Cloudflare refused the Access session revocation.')
        return result
    page = 1
    found = set()
    while True:
        result = request('?page=' + str(page))
        for app in result['result']:
            if app.get('domain') in host_names:
                request('/' + urllib.parse.quote(app['id'], safe='') + '/revoke_tokens', 'POST')
                found.add(app['domain'])
                print('Cloudflare Access sessions revoked: ' + app['domain'], flush=True)
        if page >= result['result_info']['total_pages']:
            break
        page += 1
    missing = host_names - found
    if missing:
        raise RuntimeError('No Cloudflare Access application found for: ' + ', '.join(sorted(missing)))


TOKEN_FILE = Path('/etc/systems-desk/cloudflare-api-token.conf')


def not_revoked(hosts, what_happened):
    """The message when no session was revoked: what happened, and what the person does now and later."""
    return (what_happened + ' The servers are locked out, but people signed in to ' + ', '.join(sorted(hosts)) +
            ' stay signed in. Revoke their sessions now at Cloudflare\'s website, as the table "At each company\'s'
            ' website" in operating_procedures/respond_to_a_break_in.md says for Cloudflare.')


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run on the desk that keeps access as root.')
    account = os.environ['CLOUDFLARE_ACCOUNT_ID']
    if not re.fullmatch('[a-fA-F0-9]{32}', account):
        raise SystemExit('cloudflare_account_id must be the account ID from Cloudflare.')
    hosts = set(json.loads(os.environ['PRIVATE_HOST_NAMES']).values())
    if json.loads(os.environ['STAGING_SERVERS']):
        hosts.update(json.loads(os.environ['STAGING_HOST_NAMES']).values())
    if not TOKEN_FILE.exists():
        raise SystemExit(not_revoked(hosts, 'This desk has no Cloudflare token, ' + str(TOKEN_FILE) + ', so it could not revoke'
                                     ' the Cloudflare Access sessions of your private pages.') +
                         ' After the incident, run set-up-outside-services cloudflare in your own terminal on this desk:'
                         ' it writes the token, so the next lock-out revokes the sessions itself.')
    match = re.fullmatch(r'\s*proxy_set_header Authorization "Bearer ([^"\r\n]+)";\s*', TOKEN_FILE.read_text())
    if not match:
        raise SystemExit(not_revoked(hosts, str(TOKEN_FILE) + ' holds no Bearer Authorization line, so this desk could not'
                                     ' revoke the Cloudflare Access sessions of your private pages.') +
                         ' After the incident, run set-up-outside-services cloudflare in your own terminal on this desk:'
                         ' it writes the token again.')
    try:
        revoke(account, hosts, match[1])
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise SystemExit(not_revoked(hosts, 'Cloudflare did not revoke every Access session: ' + str(error).rstrip('.') + '.'))


if __name__ == '__main__':
    main()
