#!/usr/bin/env python3
"""Servers and desks reach each other on WireGuard's own port, with no connection tracking.

  MMX_BINARY=/path/to/mmx python3 tests/wireguard_direct_port_test.py

Test servers showed a stall of 12+ minutes after a wg0 reload. Any NAT table
gives each new flow a "null NAT binding"; when two peers send first packets
at once, or a peer that learned port 51820 meets a flow redirected from 443,
the tuples clash and NAT rewrites a source port. WireGuard roams to it, and
when that entry expires the peer sits on a dead port. The fix, proved on
four real servers: servers and desks use `Endpoint = <public address>:51820`
for each other, and an nftables raw table skips connection tracking for
that traffic. The redirect from 443 stays for laptops.

These tests render the real templates with MMX: the servers' and the desk's
wg0 files and the notrack table, from the playbooks' own inputs.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server_connections_test as connections  # noqa: E402

T = connections.T
SET = 'server_and_desk_public_addresses'
PUBLIC = {name: connections.server_block(name, address)['vars']['public_ipv4_address']
          for name, (_, address) in connections.SERVERS.items()}


class DirectPort(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to render the actual templates.')

    def render(self, template, variables, nodes=None):
        """The text MMX renders from a role template, its inputs given as vars."""
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=variables)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes=nodes or {'app001': {'address': '127.0.0.1', 'vars': {}}})))
            (root/'source.template').write_text((T/template).read_text().replace('.inputs', '.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            explained = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
            self.assertEqual(explained.returncode, 0, explained.stderr)
        return explained.stdout and json.loads(explained.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    def inventory_nodes(self):
        nodes = {n: {'vars': connections.server_block(n, ip)['vars']} for n, (_, ip) in connections.SERVERS.items()}
        nodes['app003'] = {'vars': {'private_ip': '10.20.1.3'}}  # a server that does not exist yet: no public address
        return nodes

    def test_servers_peer_with_servers_and_desks_on_port_51820_never_443(self):
        moving = dict(connections.MOVING)
        text = self.render('roles/every_server/files/wireguard_wg0.conf', dict(
            inventory_nodes=self.inventory_nodes(), wireguard_listen_port=51820,
            wireguard_peer_names=[n for n in connections.SERVERS if n != 'app001'],
            database_moving_in=moving, peers_with_the_database_moving_in=True))
        endpoints = re.findall(r'^Endpoint = (\S+)$', text, re.M)
        self.assertEqual(len(endpoints), len(connections.SERVERS) - 1 + 1)
        for name in connections.SERVERS:
            if name != 'app001':
                self.assertIn('Endpoint = %s:51820\n' % PUBLIC[name], text)
        # The old database is outside the Stack and keeps the redirect's port.
        self.assertIn('Endpoint = 203.0.113.50:443\n', text)
        self.assertEqual([e for e in endpoints if e.endswith(':443')], ['203.0.113.50:443'])

    def test_the_notrack_table_holds_every_server_and_desk_address_and_no_laptop(self):
        text = self.render('files_used_by_several_roles/wireguard_notrack_between_servers_and_desks.nft', dict(
            inventory_nodes=self.inventory_nodes(), wireguard_listen_port=51820, is_systems_desk=False))
        added = re.findall(r'^add element inet stack_wireguard_notrack %s \{ (\S+) \}$' % SET, text, re.M)
        self.assertEqual(sorted(added), sorted(PUBLIC.values()))
        self.assertEqual(len(added), len(set(added)))
        for laptop in ('10.20.10.', 'LAPTOP'):
            self.assertNotIn(laptop, text)
        self.assertIn('ip saddr @%s udp dport 51820 notrack' % SET, text)
        self.assertIn('ip daddr @%s udp sport 51820 notrack' % SET, text)
        self.assertRegex(text, r'type filter hook prerouting priority raw;')
        self.assertRegex(text, r'type filter hook output priority raw;')
        # Its own table: the redirect's table and ufw's files stay as they are.
        self.assertIn('flush table inet stack_wireguard_notrack', text)

    def test_the_redirect_stays_for_laptops(self):
        text = self.render('files_used_by_several_roles/wireguard_udp_443_redirect.nft', dict(wireguard_listen_port=51820))
        self.assertIn('udp dport 443 redirect to :51820', text)
        self.assertNotIn('notrack', text)

    def test_the_playbooks_give_every_server_and_the_desk_the_table_from_the_inventory(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)/'systems'
            connections.make_project(root)
            for playbook, extra, node in (('every_server', [], 'app001'), ('systems_desk', ['--var', 'desk_name=desk01'], 'desk01')):
                explained = subprocess.run([self.mmx, 'explain', playbook, *extra, '--json'], cwd=root, text=True, capture_output=True)
                self.assertEqual(explained.returncode, 0, explained.stderr)
                tasks = [task for stage in json.loads(explained.stdout)['fleet_stages'] for task in stage.get('node_tasks') or []
                         if task['path'].endswith('/write_the_wireguard_notrack_table') and task['node'] == node]
                with self.subTest(playbook=playbook):
                    self.assertEqual(len(tasks), 1)
                    text = tasks[0]['rendered_templates'][0]['text']
                    added = re.findall(r'^add element inet stack_wireguard_notrack %s \{ (\S+) \}$' % SET, text, re.M)
                    if playbook == 'every_server':
                        self.assertEqual(sorted(added), sorted(PUBLIC.values()))
                    else:
                        # A desk review must show no change when a server joins or leaves, so the
                        # desk's table includes a file that only update-this-desks-wireguard-peers writes.
                        self.assertEqual(added, [])
                        self.assertIn('include "/etc/systems-desk/wireguard-notrack-addresses.nft"', text)

    def test_the_table_is_written_before_the_unit_that_loads_it_and_before_wg0(self):
        for role, wg0 in (('every_server', 'id: join_the_wireguard_network\n'), ('systems_desk', 'id: join_the_wireguard_network\n')):
            with self.subTest(role=role):
                text = (T/'roles'/role/'main.yml').read_text()
                table = text.index('id: write_the_wireguard_notrack_table')
                self.assertLess(text.index('id: write_the_udp_443_redirect'), text.index('id: run_the_udp_443_redirect'))
                self.assertLess(table, text.index('id: run_the_udp_443_redirect'))
                self.assertLess(table, text.index(wg0))
                self.assertIn('check_new_file', text[table:table + 900])

    def test_the_unit_loads_both_tables_and_first_boot_matches_it(self):
        unit = (T/'files_used_by_several_roles/wireguard_udp_443_redirect.service').read_text()
        cloud = (T/'server_management_scripts/server_first_boot.cloud-config.yml').read_text()
        for line in ('ExecStart=/usr/sbin/nft -f /etc/wireguard/wireguard_udp_443_redirect.nft',
                     'ExecStart=/usr/sbin/nft -f /etc/wireguard/wireguard_notrack_between_servers_and_desks.nft'):
            self.assertIn(line, unit)
            self.assertIn(line, cloud)
        # First boot knows no other server yet: its table has the rules and an empty set.
        self.assertIn('path: /etc/wireguard/wireguard_notrack_between_servers_and_desks.nft', cloud)
        self.assertIn('ip saddr @%s udp dport @@WIREGUARD_LISTEN_PORT@@ notrack' % SET, cloud)

    def test_a_desks_first_boot_listens_on_the_redirected_port_like_a_servers(self):
        renderer = T/'server_management_scripts/render_server_first_boot'
        key = 'QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        peer = 'PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0='
        # Chapter 2's desk data: only the laptop, without an endpoint.
        settings = dict(private_key=key, private_ip='10.20.9.1', peers=[dict(public_key=peer, allowed_ips=['10.20.10.1/32'])])
        result = subprocess.run(['bash', str(renderer)], input=json.dumps(settings), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        import base64
        config = base64.b64decode(re.search(r'    content: ([A-Za-z0-9+/=]+)', result.stdout)[1]).decode()
        self.assertIn('ListenPort = 51820\n', config)
        self.assertIn('udp dport 443 redirect to :51820', result.stdout)
        self.assertIn('ufw allow 51820/udp', result.stdout)

    def test_no_script_or_guide_gives_a_server_or_desk_peer_port_443(self):
        # Allowed: the old database that moves in, outside the Stack, in the servers' wg0 template.
        allowed = {'roles/every_server/files/wireguard_wg0.conf': 1}
        found = {}
        for path in T.rglob('*'):
            if not path.is_file() or '.mmx' in path.parts:
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            relative = str(path.relative_to(T))
            if relative.startswith('operating_procedures/') or relative.startswith('provider_guides/'):
                continue  # guides about the redirect and the old database are checked by hand
            for line in text.splitlines():
                if re.search(r'(public_ipv4_address|PUBLIC_IPV4_ADDRESS|public\)?\b|public_address)[^\n]*:443\b', line) or \
                        re.search(r'\bendpoint: ["\']?[0-9.<>a-z_]+:443', line):
                    found[relative] = found.get(relative, 0) + 1
        self.assertEqual(found, allowed)

    def test_the_laptops_file_keeps_port_443_and_needs_no_unsupported_setting(self):
        # doubleshell refuses PersistentKeepalive in [Peer] (doubleshell config.go,
        # "unsupported setting"), so the laptop's file must not carry it until
        # doubleshell supports it.
        text = (T/'initial_setup/02_set_up_the_laptop_and_the_systems_desk.md').read_text()
        line = next(l for l in text.splitlines() if "printf '[Interface]" in l)
        self.assertIn('Endpoint = %s:443', line)
        self.assertNotIn('PersistentKeepalive', line)


if __name__ == '__main__':
    unittest.main()
