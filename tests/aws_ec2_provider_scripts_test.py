#!/usr/bin/env python3
"""The AWS EC2 guide's request function and five provider scripts, run as the
guide prints them against a stand-in for EC2's query API.

  python3 tests/aws_ec2_provider_scripts_test.py

Builds each script from the guide's code blocks and runs it with every bash on
this machine (macOS's /bin/bash is 3.2, Debian's is 5), both through the
stand-in API proxy (no SERVER_PROVIDER_API_TOKEN, as on a desk) and
signed in the shell with curl --aws-sigv4 (as on util01). The stand-in checks
each signature as AWS's Signature Version 4 says, with its own code, and
answers in EC2's XML.
"""
import hashlib
import hmac
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
from urllib.parse import parse_qsl, quote
import uuid
import base64

GUIDE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template/provider_guides/aws_ec2.md'
ACCESS_KEY_ID, SECRET_ACCESS_KEY = 'AKIDEXAMPLE000000000', 'wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY'
REGION = 'eu-north-1'


def guide_blocks():
    """The request function's block, then the five scripts' own parts."""
    text = GUIDE.read_text()
    function_part = text.split("## The provider scripts' request function", 1)[1]
    scripts_part = text.split('## The provider scripts\n', 1)[1].split('\n## ', 1)[0]
    function = re.findall(r'```bash\n(.*?)```', function_part, re.S)[0]
    scripts = dict(re.findall(r'`(\w+_at_the_provider)`:\n\n```bash\n(.*?)```', scripts_part, re.S))
    return function, scripts


def signature_is_valid(method, target, headers, body):
    """Signature Version 4 as AWS's "Create a signed AWS API request" gives it."""
    match = re.match(r'AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/([^/]+)/aws4_request, ?'
                     r'SignedHeaders=([a-z0-9;-]+), ?Signature=([0-9a-f]{64})$', headers.get('Authorization', ''))
    if not match or match.group(1) != ACCESS_KEY_ID or match.group(3) != REGION or match.group(4) != 'ec2':
        return False
    signed = match.group(5).split(';')
    if 'host' not in signed or 'x-amz-date' not in signed:
        return False
    path, _, query = target.partition('?')
    encode = lambda text: quote(text, safe='-_.~')
    canonical_query = '&'.join(sorted(encode(k) + '=' + encode(v) for k, v in parse_qsl(query, keep_blank_values=True)))
    canonical_headers = ''.join('%s:%s\n' % (name, ' '.join(headers.get(name, '').split())) for name in signed)
    payload = hashlib.sha256(body).hexdigest()
    if headers.get('x-amz-content-sha256') not in (None, payload):
        return False
    request = '\n'.join([method, path or '/', canonical_query, canonical_headers, ';'.join(signed), payload])
    date = headers.get('x-amz-date', '')
    to_sign = '\n'.join(['AWS4-HMAC-SHA256', date, '%s/%s/ec2/aws4_request' % (match.group(2), REGION),
                         hashlib.sha256(request.encode()).hexdigest()])
    key = ('AWS4' + SECRET_ACCESS_KEY).encode()
    for part in (match.group(2), REGION, 'ec2', 'aws4_request'):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    return date.startswith(match.group(2)) and hmac.compare_digest(
        hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest(), match.group(6))


