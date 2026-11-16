#!/usr/bin/env python3
"""The Scaleway guide's request function and five provider scripts, run as
the guide prints them against a stand-in for Scaleway's Instance and IAM APIs.

  python3 tests/scaleway_provider_scripts_test.py

Builds each script from the guide's code blocks and runs it with every bash on
this machine (macOS's /bin/bash is 3.2, Debian's is 5), both through the
stand-in API proxy (no SERVER_PROVIDER_API_TOKEN, as on a desk) and with
the secret key (as on util01). The stand-in pages listings 100 entries at a
time, as Scaleway does at the scripts' page size, and refuses a plain delete
of a server stopped in place, as Scaleway did on a real Project.
"""
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
from urllib.parse import parse_qs, urlsplit

GUIDE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/provider_guides/scaleway.md'
TOKEN = 'scw-secret-123'
PROJECT = '11111111-2222-4333-8444-555555555555'
FIRST_BOOT = '#cloud-config\ndisable_root: false\nruncmd: ["true"]\n'
PAGE_SIZE = 100


def guide_blocks():
    """The request function's block, then the five scripts' own parts."""
    text = GUIDE.read_text()
    function_part = text.split("## The provider scripts' request function", 1)[1]
    scripts_part = text.split('## The five provider scripts', 1)[1].split('\n## ', 1)[0]
    function = re.findall(r'```bash\n(.*?)```', function_part, re.S)[0]
    scripts = dict(re.findall(r'`(\w+_at_the_provider)`:\n\n```bash\n(.*?)```', scripts_part, re.S))
    return function, scripts


def server(name, zone='nl-ams-1', state='running', address=None):
    return {'id': str(uuid.uuid4()), 'name': name, 'zone': zone, 'state': state, 'project': PROJECT,
            'public_ips': [{'id': str(uuid.uuid4()), 'family': 'inet', 'address': address}] if address else [],
            'volumes': {'0': {'id': str(uuid.uuid4()), 'volume_type': 'l_ssd'}}}


