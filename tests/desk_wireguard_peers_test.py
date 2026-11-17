#!/usr/bin/env python3
"""A systems desk's WireGuard peers for the servers.

  MMX_BINARY=/path/to/mmx python3 tests/desk_wireguard_peers_test.py

The coding agent runs update-this-desks-wireguard-peers after a change to
the inventory's servers. These tests run its own functions on inventories
built like the template's, render the systems desk's real wg0 template with MMX, and
run the whole command against a stand-in wg and stand-in files.
"""
import base64
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server_connections_test as connections  # noqa: E402

T = connections.T
loader = importlib.machinery.SourceFileLoader('peers', str(T/'roles/systems_desk/files/update-this-desks-wireguard-peers'))
PEERS = importlib.util.module_from_spec(importlib.util.spec_from_loader('peers', loader))
loader.exec_module(PEERS)


def key(name):
    return base64.b64encode(name.encode().ljust(32, b'.')).decode()


def inventory(state='default'):
    """The ten test servers of server_connections_test, with real-looking
    WireGuard keys, in the template's address plan."""
    nodes, groups = {}, {}
    for name, (pool, address) in connections.SERVERS.items():
        block = connections.server_block(name, address)
        block['vars']['wireguard_public_key'] = key(name)
        for laptop in block['vars'].get('allowed_laptops', []):
            laptop['wireguard_public_key'] = key(laptop['laptop_name'])
        nodes[name] = block
        groups.setdefault(pool, {'nodes': []})['nodes'].append(name)
    groups['database_restore_servers'] = {'nodes': []}
    variables = {'wireguard_network': '10.20.0.0/16',
                 'private_ip_ranges': {'systems_desks': '10.20.9.0/24', 'systems_desk_laptops': '10.20.10.0/24',
                                       'database_servers': '10.20.2.0/24'},
                 'restore01_private_ip': '10.20.8.1', 'wireguard_listen_port': 51820}
    variables.update(connections.STATES[state])
    return {'vars': variables, 'nodes': nodes, 'groups': groups}


# The stand-in inventory is JSON, which is YAML, so the tests need no YAML
# library on this machine; the desk has python3-yaml.
JSON_AS_YAML = types.SimpleNamespace(safe_load=json.loads, YAMLError=ValueError)
LAPTOP_KEYS = {key('desk01-laptop'): 'the laptop desk01-laptop', key('desk01'): 'this systems desk'}
# The addresses of the reviewed wg0.conf: the laptop peer's and this desk's.
LAPTOP_ADDRESSES = {PEERS.ipaddress.IPv4Network('10.20.10.1/32'): 'the laptop desk01-laptop',
                    PEERS.ipaddress.IPv4Network('10.20.9.1/32'): 'this systems desk'}