def xml_text(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def instance_xml(instance):
    tags = ''.join('<item><key>%s</key><value>%s</value></item>' % (xml_text(k), xml_text(v)) for k, v in instance['tags'].items())
    return ('<item>\n  <instanceId>%s</instanceId>\n  <instanceState><code>16</code><name>%s</name></instanceState>\n'
            '  %s\n  %s\n  <networkInterfaceSet><item><networkInterfaceId>eni-1</networkInterfaceId>'
            '<groupSet><item><groupName>wireguard</groupName></item></groupSet></item></networkInterfaceSet>\n</item>') % (
        instance['id'], instance['state'], '<ipAddress>%s</ipAddress>' % instance['address'] if instance['address'] else '',
        '<tagSet>%s</tagSet>' % tags if tags else '<tagSet/>')


class StandIn:
    """EC2's query API in one region, unsigned on the proxy port and signed on
    the API port."""

    def __init__(self):
        self.instances, self.launches, self.refusals, self.client_tokens = [], [], [], {}
        self.lose_the_next_create_answer, self.capacity_refusals = False, 0
        self.instances_per_page = 1
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments):
                pass

            def answer(self, code, xml):
                data = ('<?xml version="1.0" encoding="UTF-8"?>\n' + xml).encode()
                self.send_response(code)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def error(self, code, error_code, message):
                self.answer(code, '<Response><Errors><Error><Code>%s</Code><Message>%s</Message></Error></Errors>'
                                  '<RequestID>r</RequestID></Response>' % (error_code, message))

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                if self.server.server_address[1] == stand_in.api_port:
                    headers = {name.lower(): value for name, value in self.headers.items()}
                    headers['Authorization'] = self.headers.get('Authorization', '')
                    if not signature_is_valid('POST', self.path, headers, body):
                        stand_in.refusals.append(self.path)
                        return self.error(403, 'SignatureDoesNotMatch', 'The request signature we calculated does not match')
                parameters = dict(parse_qsl(body.decode(), keep_blank_values=True))
                action = parameters.get('Action')
                if parameters.get('Version') != '2016-11-15':
                    return self.error(400, 'InvalidParameterValue', 'Version')
                handler = getattr(stand_in, 'action_' + (action or ''), None)
                if not handler:
                    return self.error(400, 'InvalidAction', action)
                result = handler(parameters)
                if isinstance(result, tuple):
                    return self.error(*result)
                self.answer(200, '<%sResponse xmlns="http://ec2.amazonaws.com/doc/2016-11-15/">\n  <requestId>r</requestId>\n%s\n</%sResponse>' % (action, result, action))

        self.servers = [ThreadingHTTPServer(('127.0.0.1', 0), Handler) for _ in range(2)]
        self.proxy_port, self.api_port = (server.server_address[1] for server in self.servers)
        for server in self.servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def close(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()

    def find(self, parameters):
        return [i for i in self.instances if i['id'] == parameters.get('InstanceId.1') and i['state'] != 'terminated']

    def action_DescribeInstances(self, parameters):
        # One reservation a page, so the scripts must follow nextToken.
        start = int(parameters.get('NextToken') or 0)
        page = self.instances[start:start + self.instances_per_page]
        token = ('<nextToken>%d</nextToken>' % (start + self.instances_per_page)
                 if start + self.instances_per_page < len(self.instances) else '')
        reservations = ''.join('<item><reservationId>r-%d</reservationId><instancesSet>%s</instancesSet></item>' % (n, instance_xml(i))
                               for n, i in enumerate(page))
        for instance in page:
            if instance['state'] == 'pending':
                instance.update(state='running', address='192.0.2.10')
        return ('<reservationSet>%s</reservationSet>' % reservations if reservations else '<reservationSet/>') + token

    def action_DescribeImages(self, parameters):
        if parameters.get('ImageId.1') != 'ami-0debian13':
            return '<imagesSet/>'
        return '<imagesSet><item><imageId>ami-0debian13</imageId><rootDeviceName>/dev/xvda</rootDeviceName></item></imagesSet>'

    def action_RunInstances(self, parameters):
        self.launches.append(parameters)
        token = parameters['ClientToken']
        if token in self.client_tokens:
            instance = self.client_tokens[token]
        elif self.capacity_refusals:
            self.capacity_refusals -= 1
            return 500, 'InsufficientInstanceCapacity', 'We currently do not have sufficient t3.medium capacity'
        else:
            tags = {parameters['TagSpecification.1.Tag.%d.Key' % n]: parameters['TagSpecification.1.Tag.%d.Value' % n] for n in (1, 2)}
            instance = {'id': 'i-' + uuid.uuid4().hex[:17], 'state': 'pending', 'address': '', 'tags': tags}
            self.instances.append(instance)
            self.client_tokens[token] = instance
        if self.lose_the_next_create_answer:
            self.lose_the_next_create_answer = False
            return 503, 'Unavailable', 'lost'
        return '<instancesSet>%s</instancesSet>' % instance_xml(instance)

    def action_TerminateInstances(self, parameters):
        for instance in self.find(parameters):
            instance['state'] = 'terminated'
        return '<instancesSet/>'

    def action_StopInstances(self, parameters):
        if parameters.get('Force') != 'true' or parameters.get('SkipOsShutdown') != 'true':
            return 400, 'MissingParameter', 'the power-off must cut the power'
        for instance in self.find(parameters):
            instance['state'] = 'stopped'
        return '<instancesSet/>'


def bash_programs():
    found = {}
    for candidate in ['/bin/bash', shutil.which('bash')]:
        if candidate and os.path.exists(candidate):
            found.setdefault(os.path.realpath(candidate), candidate)
    return list(found.values())


class AWSEC2ProviderScripts(unittest.TestCase):
    def setUp(self):
        self.stand_in = StandIn()
        self.addCleanup(self.stand_in.close)
        self.directory = Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR')))
        self.addCleanup(shutil.rmtree, self.directory)
        function, scripts = guide_blocks()
        self.assertEqual(sorted(scripts), ['create_a_server_at_the_provider', 'destroy_a_server_at_the_provider',
                                           'list_the_servers_at_the_provider', 'power_off_a_server_at_the_provider',
                                           'read_the_monthly_price_at_the_provider'])
        self.assertIn('aws_ec2_address=https://ec2.eu-north-1.amazonaws.com/', function)
        self.assertIn('http://127.0.0.1:8081/', function)
        function = re.sub(r'(?m)^aws_ec2_address=\S+', 'aws_ec2_address=http://127.0.0.1:%d/' % self.stand_in.api_port, function)
        function = function.replace('http://127.0.0.1:8081/', 'http://127.0.0.1:%d/' % self.stand_in.proxy_port)
        for name, body in scripts.items():
            # The waits are for EC2, not for the stand-in.
            body = re.sub(r'sleep \d+', 'sleep 0', body)
            text = '#!/bin/bash\nset -euo pipefail\n%s\n%s' % (function, body)
            (self.directory/name).write_text(text)
            (self.directory/name).chmod(0o755)

    def run_script(self, bash, name, *arguments, signed=False, token=None):
        env = {'PATH': os.environ['PATH'], 'HOME': str(self.directory), 'TMPDIR': str(self.directory)}
        if signed:
            env['SERVER_PROVIDER_API_TOKEN'] = token or '%s:%s' % (ACCESS_KEY_ID, SECRET_ACCESS_KEY)
        return subprocess.run([bash, str(self.directory/name), *arguments], text=True, capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=120)

    def create(self, bash, name, signed, receipt, server_type='t3.medium'):
        first_boot = self.directory/('first-boot-' + name)
        first_boot.write_text('#cloud-config\ndisable_root: false\nruncmd: ["true"]\n')
        first_boot.chmod(0o600)
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--server-name', name, '--server-type', server_type,
                                 '--location', REGION, '--image', 'ami-0debian13', '--ssh-key-name', 'desk01-alex',
                                 '--first-boot-data', str(first_boot), '--wireguard-public-key', 'WIREGUARD_PUBLIC_KEY',
                                 '--wireguard-private-ip', '10.20.1.1', '--ownership-file', str(receipt), signed=signed)
        self.assertEqual(first_boot.read_text(), '', 'the create must clear the first-boot data')
        return result

    def servers(self, bash, signed):
        result = self.run_script(bash, 'list_the_servers_at_the_provider', signed=signed)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['servers']

    def test_list_create_and_destroy_through_the_proxy_and_signed(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.instances[:] = [
                        {'id': 'i-gone', 'state': 'terminated', 'address': '', 'tags': {'Name': 'old'}},
                        {'id': 'i-other', 'state': 'stopped', 'address': '', 'tags': {}},
                        {'id': 'i-quoted', 'state': 'shutting-down', 'address': '', 'tags': {'Name': 'a "b" & <c>'}}]
                    self.assertEqual(self.servers(bash, signed), [
                        {'id': 'i-other', 'name': '', 'public_ipv4_address': '', 'power_state': 'stopped'},
                        {'id': 'i-quoted', 'name': 'a "b" & <c>', 'public_ipv4_address': '', 'power_state': 'shutting-down'}])
                    receipt = self.directory/'receipt.json'
                    created = self.create(bash, 'app001', signed, receipt, 't3.xlarge')
                    self.assertEqual(created.returncode, 0, created.stderr)
                    server = json.loads(created.stdout)
                    self.assertEqual(json.loads(receipt.read_text()), server)
                    self.assertEqual({key: server[key] for key in ('name', 'public_ipv4_address', 'server_type', 'location', 'private_ip')},
                                     {'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'server_type': 't3.xlarge',
                                      'location': REGION, 'private_ip': '10.20.1.1'})
                    sent = self.stand_in.launches[-1]
                    self.assertEqual(base64.b64decode(sent['UserData']).decode(), '#cloud-config\ndisable_root: false\nruncmd: ["true"]\n')
                    self.assertEqual((sent['KeyName'], sent['BlockDeviceMapping.1.DeviceName'], sent['BlockDeviceMapping.1.Ebs.VolumeSize'],
                                      sent['TagSpecification.1.Tag.2.Value'], sent['CreditSpecification.CpuCredits'],
                                      sent['NetworkInterface.1.AssociatePublicIpAddress'], sent['MetadataOptions.HttpTokens']),
                                     ('desk01-alex', '/dev/xvda', '80', 'example_systems', 'standard', 'true', 'required'))
                    self.assertIn({'id': server['id'], 'name': 'app001', 'public_ipv4_address': '192.0.2.10', 'power_state': 'running'},
                                  self.servers(bash, signed))
                    missing = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', 'i-gone', signed=signed)
                    self.assertEqual((missing.returncode, json.loads(missing.stdout)), (0, {'id': 'i-gone', 'deleted': True}),
                                     'a terminated ID is destroyed already')
                    self.assertIn('no server with ID i-gone', missing.stderr)
                    destroyed = self.run_script(bash, 'destroy_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((destroyed.returncode, json.loads(destroyed.stdout or 'null')), (0, {'id': server['id'], 'deleted': True}),
                                     destroyed.stderr)
                    self.assertNotIn(server['id'], [s['id'] for s in self.servers(bash, signed)])
                    self.assertEqual(self.stand_in.refusals, [])

    def test_power_off_cuts_the_power_by_id_and_waits_until_stopped(self):
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.stand_in.instances.clear()
                    server = json.loads(self.create(bash, 'app001', signed, self.directory/'receipt.json').stdout)
                    off = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual((off.returncode, json.loads(off.stdout or 'null')), (0, {'id': server['id'], 'power_state': 'stopped'}), off.stderr)
                    self.assertEqual(self.servers(bash, signed)[0]['power_state'], 'stopped')
                    again = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', server['id'], signed=signed)
                    self.assertEqual(again.returncode, 0, 'a stopped server needs no action: ' + again.stderr)
                    missing = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-id', 'i-none', signed=signed)
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn('no server with ID i-none', missing.stderr)
                    by_name = self.run_script(bash, 'power_off_a_server_at_the_provider', '--server-name', 'app001', signed=signed)
                    self.assertEqual(by_name.returncode, 2, 'a name is never enough to cut power')
                    self.assertEqual(self.stand_in.refusals, [])

    def test_a_lost_create_answer_is_sent_again_with_the_same_client_token(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                self.stand_in.instances.clear()
                self.stand_in.lose_the_next_create_answer = True
                receipt = self.directory/'receipt.json'
                created = self.create(bash, 'app002', True, receipt)
                self.assertEqual(created.returncode, 0, created.stderr)
                self.assertEqual(len(self.stand_in.instances), 1)
                self.assertEqual(self.stand_in.launches[-1]['ClientToken'], self.stand_in.launches[-2]['ClientToken'])
                self.assertEqual(json.loads(receipt.read_text())['id'], self.stand_in.instances[0]['id'])

    def test_a_capacity_refusal_is_tried_again_with_a_new_client_token(self):
        bash = bash_programs()[0]
        self.stand_in.capacity_refusals = 2
        created = self.create(bash, 'app003', True, self.directory/'receipt.json')
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(len(self.stand_in.instances), 1)
        self.assertEqual(len({launch['ClientToken'] for launch in self.stand_in.launches}), 3)
        self.assertIn('InsufficientInstanceCapacity', created.stderr)

    def test_a_wrong_secret_fails_without_printing_the_answer(self):
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'list_the_servers_at_the_provider', signed=True, token=ACCESS_KEY_ID + ':wrongsecret')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('with HTTP 403 SignatureDoesNotMatch (body withheld)', result.stderr)
                self.assertNotIn('does not match', result.stdout + result.stderr)

    def test_the_create_takes_exactly_one_ssh_key_and_the_region_as_location(self):
        bash = bash_programs()[0]
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--ssh-key-name', 'a', '--ssh-key-name', 'b',
                                 '--first-boot-data', str(self.directory/'none'))
        self.assertEqual(result.returncode, 2)
        self.assertIn('exactly one --ssh-key-name', result.stderr)
        result = self.run_script(bash, 'create_a_server_at_the_provider', '--ssh-key-name', 'a', '--location', 'us-east-1',
                                 '--first-boot-data', str(self.directory/'none'))
        self.assertEqual(result.returncode, 2)
        self.assertIn('--location must be eu-north-1', result.stderr)

    def test_the_price_adds_the_server_its_disk_and_its_address(self):
        """AWS's public price files, as their columns are, with rows that
        must not match: another tenancy, another operating system, a reserved
        term, another type."""
        files = self.directory/'offers'
        header = ('"FormatVersion","v1.0"\n"Disclaimer","x"\n"SKU","OfferTermCode","RateCode","TermType","PriceDescription","Unit",'
                  '"PricePerUnit","Currency","Instance Type","Volume API Name","Tenancy","Operating System","Pre Installed S/W",'
                  '"CapacityStatus","operation","Group Description"\n')
        rows = [
            ('OnDemand', '$0.0432 per On Demand Linux t3.medium Instance Hour', 'Hrs', '0.0432000000', 't3.medium', '', 'Shared', 'Linux', 'NA', 'Used', 'RunInstances', ''),
            ('OnDemand', 'Linux, dedicated', 'Hrs', '0.0500000000', 't3.medium', '', 'Dedicated', 'Linux', 'NA', 'Used', 'RunInstances', ''),
            ('OnDemand', 'Windows', 'Hrs', '0.0800000000', 't3.medium', '', 'Shared', 'Windows', 'NA', 'Used', 'RunInstances:0002', ''),
            ('Reserved', 'reserved', 'Hrs', '0.0300000000', 't3.medium', '', 'Shared', 'Linux', 'NA', 'Used', 'RunInstances', ''),
            ('OnDemand', 'other type', 'Hrs', '0.1728000000', 't3.xlarge', '', 'Shared', 'Linux', 'NA', 'Used', 'RunInstances', ''),
            ('OnDemand', '$0.0836 per GB-month of General Purpose (gp3) provisioned storage', 'GB-Mo', '0.0836000000', '', 'gp3', '', '', '', '', '', ''),
        ]
        ec2 = header + ''.join('"SKU%d","T","R",%s,"USD",%s\n' % (n, ','.join('"%s"' % v for v in row[:4]),
                                                                  ','.join(('"%s"' % v) if v else '' for v in row[4:])) for n, row in enumerate(rows))
        vpc = header + '"V1","T","R","OnDemand","$0.005 per In-use public IPv4 address per hour","Hrs","0.0050000000","USD",,,,,,,,"Hourly charge for In-use Public IPv4 Addresses"\n'
        for offer, text in (('AmazonEC2', ec2), ('AmazonVPC', vpc)):
            path = files/offer/'current'/REGION
            path.mkdir(parents=True)
            (path/'index.csv').write_text(text)
        script = self.directory/'read_the_monthly_price_at_the_provider'
        script.write_text(script.read_text().replace('offers=https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws', 'offers=file://%s' % files))
        for bash in bash_programs():
            with self.subTest(bash=bash):
                result = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 't3.medium', '--location', REGION)
                self.assertEqual(result.returncode, 0, result.stderr)
                # (0.0432 + 0.005) * 730 + 0.0836 * 40 = 38.53
                self.assertEqual(json.loads(result.stdout), {'monthly_price': 38.53, 'currency': 'USD'})
                result = self.run_script(bash, 'read_the_monthly_price_at_the_provider', '--server-type', 't3.small', '--location', REGION)
                self.assertEqual(result.returncode, 1)
                self.assertIn('no single on-demand price for instance_hourly of t3.small', result.stderr)

    def test_a_listing_larger_than_one_command_line_argument_is_read_whole(self):
        # Linux allows 131,072 bytes for one command-line argument and macOS about 1 MiB for all of them;
        # 1500 instances of about 1.2 KB each are 1.8 MB in several pages, over both.
        self.stand_in.instances_per_page = 100
        self.stand_in.instances[:] = [{'id': 'i-%017d' % number, 'state': 'running', 'address': '192.0.2.10',
                                       'tags': {'Name': 'big%d' % number, 'padding': 'y' * 1000}} for number in range(1500)]
        for bash in bash_programs():
            for signed in (False, True):
                with self.subTest(bash=bash, signed=signed):
                    self.assertEqual(len(self.servers(bash, signed)), 1500)


if __name__ == '__main__':
    unittest.main()