class StandIn:
    """Scaleway's APIs for one Project, without a key on the proxy port and
    with the key in X-Auth-Token on the API port."""

    def __init__(self):
        self.catalog_requests = []
        self.servers, self.ips, self.volumes, self.refusals, self.posts = [], [], [], [], 0
        self.user_data, self.lose_the_next_create_answer = {}, False
        self.keys = [{'id': 'k1', 'name': 'desk01 key', 'public_key': 'ssh-ed25519 AAAAdesk desk01'},
                     {'id': 'k2', 'name': 'twice', 'public_key': 'ssh-ed25519 AAAAa a'},
                     {'id': 'k3', 'name': 'twice', 'public_key': 'ssh-ed25519 AAAAb b'},
                     {'id': 'k4', 'name': 'util01 key', 'public_key': 'ssh-ed25519 AAAAutil mmhotline@util01'}]
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def answer(self, code, body=None):
                data = b'' if body is None else json.dumps(body).encode()
                self.send_response(code)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def page(self, key, items, query):
                if query.get('project') != [PROJECT]:
                    return self.answer(400, {'type': 'invalid_arguments'})
                page = int(query.get('page', ['1'])[0])
                return self.answer(200, {key: items[(page - 1)*PAGE_SIZE:page*PAGE_SIZE], 'total_count': len(items)})

            def handle_request(self, method):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode()
                url = urlsplit(self.path)
                path, query = url.path.lstrip('/'), parse_qs(url.query)
                if method == 'GET' and path == 'product-catalog/v2alpha1/public-catalog/products' and self.server.server_address[1] == stand_in.api_port:
                    # The public catalog: 100 other products on page 1, the asked-for types on page 2.
                    stand_in.catalog_requests.append((self.headers.get('X-Auth-Token'), query['zone'][0], query['page'][0]))
                    size = int(query['page_size'][0])
                    products = [{'product': 'OTHER-%d' % n, 'unit_of_measure': {'unit': 'hour', 'size': 1},
                                 'price': {'retail_price': {'currency_code': 'EUR', 'units': 0, 'nanos': 1000000}}} for n in range(100)] + [
                        {'product': 'DEV1-M', 'unit_of_measure': {'unit': 'hour', 'size': 1},
                         'price': {'retail_price': {'currency_code': 'EUR', 'units': 0, 'nanos': 24300000}}},
                        {'product': 'DEV1-M', 'unit_of_measure': {'unit': 'month', 'size': 1},
                         'price': {'retail_price': {'currency_code': 'EUR', 'units': 99, 'nanos': 0}}}]
                    page = int(query['page'][0])
                    return self.answer(200, {'products': products[(page - 1)*size:page*size], 'total_count': len(products)})
                if self.server.server_address[1] == stand_in.api_port and self.headers.get('X-Auth-Token') != TOKEN:
                    stand_in.refusals.append('%s %s' % (method, path))
                    return self.answer(401, {'type': 'denied_authentication', 'message': 'invalid secret key'})
                if method == 'GET' and path == 'iam/v1alpha1/ssh-keys':
                    names = [k for k in stand_in.keys if query['name'][0] in k['name']]
                    return self.answer(200, {'ssh_keys': names, 'total_count': len(names)})
                match = re.fullmatch(r'instance/v1/zones/([a-z0-9-]+)/(.*)', path)
                if not match:
                    return self.answer(404, {'type': 'not_found'})
                zone, route = match.groups()
                in_zone = [s for s in stand_in.servers if s['zone'] == zone]
                found = [s for s in in_zone if route.startswith('servers/') and s['id'] == route.split('/')[1]]
                if method == 'GET' and route == 'servers':
                    return self.page('servers', in_zone, query)
                if method == 'GET' and route == 'ips':
                    return self.page('ips', [i for i in stand_in.ips if i['zone'] == zone], query)
                if method == 'GET' and route == 'volumes':
                    return self.page('volumes', [v for v in stand_in.volumes if v['zone'] == zone], query)
                if method == 'GET' and route == 'products/servers':
                    if 'project' in query:
                        return self.answer(400, {'type': 'invalid_arguments'})
                    return self.answer(200, {'servers': {
                        'DEV1-S': {'volumes_constraint': {'max_size': 20000000000}, 'per_volume_constraint': {'l_ssd': {'max_size': 800000000000}}},
                        'PLAY2-PICO': {'volumes_constraint': {'max_size': 0}, 'per_volume_constraint': {'l_ssd': {'max_size': 0}}}}})
                if method == 'GET' and found:
                    found[0]['state'] = 'running'
                    return self.answer(200, {'server': found[0]})
                if method == 'POST' and route == 'servers':
                    stand_in.posts += 1
                    request = json.loads(body)
                    created = dict(server(request['name'], zone=zone, state='stopped'), request=request)
                    stand_in.volumes.append({'id': created['volumes']['0']['id'], 'zone': zone})
                    stand_in.servers.append(created)
                    if stand_in.lose_the_next_create_answer:
                        stand_in.lose_the_next_create_answer = False
                        return self.answer(504, {'message': 'Gateway timeout'})
                    return self.answer(201, {'server': created})
                if method == 'PATCH' and found and route.endswith('/user_data/cloud-init'):
                    if self.headers.get('Content-Type') != 'text/plain':
                        return self.answer(400, {'type': 'invalid_arguments'})
                    stand_in.user_data[found[0]['id']] = body
                    return self.answer(204)
                if method == 'POST' and route == 'ips':
                    request = json.loads(body)
                    ip = {'id': str(uuid.uuid4()), 'zone': zone, 'address': '192.0.2.10', 'tags': request['tags'],
                          'server': {'id': request['server']}, 'type': request['type']}
                    stand_in.ips.append(ip)
                    owner = [s for s in in_zone if s['id'] == request['server']][0]
                    owner['public_ips'] = [{'id': ip['id'], 'family': 'inet', 'address': ip['address']}]
                    return self.answer(201, {'ip': ip})
                if method == 'POST' and found and route.endswith('/action'):
                    action = json.loads(body)['action']
                    if action == 'terminate':
                        stand_in.servers.remove(found[0])
                        stand_in.volumes[:] = [v for v in stand_in.volumes if v['id'] != found[0]['volumes']['0']['id']]
                        for ip in stand_in.ips:
                            if ip['server'] and ip['server']['id'] == found[0]['id']:
                                ip['server'] = None
                    else:
                        found[0]['state'] = {'poweron': 'running', 'stop_in_place': 'stopped in place', 'poweroff': 'stopped'}[action]
                    return self.answer(202, {'task': {'status': 'pending'}})
                if method == 'DELETE' and found:
                    if found[0]['state'] != 'stopped':
                        return self.answer(400, {'type': 'precondition_failed'})
                    stand_in.servers.remove(found[0])
                    return self.answer(204)
                for kind, items in (('volumes', stand_in.volumes), ('ips', stand_in.ips)):
                    gone = [i for i in items if method == 'DELETE' and route == '%s/%s' % (kind, i['id'])]
                    if gone:
                        items.remove(gone[0])
                        return self.answer(204)
                return self.answer(404, {'type': 'not_found'})

            def do_GET(self):
                self.handle_request('GET')

            def do_POST(self):
                self.handle_request('POST')

            def do_PATCH(self):
                self.handle_request('PATCH')

            def do_DELETE(self):
                self.handle_request('DELETE')

        self.http_servers = [ThreadingHTTPServer(('127.0.0.1', 0), Handler) for _ in range(2)]
        self.proxy_port, self.api_port = (s.server_address[1] for s in self.http_servers)
        for http_server in self.http_servers:
            threading.Thread(target=http_server.serve_forever, daemon=True).start()

    def close(self):
        for http_server in self.http_servers:
            http_server.shutdown()
            http_server.server_close()


