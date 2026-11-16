#!/usr/bin/env python3
"""Render and execute first-boot data against fake system commands."""
import base64
import json
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
RENDERER = TEMPLATE / 'server_management_scripts/render_server_first_boot'
PRIVATE_KEY = 'QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
PUBLIC_KEY = 'PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0='


class FirstBoot(unittest.TestCase):
    def render(self, **changes):
        settings = dict(private_key=PRIVATE_KEY, private_ip='10.20.1.3',
                        peers=[dict(public_key=PUBLIC_KEY, allowed_ips=['10.20.0.1/32'],
                                    endpoint='203.0.113.1:443', persistent_keepalive=25)])
        settings.update(changes)
        return subprocess.run(['bash', str(RENDERER)], input=json.dumps(settings),
                              text=True, capture_output=True)

    def test_ssh_config_reaches_servers_over_wg0_without_doubleshell(self):
        # The desks and util01 have their own wg0; the laptop reaches only its
        # desk, through its own ~/.ssh/config entry, never through this file.
        text = (TEMPLATE/'ssh/config').read_text()
        self.assertNotIn('ProxyCommand', text)
        self.assertNotIn('doubleshell', text)
        self.assertNotIn('Match host', text)

    def test_template_ssh_examples_use_wireguard_addresses(self):
        addresses = []
        for path in TEMPLATE.rglob('*'):
            if not path.is_file():
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue  # Binary signing keys contain no SSH examples.
            for target in re.findall(r'\b(?:root|triage)@((?:[0-9]{1,3}\.){3}[0-9]{1,3}|\[[0-9A-Fa-f:]+\])', text):
                address = ipaddress.ip_address(target.strip('[]'))
                addresses.append(address)
                self.assertTrue(address.is_loopback or address in ipaddress.ip_network('10.20.0.0/16'),
                                f'{path.relative_to(TEMPLATE)} uses public SSH target {target}')
        self.assertTrue(addresses)

    def test_renderer_writes_exact_key_address_and_peer(self):
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('@@WIREGUARD_', result.stdout)
        encoded = re.search(r"    content: ([A-Za-z0-9+/=]+)", result.stdout)[1]
        config = base64.b64decode(encoded).decode()
        self.assertIn('PrivateKey = ' + PRIVATE_KEY + '\n', config)
        self.assertIn('Address = 10.20.1.3/16\nListenPort = 51820\n', config)
        self.assertIn('Endpoint = 203.0.113.1:443', config)
        self.assertEqual(result.stderr, '')

    def test_private_ipv4_ranges_are_accepted_and_public_or_invalid_addresses_are_refused(self):
        for address in ('172.20.5.1', '192.168.3.4', '10.30.0.1'):
            with self.subTest(address=address):
                result = self.render(private_ip=address)
                self.assertEqual(result.returncode, 0, result.stderr)
                config = base64.b64decode(re.search(r'    content: ([A-Za-z0-9+/=]+)', result.stdout)[1]).decode()
                self.assertIn('Address = ' + address + '/16', config)
        for address in ('8.8.8.8', '172.32.0.1', '10.20.300.1'):
            with self.subTest(address=address):
                result = self.render(private_ip=address)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16', result.stderr)

    def test_logic_has_no_fixed_example_network(self):
        # Inventory is the example data. The script README has usage examples.
        allowed_files = {'inventories/servers.yml', 'server_management_scripts/README.md'}
        files = []
        for directory in ('roles', 'playbooks', 'server_management_scripts', 'ssh', 'inventories'):
            files.extend(path for path in (TEMPLATE/directory).rglob('*') if path.is_file())
        for path in files:
            if path.relative_to(TEMPLATE).as_posix() in allowed_files:
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if '10.20.' in line:
                    self.assertTrue(line.lstrip().startswith('#') and 'example' in line.lower(),
                                    f'{path.relative_to(TEMPLATE)}:{number}: fixed network: {line}')

    def test_invalid_input_never_prints_first_boot_data(self):
        for settings in ({'private_key': 'bad'}, {'private_ip': '203.0.113.1'}, {'private_ip': '10.20.999.1'}, {'peers': ''}):
            with self.subTest(settings=settings):
                result = self.render(**settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertNotIn(PRIVATE_KEY, result.stderr)

    def test_structured_peers_render_ipv4_ipv6_and_systems_desk(self):
        result = self.render(peers=[
            dict(public_key=PUBLIC_KEY, allowed_ips=['10.20.0.1/32', 'fd00::1/128'],
                 endpoint='[2001:db8::1]:443', persistent_keepalive=25),
            dict(public_key='urzzcMKwVZ9bM84MmgWUjMRxOTNn2PDtEF5it/uZFQ4=', allowed_ips=['10.20.9.1/32'], endpoint='203.0.113.91:443')])
        self.assertEqual(result.returncode, 0, result.stderr)
        config = base64.b64decode(re.search(r'    content: ([A-Za-z0-9+/=]+)', result.stdout)[1]).decode()
        self.assertIn('[Peer]\nPublicKey = '+PUBLIC_KEY+'\nAllowedIPs = 10.20.0.1/32, fd00::1/128\nEndpoint = [2001:db8::1]:443\nPersistentKeepalive = 25\n', config)
        self.assertTrue(config.endswith('[Peer]\nPublicKey = urzzcMKwVZ9bM84MmgWUjMRxOTNn2PDtEF5it/uZFQ4=\nAllowedIPs = 10.20.9.1/32\nEndpoint = 203.0.113.91:443\n'))
        script = '\n'.join(line[6:] for line in result.stdout.split('    - |\n', 1)[1].splitlines())
        self.assertNotIn(PRIVATE_KEY, script)

    def test_endpoint_free_peer_can_enroll_a_laptop_on_its_desk(self):
        result = self.render(private_ip='10.20.9.1', peers=[
            dict(public_key=PUBLIC_KEY, allowed_ips=['10.20.10.1/32'])])
        self.assertEqual(result.returncode, 0, result.stderr)
        config = base64.b64decode(re.search(r'    content: ([A-Za-z0-9+/=]+)', result.stdout)[1]).decode()
        self.assertIn('AllowedIPs = 10.20.10.1/32\n', config)
        self.assertNotIn('Endpoint =', config)

    def test_hooks_newlines_unknown_fields_and_invalid_peers_are_refused_by_field(self):
        base = dict(public_key=PUBLIC_KEY, allowed_ips=['10.20.0.1/32'])
        cases = [
            ({'peers': 'PreUp = touch /root/compromised'}, 'peers'),
            ({'peers': [dict(base, PreUp='touch /root/compromised')]}, 'peers[0].PreUp'),
            ({'peers': [dict(base, public_key=PUBLIC_KEY+'\nPreUp = evil')]}, 'peers[0].public_key'),
            ({'peers': [dict(base, allowed_ips=['10.20.0.1/32\nPreUp = evil'])]}, 'peers[0].allowed_ips'),
            ({'peers': [dict(base, endpoint='203.0.113.1:443\nPreUp = evil')]}, 'peers[0].endpoint'),
            ({'peers': [dict(base, persistent_keepalive='25\nPreUp = evil')]}, 'peers[0].persistent_keepalive'),
            ({'PreUp': 'evil'}, 'PreUp'),
            ({'private_key': PRIVATE_KEY+'\n'}, 'private_key'),
            ({'private_ip': '10.20.0.1\n'}, 'private_ip'),
            ({'peers': [None]}, 'peers[0]'),
            ({'peers': [[]]}, 'peers[0]'),
            ({'peers': [dict(base, public_key=PUBLIC_KEY[:-2]+'B=')]}, 'peers[0].public_key'),
            ({'peers': [dict(base, allowed_ips='10.20.0.1/32')]}, 'peers[0].allowed_ips'),
            ({'peers': [dict(base, allowed_ips=[])]}, 'peers[0].allowed_ips'),
        ]
        for settings, field in cases:
            with self.subTest(settings=settings):
                result = self.render(**settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn(field, result.stderr)
                self.assertNotIn(PRIVATE_KEY, result.stderr)

    def test_prefixes_endpoints_and_keepalive_hold_only_their_characters(self):
        valid = ['0.0.0.0/0', '10.20.0.1/32', '::/0', '2001:db8::1/128', '::ffff:192.0.2.1/128']
        base = dict(public_key=PUBLIC_KEY, allowed_ips=valid)
        self.assertEqual(self.render(peers=[base]).returncode, 0)
        for prefix in ('10.20.0.1', '10.20.0.1/32 ', 'example.com/32', '10.20.0.1/32,10.20.0.2/32', '::1/128\n'):
            with self.subTest(prefix=prefix):
                result = self.render(peers=[dict(base, allowed_ips=[prefix])])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('peers[0].allowed_ips', result.stderr)
                self.assertEqual(result.stdout, '')
        for endpoint in ('192.0.2.1:443', '[2001:db8::1]:443'):
            with self.subTest(endpoint=endpoint):
                result = self.render(peers=[dict(base, endpoint=endpoint)])
                self.assertEqual(result.returncode, 0, result.stderr)
        for endpoint in ('192.0.2.1', '2001:db8::1:443', 'example.com:443', '192.0.2.1:443\n', None):
            with self.subTest(endpoint=endpoint):
                result = self.render(peers=[dict(base, endpoint=endpoint)])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('peers[0].endpoint', result.stderr)
                self.assertEqual(result.stdout, '')
        for seconds in (0, 25, 65535):
            result = self.render(peers=[dict(base, persistent_keepalive=seconds)])
            self.assertEqual(result.returncode, 0, result.stderr)
        for seconds in (-1, 65536, 0.5, '25', None, True):
            result = self.render(peers=[dict(base, persistent_keepalive=seconds)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('peers[0].persistent_keepalive', result.stderr)

    def test_one_json_object_is_required(self):
        for data in ('{} {}', '[]', 'null'):
            result = subprocess.run(['bash', str(RENDERER)], input=data, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertIn('input', result.stderr)

    def test_boot_closes_public_ssh_before_packages_and_keeps_key_for_mmx(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            etc = root/'etc'; (etc/'default').mkdir(parents=True); (etc/'cloud').mkdir()
            (etc/'default/ufw').write_text('IPV6=no\nMANAGE_BUILTINS=yes\n')
            binary = root/'bin'; binary.mkdir()
            log = root/'commands'
            fake = '''import json, os, pathlib, sys
with open(os.environ['COMMAND_LOG'],'a') as f: f.write(json.dumps([pathlib.Path(sys.argv[0]).name,*sys.argv[1:]])+'\\n')
'''
            fake += '''
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if name == 'sed':
    p=pathlib.Path(args[-1]); p.write_text(p.read_text().replace('IPV6=no','IPV6=yes').replace('MANAGE_BUILTINS=yes','MANAGE_BUILTINS=no'))
'''
            for name in ('iptables','ip6tables','apt-get','ufw','systemctl','chown','sed'):
                command = binary/name; command.write_text('#!'+sys.executable+'\n'+fake); command.chmod(0o755)
            rendered = self.render().stdout
            (etc/'wireguard').mkdir()
            (etc/'wireguard/wg0.private_key').write_text(PRIVATE_KEY+'\n')
            encoded = re.search(r'    content: ([A-Za-z0-9+/=]+)', rendered)[1]
            (etc/'wireguard/wg0.conf').write_bytes(base64.b64decode(encoded))
            guards = ["iptables -I INPUT 1 ! -i wg0 -p tcp --dport 22 -j DROP", "ip6tables -I INPUT 1 ! -i wg0 -p tcp --dport 22 -j DROP"]
            self.assertIn("[iptables, -I, INPUT, '1', '!', -i, wg0, -p, tcp, --dport, '22', -j, DROP]", rendered)
            self.assertIn("[ip6tables, -I, INPUT, '1', '!', -i, wg0, -p, tcp, --dport, '22', -j, DROP]", rendered)
            script = '\n'.join(guards) + '\n' + '\n'.join(line[6:] for line in rendered.split('    - |\n', 1)[1].splitlines())
            script = script.replace('/etc/', str(etc)+'/')
            result = subprocess.run(['bash','-c',script], env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],'COMMAND_LOG':str(log)}, text=True,capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([c[0] for c in commands[:2]], ['iptables','ip6tables'])
            for command in commands[:2]: self.assertEqual(command[-4:], ['--dport','22','-j','DROP'])
            # util01 runs MMX against its own private address over loopback, which the guards drop.
            enable = commands.index(['ufw','--force','enable'])
            for name in ('iptables','ip6tables'):
                removal = [name,'-D','INPUT','!','-i','wg0','-p','tcp','--dport','22','-j','DROP']
                self.assertIn(removal, commands)
                self.assertGreater(commands.index(removal), enable)
            self.assertIn(['ufw','allow','51820/udp'], commands)
            ssh_rules = [c for c in commands if c[:2] == ['ufw','allow'] and '22' in c]
            self.assertEqual(ssh_rules, [['ufw','allow','in','on','wg0','to','any','port','22','proto','tcp']])
            self.assertFalse(any(c[:3] == ['ufw','allow','22/tcp'] for c in commands))
            for address in ('169.254.169.254', 'fd00:ec2::254'):
                self.assertIn(['ufw','deny','out','to',address,'port','80','proto','tcp'], commands)
            self.assertEqual((etc/'wireguard/wg0.private_key').read_text(), PRIVATE_KEY+'\n')
            self.assertEqual((etc/'wireguard/wg0.private_key').stat().st_mode & 0o777, 0o600)
            self.assertTrue((etc/'cloud/cloud-init.disabled').exists())
            self.assertIn('IPV6=yes', (etc/'default/ufw').read_text())
            self.assertIn('MANAGE_BUILTINS=no', (etc/'default/ufw').read_text())
            self.assertNotIn(['ufw','--force','reset'], commands)


if __name__ == '__main__':
    unittest.main()
