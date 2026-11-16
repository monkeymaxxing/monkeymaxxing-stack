#!/usr/bin/env python3
"""The DigitalOcean guide's request function and five provider scripts, run
as the guide prints them against a stand-in for DigitalOcean's v2 API.

  python3 tests/digitalocean_provider_scripts_test.py

Builds each script from the guide's code blocks and runs it with every bash on
this machine (macOS's /bin/bash is 3.2, Debian's is 5), both through the
stand-in API proxy (no SERVER_PROVIDER_API_TOKEN, as on a desk) and with
the token (as on util01). The stand-in pages every listing two entries at a
time, so the scripts must follow every page.
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
from urllib.parse import parse_qs, urlsplit

GUIDE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/provider_guides/digitalocean.md'
TOKEN = 'dop_v1_token123'
PAGE_SIZE = 2


def guide_blocks():
    """The request function's block, then the five scripts' own parts."""
    text = GUIDE.read_text()
    function_part = text.split("## The provider scripts' request function", 1)[1]
    scripts_part = text.split('## The five provider scripts', 1)[1].split('\n## ', 1)[0]
    function = re.findall(r'```bash\n(.*?)```', function_part, re.S)[0]
    scripts = dict(re.findall(r'`(\w+_at_the_provider)`:\n\n```bash\n(.*?)```', scripts_part, re.S))
    return function, scripts


class StandIn:
    """DigitalOcean's v2 API for one team, without a token on the proxy port
    and with the token on the API port."""

    def __init__(self):
        self.droplets, self.gpu_droplets, self.lose_the_next_create_answer, self.refusals = [], [], False, []
        self.keys = [{'id': 1001, 'name': 'desk01 key'}, {'id': 1002, 'name': 'twice'}, {'id': 1003, 'name': 'twice'},
                     {'id': 1004, 'name': 'util01 key'}]
        self.next_id, self.posts = 5000, 0
        # Three pages of two: the size asked for is on the last.
        self.sizes = [{'slug': 's-%d' % n, 'price_monthly': n, 'regions': ['ams3']} for n in range(4)] + [
            {'slug': 's-2vcpu-4gb', 'price_monthly': 24.0, 'price_hourly': 0.03571, 'regions': ['ams3', 'fra1']}]
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
                page = int(query.get('page', ['1'])[0])
                chunk = items[(page - 1)*PAGE_SIZE:page*PAGE_SIZE]
                pages = {'next': 'https://api.digitalocean.com/v2/x?page=%d' % (page + 1)} if page*PAGE_SIZE < len(items) else {}
                return self.answer(200, {key: chunk, 'links': {'pages': pages}, 'meta': {'total': len(items)}})

            def handle_request(self, method):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode()
                url = urlsplit(self.path)
                path, query = url.path.split('/v2/', 1)[-1].lstrip('/'), parse_qs(url.query)
                if self.server.server_address[1] == stand_in.api_port and self.headers.get('Authorization') != 'Bearer ' + TOKEN:
                    stand_in.refusals.append('%s %s' % (method, path))
                    return self.answer(401, {'id': 'unauthorized', 'message': 'Unable to authenticate you'})
                found = [d for d in stand_in.droplets + stand_in.gpu_droplets
                         if path.startswith('droplets/') and str(d['id']) == path.split('/')[1]]
                if method == 'GET' and path == 'droplets':
                    if query.get('type') == ['gpus']:
                        return self.page('droplets', stand_in.gpu_droplets, query)
                    return self.page('droplets', stand_in.droplets, query)
                if method == 'GET' and path == 'account/keys':
                    return self.page('ssh_keys', stand_in.keys, query)
                if method == 'GET' and path == 'sizes':
                    return self.page('sizes', stand_in.sizes, query)
                if method == 'GET' and found:
                    found[0].update(status='active', networks={'v4': [{'type': 'private', 'ip_address': '10.110.0.2'},
                                                                      {'type': 'public', 'ip_address': '192.0.2.10'}]})
                    return self.answer(200, {'droplet': found[0]})
                if method == 'POST' and path == 'droplets':
                    stand_in.posts += 1
                    request = json.loads(body)
                    stand_in.next_id += 1
                    droplet = {'id': stand_in.next_id, 'name': request['name'], 'status': 'new', 'networks': {'v4': []},
                               'user_data': request['user_data'], 'ssh_keys': request['ssh_keys'], 'size_slug': request['size'],
                               'region': request['region'], 'image': request['image']}
                    stand_in.droplets.append(droplet)
                    if stand_in.lose_the_next_create_answer:
                        stand_in.lose_the_next_create_answer = False
                        return self.answer(504, {'id': 'timeout', 'message': 'Gateway timeout ' + request['user_data']})
                    return self.answer(202, {'droplet': droplet})
                if method == 'POST' and found and path.endswith('/actions'):
                    kind = json.loads(body)['type']
                    found[0]['status'] = {'power_off': 'off', 'power_on': 'active'}[kind]
                    return self.answer(201, {'action': {'id': 1, 'type': kind, 'status': 'in-progress'}})
                if method == 'DELETE' and found:
                    (stand_in.droplets if found[0] in stand_in.droplets else stand_in.gpu_droplets).remove(found[0])
                    return self.answer(204)
                return self.answer(404, {'id': 'not_found', 'message': 'The resource you requested could not be found.'})

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


class DigitalOceanProviderScripts(unittest.TestCase):
    def setUp(self):
        self.stand_in = StandIn()
        self.addCleanup(self.stand_in.close)
        self.directory = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.addCleanup(shutil.rmtree, self.directory)
        function, scripts = guide_blocks()
        self.assertEqual(sorted(scripts), ['create_a_server_at_the_provider', 'destroy_a_server_at_the_provider',
                                           'list_the_servers_at_the_provider', 'power_off_a_server_at_the_provider',
                                           'read_the_monthly_price_at_the_provider'])
        self.assertIn('digitalocean_api_address=https://api.digitalocean.com/v2/', function)
        self.assertIn('http://127.0.0.1:8081/', function)
        function = re.sub(r'(?m)^digitalocean_api_address=\S+', 'digitalocean_api_address=http://127.0.0.1:%d/v2/' % self.stand_in.api_port, function)
        function = function.replace('http://127.0.0.1:8081/', 'http://127.0.0.1:%d/' % self.stand_in.proxy_port)
        for name, body in scripts.items():
            # The waits are for DigitalOcean, not for the stand-in.
            text = '#!/bin/bash\nset -euo pipefail\n%s\n%s' % (function, re.sub(r'sleep \d+', 'sleep 0', body))
            (self.directory/name).write_text(text)
            (self.directory/name).chmod(0o755)

    def run_script(self, bash, name, *arguments, with_token=False, token=TOKEN):
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.directory), 'TMPDIR': str(self.directory)}
        if with_token:
            env['SERVER_PROVIDER_API_TOKEN'] = token
        return subprocess.run([bash, str(self.directory/name), *arguments], text=True, capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=120)

    def create(self, bash, name, with_token, receipt, keys=('desk01 key', 'util01 key')):
        first_boot = self.directory/('first-boot-' + name)
        first_boot.write_text('#cloud-config\ndisable_root: false\nruncmd: ["true"]\n')
        first_boot.chmod(0o600)
        key_arguments = [part for key in keys for part in ('--ssh-key-name', key)]
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--server-name', name, '--server-type', 's-2vcpu-4gb',
                                 '--location', 'ams3', '--image', 'debian-13-x64', *key_arguments,
                                 '--first-boot-data', str(first_boot), '--wireguard-public-key', 'WIREGUARD_PUBLIC_KEY',
                                 '--wireguard-private-ip', '10.20.1.1', '--ownership-file', str(receipt), with_token=with_token)
        self.assertEqual(first_boot.read_text(), '', 'the create must clear the first-boot data')
        return result

    def servers(self, bash, with_token):
        result = self.run_script(bash, 'list_the_servers_at_the_provider', with_token=with_token)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['servers']

    def test_list_create_and_destroy_through_the_proxy_and_with_the_token(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.droplets[:] = [{'id': 10 + n, 'name': 'other%d' % n, 'status': 'active', 'networks': {'v4': []}}
                                                 for n in range(3)]
                    self.stand_in.gpu_droplets[:] = [{'id': 99, 'name': 'gpu1', 'status': 'off', 'networks': {'v4': []}}]
                    listed = self.servers(bash, with_token)
                    self.assertEqual(sorted(s['id'] for s in listed), ['10', '11', '12', '99'], 'every page, and the GPU listing')
                    self.assertEqual([s['power_state'] for s in listed if s['id'] == '99'], ['stopped'])
                    receipt = self.directory/'receipt.json'
                    created = self.create(bash, 'app001', with_token, receipt)
                    self.assertEqual(created.returncode, 0, created.stderr)
                    server = json.loads(created.stdout)
                    self.assertEqual(json.loads(receipt.read_text()), server)
                    self.assertEqual({key: server[key] for key in ('name', 'public_ipv4_address', 'server_type', 'location', 'private_ip')},
                                     {'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'server_type': 's-2vcpu-4gb',
                                      'location': 'ams3', 'private_ip': '10.20.1.1'})
                    sent = self.stand_in.droplets[-1]
                    self.assertEqual((sent['user_data'], sent['ssh_keys'], sent['image'], sent['region'], sent['size_slug']),
                                     ('#cloud-config\ndisable_root: false\nruncmd: ["true"]\n', [1001, 1004], 'debian-13-x64',
                                      'ams3', 's-2vcpu-4gb'))
                    self.assertIn({'id': server['id'], 'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'power_state': 'running'},
                                  self.servers(bash, with_token))
                    sent['status'] = 'new'
                    self.assertIn('new', [s['power_state'] for s in self.servers(bash, with_token)])
                    missing = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', '424242', with_token=with_token)
                    self.assertEqual((missing.returncode, json.loads(missing.stdout)), (0, {'id': '424242', 'deleted': True}),
                                     'an ID the provider does not list is destroyed already')
                    self.assertIn('no server with ID 424242', missing.stderr)
                    destroyed = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', server['id'], with_token=with_token)
                    self.assertEqual((destroyed.returncode, json.loads(destroyed.stdout or 'null')), (0, {'id': server['id'], 'deleted': True}),
                                     destroyed.stderr)
                    self.assertNotIn(server['id'], [s['id'] for s in self.servers(bash, with_token)])
                    by_name = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-name', 'other1', with_token=with_token)
                    self.assertEqual(by_name.returncode, 0, by_name.stderr)
                    self.assertEqual(sorted(s['id'] for s in self.servers(bash, with_token)), ['10', '12', '99'])
                    self.assertEqual(self.stand_in.refusals, [])

    def test_power_off_cuts_the_power_by_the_id_and_waits_until_stopped(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.stand_in.droplets.clear()
                    server = json.loads(self.create(bash, 'app001', with_token, self.directory/'receipt.json').stdout)
                    off = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], with_token=with_token)
                    self.assertEqual((off.returncode, json.loads(off.stdout or 'null')), (0, {'id': server['id'], 'power_state': 'stopped'}), off.stderr)
                    self.assertEqual(self.servers(bash, with_token)[0]['power_state'], 'stopped')
                    again = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], with_token=with_token)
                    self.assertEqual(again.returncode, 0, 'a stopped server needs no action: ' + again.stderr)
                    missing = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', '424242', with_token=with_token)
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn('no server with ID 424242', missing.stderr)
                    by_name = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-name', 'app001', with_token=with_token)
                    self.assertEqual(by_name.returncode, 2, 'a name is never enough to cut power')
                    self.assertEqual(self.stand_in.refusals, [])

    def test_a_lost_create_answer_finds_the_one_new_server_and_never_posts_again(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                self.stand_in.droplets[:] = [{'id': 10, 'name': 'app002', 'status': 'active', 'networks': {'v4': []}}]
                self.stand_in.posts = 0
                self.stand_in.lose_the_next_create_answer = True
                receipt = self.directory/'receipt.json'
                created = self.create(bash, 'app002', True, receipt)
                self.assertEqual(created.returncode, 0, created.stderr)
                self.assertEqual(self.stand_in.posts, 1)
                self.assertEqual(json.loads(receipt.read_text())['id'], str(self.stand_in.droplets[-1]['id']))
                self.assertNotIn('runcmd', created.stdout + created.stderr, 'an error answer can repeat the first-boot data')

    def test_a_key_name_must_match_exactly_one_key(self):
        for name in ('twice', 'nobody'):
            with self.subTest(name=name):
                self.stand_in.posts = 0
                result = self.create(bash_programs()[0], 'app003', True, self.directory/'receipt.json', keys=(name,))
                self.assertEqual(result.returncode, 1)
                self.assertIn('expected exactly one SSH key named ' + name, result.stderr)
                self.assertEqual(self.stand_in.posts, 0)

    def test_the_monthly_price_of_a_size_in_a_region(self):
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    price = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 's-2vcpu-4gb',
                                            '--location', 'fra1', with_token=with_token)
                    self.assertEqual(price.returncode, 0, price.stderr)
                    answer = json.loads(price.stdout)
                    # jq keeps the answer's own spelling of the number, such as 24.0.
                    self.assertEqual(float(answer.pop('monthly_price')), 24)
                    self.assertEqual(answer, {'server_type': 's-2vcpu-4gb', 'location': 'fra1', 'currency': 'USD'})
                    self.assertIn('without the tax', price.stderr)
                    for server_type, location, text in (('s-9vcpu', 'fra1', 'DigitalOcean lists no size s-9vcpu'),
                                                        ('s-2vcpu-4gb', 'nyc1', 'size s-2vcpu-4gb is not offered in region nyc1')):
                        missing = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', server_type,
                                                  '--location', location, with_token=with_token)
                        self.assertEqual((missing.returncode, missing.stdout), (1, ''))
                        self.assertIn(text, missing.stderr)
                    self.assertEqual(self.stand_in.refusals, [])

    def test_a_wrong_token_fails_without_printing_the_answer(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'list_the_servers_at_the_provider', with_token=True, token='wrong')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('with HTTP 401 (body withheld)', result.stderr)
                self.assertNotIn('authenticate', result.stdout + result.stderr)


    def test_listings_larger_than_one_command_line_argument_are_read_whole(self):
        # Linux allows 131,072 bytes for one command-line argument and macOS about 1 MiB for all of them;
        # 1500 droplets and 1500 sizes of about 1.1 KB each are 1.6 MB each, over both, in several pages.
        global PAGE_SIZE
        original, PAGE_SIZE = PAGE_SIZE, 200
        self.addCleanup(globals().update, PAGE_SIZE=original)
        self.stand_in.droplets[:] = [{'id': 20000 + n, 'name': 'big%d' % n, 'status': 'active', 'networks': {'v4': []}, 'padding': 'y' * 1000}
                                     for n in range(1500)]
        self.stand_in.gpu_droplets[:] = [{'id': 99, 'name': 'gpu1', 'status': 'off', 'networks': {'v4': []}}]
        self.stand_in.sizes[:0] = [{'slug': 'filler-%d' % n, 'price_monthly': 1, 'regions': ['ams3'], 'padding': 'y' * 1000} for n in range(1500)]
        for bash in bash_programs():
            for with_token in (False, True):
                with self.subTest(bash=bash, with_token=with_token):
                    self.assertEqual(len(self.servers(bash, with_token)), 1501)
                    price = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 's-2vcpu-4gb',
                                            '--location', 'fra1', with_token=with_token)
                    self.assertEqual(price.returncode, 0, price.stderr)


if __name__ == '__main__':
    unittest.main()
