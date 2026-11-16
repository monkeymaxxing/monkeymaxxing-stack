#!/usr/bin/env python3
"""remove_server, run without server_name, removes only the app server the load no longer needs.

  MMX_BINARY=/path/to/mmx python3 tests/remove_an_app_server_for_the_load_test.py

server_management_scripts/remove_an_app_server_for_the_load holds the two
parts of the run on util01: `choose`, before remove_server's stages take the
server out of service, and `finish`, after them. The test uses the
stand-ins and the Git host of tests/replace_failed_servers_test.py, with the
env from `mmx explain remove_server --json`.

It checks `choose`: the server the load decision names; "nothing to
remove"; each refusal with nothing chosen (the lock-out, a pool of mixed
types, an app server that does not report, an unfinished replacement). It
checks `finish`: nothing committed or destroyed while the server's tunnel
connector runs or another app server does not do its work; otherwise one
commit with the trailers, the inventory and known_hosts without the server,
a one-time playbook moved, then the destroy by the provider ID of the entry
that matches the name and the public address, never by name, and the price
that stops. And it checks the playbook: one source of the server's name,
the person's server_name kept, and the last stage only without it.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replace_failed_servers_test as replacement  # noqa: E402
from add_an_app_server_for_the_load_test import FAKE  # noqa: E402

T = replacement.T
node = replacement.node
git = replacement.git
NAME = '{{ .outputs.find_the_server_to_remove.util01.server_name }}'
APP002 = {'id': 'id-app002', 'name': 'app002', 'public_ipv4_address': '203.0.113.112', 'power_state': 'running'}
REMOVE = {'decision': 'remove', 'why': 'the busiest CPU reading ... below 50%: the pool can spare a server; remove app002, its newest',
          'server_to_remove': 'app002', 'app_servers': 2, 'cpu_limit_percent': 35}

FAKE_WITH_CLOUDFLARED = FAKE.replace(
    "    elif args[-1] == 'nproc':",
    "    elif args[-3:] == ['systemctl', 'is-active', '--quiet'] or args[-4:-1] == ['systemctl', 'is-active', '--quiet']:\n"
    "        sys.exit(0 if target[5:] in os.environ.get('CLOUDFLARED_RUNS_ON', '').split(',') else 3)\n"
    "    elif args[-1] == 'nproc':")
assert 'CLOUDFLARED_RUNS_ON' in FAKE_WITH_CLOUDFLARED


class RemoveAnAppServerForTheLoad(unittest.TestCase):
    tearDown = replacement.ReplaceFailedServers.tearDown
    commit_all = replacement.ReplaceFailedServers.commit_all
    edit_inventory = replacement.ReplaceFailedServers.edit_inventory
    add_app_server = replacement.ReplaceFailedServers.add_app_server
    add_server = replacement.ReplaceFailedServers.add_server
    replacement_commit = replacement.ReplaceFailedServers.replacement_commit
    main_at_the_git_host = replacement.ReplaceFailedServers.main_at_the_git_host

    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to validate the changed inventory with MMX.')

    def setUp(self):
        replacement.ReplaceFailedServers.setUp(self)
        for name in ('list_the_servers_at_the_provider', 'destroy_a_server_at_the_provider', 'read_the_monthly_price_at_the_provider'):
            self.fake(self.repository/'server_management_scripts'/name)
        self.add_app_server('app002', 2)
        self.commit_all('A second app server')

    def fake(self, path):
        path.write_text('#!' + sys.executable + '\n' + FAKE_WITH_CLOUDFLARED)
        path.chmod(0o755)

    def explain(self, *arguments):
        result = subprocess.run([self.mmx, 'explain', 'remove_server', '--json', *arguments], cwd=self.repository,
                                text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def env(self, stage, task, **settings):
        explained = self.explain()
        stage = next(s for s in explained['fleet_stages'] if s['path'] == stage)
        task = next(t for t in stage['node_tasks'] if t['path'].endswith('/' + task))
        # The last stage's when reads an output, so explain leaves its values
        # unevaluated; the same settings come from add_an_app_server_for_the_load's explain.
        result = subprocess.run([self.mmx, 'explain', 'add_an_app_server_for_the_load', '--json'], cwd=self.repository,
                                text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        known = {item['field'][10:]: item['value'] for item in json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][2]['arguments']
                 if item['field'].startswith('shell.env.')}
        env = {}
        for item in task['arguments']:
            if item['field'].startswith('shell.env.'):
                key = item['field'][10:]
                value = item['value'] if item['value'] is not None else known.get(key)
                env[key] = value if isinstance(value, str) else json.dumps(value) if value is not None else 'stand-in'
        env['SYSTEMS_REPOSITORY_SSH_URL'] = str(self.origin)
        env.update(settings)
        return env

    def run_program(self, part, fleet=None, load=REMOVE, provider=(APP002,), util01_listed=True, **settings):
        (self.state/'fleet.json').write_text(json.dumps({'nodes': fleet or [node('app001'), node('app002'), node('db01')]}))
        (self.state/'app_pool_for_the_load.json').write_text(json.dumps(load))
        if part == 'choose':
            env = self.env('find_the_server_to_remove', 'choose_the_app_server_the_load_no_longer_needs', **settings)
            arguments = ['choose']
        else:
            env = self.env('finish_the_removal_for_the_load', 'commit_the_removal_and_destroy_the_server', **settings)
            arguments = ['finish', 'app002']
        env = {**os.environ, **env, 'PATH': f'{self.binary}:{os.environ["PATH"]}', 'COMMAND_LOG': str(self.log),
               'REAL_MMX': self.mmx, 'PROVIDER_SERVERS': json.dumps({'servers': list(provider) + ([replacement.UTIL01_AT_THE_PROVIDER] if util01_listed else [])})}
        result = subprocess.run(['bash', str(self.repository/'server_management_scripts/remove_an_app_server_for_the_load'), *arguments],
                                cwd=self.repository, env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=120)
        commands = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        self.log.unlink(missing_ok=True)
        return result, commands

    def chosen(self):
        path = self.state/'server_to_remove'
        return path.read_text().strip() if path.exists() else None

    def commits_at_the_git_host(self):
        return int(git(self.origin, 'rev-list', '--count', 'main').strip())

    # choose
    def test_choose_writes_the_server_the_load_names(self):
        result, commands = self.run_program('choose')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.chosen(), 'app002')
        self.assertIn('remove_server takes app002 out of service next', result.stdout)
        self.assertEqual(commands, [])

    def test_choose_with_no_spare_server_chooses_nothing(self):
        (self.state/'server_to_remove').write_text('app001\n')   # a stale choice of an earlier run
        result, _ = self.run_program('choose', load={'decision': 'none', 'why': 'not below 50%: the pool cannot spare a server'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('nothing to remove: not below 50%', result.stdout)
        self.assertEqual(self.chosen(), '')

    def assert_refused(self, result, text):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('remove_server refuses: ' + text, result.stdout)
        self.assertIsNone(self.chosen())

    def test_choose_refusals(self):
        cases = (
            ({'EVERYONE_LOCKED_OUT_EXCEPT_DESK': 'desk01'}, {}, 'the lock-out is on'),
            ({}, {'load': {'decision': 'stopped_by_a_bound', 'why': 'the app pool mixes server types'}}, 'the app pool mixes server types'),
            ({}, {'fleet': [node('app001', 'silent', 300), node('app002'), node('db01')]}, 'app001 is silent'),
            ({}, {'fleet': [node('app001'), node('db01')]}, 'app002 is not in the fleet hub'),
        )
        for settings, arguments, text in cases:
            with self.subTest(text=text):
                (self.state/'server_to_remove').unlink(missing_ok=True)
                result, _ = self.run_program('choose', **arguments, **settings)
                self.assert_refused(result, text)

    def test_choose_refuses_during_an_unfinished_replacement(self):
        self.replacement_commit('app001', 'id-app001', 'app003', 3, 1)
        result, _ = self.run_program('choose', fleet=[node('app002'), node('app003'), node('db01')])
        self.assert_refused(result, 'the replacement of app001 by app003 in app_servers is unfinished')

    # finish
    def test_finish_commits_then_destroys_by_the_matching_id(self):
        (self.repository/'one_time_playbooks/2026-11-12_free_disk_space_on_app002.yml').write_text(
            'fleet_stages:\n  - id: free_disk_space\n    nodes: app002\n    node_tasks:\n      - id: clean\n        shell:\n'
            '          script: "true"\n          dryrun: "true"\n')
        with open(self.repository/'ssh/known_hosts', 'a') as file:
            file.write('10.20.1.2 ssh-ed25519 app002-host-key\n')
        self.commit_all('A one-time playbook and the host key of app002')
        provider = (APP002, {'id': 'other', 'name': 'app002', 'public_ipv4_address': '198.51.100.9', 'power_state': 'running'})
        result, commands = self.run_program('finish', provider=provider)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        inventory = self.main_at_the_git_host()
        self.assertNotIn('app002', inventory)
        self.assertIn('  app_servers:\n    nodes: [app001]\n', inventory)
        self.assertIn('  app001:\n', inventory)
        self.assertNotIn('app002-host-key', self.main_at_the_git_host('ssh/known_hosts'))
        files = git(self.origin, 'ls-tree', '-r', '--name-only', 'main', 'one_time_playbooks')
        self.assertIn('one_time_playbooks/completed/2026-11-12_free_disk_space_on_app002.yml', files)
        self.assertEqual(git(self.origin, 'log', '-1', '--format=%s', 'main').strip(), 'Remove app002 from app_servers: the load no longer needs it')
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main')
        self.assertEqual(trailers.strip().splitlines(), ['Server-pool: app_servers', 'Removed-server: app002',
                                                         'Removed-server-provider-id: id-app002'])
        destroys = [c for c in commands if c[0] == 'destroy_a_server_at_the_provider']
        self.assertEqual(destroys, [['destroy_a_server_at_the_provider', '--server-id', 'id-app002']])
        # The checks come first: the tunnel connector, then every other app server's work.
        names = [c[-1] if c[0] == 'ssh' else c[0] for c in commands]
        self.assertLess(names.index('/usr/local/bin/check-that-this-server-does-its-work'), names.index('destroy_a_server_at_the_provider'))
        self.assertIn('app002: destroyed at the provider (ID id-app002)', result.stdout)
        self.assertIn('app002, cx33 in fsn1, costs 7.49 EUR a month with its public address', result.stdout)
        self.assertIn('app_servers holds 1 servers; what stops:', result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith('the fleet hub forgets it'), result.stdout)
        self.assertEqual(list(self.state.glob('attempt.*')), [])

    def test_finish_never_destroys_by_name_alone(self):
        result, commands = self.run_program('finish', provider=(
            {'id': 'someone-else', 'name': 'app002', 'public_ipv4_address': '198.51.100.9', 'power_state': 'running'},))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('destroy_a_server_at_the_provider', [c[0] for c in commands])
        self.assertIn('so nothing was destroyed: a person checks the provider', result.stdout)
        self.assertIn('Removed-server-provider-id: none', git(self.origin, 'log', '-1', '--format=%B', 'main'))

    def test_finish_refuses_a_provider_list_without_util01(self):
        """A partial list would leave the server running and paid for, with no ID to destroy."""
        before = self.commits_at_the_git_host()
        result, commands = self.run_program('finish', util01_listed=False)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("remove_server refuses: the provider's list does not hold util01", result.stdout)
        self.assertIn('request every_server to put it back', result.stdout)
        self.assertNotIn('destroy_a_server_at_the_provider', [c[0] for c in commands])
        self.assertEqual(self.commits_at_the_git_host(), before)

    def test_finish_refuses_while_the_server_still_serves_or_another_does_not(self):
        before = self.commits_at_the_git_host()
        for settings, text in (({'CLOUDFLARED_RUNS_ON': '10.20.1.2'}, "app002's tunnel connector still runs"),
                               ({'NOT_WORKING': '10.20.1.1'}, 'app001 does not do its work')):
            with self.subTest(text=text):
                result, commands = self.run_program('finish', **settings)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('remove_server refuses: ' + text, result.stdout)
                self.assertIn('request every_server to put', result.stdout)
                self.assertNotIn('destroy_a_server_at_the_provider', [c[0] for c in commands])
                self.assertEqual(self.commits_at_the_git_host(), before)

    def test_a_failed_destroy_names_the_id(self):
        result, _ = self.run_program('finish', DESTROY_EXIT='1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('its destroy at the provider FAILED: a person destroys it with '
                      'server_management_scripts/destroy_a_server_at_the_provider --server-id id-app002', result.stdout)

    # The playbook.
    def test_one_source_of_the_name_and_the_last_stage_only_without_server_name(self):
        playbook = (T/'playbooks/remove_server.yml').read_text()
        later = playbook.split('  - id: refuse_the_only_app_server')[1]
        self.assertNotIn('.vars.server_name', later.split('  - id: finish_the_removal_for_the_load')[0])
        self.assertGreaterEqual(later.count(NAME), 10)
        finish = playbook.split('  - id: finish_the_removal_for_the_load')[1]
        self.assertIn('- {equals: ["{{ .vars.server_name }}", ""]}', finish)
        self.assertIn(f'- not: {{equals: ["{NAME}", ""]}}', finish)
        # With a person's server_name, the load's three tasks are skipped and only the name is read.
        explained = self.explain('--var', 'server_name=app002')
        find = next(s for s in explained['fleet_stages'] if s['path'] == 'find_the_server_to_remove')
        self.assertEqual([t['status'] for t in find['node_tasks']], ['skipped', 'skipped', 'skipped', 'ready'])
        explained = self.explain()
        find = next(s for s in explained['fleet_stages'] if s['path'] == 'find_the_server_to_remove')
        self.assertEqual([t['status'] for t in find['node_tasks']], ['ready', 'ready', 'ready', 'ready'])

    def test_the_only_app_server_is_refused_before_any_change(self):
        playbook = (T/'playbooks/remove_server.yml').read_text()
        stages = re.findall(r'(?m)^  - id: (\S+)', playbook)
        self.assertLess(stages.index('refuse_the_only_app_server'), stages.index('hold_the_alerts_of_the_server'))
        self.assertIn(f'not: {{equals: ["{{{{ .inventory.groups.app_servers }}}}", ["{NAME}"]]}}', playbook)


    def test_a_stage_that_later_stages_require_on_all_nodes_never_skips_a_node_with_when(self):
        """A node that `when` skips does not count as succeeded for `requires.all_nodes` (MMX docs/reference/playbook-file.md),
        so a run of remove_server stopped at leave_the_tunnel. Pick the node with `nodes`, not `when`."""
        for playbook in sorted((T/'playbooks').glob('*.yml')):
            lines = playbook.read_text().splitlines()
            required = {name.strip() for line in lines for match in [re.match(r'\s*all_nodes:\s*\[(.*)\]', line)] if match
                        for name in match.group(1).split(',')}
            for number, line in enumerate(lines):
                match = re.match(r'( *)- id: (\S+)$', line)
                if not match or match.group(2) not in required:
                    continue
                properties = len(match.group(1)) + 2
                for following in lines[number + 1:]:
                    if re.match(r' {0,%d}- id:' % len(match.group(1)), following):
                        break
                    self.assertFalse(following.startswith(' ' * properties + 'when:'),
                                     f'{playbook.name}: {match.group(2)} has a when and is required on all_nodes')

    def test_the_hold_on_the_removed_servers_alerts_selects_only_that_server(self):
        stage = next(s for s in self.explain()['fleet_stages'] if s['path'] == 'hold_the_alerts_of_the_server')
        self.assertEqual(stage['selection'], '{{ .outputs.find_the_server_to_remove.util01.servers_to_remove }}')
        self.assertNotIn('when', stage)

    def test_with_nothing_to_remove_the_hold_selects_no_node_and_is_skipped(self):
        """The name "" is no node or group, so the hold failed the run. An empty list selects no node,
        and skip_when_no_nodes_are_selected then leaves the stage out and meets requires.all_nodes."""
        playbook = (T/'playbooks/remove_server.yml').read_text()
        hold = playbook.split('  - id: hold_the_alerts_of_the_server')[1].split('\n  - id: ')[0]
        self.assertIn('skip_when_no_nodes_are_selected: true', hold)
        program = re.search(r"PROGRAM: >-\n(.*?)\n\s+SERVER_NAME:", playbook, re.S).group(1)
        program = ' '.join(line.strip() for line in program.splitlines())
        for name, expected in (('', []), ('app002', ['app002'])):
            result = subprocess.run(['bash', '-c', program.replace('/var/lib/replace_failed_servers/server_to_remove', '/nonexistent')],
                                    env={**os.environ, 'SERVER_NAME': name}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['servers_to_remove'], expected)


if __name__ == '__main__':
    unittest.main()
