#!/usr/bin/env python3
"""The Google Compute Engine guide's request function and five provider
scripts, run as the guide prints them against a stand-in for Compute Engine,
its price catalog and Google's token address.

  python3 tests/google_compute_engine_provider_scripts_test.py

Builds each script from the guide's code blocks and runs it with every bash on
this machine (macOS's /bin/bash is 3.2, Debian's is 5), both through the
stand-in API proxy (no SERVER_PROVIDER_API_TOKEN, as on a desk) and
with the token made in the shell (as on util01). The stand-in token address
checks each JWT's RS256 signature with the key's public key, through openssl,
and its claims.
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
import time
import unittest
from urllib.parse import parse_qs, urlsplit

GUIDE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/provider_guides/google_compute_engine.md'
PROJECT = 'example-systems-123456'
ACCOUNT = 'util01-restore-drill@%s.iam.gserviceaccount.com' % PROJECT
SCOPES = 'https://www.googleapis.com/auth/compute https://www.googleapis.com/auth/cloud-billing.readonly'


def guide_blocks():
    """The request function's block, then the five scripts' own parts."""
    text = GUIDE.read_text()
    function_part = text.split("## The provider scripts' request function", 1)[1]
    scripts_part = text.split('## The provider scripts\n', 1)[1].split('\n## ', 1)[0]
    function = re.findall(r'```bash\n(.*?)```', function_part, re.S)[0]
    scripts = dict(re.findall(r'`(\w+_at_the_provider)`:\n\n```bash\n(.*?)```', scripts_part, re.S))
    return function, scripts


def unbase64url(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


class StandIn:
    """Compute Engine, the price catalog and the token address: unsigned on
    the proxy port, with a bearer token from the token address on the API port."""

    def __init__(self, directory, public_key):
        self.directory, self.public_key = directory, public_key
        self.instances, self.creates, self.request_ids, self.operations = [], [], {}, {}
        self.tokens, self.refusals, self.stops = [], [], []
        self.lose_the_next_create_answer, self.capacity_refusals = False, 0
        self.instances_per_page, self.filler_skus, self.skus_per_page = 1, 0, 2
        self.next_id = 7000000000000000001  # beyond the largest whole number jq keeps exactly
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def answer(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def handle_request(self, method):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode()
                url = urlsplit(self.path)
                path, query = url.path.lstrip('/'), {k: v[0] for k, v in parse_qs(url.query).items()}
                if self.server.server_address[1] == stand_in.api_port:
                    if path == 'token':
                        return stand_in.token(self, body)
                    if self.headers.get('Authorization') not in ['Bearer ' + t for t in stand_in.tokens]:
                        stand_in.refusals.append(path)
                        return self.answer(401, {'error': {'code': 401, 'status': 'UNAUTHENTICATED'}})
                    path = path.replace('compute/v1/', '', 1)
                return stand_in.route(self, method, path, query, body)

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

    def token(self, handler, body):
        form = {k: v[0] for k, v in parse_qs(body).items()}
        parts = form.get('assertion', '').split('.')
        valid = form.get('grant_type') == 'urn:ietf:params:oauth:grant-type:jwt-bearer' and len(parts) == 3
        if valid:
            signed, signature = self.directory/'signed', self.directory/'signature'
            signed.write_bytes(('%s.%s' % (parts[0], parts[1])).encode())
            signature.write_bytes(unbase64url(parts[2]))
            valid = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(self.public_key), '-signature', str(signature), str(signed)],
                                   capture_output=True).returncode == 0
        if valid:
            header, claims = json.loads(unbase64url(parts[0])), json.loads(unbase64url(parts[1]))
            valid = (header.get('alg') == 'RS256' and claims.get('iss') == ACCOUNT and claims.get('scope') == SCOPES
                     and claims.get('aud') == 'https://oauth2.googleapis.com/token' and claims['exp'] - claims['iat'] == 3600
                     and abs(claims['iat'] - time.time()) < 60)
        if not valid:
            return handler.answer(400, {'error': 'invalid_grant', 'error_description': 'Invalid JWT Signature.'})
        self.tokens.append('ya29.stand-in-%d' % len(self.tokens))
        handler.answer(200, {'access_token': self.tokens[-1], 'expires_in': 3599, 'token_type': 'Bearer'})

    def route(self, handler, method, path, query, body):
        project = 'projects/%s/' % PROJECT
        if path.startswith('cloudbilling/v1/services/6F81-5844-456A/skus') or path.startswith('v1/services/6F81-5844-456A/skus'):
            return self.skus(handler, query)
        if not path.startswith(project):
            return handler.answer(403, {'error': {'code': 403, 'status': 'PERMISSION_DENIED'}})
        route = path[len(project):]
        if method == 'GET' and route == 'aggregated/instances':
            # One instance a page, so the scripts must follow nextPageToken.
            start = int(query.get('pageToken') or 0)
            page = self.instances[start:start + self.instances_per_page]
            for instance in page:
                if instance['status'] == 'PROVISIONING':
                    instance.update(status='RUNNING', networkInterfaces=[{'accessConfigs': [{'natIP': '192.0.2.20'}]}])
            answer = {'items': {}}
            for i in page:
                answer['items'].setdefault('zones/' + i['zone'].split('/')[-1], {'instances': []})['instances'].append(i)
            answer['items']['zones/asia-east1-a'] = {'warning': {'code': 'NO_RESULTS_ON_PAGE'}}
            if start + self.instances_per_page < len(self.instances):
                answer['nextPageToken'] = str(start + self.instances_per_page)
            return handler.answer(200, answer)
        match = re.match(r'zones/([^/]+)/(instances|operations|machineTypes)(?:/([^/]+))?(?:/(stop))?$', route)
        if not match:
            return handler.answer(404, {'error': {'code': 404, 'status': 'NOT_FOUND'}})
        zone, kind, name, action = match.groups()
        if kind == 'machineTypes':
            shared = name.startswith('e2-micro')
            return handler.answer(200, {'name': name, 'guestCpus': 2, 'memoryMb': 4096, 'isSharedCpu': shared})
        if kind == 'operations':
            return handler.answer(200, self.operations[name])
        if method == 'POST' and not name:
            return self.create(handler, zone, query, json.loads(body))
        found = [i for i in self.instances if i['id'] == name]
        if not found:
            return handler.answer(404, {'error': {'code': 404, 'status': 'NOT_FOUND'}})
        if method == 'POST' and action == 'stop':
            self.stops.append(query)
            found[0]['status'] = 'TERMINATED'
        elif method == 'DELETE':
            self.instances.remove(found[0])
        return handler.answer(200, {'status': 'RUNNING', 'name': 'operation-x'})

    def create(self, handler, zone, query, request):
        self.creates.append((query.get('requestId'), request))
        operation = self.request_ids.get(query.get('requestId'))
        if not operation:
            name = 'operation-%d' % len(self.operations)
            if self.capacity_refusals:
                self.capacity_refusals -= 1
                operation = {'name': name, 'status': 'DONE', 'targetId': str(self.next_id + 99),
                             'error': {'errors': [{'code': 'ZONE_RESOURCE_POOL_EXHAUSTED'}]}}
            else:
                instance = {'id': str(self.next_id), 'name': request['name'], 'zone': 'https://x/compute/v1/projects/%s/zones/%s' % (PROJECT, zone),
                            'status': 'PROVISIONING', 'networkInterfaces': [{}], 'request': request}
                self.next_id += 1
                self.instances.append(instance)
                operation = {'name': name, 'status': 'RUNNING', 'targetId': instance['id']}
            self.operations[name] = operation
            self.request_ids[query.get('requestId')] = operation
        if self.lose_the_next_create_answer:
            self.lose_the_next_create_answer = False
            return handler.answer(503, {'error': {'code': 503, 'status': 'UNAVAILABLE'}})
        answer = dict(operation)
        operation['status'] = 'DONE'
        return handler.answer(200, answer)

    def skus(self, handler, query):
        price = lambda units, nanos: {'pricingExpression': {'tieredRates': [{'unitPrice': {'currencyCode': 'USD', 'units': units, 'nanos': nanos}}]}}
        sku = lambda description, regions, units, nanos, usage='OnDemand': {
            'description': description, 'serviceRegions': regions, 'category': {'usageType': usage}, 'pricingInfo': [price(units, nanos)]}
        catalog = [sku('E2 Instance Core running in Netherlands', ['europe-west4'], '0', 24000000),
                   sku('E2 Instance Core running in Americas', ['us-east1'], '0', 21000000),
                   sku('E2 Instance Core running in Netherlands', ['europe-west4'], '0', 5000000, 'Preemptible'),
                   sku('E2 Instance Ram running in Netherlands', ['europe-west4'], '0', 3200000),
                   sku('Balanced PD Capacity in Netherlands', ['europe-west4'], '0', 110000000),
                   sku('External IP Charge on a Standard VM', ['global'], '0', 5000000)]
        # Filler SKUs the script keeps (on demand, in the region) make the kept data large, as the real
        # catalog's 1.5 MB is; each is about 1.1 KB.
        catalog = [sku('Filler SKU %d %s' % (number, 'x' * 1000), ['europe-west4'], '0', 1) for number in range(self.filler_skus)] + catalog
        start = int(query.get('pageToken') or 0)
        answer = {'skus': catalog[start:start + self.skus_per_page]}
        if start + self.skus_per_page < len(catalog):
            answer['nextPageToken'] = str(start + self.skus_per_page)
        return handler.answer(200, answer)


def bash_programs():
    found = {}
    for candidate in ['/bin/bash', shutil.which('bash')]:
        if candidate and os.path.exists(candidate):
            found.setdefault(os.path.realpath(candidate), candidate)
    return list(found.values())


class GoogleComputeEngineProviderScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        private, public = cls.keys/'private.pem', cls.keys/'public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(private)], check=True, capture_output=True)
        subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)], check=True, capture_output=True)
        key_file = json.dumps({'type': 'service_account', 'project_id': PROJECT, 'private_key_id': 'abc',
                               'private_key': private.read_text(), 'client_email': ACCOUNT,
                               'token_uri': 'https://oauth2.googleapis.com/token'})
        cls.token = base64.b64encode(key_file.encode()).decode()
        cls.public_key = public

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.keys)

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.addCleanup(shutil.rmtree, self.directory)
        self.stand_in = StandIn(self.directory, self.public_key)
        self.addCleanup(self.stand_in.close)
        function, scripts = guide_blocks()
        self.assertEqual(sorted(scripts), ['create_a_server_at_the_provider', 'destroy_a_server_at_the_provider',
                                           'list_the_servers_at_the_provider', 'power_off_a_server_at_the_provider',
                                           'read_the_monthly_price_at_the_provider'])
        api = 'http://127.0.0.1:%d/' % self.stand_in.api_port
        for real in ('https://compute.googleapis.com/compute/v1/', 'https://oauth2.googleapis.com/token', 'https://cloudbilling.googleapis.com/',
                     'http://127.0.0.1:8081/'):
            self.assertIn(real, function)
        function = function.replace('https://compute.googleapis.com/compute/v1/', api + 'compute/v1/')
        # The token address the request goes to; the JWT's audience stays Google's.
        function = function.replace('--data-binary @- https://oauth2.googleapis.com/token', '--data-binary @- %stoken' % api)
        function = function.replace('https://cloudbilling.googleapis.com/', api)
        function = function.replace('http://127.0.0.1:8081/', 'http://127.0.0.1:%d/' % self.stand_in.proxy_port)
        function = re.sub(r'(?m)^google_project_id=\S+', 'google_project_id=' + PROJECT, function)
        for name, body in scripts.items():
            # The waits are for Compute Engine, not for the stand-in.
            body = re.sub(r'sleep \d+', 'sleep 0', body)
            text = '#!/bin/bash\nset -euo pipefail\n%s\n%s' % (function, body)
            (self.directory/name).write_text(text)
            (self.directory/name).chmod(0o755)

    def run_script(self, bash, name, *arguments, signed=False, token=None):
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.directory), 'TMPDIR': str(self.directory)}
        if signed:
            env['SERVER_PROVIDER_API_TOKEN'] = token or self.token
        return subprocess.run([bash, str(self.directory/name), *arguments], text=True, capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=120)

    def create(self, bash, name, signed, receipt, server_type='e2-custom-2-4096', keys=('util01, the mmhotline user',)):
        first_boot = self.directory/('first-boot-' + name)
        first_boot.write_text('#cloud-config\ndisable_root: false\nruncmd: ["true"]\n')
        first_boot.chmod(0o600)
        key_arguments = [a for key in keys for a in ('--ssh-key-name', key)]
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--server-name', name, '--server-type', server_type,
                                 '--location', 'europe-west4-a', '--image', 'projects/%s/global/images/debian-13' % PROJECT, *key_arguments,
                                 '--first-boot-data', str(first_boot), '--wireguard-public-key', 'WIREGUARD_PUBLIC_KEY',
                                 '--wireguard-private-ip', '10.20.1.1', '--ownership-file', str(receipt), signed=signed)
        self.assertEqual(first_boot.read_text(), '', 'the create must clear the first-boot data')
        return result

    def servers(self, bash, signed):
        result = self.run_script(bash, 'list_the_servers_at_the_provider', signed=signed)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['servers']

    def test_list_create_and_destroy_through_the_proxy_and_with_a_token(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    tokens_before = len(self.stand_in.tokens)
                    self.stand_in.instances[:] = [{'id': '6999999999999999999', 'name': 'old', 'status': 'STOPPING',
                                                   'zone': 'https://x/zones/us-east1-b', 'networkInterfaces': [{}]}]
                    self.assertEqual(self.servers(bash, signed), [{'id': '6999999999999999999', 'name': 'old', 'public_ipv4_address': '',
                                                                   'power_state': 'STOPPING'}])
                    receipt = self.directory/'receipt.json'
                    created = self.create(bash, 'app001', signed, receipt, 'e2-custom-4-8192', ('desk01, alex', 'util01, the mmhotline user'))
                    self.assertEqual(created.returncode, 0, created.stderr)
                    server = json.loads(created.stdout)
                    self.assertEqual(json.loads(receipt.read_text()), server)
                    self.assertEqual({key: server[key] for key in ('name', 'public_ipv4_address', 'server_type', 'location', 'private_ip')},
                                     {'name': 'app001', 'public_ipv4_address': '192.0.2.20', 'server_type': 'e2-custom-4-8192',
                                      'location': 'europe-west4-a', 'private_ip': '10.20.1.1'})
                    sent = self.stand_in.instances[-1]['request']
                    metadata = {item['key']: item['value'] for item in sent['metadata']['items']}
                    self.assertEqual(metadata['user-data'], '#cloud-config\ndisable_root: false\nruncmd: ["true"]\n')
                    # cloud-init 25.1.4's GCE data source keeps a line only for the user `cloudinit` or the
                    # image's default user, so a `root:` line installs no key (proved on Debian 13).
                    self.assertEqual(metadata['ssh-keys'].splitlines(), [
                        'cloudinit:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExampleExampleExampleExampl alex@desk01',
                        'cloudinit:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExampleExampleExampleExampm mmhotline@util01'])
                    for line in metadata['ssh-keys'].splitlines():
                        self.assertTrue(line.startswith('cloudinit:'), line)
                        self.assertFalse(line.startswith('root:'), line)
                    self.assertEqual((metadata['block-project-ssh-keys'], sent['disks'][0]['initializeParams']['diskSizeGb'],
                                      sent['serviceAccounts'], sent['labels']),
                                     ('TRUE', '80', [], {'stack-system-id': 'example_systems'}))
                    self.assertIn({'id': server['id'], 'name': 'app001', 'public_ipv4_address': '192.0.2.20', 'power_state': 'running'},
                                  self.servers(bash, signed))
                    missing = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', '123', signed=signed)
                    self.assertEqual((missing.returncode, json.loads(missing.stdout)), (0, {'id': '123', 'deleted': True}))
                    self.assertIn('no server with ID 123', missing.stderr)
                    destroyed = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((destroyed.returncode, json.loads(destroyed.stdout or 'null')), (0, {'id': server['id'], 'deleted': True}),
                                     destroyed.stderr)
                    self.assertNotIn(server['id'], [s['id'] for s in self.servers(bash, signed)])
                    self.assertEqual(self.stand_in.refusals, [])
                    # Six script runs, each makes one token however many requests it sends.
                    self.assertEqual(len(self.stand_in.tokens) - tokens_before, 6 if signed else 0)

    def test_power_off_stops_by_id_and_waits_until_stopped(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.instances.clear()
                    server = json.loads(self.create(bash, 'app001', signed, self.directory/'receipt.json').stdout)
                    off = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((off.returncode, json.loads(off.stdout or 'null')), (0, {'id': server['id'], 'power_state': 'stopped'}), off.stderr)
                    self.assertEqual(self.stand_in.stops[-1], {'noGracefulShutdown': 'true'})
                    self.assertEqual(self.servers(bash, signed)[0]['power_state'], 'stopped')
                    stops = len(self.stand_in.stops)
                    again = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((again.returncode, len(self.stand_in.stops)), (0, stops), 'a stopped server needs no action: ' + again.stderr)
                    missing = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', '123', signed=signed)
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn('no server with ID 123', missing.stderr)
                    by_name = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-name', 'app001', signed=signed)
                    self.assertEqual(by_name.returncode, 2, 'a name is never enough to cut power')

    def test_a_lost_create_answer_is_sent_again_with_the_same_request_id(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                self.stand_in.instances.clear()
                self.stand_in.lose_the_next_create_answer = True
                receipt = self.directory/'receipt.json'
                created = self.create(bash, 'app002', True, receipt)
                self.assertEqual(created.returncode, 0, created.stderr)
                self.assertEqual(len(self.stand_in.instances), 1)
                self.assertEqual(self.stand_in.creates[-1][0], self.stand_in.creates[-2][0])
                self.assertRegex(self.stand_in.creates[-1][0], r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
                self.assertEqual(json.loads(receipt.read_text())['id'], self.stand_in.instances[0]['id'])

    def test_a_capacity_refusal_is_tried_again_with_a_new_request_id(self):
        bash = bash_programs()[0]
        self.stand_in.capacity_refusals = 2
        created = self.create(bash, 'app003', True, self.directory/'receipt.json')
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(len(self.stand_in.instances), 1)
        self.assertEqual(len({request_id for request_id, _ in self.stand_in.creates}), 3)
        self.assertIn('ZONE_RESOURCE_POOL_EXHAUSTED', created.stderr)
        self.assertEqual(json.loads(created.stdout)['id'], self.stand_in.instances[0]['id'])

    def test_a_wrong_key_gets_no_token_and_prints_nothing_of_the_key(self):
        other = self.keys/'other.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(other)], check=True, capture_output=True)
        key_file = json.dumps({'type': 'service_account', 'private_key': other.read_text(), 'client_email': ACCOUNT,
                               'token_uri': 'https://oauth2.googleapis.com/token'})
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'list_the_servers_at_the_provider', signed=True, token=base64.b64encode(key_file.encode()).decode())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('400', result.stderr)
                self.assertNotIn('PRIVATE KEY', result.stdout + result.stderr)
                self.assertEqual(self.stand_in.tokens, [])

    def test_the_price_adds_cores_memory_address_and_disk(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    result = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'e2-custom-2-4096',
                                             '--location', 'europe-west4-a', signed=signed)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    # (0.024 * 2 + 0.0032 * 4 + 0.005) * 730 + 0.11 * 40 = 52.43
                    self.assertEqual(json.loads(result.stdout), {'monthly_price': 52.43, 'currency': 'USD'})
                    shared = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'e2-micro',
                                             '--location', 'europe-west4-a', signed=signed)
                    self.assertEqual(shared.returncode, 1)
                    self.assertIn('shares a CPU core', shared.stderr)

    def test_a_price_catalog_and_a_listing_larger_than_one_command_line_argument_are_read_whole(self):
        # Linux allows 131,072 bytes for one command-line argument and macOS about 1 MiB for all of them, so
        # the kept data here is 1.7 MB, over both, in several pages: a script that hands the kept data to jq
        # as an argument fails with "Argument list too long".
        self.stand_in.filler_skus, self.stand_in.skus_per_page = 1500, 400
        self.stand_in.instances_per_page = 100
        self.stand_in.instances[:] = [{'id': str(6000000000000000000 + number), 'name': 'big%d' % number, 'status': 'RUNNING',
                                       'zone': 'https://x/zones/europe-west4-a', 'networkInterfaces': [{}], 'padding': 'y' * 1000}
                                      for number in range(1500)]
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    result = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 'e2-custom-2-4096',
                                             '--location', 'europe-west4-a', signed=signed)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {'monthly_price': 52.43, 'currency': 'USD'})
                    self.assertEqual(len(self.servers(bash, signed)), 1500)


if __name__ == '__main__':
    unittest.main()
