#!/usr/bin/env python3
"""The OVHcloud guide's request function and five provider scripts, run as
the guide prints them against a stand-in for OVHcloud's v1 API.

  python3 tests/ovhcloud_provider_scripts_test.py

Builds each script from the guide's code blocks and runs it with every bash on
this machine (macOS's /bin/bash is 3.2, Debian's is 5), both through the
stand-in API proxy (no SERVER_PROVIDER_API_TOKEN, as on a desk) and
signed in the shell (as on util01). The stand-in checks each signature as
OVHcloud does: SHA-1 over the secret, the consumer key, the method, the whole
URL, the exact body and the time.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
import uuid

GUIDE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/provider_guides/ovhcloud_public_cloud.md'
APPLICATION_KEY, APPLICATION_SECRET, CONSUMER_KEY = 'appkey123', 'appsecret456', 'consumer789'
PROJECT = 'proj0123'
OVHCLOUD_TIME = 1760000000


def guide_blocks():
    """The request function's block, then the five scripts' own parts."""
    text = GUIDE.read_text()
    function_part = text.split("## The provider scripts' request function", 1)[1]
    scripts_part = text.split('## The five provider scripts', 1)[1].split('\n## ', 1)[0]
    function = re.findall(r'```bash\n(.*?)```', function_part, re.S)[0]
    scripts = dict(re.findall(r'`(\w+_at_the_provider)`:\n\n```bash\n(.*?)```', scripts_part, re.S))
    return function, scripts


class StandIn:
    """OVHcloud's v1 API for one project, unsigned on the proxy port and
    signed on the API port."""

    def __init__(self):
        self.catalog_requests = []
        self.instances, self.lose_the_next_create_answer, self.refusals = [], False, []
        # The account's VPS servers, by service name, outside the project.
        self.vps = {}
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def answer(self, code, body):
                data = (body if isinstance(body, str) else json.dumps(body)).encode()
                self.send_response(code)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def handle_request(self, method):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode()
                path = self.path.split('/1.0/', 1)[-1].lstrip('/')
                port = self.server.server_address[1]
                if path == 'auth/time':
                    return self.answer(200, str(OVHCLOUD_TIME))
                if path.startswith('order/catalog/public/cloud?') and port == stand_in.api_port:
                    # The public catalog, outside the project: answered without a signature.
                    stand_in.catalog_requests.append((self.headers.get('X-Ovh-Signature'), path.split('?', 1)[1]))
                    return self.answer(200, {'locale': {'currencyCode': 'USD', 'taxRate': 0}, 'addons': [
                        {'planCode': 'd2-4.consumption', 'pricings': [{'price': 2190000, 'intervalUnit': 'none'}]},
                        {'planCode': 'd2-4.monthly.postpaid', 'pricings': [{'price': 1100000000, 'intervalUnit': 'month'}]}]})
                if port == stand_in.api_port:
                    url = 'http://127.0.0.1:%d/1.0/%s' % (port, path)
                    timestamp = self.headers.get('X-Ovh-Timestamp', '')
                    signed = '+'.join([APPLICATION_SECRET, CONSUMER_KEY, method, url, body, timestamp])
                    if (self.headers.get('X-Ovh-Application') != APPLICATION_KEY or self.headers.get('X-Ovh-Consumer') != CONSUMER_KEY
                            or self.headers.get('X-Ovh-Signature') != '$1$' + hashlib.sha1(signed.encode()).hexdigest()):
                        stand_in.refusals.append('%s %s' % (method, path))
                        return self.answer(400, {'message': 'Invalid signature'})
                vps_route = path.split('?')[0].split('/')
                if method == 'GET' and vps_route[0] == 'vps':
                    if len(vps_route) == 1:
                        return self.answer(200, sorted(stand_in.vps))
                    vps = stand_in.vps.get(vps_route[1])
                    if vps is None:
                        return self.answer(404, {'message': 'not found'})
                    if vps_route[2:] == ['ips']:
                        return self.answer(200, ['2001:db8::77', vps['ip']])
                    return self.answer(200, {'name': vps_route[1], 'state': vps['state']})
                project = 'cloud/project/%s/' % PROJECT
                if not path.startswith(project):
                    return self.answer(403, {'message': 'This call has not been granted'})
                route = path[len(project):].split('?')[0]
                found = [i for i in stand_in.instances if route.startswith('instance/') and i['id'] == route.split('/')[1]]
                if method == 'GET' and route == 'instance':
                    return self.answer(200, stand_in.instances)
                if method == 'GET' and found:
                    found[0].update(status='ACTIVE', ipAddresses=[{'version': 6, 'type': 'public', 'ip': '2001:db8::1'},
                                                                   {'version': 4, 'type': 'public', 'ip': '192.0.2.10'}])
                    return self.answer(200, found[0])
                if method == 'POST' and route == 'instance':
                    request = json.loads(body)
                    instance = {'id': str(uuid.uuid4()), 'name': request['name'], 'status': 'BUILD', 'ipAddresses': [],
                                'userData': request['userData'], 'sshKeyId': request['sshKeyId'], 'networks': request['networks']}
                    stand_in.instances.append(instance)
                    if stand_in.lose_the_next_create_answer:
                        stand_in.lose_the_next_create_answer = False
                        return self.answer(504, {'message': 'Gateway timeout'})
                    return self.answer(200, dict(instance, rescuePassword='never printed'))
                if method == 'POST' and found and route.endswith(('/stop', '/start')):
                    found[0]['status'] = 'SHUTOFF' if route.endswith('/stop') else 'ACTIVE'
                    return self.answer(200, 'null')
                if method == 'DELETE' and found:
                    stand_in.instances.remove(found[0])
                    return self.answer(200, 'null')
                catalog = {'flavor': [{'id': 'flavor-d2-4', 'name': 'd2-4', 'available': True,
                                       'planCodes': {'monthly': 'd2-4.monthly.postpaid', 'hourly': 'd2-4.consumption'}}],
                           'image': [{'id': 'image-debian-13', 'name': 'Debian 13', 'status': 'active'}],
                           'sshkey': [{'id': 'key-desk01', 'name': 'desk01 key'}],
                           'network/public': [{'id': 'not-this-one', 'regions': [
                               {'region': 'US-EAST-VA-1', 'status': 'ACTIVE', 'openstackId': 'ext-net-va-1'}]}]}
                if 'region=NOWHERE-1' in path:
                    return self.answer(404, {'message': 'region not found'})
                if method == 'GET' and route in catalog:
                    return self.answer(200, catalog[route])
                return self.answer(404, {'message': 'not found'})

            def do_GET(self):
                self.handle_request('GET')

            def do_POST(self):
                self.handle_request('POST')

            def do_DELETE(self):
                self.handle_request('DELETE')

        self.servers = [ThreadingHTTPServer(('127.0.0.1', 0), Handler) for _ in range(2)]
        self.proxy_port, self.api_port = (server.server_address[1] for server in self.servers)
        for server in self.servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def close(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()


def bash_programs():
    found = {}
    for candidate in ['/bin/bash', shutil.which('bash')]:
        if candidate and os.path.exists(candidate):
            found.setdefault(os.path.realpath(candidate), candidate)
    return list(found.values())


class OVHcloudProviderScripts(unittest.TestCase):
    def setUp(self):
        self.stand_in = StandIn()
        self.addCleanup(self.stand_in.close)
        self.directory = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.addCleanup(shutil.rmtree, self.directory)
        (self.directory/'inventories').mkdir()
        self.write_inventory('')
        function, scripts = guide_blocks()
        self.assertEqual(sorted(scripts), ['create_a_server_at_the_provider', 'destroy_a_server_at_the_provider',
                                           'list_the_servers_at_the_provider', 'power_off_a_server_at_the_provider',
                                           'read_the_monthly_price_at_the_provider'])
        self.assertIn('ovhcloud_api_address=https://api.us.ovhcloud.com/1.0/', function)
        self.assertIn('http://127.0.0.1:8081/', function)
        function = re.sub(r'(?m)^ovhcloud_api_address=\S+', 'ovhcloud_api_address=http://127.0.0.1:%d/1.0/' % self.stand_in.api_port, function)
        function = re.sub(r'(?m)^ovhcloud_project_id=\S+', 'ovhcloud_project_id=' + PROJECT, function)
        function = function.replace('http://127.0.0.1:8081/', 'http://127.0.0.1:%d/' % self.stand_in.proxy_port)
        for name, body in scripts.items():
            # The lost-answer wait is for OVHcloud, not for the stand-in.
            text = '#!/bin/bash\nset -euo pipefail\n%s\n%s' % (function, body.replace('sleep 30 ', 'sleep 0 ').replace('sleep 10\n', 'sleep 0\n'))
            (self.directory/name).write_text(text)
            (self.directory/name).chmod(0o755)

    def write_inventory(self, util01_vars):
        """The systems repository's inventory, from whose root the scripts run."""
        (self.directory/'inventories/servers.yml').write_text(
            'vars:\n  wireguard_network: 10.20.0.0/16\n\nnodes:\n'
            '  desk01:\n    address: 127.0.0.1\n    vars:\n'
            '      # Its name at the provider (an OVHcloud VPS service name); "" when the provider uses the ID.\n'
            '      provider_server_name: ""\n'
            '  util01:\n    address: 10.20.0.1\n    vars:\n      public_ipv4_address: 192.0.2.77\n' + util01_vars +
            '  db01:\n    address: 10.20.2.1\n    vars:\n'
            '      provider_server_name: "vps-gone0000.vps.ovh.us"   # ended, no longer in the account\n'
            '\ngroups:\n  util_server:\n    nodes: [util01]\n')

    def run_script(self, bash, name, *arguments, signed=False, token=None):
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.directory), 'TMPDIR': str(self.directory)}
        if signed:
            env['SERVER_PROVIDER_API_TOKEN'] = token or '%s:%s:%s' % (APPLICATION_KEY, APPLICATION_SECRET, CONSUMER_KEY)
        return subprocess.run([bash, str(self.directory/name), *arguments], text=True, capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=120, cwd=self.directory)

    def create(self, bash, name, signed, receipt):
        first_boot = self.directory/('first-boot-' + name)
        first_boot.write_text('#cloud-config\ndisable_root: false\nruncmd: ["true"]\n')
        first_boot.chmod(0o600)
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--server-name', name, '--server-type', 'd2-4',
                                 '--location', 'US-EAST-VA-1', '--image', 'Debian 13', '--ssh-key-name', 'desk01 key',
                                 '--first-boot-data', str(first_boot), '--wireguard-public-key', 'WIREGUARD_PUBLIC_KEY',
                                 '--wireguard-private-ip', '10.20.1.1', '--ownership-file', str(receipt), signed=signed)
        self.assertEqual(first_boot.read_text(), '', 'the create must clear the first-boot data')
        return result

    def servers(self, bash, signed):
        result = self.run_script(bash, 'list_the_servers_at_the_provider', signed=signed)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['servers']

    def test_list_create_stop_start_and_destroy_through_the_proxy_and_signed(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.instances.clear()
                    self.assertEqual(self.servers(bash, signed), [])
                    receipt = self.directory/'receipt.json'
                    created = self.create(bash, 'app001', signed, receipt)
                    self.assertEqual(created.returncode, 0, created.stderr)
                    server = json.loads(created.stdout)
                    self.assertEqual(json.loads(receipt.read_text()), server)
                    self.assertEqual({key: server[key] for key in ('name', 'public_ipv4_address', 'server_type', 'location', 'private_ip')},
                                     {'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'server_type': 'd2-4',
                                      'location': 'US-EAST-VA-1', 'private_ip': '10.20.1.1'})
                    sent = self.stand_in.instances[0]
                    self.assertEqual((sent['userData'], sent['sshKeyId'], sent['networks']),
                                     ('#cloud-config\ndisable_root: false\nruncmd: ["true"]\n', 'key-desk01', [{'networkId': 'ext-net-va-1'}]))
                    self.assertNotIn('never printed', created.stdout + created.stderr)
                    self.assertEqual(self.servers(bash, signed), [{'id': server['id'], 'name': 'app001',
                                                                   'public_ipv4_address': '192.0.2.10', 'power_state': 'running'}])
                    sent['status'] = 'SHUTOFF'
                    self.assertEqual(self.servers(bash, signed)[0]['power_state'], 'stopped')
                    sent['status'] = 'REBOOT'
                    self.assertEqual(self.servers(bash, signed)[0]['power_state'], 'REBOOT')
                    missing = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', 'not-a-server', signed=signed)
                    self.assertEqual((missing.returncode, json.loads(missing.stdout)), (0, {'id': 'not-a-server', 'deleted': True}),
                                     'an ID the provider does not list is destroyed already')
                    self.assertIn('no server with ID not-a-server', missing.stderr)
                    destroyed = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((destroyed.returncode, json.loads(destroyed.stdout or 'null')), (0, {'id': server['id'], 'deleted': True}),
                                     destroyed.stderr)
                    self.assertEqual(self.servers(bash, signed), [])
                    self.assertEqual(self.stand_in.refusals, [])

    def test_power_off_stops_a_server_by_its_id_and_waits_until_stopped(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.instances.clear()
                    receipt = self.directory/'receipt.json'
                    server = json.loads(self.create(bash, 'app001', signed, receipt).stdout)
                    off = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((off.returncode, json.loads(off.stdout or 'null')), (0, {'id': server['id'], 'power_state': 'stopped'}), off.stderr)
                    self.assertEqual(self.servers(bash, signed)[0]['power_state'], 'stopped')
                    again = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual(again.returncode, 0, 'a stopped server needs no action: ' + again.stderr)
                    missing = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', 'not-a-server', signed=signed)
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn('no server with ID not-a-server', missing.stderr)
                    by_name = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-name', 'app001', signed=signed)
                    self.assertEqual(by_name.returncode, 2, 'a name is never enough to cut power')
                    self.assertEqual(self.stand_in.refusals, [])

    def test_the_list_holds_the_vps_servers_the_inventory_names_and_never_acts_on_one(self):
        self.write_inventory('      provider_server_name: "vps-77f3667b.vps.ovh.us"\n')
        self.stand_in.vps = {'vps-77f3667b.vps.ovh.us': {'state': 'running', 'ip': '192.0.2.77'},
                             'vps-0ther000.vps.ovh.us': {'state': 'running', 'ip': '192.0.2.99'}}
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.instances.clear()
                    self.create(bash, 'restore01', signed, self.directory/'receipt.json')
                    servers = self.servers(bash, signed)
                    # util01 by its inventory name, with the VPS service name as its ID; another
                    # VPS of the account, which the inventory does not name, stays out.
                    self.assertEqual([(s['name'], s['id'], s['public_ipv4_address'], s['power_state']) for s in servers if s['name'] != 'restore01'],
                                     [('util01', 'vps-77f3667b.vps.ovh.us', '192.0.2.77', 'running')])
                    self.assertEqual(len(servers), 2)
                    for script in ('destroy_a_server_at_the_provider', 'power_off_a_server_at_the_provider'):
                        refused = self.run_script(bash, script, '--server-id', 'vps-77f3667b.vps.ovh.us', signed=signed)
                        self.assertEqual((refused.returncode, refused.stdout), (1, ''), script)
                        self.assertIn('is an OVHcloud VPS', refused.stderr)
                    self.assertIn('vps-77f3667b.vps.ovh.us', self.stand_in.vps)
                    self.assertEqual(self.stand_in.refusals, [])

    def test_the_list_refuses_outside_the_systems_repository(self):
        (self.directory/'inventories/servers.yml').unlink()
        result = self.run_script(bash_programs()[0], 'list_the_servers_at_the_provider')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('run this script from the systems repository', result.stderr)

    def test_a_lost_create_answer_finds_the_one_new_server_and_never_posts_again(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                self.stand_in.instances.clear()
                self.stand_in.lose_the_next_create_answer = True
                receipt = self.directory/'receipt.json'
                created = self.create(bash, 'app002', True, receipt)
                self.assertEqual(created.returncode, 0, created.stderr)
                self.assertEqual(len(self.stand_in.instances), 1)
                self.assertEqual(json.loads(receipt.read_text())['id'], self.stand_in.instances[0]['id'])

    def test_a_wrong_secret_fails_without_printing_the_answer(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'list_the_servers_at_the_provider', signed=True,
                                         token='%s:wrongsecret:%s' % (APPLICATION_KEY, CONSUMER_KEY))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('with HTTP 400 (body withheld)', result.stderr)
                self.assertNotIn('Invalid signature', result.stdout + result.stderr)

    def test_the_create_takes_exactly_one_ssh_key(self):
        result = self.run_script(bash_programs()[0], 'create_a_server_at_the_provider', '--ssh-key-name', 'a', '--ssh-key-name', 'b',
                                 '--first-boot-data', str(self.directory/'none'))
        self.assertEqual(result.returncode, 2)
        self.assertIn('exactly one --ssh-key-name', result.stderr)

    def test_the_hourly_plan_of_a_flavor_times_730_from_the_public_catalog(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.catalog_requests.clear()
                    price = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'd2-4',
                                            '--location', 'US-EAST-VA-1', signed=signed)
                    self.assertEqual(price.returncode, 0, price.stderr)
                    # The servers are billed by the hour: 2190000 hundred-millionths is 0.0219 dollars an hour,
                    # times 730 hours is 15.987, not the monthly plan's 11 dollars.
                    self.assertEqual(json.loads(price.stdout), {'server_type': 'd2-4', 'location': 'US-EAST-VA-1',
                                                                'monthly_price': '15.99', 'currency': 'USD'})
                    self.assertIn('billed by the hour', price.stderr)
                    self.assertEqual(self.stand_in.catalog_requests, [(None, 'ovhSubsidiary=US')],
                                     'the public catalog, never signed with util01\'s credential')
                    missing = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'b2-15',
                                              '--location', 'US-EAST-VA-1', signed=signed)
                    self.assertEqual((missing.returncode, missing.stdout), (1, ''))
                    self.assertIn('OVHcloud lists no hourly plan for the flavor b2-15', missing.stderr)
                    nowhere = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'd2-4',
                                              '--location', 'NOWHERE-1', signed=signed)
                    self.assertEqual((nowhere.returncode, nowhere.stdout), (1, ''))
                    self.assertIn('does not offer the region NOWHERE-1', nowhere.stderr)


if __name__ == '__main__':
    unittest.main()
