#!/usr/bin/env python3
"""destroy_replaced_servers destroys only by trailer ID, and only after the new server works.

  MMX_BINARY=/path/to/mmx python3 tests/destroy_replaced_servers_test.py

The test uses the harness of tests/replace_failed_servers_test.py: a copy of
the template in a Git repository with a bare "Git host", the env from
`mmx explain destroy_replaced_servers --json`, the fleet hub's answer, and
stand-in provider scripts and ssh. It checks that nothing is destroyed while
the new server does not report or does not do its work, that a failed server
is destroyed by the ID in its replacement commit's trailer and never by a
name, that an ID the provider lists under an inventory server's name is
never destroyed, that a whole chain (a bad new server replaced again) is
destroyed together, that a rerun after a failed destroy finishes the
work without destroying anything twice, and that a jobs server and a
load-balancer server are destroyed the same way, with the new server
checked at its own pool's address.
"""
import json
import os
from pathlib import Path
import subprocess
import unittest

import replace_failed_servers_test as harness
from replace_failed_servers_test import git, node

APP001 = {'id': 'id-app001', 'name': 'app001', 'public_ipv4_address': '203.0.113.11', 'power_state': 'stopped'}


class DestroyReplacedServers(unittest.TestCase):
    # The harness of tests/replace_failed_servers_test.py.
    setUpClass = classmethod(harness.ReplaceFailedServers.setUpClass.__func__)
    setUp = harness.ReplaceFailedServers.setUp
    tearDown = harness.ReplaceFailedServers.tearDown
    fake = harness.ReplaceFailedServers.fake
    commit_all = harness.ReplaceFailedServers.commit_all
    replacement_commit = harness.ReplaceFailedServers.replacement_commit
    add_server = harness.ReplaceFailedServers.add_server
    edit_inventory = harness.ReplaceFailedServers.edit_inventory

    def run_destroy(self, fleet, provider=(APP001,), util01_listed=True, **settings):
        (self.state/'fleet.json').write_text(json.dumps({'nodes': fleet}))
        result = subprocess.run([self.mmx, 'explain', 'destroy_replaced_servers', '--json'], cwd=self.repository,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        env = {}
        for item in json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][1]['arguments']:
            if item['field'].startswith('shell.env.'):
                value = item['value']
                env[item['field'][10:]] = value if isinstance(value, str) else json.dumps(value) if value is not None else 'stand-in token'
        env.update(SYSTEMS_REPOSITORY_SSH_URL=str(self.origin), **settings)
        self.log.unlink(missing_ok=True)
        result = subprocess.run(['bash', str(self.repository/'server_management_scripts/destroy_replaced_servers')],
                                cwd=self.repository, text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=120,
                                env={**os.environ, **env, 'PATH': f'{self.binary}:{os.environ["PATH"]}',
                                     'COMMAND_LOG': str(self.log), 'NEW_KEY': 'unused',
                                     'PROVIDER_SERVERS': json.dumps({'servers': [harness.UTIL01_AT_THE_PROVIDER] * util01_listed
                                                                                + list(provider)})})
        commands = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, commands

    def destroys(self, commands):
        return [c for c in commands if c[0] == 'destroy_a_server_at_the_provider']

    def commits(self):
        return int(git(self.origin, 'rev-list', '--count', 'main'))

    def replaced_app001_with_app002(self):
        known_hosts = self.repository/'ssh/known_hosts'
        known_hosts.write_text(known_hosts.read_text() + '10.20.1.1 ssh-ed25519 app001-key\n10.20.1.2 ssh-ed25519 app002-key\n')
        self.replacement_commit('app001', 'id-app001', 'app002', 2, 1)

    def test_nothing_to_destroy(self):
        result, commands = self.run_destroy([node('app001'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('nothing to destroy', result.stdout)
        self.assertEqual(commands, [])

    def test_nothing_is_destroyed_while_the_new_server_does_not_do_its_work(self):
        self.replaced_app001_with_app002()
        before = self.commits()
        for fleet, settings, text in (([node('db01')], {}, 'the fleet hub says not in the hub'),
                                      ([node('app002', 'waiting_for_first_report'), node('db01')], {}, 'waiting_for_first_report'),
                                      ([node('app002', 'silent', 200), node('db01')], {}, 'the fleet hub says silent'),
                                      ([node('app002'), node('db01')], {'NOT_WORKING': '10.20.1.2'}, 'app002 does not do its work yet: nothing of app001 destroyed')):
            with self.subTest(text=text):
                result, commands = self.run_destroy(fleet, **settings)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(text, result.stdout)
                self.assertEqual(self.destroys(commands), [])
                self.assertEqual(self.commits(), before)

    def test_the_failed_server_is_destroyed_by_its_trailer_id_and_recorded(self):
        self.replaced_app001_with_app002()
        result, commands = self.run_destroy([node('app002'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.destroys(commands), [['destroy_a_server_at_the_provider', '--server-id', 'id-app001']])
        message = git(self.origin, 'log', '-1', '--format=%B', 'main')
        self.assertTrue(message.startswith('Destroy app001 at the provider: app002 does its work\n'), message)
        trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main').strip().splitlines()
        self.assertEqual(trailers, ['Server-pool: app_servers', 'Destroyed-server: app001', 'Destroyed-server-provider-id: id-app001'])
        known_hosts = git(self.origin, 'show', 'main:ssh/known_hosts')
        self.assertNotIn('app001-key', known_hosts)
        self.assertIn('app002-key', known_hosts)
        # Requested again: nothing waits, nothing is destroyed.
        result, commands = self.run_destroy([node('app002'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('nothing to destroy', result.stdout)
        self.assertEqual(self.destroys(commands), [])

    def test_an_id_the_provider_lists_under_an_inventory_servers_name_is_never_destroyed(self):
        self.replaced_app001_with_app002()
        result, commands = self.run_destroy([node('app002'), node('db01')],
                                            provider=({'id': 'id-app001', 'name': 'db01', 'public_ipv4_address': '203.0.113.21', 'power_state': 'running'},))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('the provider lists ID id-app001 as db01, a server in the inventory', result.stdout)
        self.assertEqual(self.destroys(commands), [])

    def test_a_list_without_util01_destroys_and_commits_nothing(self):
        # 2026-11-12 at a real provider: an empty list made app001 "counted as
        # destroyed", and the commit said so, while app001 still existed.
        self.replaced_app001_with_app002()
        before = self.commits()
        for provider in ((), (APP001,)):
            with self.subTest(provider=provider):
                result, commands = self.run_destroy([node('app002'), node('db01')], provider=provider, util01_listed=False)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("the provider's list does not hold util01, the server this program runs on", result.stdout)
                self.assertNotIn('counted as destroyed', result.stdout)
                self.assertEqual(self.destroys(commands), [])
                self.assertEqual(self.commits(), before)

    def test_a_whole_chain_is_destroyed_once_its_newest_server_works(self):
        self.replaced_app001_with_app002()
        self.replacement_commit('app002', 'created-app002', 'app003', 3, 2)
        provider = (APP001, {'id': 'created-app002', 'name': 'app002', 'public_ipv4_address': '203.0.113.200', 'power_state': 'stopped'})
        result, commands = self.run_destroy([node('app003'), node('db01')], provider=provider)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sorted(c[2] for c in self.destroys(commands)), ['created-app002', 'id-app001'])
        self.assertIn('Destroyed-server: app002\nDestroyed-server-provider-id: created-app002',
                      git(self.origin, 'log', '-1', '--format=%B', 'main'))

    def test_a_jobs_server_and_a_load_balancer_server_are_destroyed_by_trailer_id(self):
        for pool, old, new, block, number in (('jobs_servers', 'jobs001', 'jobs002', 3, 2),
                                              ('load_balancer_servers', 'lb01', 'lb03', 4, 3)):
            with self.subTest(pool=pool):
                self.add_server(pool, old, 1)
                known_hosts = self.repository/'ssh/known_hosts'
                known_hosts.write_text(known_hosts.read_text() + f'10.20.{block}.1 ssh-ed25519 {old}-key\n'
                                       f'10.20.{block}.{number} ssh-ed25519 {new}-key\n')
                self.commit_all(f'Add {old}')
                self.replacement_commit(old, f'id-{old}', new, number, 1, pool=pool)
                old_at_the_provider = {'id': f'id-{old}', 'name': old, 'public_ipv4_address': '203.0.113.99', 'power_state': 'stopped'}
                result, commands = self.run_destroy([node('app001'), node('db01'), node(new)], provider=(old_at_the_provider,))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.destroys(commands), [['destroy_a_server_at_the_provider', '--server-id', f'id-{old}']])
                # The new server's own check, at its pool's address.
                self.assertIn(['ssh', '-F', 'ssh/config', '-o', 'ConnectTimeout=10', f'root@10.20.{block}.{number}',
                               '/usr/local/bin/check-that-this-server-does-its-work'], commands)
                trailers = git(self.origin, 'log', '-1', '--format=%(trailers:only,unfold)', 'main').strip().splitlines()
                self.assertEqual(trailers, [f'Server-pool: {pool}', f'Destroyed-server: {old}', f'Destroyed-server-provider-id: id-{old}'])
                known_hosts = git(self.origin, 'show', 'main:ssh/known_hosts')
                self.assertNotIn(f'{old}-key', known_hosts)
                self.assertIn(f'{new}-key', known_hosts)
                git(self.repository, 'pull', '--quiet', 'origin', 'main')

    def marks(self, commands):
        return [c for c in commands if c[:2] == ['mmx', 'mark-node-work-failed']]

    def test_mmx_is_told_each_destroyed_server_is_gone(self):
        # After the provider confirmed the destroy, MMX's unconfirmed work of the server is recorded.
        self.replaced_app001_with_app002()
        self.replacement_commit('app002', 'created-app002', 'app003', 3, 2)
        provider = (APP001, {'id': 'created-app002', 'name': 'app002', 'public_ipv4_address': '203.0.113.200', 'power_state': 'stopped'})
        result, commands = self.run_destroy([node('app003'), node('db01')], provider=provider)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ('app001', 'app002'):
            mark = ['mmx', 'mark-node-work-failed', '--node', name, '--json', '--non-interactive']
            self.assertIn(mark, commands)
            destroy = ['destroy_a_server_at_the_provider', '--server-id', 'id-app001' if name == 'app001' else 'created-app002']
            self.assertLess(commands.index(destroy), commands.index(mark))
        # A server the provider no longer lists is gone too.
        git(self.origin, 'update-ref', 'refs/heads/main', 'main~1')
        result, commands = self.run_destroy([node('app003'), node('db01')], provider=())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.marks(commands)), 2)

    def test_a_server_that_answers_after_its_destroy_stops_the_run_and_commits_nothing_more(self):
        # Exit 2: MMX reached the server although the provider said destroyed.
        self.replaced_app001_with_app002()
        before = self.commits()
        result, commands = self.run_destroy([node('app002'), node('db01')], MARK_EXIT='2')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('MMX reached app001 although the provider says it is destroyed', result.stdout)
        self.assertEqual(self.commits(), before)
        # The rerun: the provider no longer lists app001; MMX still answers, so it stops again.
        result, commands = self.run_destroy([node('app002'), node('db01')], provider=(), MARK_EXIT='2')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(self.commits(), before)

    def test_mmx_that_cannot_tell_or_fails_is_reported_and_the_destroy_still_finishes(self):
        self.replaced_app001_with_app002()
        for code, provider in (('3', (APP001,)), ('4', (APP001,))):
            with self.subTest(exit_code=code):
                result, commands = self.run_destroy([node('app002'), node('db01')], provider=provider, MARK_EXIT=code)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.destroys(commands), [['destroy_a_server_at_the_provider', '--server-id', 'id-app001']])
                self.assertIn(f'app001 is gone, but mmx mark-node-work-failed exited {code}', result.stdout)
                self.assertIn('Destroyed-server: app001', git(self.origin, 'log', '-1', '--format=%B', 'main'))
                # Back to before the cleanup commit, for the next exit code.
                git(self.origin, 'update-ref', 'refs/heads/main', 'main~1')

    def test_a_rerun_after_a_failed_destroy_finishes_without_destroying_twice(self):
        self.replaced_app001_with_app002()
        before = self.commits()
        result, commands = self.run_destroy([node('app002'), node('db01')], DESTROY_EXIT='1')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('destroying app001 (ID id-app001) at the provider failed', result.stdout)
        self.assertEqual(self.commits(), before)
        # The rerun: the provider still lists app001, so it is destroyed now.
        result, commands = self.run_destroy([node('app002'), node('db01')])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.destroys(commands), [['destroy_a_server_at_the_provider', '--server-id', 'id-app001']])
        # A rerun after a destroy that worked but whose commit was lost: the
        # provider no longer lists the ID, which counts as destroyed.
        git(self.origin, 'update-ref', 'refs/heads/main', 'main~1')
        result, commands = self.run_destroy([node('app002'), node('db01')], provider=())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('the provider no longer lists app001 (ID id-app001): counted as destroyed', result.stdout)
        self.assertEqual(self.destroys(commands), [])
        self.assertIn('Destroyed-server: app001', git(self.origin, 'log', '-1', '--format=%B', 'main'))


if __name__ == '__main__':
    unittest.main()
