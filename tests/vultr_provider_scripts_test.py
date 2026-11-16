#!/usr/bin/env python3
"""The Vultr guide's request function and five provider scripts, run as the
guide prints them against a stand-in for Vultr's v2 API.

  python3 tests/vultr_provider_scripts_test.py

Builds each script from the guide's code blocks and runs it with every bash on
this machine (macOS's /bin/bash is 3.2, Debian's is 5), both through the
stand-in API proxy (no SERVER_PROVIDER_API_TOKEN, as on a desk) and with
the key (as on util01). The stand-in pages every listing two entries at a time
with Vultr's cursors, so the scripts must follow every page.
"""
import base64
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

GUIDE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/provider_guides/vultr.md'
TOKEN = 'VULTRKEY123'
PAGE_SIZE = 2
FIRST_BOOT = '#cloud-config\ndisable_root: false\nruncmd: ["true"]\n'


def guide_blocks():
    """The request function's block, then the five scripts' own parts."""
    text = GUIDE.read_text()
    function_part = text.split("## The provider scripts' request function", 1)[1]
    scripts_part = text.split('## The five provider scripts', 1)[1].split('\n## ', 1)[0]
    function = re.findall(r'```bash\n(.*?)```', function_part, re.S)[0]
    scripts = dict(re.findall(r'`(\w+_at_the_provider)`:\n\n```bash\n(.*?)```', scripts_part, re.S))
    return function, scripts


def instance(label, power_status='running', status='active', main_ip='0.0.0.0'):
    return {'id': str(uuid.uuid4()), 'label': label, 'status': status, 'power_status': power_status,
            'server_status': 'ok', 'main_ip': main_ip, 'default_password': 'never printed'}


class StandIn:
    """Vultr's v2 API for one account, without a key on the proxy port and
    with the key on the API port."""

    def __init__(self):
        self.instances, self.lose_the_next_create_answer, self.refusals, self.posts = [], False, [], 0
        self.keys = [{'id': 'key-desk01', 'name': 'desk01 key'}, {'id': 'key-a', 'name': 'twice'}, {'id': 'key-b', 'name': 'twice'},
                     {'id': 'key-util01', 'name': 'util01 key'}]
        self.os = [{'id': 2136, 'name': 'Debian 12 x64 (bookworm)'}, {'id': 2625, 'name': 'Debian 13 x64 (trixie)'},
                   {'id': 159, 'name': 'Custom'}]
        # Three pages of two: the plan asked for is on the last.
        self.plans = [{'id': 'vc2-%dc' % n, 'monthly_cost': n, 'locations': ['ams']} for n in range(4)] + [
            {'id': 'vc2-2c-4gb', 'monthly_cost': 20, 'hourly_cost': 0.03, 'locations': ['ams', 'fra']}]
        self.plan_listing_authorizations = []
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
                # Vultr's cursors are base64, so they can hold '+' and '=', which must arrive whole.
                start = int(query['cursor'][0].split('+')[1].rstrip('=')) if 'cursor' in query else 0
                following = 'next+%d==' % (start + PAGE_SIZE) if start + PAGE_SIZE < len(items) else ''
                return self.answer(200, {key: items[start:start + PAGE_SIZE],
                                         'meta': {'total': len(items), 'links': {'next': following, 'prev': ''}}})

            def handle_request(self, method):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode()
                url = urlsplit(self.path)
                path, query = url.path.split('/v2/', 1)[-1].lstrip('/'), parse_qs(url.query)
                if method == 'GET' and path == 'plans' and self.server.server_address[1] == stand_in.api_port:
                    # Vultr's plan listing is public.
                    stand_in.plan_listing_authorizations.append(self.headers.get('Authorization'))
                    return self.page('plans', stand_in.plans, query)
                if self.server.server_address[1] == stand_in.api_port and self.headers.get('Authorization') != 'Bearer ' + TOKEN:
                    stand_in.refusals.append('%s %s' % (method, path))
                    return self.answer(401, {'error': 'Invalid API token.', 'status': 401})
                found = [i for i in stand_in.instances if path.startswith('instances/') and i['id'] == path.split('/')[1]]
                listings = {'instances': stand_in.instances, 'ssh-keys': stand_in.keys, 'os': stand_in.os}
                if method == 'GET' and path in listings:
                    return self.page(path.replace('-', '_'), listings[path], query)
                if method == 'GET' and found:
                    found[0].update(status='active', power_status='running', main_ip='192.0.2.10')
                    return self.answer(200, {'instance': found[0]})
                if method == 'POST' and path == 'instances':
                    stand_in.posts += 1
                    request = json.loads(body)
                    created = dict(instance(request['label'], power_status='stopped', status='pending'), request=request)
                    stand_in.instances.append(created)
                    if stand_in.lose_the_next_create_answer:
                        stand_in.lose_the_next_create_answer = False
                        return self.answer(504, {'error': 'Gateway timeout ' + request['user_data']})
                    return self.answer(202, {'instance': created})
                if method == 'POST' and found and path.endswith(('/halt', '/start')):
                    found[0]['power_status'] = 'stopped' if path.endswith('/halt') else 'running'
                    return self.answer(204)
                if method == 'DELETE' and found:
                    stand_in.instances.remove(found[0])
                    return self.answer(204)
                return self.answer(404, {'error': 'Invalid instance-id.', 'status': 404})

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