class ServerPeers(unittest.TestCase):
    def test_a_desk_peers_with_every_server_it_peered_with_before_in_every_state(self):
        for state in connections.STATES:
            with self.subTest(state=state):
                peers = PEERS.server_peers(inventory(state), LAPTOP_KEYS, LAPTOP_ADDRESSES)
                names = sorted(name for name, _, _ in peers.values())
                before = connections.PEERS_BEFORE_THE_TABLE[state]['desk01'].split()
                self.assertEqual(names, [name for name in before if name != 'desk01-laptop'])
                self.assertEqual(peers[key('app001')], ('app001', '10.20.1.1', '203.0.113.11'))

    def test_a_server_without_a_wireguard_key_and_a_restore_server_are_left_out(self):
        servers = inventory()
        del servers['nodes']['jobs001']['vars']['wireguard_public_key']
        servers['groups']['database_restore_servers']['nodes'] = ['staging01']
        names = {name for name, _, _ in PEERS.server_peers(servers, LAPTOP_KEYS, LAPTOP_ADDRESSES).values()}
        self.assertNotIn('jobs001', names)
        self.assertNotIn('staging01', names)

    def test_a_recovery_database_server_is_a_peer_and_restore01_is_not(self):
        # During "Every database server is lost", db03 waits in database_restore_servers
        # with a database server's address, and the desks run its restore over WireGuard.
        # restore01 has vars.restore01_private_ip and peers only with util01.
        servers = inventory()
        for name, address in (('db03', '10.20.2.3'), ('restore01', '10.20.8.1')):
            block = connections.server_block(name, address)
            block['vars']['wireguard_public_key'] = key(name)
            servers['nodes'][name] = block
        servers['groups']['database_restore_servers']['nodes'] = ['db03', 'restore01']
        peers = PEERS.server_peers(servers, LAPTOP_KEYS, LAPTOP_ADDRESSES)
        self.assertEqual(peers[key('db03')], ('db03', '10.20.2.3', '203.0.113.23'))
        self.assertNotIn('restore01', {name for name, _, _ in peers.values()})

    def test_a_value_a_server_must_not_have_is_refused_by_name(self):
        def change(node, field, value):
            def apply(servers):
                servers['nodes'][node]['vars'][field] = value
            return apply
        cases = {
            'a key that is not WireGuard\'s': (change('app001', 'wireguard_public_key', 'APP001KEY'), 'not a WireGuard public key'),
            'a key with a newline': (change('app001', 'wireguard_public_key', key('app001')[:-1] + '\n'), 'not a WireGuard public key'),
            'a private address outside the network': (change('app001', 'private_ip', '10.30.1.1'), 'outside vars.wireguard_network'),
            'a private address in the systems desks\' block': (change('app001', 'private_ip', '10.20.9.7'), 'private_ip_ranges.systems_desks'),
            'a private address in the laptops\' block': (change('app001', 'private_ip', '10.20.10.1'),
                                                          'private_ip_ranges.systems_desk_laptops'),
            'a private address that is not one': (change('app001', 'private_ip', '10.20.1.1/16'), 'not an IPv4 address'),
            'a public address that is not IPv4': (change('app001', 'public_ipv4_address', '203.0.113.11:51820'), 'not an IPv4 address'),
            'a laptop\'s key': (change('app001', 'wireguard_public_key', key('desk01-laptop')), 'the WireGuard key of the laptop desk01-laptop'),
            'this systems desk\'s key': (change('app001', 'wireguard_public_key', key('desk01')), 'the WireGuard key of this systems desk'),
            'two servers with one key': (change('app002', 'wireguard_public_key', key('app001')), 'have one wireguard_public_key'),
            'two servers with one address': (change('app002', 'private_ip', '10.20.1.1'), 'have one private_ip'),
        }
        for case, (apply, message) in cases.items():
            with self.subTest(case=case):
                servers = inventory()
                apply(servers)
                with self.assertRaises(PEERS.Stop) as stopped:
                    PEERS.server_peers(servers, LAPTOP_KEYS, LAPTOP_ADDRESSES)
                self.assertIn(message, str(stopped.exception))
                self.assertTrue(str(stopped.exception).endswith('Nothing changed.'))
        # A push that also moves the inventory's blocks still cannot give a
        # server the laptop's or this desk's address from the reviewed wg0.
        for address, owner in (('10.20.10.1', 'the laptop desk01-laptop'), ('10.20.9.1', 'this systems desk')):
            with self.subTest(address=address):
                servers = inventory()
                servers['vars']['private_ip_ranges'].update(systems_desks='10.20.200.0/24', systems_desk_laptops='10.20.201.0/24')
                servers['nodes']['app001']['vars']['private_ip'] = address
                with self.assertRaises(PEERS.Stop) as stopped:
                    PEERS.server_peers(servers, LAPTOP_KEYS, LAPTOP_ADDRESSES)
                self.assertIn('is %s, the WireGuard address of %s. A server never takes it.' % (address, owner), str(stopped.exception))
        servers = inventory()
        servers['nodes']['app001\n[Peer]'] = servers['nodes'].pop('app001')
        with self.assertRaises(PEERS.Stop) as stopped:
            PEERS.server_peers(servers, LAPTOP_KEYS, LAPTOP_ADDRESSES)
        self.assertIn('is not a server name', str(stopped.exception))