def bash_programs():
    found = {}
    for candidate in ['/bin/bash', shutil.which('bash')]:
        if candidate and os.path.exists(candidate):
            found.setdefault(os.path.realpath(candidate), candidate)
    return list(found.values())


class ScalewayProviderScripts(unittest.TestCase):
    def setUp(self):
        self.stand_in = StandIn()
        self.addCleanup(self.stand_in.close)
        self.directory = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.addCleanup(shutil.rmtree, self.directory)
        function, scripts = guide_blocks()
        self.assertEqual(sorted(scripts), ['create_a_server_at_the_provider', 'destroy_a_server_at_the_provider',
                                           'list_the_servers_at_the_provider', 'power_off_a_server_at_the_provider',
                                           'read_the_monthly_price_at_the_provider'])
        self.assertIn('scaleway_api_address=https://api.scaleway.com/', function)
        self.assertIn('http://127.0.0.1:8081/', function)
        function = re.sub(r'(?m)^scaleway_api_address=\S+', 'scaleway_api_address=http://127.0.0.1:%d/' % self.stand_in.api_port, function)
        function = re.sub(r'(?m)^scaleway_project_id=\S+', 'scaleway_project_id=' + PROJECT, function)
        function = function.replace('http://127.0.0.1:8081/', 'http://127.0.0.1:%d/' % self.stand_in.proxy_port)
        for name, body in scripts.items():
            # The waits are for Scaleway, not for the stand-in.
            text = '#!/bin/bash\nset -euo pipefail\n%s\n%s' % (function, re.sub(r'sleep \d+', 'sleep 0', body))
            (self.directory/name).write_text(text)
            (self.directory/name).chmod(0o755)

    def run_script(self, bash, name, *arguments, with_token=False, token=TOKEN):
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.directory), 'TMPDIR': str(self.directory)}
        if with_token:
            env['SERVER_PROVIDER_API_TOKEN'] = token
        return subprocess.run([bash, str(self.directory/name), *arguments], text=True, capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=120)

    def create(self, bash, name, with_token, receipt, keys=('desk01 key', 'util01 key'), server_type='DEV1-S', location='nl-ams-1',
               first_boot_text=FIRST_BOOT):
        first_boot = self.directory/('first-boot-' + name)
        first_boot.write_text(first_boot_text)
        first_boot.chmod(0o600)
        key_arguments = [part for key in keys for part in ('--ssh-key-name', key)]
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--server-name', name, '--server-type', server_type,
                                 '--location', location, '--image', 'debian_trixie', *key_arguments,
                                 '--first-boot-data', str(first_boot), '--wireguard-public-key', 'WIREGUARD_PUBLIC_KEY',
                                 '--wireguard-private-ip', '10.20.1.1', '--ownership-file', str(receipt), with_token=with_token)
        self.assertEqual(first_boot.read_text(), '', 'the create must clear the first-boot data')
        return result

    def servers(self, bash, with_token):
        result = self.run_script(bash, 'list_the_servers_at_the_provider', with_token=with_token)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['servers']

    def test_list_create_and_destroy_through_the_proxy_and_with_the_key(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.servers[:] = [server('other%03d' % n, address='198.51.100.1') for n in range(101)]
                    self.stand_in.servers.append(server('paris1', zone='fr-par-1', state='stopped in place'))
                    self.stand_in.ips.clear()
                    self.stand_in.volumes.clear()
                    listed = self.servers(bash, with_token)
                    self.assertEqual(len(listed), 102, 'every page, in every zone')
                    self.assertEqual([s['power_state'] for s in listed if s['name'] == 'paris1'], ['stopped'])
                    receipt = self.directory/'receipt.json'
                    created = self.create(bash, 'app001', with_token, receipt)
                    self.assertEqual(created.returncode, 0, created.stderr)
                    new = json.loads(created.stdout)
                    self.assertEqual(json.loads(receipt.read_text()), new)
                    self.assertEqual({key: new[key] for key in ('name', 'public_ipv4_address', 'server_type', 'location', 'private_ip')},
                                     {'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'server_type': 'DEV1-S',
                                      'location': 'nl-ams-1', 'private_ip': '10.20.1.1'})
                    request = self.stand_in.servers[-1]['request']
                    self.assertEqual((request['commercial_type'], request['image'], request['project'], request['dynamic_ip_required'],
                                      request['volumes']), ('DEV1-S', 'debian_trixie', PROJECT, False,
                                                            {'0': {'size': 20000000000, 'volume_type': 'l_ssd'}}))
                    self.assertEqual(self.stand_in.user_data[new['id']], FIRST_BOOT +
                                     'allow_public_ssh_keys: false\nusers:\n  - name: root\n    ssh_authorized_keys:\n'
                                     '      - "ssh-ed25519 AAAAdesk desk01"\n      - "ssh-ed25519 AAAAutil mmhotline@util01"\n')
                    self.assertEqual(self.stand_in.ips[-1]['tags'], ['server-' + new['id']])
                    self.assertIn({'id': new['id'], 'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'power_state': 'running'},
                                  self.servers(bash, with_token))
                    missing = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', 'not-a-server', with_token=with_token)
                    self.assertEqual((missing.returncode, json.loads(missing.stdout)), (0, {'id': 'not-a-server', 'deleted': True}),
                                     'an ID the provider does not list is destroyed already')
                    self.assertIn('no server with ID not-a-server', missing.stderr)
                    destroyed = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', new['id'], with_token=with_token)
                    self.assertEqual((destroyed.returncode, json.loads(destroyed.stdout or 'null')), (0, {'id': new['id'], 'deleted': True}),
                                     destroyed.stderr)
                    self.assertNotIn(new['id'], [s['id'] for s in self.servers(bash, with_token)])
                    self.assertEqual((self.stand_in.ips, self.stand_in.volumes), ([], []), 'no address or disk left behind')
                    by_name = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-name', 'paris1', with_token=with_token)
                    self.assertEqual(by_name.returncode, 0, 'a server stopped in place is terminated: ' + by_name.stderr)
                    self.assertNotIn('paris1', [s['name'] for s in self.servers(bash, with_token)])
                    self.assertEqual(self.stand_in.refusals, [])

    def test_a_rerun_of_the_destroy_removes_an_address_whose_server_is_gone(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                self.stand_in.servers.clear()
                self.stand_in.ips[:] = [{'id': 'ip-left', 'zone': 'pl-waw-2', 'address': '192.0.2.20', 'tags': ['server-gone-id'], 'server': None},
                                        {'id': 'ip-other', 'zone': 'pl-waw-2', 'address': '192.0.2.21', 'tags': ['server-another'], 'server': None}]
                result = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', 'gone-id', with_token=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([ip['id'] for ip in self.stand_in.ips], ['ip-other'])

    def test_power_off_stops_in_place_by_the_id_and_waits_until_stopped(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.servers.clear()
                    new = json.loads(self.create(bash, 'app001', with_token, self.directory/'receipt.json', location='pl-waw-3').stdout)
                    off = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', new['id'], with_token=with_token)
                    self.assertEqual((off.returncode, json.loads(off.stdout or 'null')), (0, {'id': new['id'], 'power_state': 'stopped'}), off.stderr)
                    self.assertEqual(self.stand_in.servers[0]['state'], 'stopped in place')
                    self.assertEqual(self.servers(bash, with_token)[0]['power_state'], 'stopped')
                    again = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', new['id'], with_token=with_token)
                    self.assertEqual(again.returncode, 0, 'a stopped server needs no action: ' + again.stderr)
                    missing = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', 'not-a-server', with_token=with_token)
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn('no server with ID not-a-server', missing.stderr)
                    by_name = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-name', 'app001', with_token=with_token)
                    self.assertEqual(by_name.returncode, 2, 'a name is never enough to cut power')
                    self.assertEqual(self.stand_in.refusals, [])

    def test_a_lost_create_answer_finds_the_one_new_server_and_never_posts_again(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                self.stand_in.servers[:] = [server('app002')]
                self.stand_in.posts = 0
                self.stand_in.lose_the_next_create_answer = True
                receipt = self.directory/'receipt.json'
                created = self.create(bash, 'app002', True, receipt)
                self.assertEqual(created.returncode, 0, created.stderr)
                self.assertEqual(self.stand_in.posts, 1)
                self.assertEqual(json.loads(receipt.read_text())['id'], self.stand_in.servers[-1]['id'])

    def test_the_create_refuses_before_any_post(self):
        cases = ((dict(keys=('twice',)), 'expected exactly one SSH key named twice'),
                 (dict(keys=('nobody',)), 'expected exactly one SSH key named nobody'),
                 (dict(server_type='PLAY2-PICO'), 'PLAY2-PICO in nl-ams-1 has no local disk'),
                 (dict(location='us-east-1'), 'us-east-1 is not in scaleway_zones'),
                 (dict(first_boot_text=FIRST_BOOT + 'users: []\n'), 'already sets users or allow_public_ssh_keys'))
        for arguments, message in cases:
            with self.subTest(message=message):
                self.stand_in.posts = 0
                result = self.create(bash_programs()[0], 'app003', True, self.directory/'receipt.json', **arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.stand_in.posts, 0)

    def test_a_wrong_key_fails_without_printing_the_answer(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'list_the_servers_at_the_provider', with_token=True, token='wrong')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('with HTTP 401 (body withheld)', result.stderr)
                self.assertNotIn('invalid secret key', result.stdout + result.stderr)

    def test_an_hourly_price_becomes_a_month_of_730_hours(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.catalog_requests.clear()
                    price = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'DEV1-M',
                                            '--location', 'nl-ams-1', with_token=with_token)
                    self.assertEqual(price.returncode, 0, price.stderr)
                    # 0.0243 euros an hour x 730 hours = 17.739, so 17.74.
                    self.assertEqual(json.loads(price.stdout), {'server_type': 'DEV1-M', 'location': 'nl-ams-1',
                                                                'monthly_price': '17.74', 'currency': 'EUR'})
                    self.assertIn('730 hours', price.stderr)
                    self.assertIn('flexible IPv4 address is priced apart and left out', price.stderr)
                    self.assertEqual(self.stand_in.catalog_requests, [(None, 'nl-ams-1', '1'), (None, 'nl-ams-1', '2')],
                                     'both pages, and never the secret key')
                    for server_type, location, text in (('DEV1-XL', 'nl-ams-1', 'no hourly price for DEV1-XL'),
                                                        ('DEV1-M', 'us-east-1', 'unknown zone us-east-1')):
                        missing = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', server_type,
                                                  '--location', location, with_token=with_token)
                        self.assertEqual((missing.returncode, missing.stdout), (1, ''))
                        self.assertIn(text, missing.stderr)


    def test_a_listing_larger_than_one_command_line_argument_is_read_whole(self):
        # Linux allows 131,072 bytes for one command-line argument and macOS about 1 MiB for all of them;
        # 1500 servers of about 1.1 KB each are 1.6 MB, over both, in 15 pages.
        self.stand_in.servers[:] = [dict(server('big%04d' % n, address='198.51.100.1'), padding='y' * 1000) for n in range(1500)]
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.assertEqual(len(self.servers(bash, with_token)), 1500)


if __name__ == '__main__':
    unittest.main()