class VultrProviderScripts(unittest.TestCase):
    def setUp(self):
        self.stand_in = StandIn()
        self.addCleanup(self.stand_in.close)
        self.directory = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.addCleanup(shutil.rmtree, self.directory)
        function, scripts = guide_blocks()
        self.assertEqual(sorted(scripts), ['create_a_server_at_the_provider', 'destroy_a_server_at_the_provider',
                                           'list_the_servers_at_the_provider', 'power_off_a_server_at_the_provider',
                                           'read_the_monthly_price_at_the_provider'])
        self.assertIn('vultr_api_address=https://api.vultr.com/v2/', function)
        self.assertIn('http://127.0.0.1:8081/', function)
        function = re.sub(r'(?m)^vultr_api_address=\S+', 'vultr_api_address=http://127.0.0.1:%d/v2/' % self.stand_in.api_port, function)
        function = function.replace('http://127.0.0.1:8081/', 'http://127.0.0.1:%d/' % self.stand_in.proxy_port)
        for name, body in scripts.items():
            # The waits are for Vultr, not for the stand-in.
            text = '#!/bin/bash\nset -euo pipefail\n%s\n%s' % (function, re.sub(r'sleep \d+', 'sleep 0', body))
            (self.directory/name).write_text(text)
            (self.directory/name).chmod(0o755)

    def run_script(self, bash, name, *arguments, with_token=False, token=TOKEN):
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.directory), 'TMPDIR': str(self.directory)}
        if with_token:
            env['SERVER_PROVIDER_API_TOKEN'] = token
        return subprocess.run([bash, str(self.directory/name), *arguments], text=True, capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=120)

    def create(self, bash, name, with_token, receipt, keys=('desk01 key', 'util01 key'), image='Debian 13 x64 (trixie)'):
        first_boot = self.directory/('first-boot-' + name)
        first_boot.write_text(FIRST_BOOT)
        first_boot.chmod(0o600)
        key_arguments = [part for key in keys for part in ('--ssh-key-name', key)]
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--server-name', name, '--server-type', 'vc2-2c-4gb',
                                 '--location', 'ams', '--image', image, *key_arguments,
                                 '--first-boot-data', str(first_boot), '--wireguard-public-key', 'WIREGUARD_PUBLIC_KEY',
                                 '--wireguard-private-ip', '10.20.1.1', '--ownership-file', str(receipt), with_token=with_token)
        self.assertEqual(first_boot.read_text(), '', 'the create must clear the first-boot data')
        return result

    def servers(self, bash, with_token):
        result = self.run_script(bash, 'list_the_servers_at_the_provider', with_token=with_token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('never printed', result.stdout)
        return json.loads(result.stdout)['servers']

    def test_list_create_and_destroy_through_the_proxy_and_with_the_token(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.instances[:] = [instance('other%d' % n, main_ip='198.51.100.%d' % n) for n in range(4)]
                    self.stand_in.instances[3]['power_status'] = 'stopped'
                    listed = self.servers(bash, with_token)
                    self.assertEqual([s['name'] for s in listed], ['other0', 'other1', 'other2', 'other3'], 'every page')
                    self.assertEqual([s['power_state'] for s in listed], ['running', 'running', 'running', 'stopped'])
                    receipt = self.directory/'receipt.json'
                    created = self.create(bash, 'app001', with_token, receipt)
                    self.assertEqual(created.returncode, 0, created.stderr)
                    self.assertNotIn('never printed', created.stdout + created.stderr)
                    server = json.loads(created.stdout)
                    self.assertEqual(json.loads(receipt.read_text()), server)
                    self.assertEqual({key: server[key] for key in ('name', 'public_ipv4_address', 'server_type', 'location', 'private_ip')},
                                     {'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'server_type': 'vc2-2c-4gb',
                                      'location': 'ams', 'private_ip': '10.20.1.1'})
                    request = self.stand_in.instances[-1]['request']
                    self.assertEqual(base64.b64decode(request['user_data']).decode(), FIRST_BOOT)
                    self.assertEqual((request['sshkey_id'], request['os_id'], request['region'], request['plan'], request['enable_vpc']),
                                     (['key-desk01', 'key-util01'], 2625, 'ams', 'vc2-2c-4gb', False))
                    self.assertIn({'id': server['id'], 'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'power_state': 'running'},
                                  self.servers(bash, with_token))
                    self.stand_in.instances[-1].update(main_ip='0.0.0.0', power_status='starting')
                    self.assertIn({'id': server['id'], 'name': 'app001', 'public_ipv4_address': '', 'power_state': 'starting'},
                                  self.servers(bash, with_token))
                    missing = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', 'not-a-server', with_token=with_token)
                    self.assertEqual((missing.returncode, json.loads(missing.stdout)), (0, {'id': 'not-a-server', 'deleted': True}),
                                     'an ID the provider does not list is destroyed already')
                    self.assertIn('no server with ID not-a-server', missing.stderr)
                    destroyed = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', server['id'], with_token=with_token)
                    self.assertEqual((destroyed.returncode, json.loads(destroyed.stdout or 'null')), (0, {'id': server['id'], 'deleted': True}),
                                     destroyed.stderr)
                    self.assertNotIn(server['id'], [s['id'] for s in self.servers(bash, with_token)])
                    by_name = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-name', 'other1', with_token=with_token)
                    self.assertEqual(by_name.returncode, 0, by_name.stderr)
                    self.assertEqual([s['name'] for s in self.servers(bash, with_token)], ['other0', 'other2', 'other3'])
                    self.assertEqual(self.stand_in.refusals, [])

    def test_power_off_halts_by_the_id_and_waits_until_stopped(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.instances.clear()
                    server = json.loads(self.create(bash, 'app001', with_token, self.directory/'receipt.json').stdout)
                    off = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], with_token=with_token)
                    self.assertEqual((off.returncode, json.loads(off.stdout or 'null')), (0, {'id': server['id'], 'power_state': 'stopped'}), off.stderr)
                    self.assertEqual(self.servers(bash, with_token)[0]['power_state'], 'stopped')
                    again = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], with_token=with_token)
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
                self.stand_in.instances[:] = [instance('app002')]
                self.stand_in.posts = 0
                self.stand_in.lose_the_next_create_answer = True
                receipt = self.directory/'receipt.json'
                created = self.create(bash, 'app002', True, receipt)
                self.assertEqual(created.returncode, 0, created.stderr)
                self.assertEqual(self.stand_in.posts, 1)
                self.assertEqual(json.loads(receipt.read_text())['id'], self.stand_in.instances[-1]['id'])

    def test_a_key_name_and_the_image_must_each_match_exactly_one(self):
        for keys, image, message in ((('twice',), 'Debian 13 x64 (trixie)', 'expected exactly one SSH key named twice'),
                                     (('nobody',), 'Debian 13 x64 (trixie)', 'expected exactly one SSH key named nobody'),
                                     (('util01 key',), 'Debian 13', 'expected exactly one operating system named Debian 13')):
            with self.subTest(message=message):
                self.stand_in.posts = 0
                result = self.create(bash_programs()[0], 'app003', True, self.directory/'receipt.json', keys=keys, image=image)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.stand_in.posts, 0)

    def test_a_wrong_key_fails_without_printing_the_answer(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'list_the_servers_at_the_provider', with_token=True, token='wrong')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('with HTTP 401 (body withheld)', result.stderr)
                self.assertNotIn('Invalid API token', result.stdout + result.stderr)

    def test_the_monthly_price_of_a_plan_in_a_region_without_the_key(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.plan_listing_authorizations.clear()
                    price = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'vc2-2c-4gb',
                                            '--location', 'fra', with_token=with_token)
                    self.assertEqual(price.returncode, 0, price.stderr)
                    self.assertEqual(json.loads(price.stdout), {'server_type': 'vc2-2c-4gb', 'location': 'fra',
                                                                'monthly_price': '20', 'currency': 'USD'})
                    self.assertEqual(self.stand_in.plan_listing_authorizations, [None, None, None],
                                     'every page, and never the key: util01\'s key needs no right for the public listing')
                    for server_type, location, text in (('vc2-9c', 'fra', 'Vultr lists no plan vc2-9c'),
                                                        ('vc2-2c-4gb', 'ewr', 'plan vc2-2c-4gb is not offered in region ewr')):
                        missing = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', server_type,
                                                  '--location', location, with_token=with_token)
                        self.assertEqual((missing.returncode, missing.stdout), (1, ''))
                        self.assertIn(text, missing.stderr)


    def test_listings_larger_than_one_command_line_argument_are_read_whole(self):
        # Linux allows 131,072 bytes for one command-line argument and macOS about 1 MiB for all of them;
        # 1500 instances and 1500 plans of about 1.1 KB each are 1.6 MB each, over both, in several pages.
        global PAGE_SIZE
        original, PAGE_SIZE = PAGE_SIZE, 200
        self.addCleanup(globals().update, PAGE_SIZE=original)
        self.stand_in.instances[:] = [dict(instance('big%d' % n), padding='y' * 1000) for n in range(1500)]
        self.stand_in.plans[:0] = [{'id': 'filler-%d' % n, 'monthly_cost': 1, 'locations': ['fra'], 'padding': 'y' * 1000} for n in range(1500)]
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.assertEqual(len(self.servers(bash, with_token)), 1500)
                    price = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'vc2-2c-4gb',
                                            '--location', 'fra', with_token=with_token)
                    self.assertEqual(price.returncode, 0, price.stderr)


if __name__ == '__main__':
    unittest.main()