class DeskWireGuardFile(unittest.TestCase):
    """The systems desk's wg0 file, rendered by MMX from the real template."""

    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to render the actual template.')

    def rendered(self, server_peers):
        laptops = inventory()['nodes']['desk01']['vars']['allowed_laptops']
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers')))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'desk01': {'address': '127.0.0.1', 'vars': dict(
                private_ip='10.20.9.1', wireguard_listen_port=51820, allowed_laptops=laptops, server_peers=server_peers)}})))
            template = (T/'roles/systems_desk/files/wireguard_wg0.conf').read_text()
            self.assertIn('.node_tasks.read_this_desks_server_peers.content', template)
            template = template.replace('.node_tasks.read_this_desks_server_peers.content', '.vars.server_peers').replace('.inputs', '.vars')
            (root/'source.template').write_text(template)
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            explained = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
            self.assertEqual(explained.returncode, 0, explained.stderr)
        return json.loads(explained.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    def test_the_file_keeps_the_laptops_above_the_line_and_the_server_peers_below_it(self):
        peers = PEERS.server_peers(inventory(), LAPTOP_KEYS, LAPTOP_ADDRESSES)
        server_peers = PEERS.server_peers_file('0123abc', peers, 51820)
        text = self.rendered(server_peers)
        self.assertIn(PEERS.SERVER_PEERS_LINE + '\n', text)
        self.assertIn('Address = 10.20.9.1/16\nListenPort = 51820\n', text)
        above, below = text.split(PEERS.SERVER_PEERS_LINE, 1)
        self.assertEqual(PEERS.peer_sections(above), [(key('desk01-laptop'), 'desk01-laptop')])
        self.assertEqual(sorted(name for _, name in PEERS.peer_sections(below)), sorted(name for name, _, _ in peers.values()))
        self.assertIn('[Peer]\n# app001\nPublicKey = %s\nEndpoint = 203.0.113.11:51820\nAllowedIPs = 10.20.1.1/32\n' % key('app001'), below)
        self.assertIn('PostUp = test ! -s /etc/systems-desk/wireguard-server-peers.conf || '
                      'wg addconf %i /etc/systems-desk/wireguard-server-peers.conf\n', above)
        # A new desk, before the coding agent first runs the command.
        empty = self.rendered('')
        self.assertEqual(PEERS.peer_sections(empty.split(PEERS.SERVER_PEERS_LINE, 1)[1]), [])


class TheWholeCommand(unittest.TestCase):
    """main() with a stand-in fetch, stand-in files and a stand-in wg."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        root = Path(self.directory.name)
        self.server_peers, self.wg0 = root/'wireguard-server-peers.conf', root/'wg0.conf'
        self.notrack_addresses = root/'wireguard-notrack-addresses.nft'
        old = {'app001': ('10.20.1.1', '203.0.113.11'), 'oldapp': ('10.20.1.7', '203.0.113.17')}
        old_peers = PEERS.server_peers_file('old', {key(n): (n, ip, public) for n, (ip, public) in old.items()}, 443)
        self.wg0.write_text('[Interface]\nAddress = 10.20.9.1/16\n\n[Peer]\n# desk01-laptop\nPublicKey = %s\nAllowedIPs = 10.20.10.1/32\n\n%s\n%s'
                            % (key('desk01-laptop'), PEERS.SERVER_PEERS_LINE, old_peers))
        self.running = {key('desk01-laptop'): ('(none)', '10.20.10.1/32'),
                        key('app001'): ('203.0.113.11:443', '10.20.1.1/32'),
                        key('oldapp'): ('203.0.113.17:443', '10.20.1.7/32')}
        self.calls = []
        self.inventory = json.dumps(inventory())

    def tearDown(self):
        self.directory.cleanup()

    def wg(self, arguments, **_):
        self.calls.append(arguments)
        if arguments[1:] == ['show', 'wg0', 'public-key']:
            return subprocess.CompletedProcess(arguments, 0, key('desk01') + '\n', '')
        if arguments[1:] == ['show', 'wg0', 'dump']:
            lines = ['private\tpublic\t443\toff'] + ['%s\t(none)\t%s\t%s\t0\t0\t0\toff' % (k, e, a) for k, (e, a) in self.running.items()]
            return subprocess.CompletedProcess(arguments, 0, '\n'.join(lines) + '\n', '')
        if arguments[1:3] == ['set', 'wg0']:
            return subprocess.CompletedProcess(arguments, 0, '', '')
        if arguments[0] == PEERS.NFT:
            return subprocess.CompletedProcess(arguments, 0, '', '')
        raise AssertionError(arguments)

    def press(self):
        out = io.StringIO()
        with patch.object(PEERS, 'SERVER_PEERS', self.server_peers), patch.object(PEERS, 'WG0_CONF', self.wg0), \
                patch.object(PEERS, 'NOTRACK_ADDRESSES', self.notrack_addresses), \
                patch.object(PEERS, 'fetch_the_pushed_inventory', lambda: ('abc123', self.inventory)), \
                patch.object(PEERS.os, 'geteuid', lambda: 0), patch.object(PEERS.subprocess, 'run', self.wg), \
                patch.dict(sys.modules, {'yaml': JSON_AS_YAML}), contextlib.redirect_stdout(out):
            PEERS.main([])
        return out.getvalue()

    def test_it_adds_new_servers_removes_gone_ones_and_keeps_the_laptops(self):
        self.running[key('app001')] = ('203.0.113.11:51820', '10.20.1.1/32')  # already current
        said = self.press()
        sets = [call for call in self.calls if call[1:3] == ['set', 'wg0']]
        self.assertIn([PEERS.WG, 'set', 'wg0', 'peer', key('oldapp'), 'remove'], sets)
        self.assertIn([PEERS.WG, 'set', 'wg0', 'peer', key('db01'), 'endpoint', '203.0.113.21:51820', 'allowed-ips', '10.20.2.1/32'], sets)
        self.assertFalse(any(key('desk01-laptop') in call or key('app001') in call for call in sets), sets)
        self.assertIn('Removed: oldapp (10.20.1.7/32).', said)
        self.assertIn('Added: db01 (10.20.2.1).', said)
        self.assertTrue(said.startswith('Pushed main commit abc123.\n'), said)
        written = self.server_peers.read_text()
        self.assertIn('pushed main commit abc123', written)
        self.assertNotIn('oldapp', written)
        self.assertEqual(oct(self.server_peers.stat().st_mode & 0o777), '0o600')

    def test_an_existing_desk_moves_every_server_peer_from_port_443_to_51820(self):
        # app001 runs at :443 (the earlier version). The command sets :51820
        # on the running wg0 and keeps the peer: no peer is removed, so no
        # session is cut. The desk's notrack set learns every server address
        # at once, so the pair is untracked before the next wg0 reload.
        self.press()
        sets = [call for call in self.calls if call[1:3] == ['set', 'wg0']]
        self.assertIn([PEERS.WG, 'set', 'wg0', 'peer', key('app001'), 'endpoint', '203.0.113.11:51820', 'allowed-ips', '10.20.1.1/32'], sets)
        self.assertNotIn(':443', self.server_peers.read_text())
        added = [call for call in self.calls if call[0] == PEERS.NFT]
        self.assertEqual(len(added), 1, added)
        # The same addresses, in the file the desk's table includes at every load (so a reboot keeps them).
        saved = self.notrack_addresses.read_text()
        self.assertIn('add element inet stack_wireguard_notrack server_and_desk_public_addresses { ', saved)
        self.assertIn('203.0.113.11', saved)
        self.assertNotIn('203.0.113.17', saved)
        self.assertEqual(oct(self.notrack_addresses.stat().st_mode & 0o777), '0o600')
        self.assertEqual(added[0][:6], [PEERS.NFT, 'add', 'element', 'inet', 'stack_wireguard_notrack', 'server_and_desk_public_addresses'])
        self.assertIn('203.0.113.11', added[0][6])
        self.assertNotIn('203.0.113.17', added[0][6])  # oldapp is gone from the inventory

    def test_the_port_comes_from_the_inventory_and_a_missing_one_is_refused(self):
        servers = inventory()
        del servers['vars']['wireguard_listen_port']
        self.inventory = json.dumps(servers)
        with self.assertRaises(PEERS.Stop) as stopped:
            self.press()
        self.assertIn('vars.wireguard_listen_port', str(stopped.exception))
        self.assertFalse(self.server_peers.exists())

    def test_a_second_run_changes_nothing_and_says_so(self):
        self.running = {key('desk01-laptop'): ('(none)', '10.20.10.1/32')}
        for k, (name, ip, public) in PEERS.server_peers(inventory(), LAPTOP_KEYS, LAPTOP_ADDRESSES).items():
            self.running[k] = ('%s:51820' % public, '%s/32' % ip)
        said = self.press()
        self.assertIn('No change', said)
        self.assertFalse([call for call in self.calls if call[1:3] == ['set', 'wg0']])

    def test_a_refused_inventory_changes_nothing(self):
        servers = inventory()
        servers['nodes']['app001']['vars']['private_ip'] = '10.20.10.1'
        self.inventory = json.dumps(servers)
        with self.assertRaises(PEERS.Stop):
            self.press()
        self.assertFalse(self.server_peers.exists())
        self.assertFalse([call for call in self.calls if call[1:3] == ['set', 'wg0']])

    def test_the_laptop_and_desk_addresses_come_from_the_reviewed_wg0_not_the_push(self):
        # The pushed inventory moves the laptops' and desks' blocks and gives
        # app001 the laptop's, or this desk's, address in the reviewed wg0.conf.
        for address, owner in (('10.20.10.1', 'the laptop desk01-laptop'), ('10.20.9.1', 'this systems desk')):
            with self.subTest(address=address):
                servers = inventory()
                servers['vars']['private_ip_ranges'].update(systems_desks='10.20.200.0/24', systems_desk_laptops='10.20.201.0/24')
                servers['nodes']['app001']['vars']['private_ip'] = address
                self.inventory = json.dumps(servers)
                self.calls = []
                with self.assertRaises(PEERS.Stop) as stopped:
                    self.press()
                self.assertIn('is %s, the WireGuard address of %s. A server never takes it.' % (address, owner), str(stopped.exception))
                self.assertFalse(self.server_peers.exists())
                self.assertFalse([call for call in self.calls if call[1:3] == ['set', 'wg0']])

    def test_it_takes_no_arguments(self):
        with self.assertRaises(PEERS.Stop) as stopped:
            PEERS.main(['--remove-everything'])
        self.assertIn('takes no arguments', str(stopped.exception))

    def test_the_desk_playbooks_form_is_refused_without_root(self):
        with patch.object(PEERS.os, 'geteuid', lambda: 1000), self.assertRaises(PEERS.Stop) as stopped:
            PEERS.main([PEERS.ONLY_WRITE_THE_SERVER_PEERS_FILE, '[]'])
        self.assertIn('takes no arguments', str(stopped.exception))


class TheDeskPlaybooksForm(unittest.TestCase):
    """--only-write-the-server-peers-file, which the systems desk playbook runs as
    root before it rewrites wg0: on a systems desk from an earlier Stack version, wg0's
    file has no server-peers line and the peers file does not exist yet."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        root = Path(self.directory.name)
        self.server_peers, self.wg0 = root/'wireguard-server-peers.conf', root/'wg0.conf'
        self.notrack_addresses = root/'wireguard-notrack-addresses.nft'
        # An earlier version's wg0.conf: laptop and server peers, no server-peers line.
        self.wg0.write_text('[Interface]\nAddress = 10.20.9.1/16\n\n[Peer]\nPublicKey = %s\nAllowedIPs = 10.20.10.1/32\n\n'
                            '[Peer]\nPublicKey = %s\nAllowedIPs = 10.20.1.1/32\n' % (key('desk01-laptop'), key('app001')))
        self.wg0_before = self.wg0.read_text()
        self.calls = []
        self.inventory = json.dumps(inventory())
        self.laptops = json.dumps(inventory()['nodes']['desk01']['vars']['allowed_laptops'])

    def tearDown(self):
        self.directory.cleanup()

    def wg(self, arguments, **_):
        self.calls.append(arguments)
        if arguments[1:] == ['show', 'wg0', 'public-key']:
            return subprocess.CompletedProcess(arguments, 0, key('desk01') + '\n', '')
        raise AssertionError('the systems desk playbook\'s form touched the running wg0: %s' % arguments)

    def fetch(self):
        return 'abc123', self.inventory

    def press(self):
        out = io.StringIO()
        with patch.object(PEERS, 'SERVER_PEERS', self.server_peers), patch.object(PEERS, 'WG0_CONF', self.wg0), \
                patch.object(PEERS, 'NOTRACK_ADDRESSES', self.notrack_addresses), \
                patch.object(PEERS, 'fetch_the_pushed_inventory', self.fetch), \
                patch.object(PEERS.os, 'geteuid', lambda: 0), patch.object(PEERS.subprocess, 'run', self.wg), \
                patch.dict(sys.modules, {'yaml': JSON_AS_YAML}), contextlib.redirect_stdout(out):
            code = PEERS.main([PEERS.ONLY_WRITE_THE_SERVER_PEERS_FILE, self.laptops])
        return code, out.getvalue()

    def test_an_earlier_desk_gets_the_server_peers_of_pushed_main_without_touching_wg0(self):
        code, said = self.press()
        self.assertEqual(code, 2)
        written = self.server_peers.read_text()
        self.assertIn('pushed main commit abc123', written)
        expected = PEERS.server_peers(inventory(), LAPTOP_KEYS, LAPTOP_ADDRESSES)
        self.assertEqual(sorted(name for _, name in PEERS.peer_sections(written)), sorted(name for name, _, _ in expected.values()))
        self.assertIn('[Peer]\n# app001\nPublicKey = %s\nEndpoint = 203.0.113.11:51820\nAllowedIPs = 10.20.1.1/32\n' % key('app001'), written)
        self.assertEqual(oct(self.server_peers.stat().st_mode & 0o777), '0o600')
        self.assertEqual(self.wg0.read_text(), self.wg0_before)
        self.assertIn('abc123', said)
        self.assertIn('app001', said)
        self.assertIn('203.0.113.11', self.notrack_addresses.read_text())
        # The same pushed main again: no change.
        code, said = self.press()
        self.assertEqual(code, 0)
        self.assertIn('already holds', said)

    def test_a_refused_server_value_stops_with_the_same_message_and_writes_nothing(self):
        servers = inventory()
        servers['nodes']['app001']['vars']['wireguard_public_key'] = key('desk01-laptop')
        self.inventory = json.dumps(servers)
        with self.assertRaises(PEERS.Stop) as stopped:
            self.press()
        self.assertIn('is %s, the WireGuard key of the laptop desk01-laptop. A server never takes it. Nothing changed.' % key('desk01-laptop'),
                      str(stopped.exception))
        with self.assertRaises(PEERS.Stop) as same:
            PEERS.server_peers(servers, LAPTOP_KEYS, LAPTOP_ADDRESSES)
        self.assertEqual(str(stopped.exception), str(same.exception))
        self.assertFalse(self.server_peers.exists())

    def test_a_pushed_inventory_cannot_move_a_laptops_address_to_a_server(self):
        # The pushed inventory moves the laptops' block and gives app001 the
        # laptop's address; the reviewed wg0.conf still names the laptop's.
        for address, owner in (('10.20.10.1', 'the laptop desk01-laptop'), ('10.20.9.1', 'this systems desk')):
            with self.subTest(address=address):
                servers = inventory()
                servers['vars']['private_ip_ranges'].update(systems_desks='10.20.200.0/24', systems_desk_laptops='10.20.201.0/24')
                servers['nodes']['app001']['vars']['private_ip'] = address
                self.inventory = json.dumps(servers)
                self.calls = []
                with self.assertRaises(PEERS.Stop) as stopped:
                    self.press()
                self.assertIn('the WireGuard address of %s' % owner, str(stopped.exception))
                self.assertFalse(any(call[1:3] == ['set', 'wg0'] for call in self.calls))

    def test_this_desks_own_key_is_refused_for_a_server(self):
        servers = inventory()
        servers['nodes']['app001']['vars']['wireguard_public_key'] = key('desk01')
        self.inventory = json.dumps(servers)
        with self.assertRaises(PEERS.Stop) as stopped:
            self.press()
        self.assertIn('the WireGuard key of this systems desk', str(stopped.exception))

    def test_without_pushed_main_the_file_stays_as_it_is(self):
        def no_git_host():
            raise PEERS.FetchFailed('git fetch failed: Permission denied (publickey). Nothing changed.')
        self.fetch = no_git_host
        self.server_peers.write_text('kept\n')
        code, said = self.press()
        self.assertEqual(code, 0)
        self.assertEqual(self.server_peers.read_text(), 'kept\n')
        self.assertIn('stays as it is', said)
        self.assertIn('Permission denied', said)

    def test_a_laptop_list_that_is_not_json_is_refused(self):
        self.laptops = 'work-laptop'
        with self.assertRaises(PEERS.Stop) as stopped:
            self.press()
        self.assertIn('allowed_laptops as JSON', str(stopped.exception))


class Wiring(unittest.TestCase):
    def test_the_desk_role_installs_the_command_and_lets_the_coding_agent_run_it_without_arguments(self):
        role = (T/'roles/systems_desk/main.yml').read_text()
        self.assertIn('source: files/update-this-desks-wireguard-peers', role)
        self.assertIn(r'coding-agent ALL=(root) NOPASSWD: /usr/local/bin/update-this-desks-wireguard-peers \"\"\n', role)
        self.assertIn('template: files/wireguard_wg0.conf', role)

    def test_the_desk_playbook_fills_the_server_peers_before_it_rewrites_wg0(self):
        role = (T/'roles/systems_desk/main.yml').read_text()
        ids = re.findall(r'(?m)^\s+- id: (\S+)', role)
        order = ['install_the_wireguard_peers_command', 'start_the_persistent_ssh_agent', 'start_the_shared_socket_relay',
                 'keep_a_file_for_this_desks_server_peers', 'write_this_desks_server_peers_from_pushed_main',
                 'read_this_desks_server_peers', 'join_the_wireguard_network']
        self.assertEqual([ids.index(name) for name in order], sorted(ids.index(name) for name in order))
        task = role[role.index('- id: write_this_desks_server_peers_from_pushed_main'):role.index('- id: read_this_desks_server_peers')]
        self.assertIn('/usr/local/bin/update-this-desks-wireguard-peers %s "$ALLOWED_LAPTOPS"' % PEERS.ONLY_WRITE_THE_SERVER_PEERS_FILE, task)
        self.assertIn('ALLOWED_LAPTOPS: "{{ .inputs.allowed_laptops }}"', task)
        self.assertEqual(PEERS.SERVER_PEERS_LINE,
                         re.search(r'(?m)^# Server peers, copied from .*$', (T/'roles/systems_desk/files/wireguard_wg0.conf').read_text()).group(0))


if __name__ == '__main__':
    unittest.main()
