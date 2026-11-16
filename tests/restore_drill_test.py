#!/usr/bin/env python3
"""Exercise the drill's ownership, cleanup, result and inventory contracts."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
SOURCE = TEMPLATE / 'playbooks/weekly_database_restore_drill.yml'
# MMHotline's waiting lines (internal/systemsrepository/copy_lock.go and
# internal/app/triage_agent_mmx_runs.go in MMHotline).
WAITING_RUN = ('mmhotline: mmx run replace_failed_servers --inventory servers for the triage agent, started '
               '2026-11-02T03:04:00Z, process 4242; waiting since 2026-11-02T03:04:00Z')
WAITING_FETCH = ('mmhotline: a short hold of the systems repository copy, such as a fetch at a triage agent run\'s '
                 'start; waiting since 2026-11-02T03:04:00Z')
FAKE = r'''import base64, json, os, pathlib, re, shutil, signal, sys, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as file:
    file.write(json.dumps([name, *args]) + '\n')
if name == 'date':
    print('2026-11-02T00:00:00Z' if args == ['-u', '+%FT%TZ'] else '1793577660' if '-d' in args else '1793577600')
elif name == 'list_the_servers_at_the_provider':
    names = ['restore01'] if os.environ.get('LEFTOVER') else []
    names += [n for n in os.environ.get('PROVIDER_SERVER_NAMES', '').split(',') if n]
    # util01, the machine the drill runs on, is in every list of this system's servers.
    if not os.environ.get('LIST_WITHOUT_UTIL01') and 'util01' not in names:
        names.append('util01')
    print(json.dumps({'servers': [{'name': n, 'id': 'someone-elses-server',
                                   'public_ipv4_address': '203.0.113.1' if n == 'util01' else '203.0.113.99'} for n in names]}))
    sys.exit(int(os.environ.get('LIST_EXIT', '0')))
elif name == 'create_a_server_at_the_provider':
    cloud_config = pathlib.Path(args[args.index('--first-boot-data') + 1]).read_text()
    wireguard = base64.b64decode(re.search(r'    content: ([A-Za-z0-9+/=]+)', cloud_config)[1]).decode()
    assert 'AllowedIPs = 10.20.0.1/32' in wireguard
    assert 'Endpoint = 203.0.113.1:51820' in wireguard
    assert 'PersistentKeepalive = 25' in wireguard
    assert wireguard.count('[Peer]') == 1
    assert 'Address = ' + os.environ['RESTORE01_PRIVATE_IP'] + '/16' in wireguard
    assert args[args.index('--wireguard-private-ip') + 1] == os.environ['RESTORE01_PRIVATE_IP']
    assert args[args.index('--image') + 1] == os.environ['SERVER_IMAGE']
    assert args[args.index('--ssh-key-name') + 1] == os.environ['UTIL01_SSH_KEY_NAME']
    path = pathlib.Path(args[args.index('--ownership-file') + 1])
    receipt = {'id':'owned-123','name':'restore01','public_ipv4_address':'203.0.113.90', 'ssh_known_hosts_line':'203.0.113.90 ssh-ed25519 test-key'}
    receipt.update(json.loads(os.environ.get('RECEIPT_OVERRIDES','{}')))
    path.write_text(json.dumps(receipt))
    print(json.dumps(receipt))
    sys.exit(int(os.environ.get('CREATE_EXIT', '0')))
elif name == 'destroy_a_server_at_the_provider':
    assert args == ['--server-id', 'owned-123'], args
    if os.environ.get('DESTROY_EXIT', '0') == '0' and os.environ.get('FLAGS'):
        pathlib.Path(os.environ['FLAGS'], 'restore01_destroyed').write_text('')
    sys.exit(int(os.environ.get('DESTROY_EXIT', '0')))
elif name == 'sleep':
    time.sleep(float(args[0]) / 10)  # The drill's waits, ten times shorter.
elif name == 'flock':
    if '--nonblock' in args: sys.exit(int(os.environ.get('BUSY','0')))
elif name == 'git':
    if args[0] != 'clone':
        if args[0] == 'symbolic-ref': print('main')
        elif args[0] == 'rev-parse': print('abc123')
        elif args[0] == 'merge-base': sys.exit(int(os.environ.get('MERGE_BASE_EXIT','0')))
        sys.exit(0)
    assert args[:2] == ['clone','--quiet']
    shutil.copytree('.', args[-1], ignore=shutil.ignore_patterns('.mmx','server_management_scripts'))
elif name == 'find_the_trusted_commit_of_the_systems_repository':
    print('abc123')
    sys.exit(int(os.environ.get('TRUSTED_COMMIT_EXIT','0')))
elif name == 'wg':
    print('QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' if args == ['genkey'] else 'PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0=')
elif name == 'mmx':
    if args == ['nodes', '--json']:
        print(json.dumps({'nodes':[{'name': n} for n in os.environ.get('INVENTORY_NODE_NAMES', '').split(',') if n], 'groups':{'database_restore_servers':['db-recovery'] if os.environ.get('INVENTORY_LEFTOVER') else []}}))
    elif args[0] == 'dryrun': sys.exit(int(os.environ.get('DRYRUN_EXIT','0')))
    elif args[:2] == ['explain', 'every_server']:
        # The daily comparison first asks whether a lock-out is set; the
        # check is skipped when it is not (tests/break_in_response_test.py
        # runs the timer's question against MMX itself).
        print(json.dumps({'fleet_stages':[{'node_tasks':[{'path':'every_server/a_lock_out_starts_only_with_the_lock_out_button','status':'skipped'}]}]}))
    elif args[:2] == ['run', 'weekly_database_restore_drill']:
        # The scheduled service's controller: the drill wrote this result.
        if os.environ.get('DRILL_RESULT'):
            pathlib.Path(os.environ['DRILL_RESULT_PATH']).write_text(os.environ['DRILL_RESULT'])
        sys.exit(int(os.environ.get('DRILL_EXIT', '0')))
    elif args[0] == 'run':
        inventory = pathlib.Path('inventories/servers.yml').read_text()
        assert '  restore01:\n    address: ' + os.environ['RESTORE01_PRIVATE_IP'] in inventory
        assert 'nodes: [restore01]' in inventory
        assert 'private_ip: ' + os.environ['RESTORE01_PRIVATE_IP'] in inventory
        assert 'public_ipv4_address: 203.0.113.90' in inventory
        assert 'test-key' in pathlib.Path('ssh/known_hosts').read_text()
        assert '--var' in args and 'recover_to=latest' in args
        assert 'read_backup_bucket_as_of=2026-11-02 00:00:00+00' in args
        if os.environ.get('STOP'):
            os.kill(os.getppid(), signal.SIGTERM)
        if os.environ.get('MARKER') == 'during_restore':
            # A long restore: it ends when restore01 is destroyed under it,
            # unless IGNORES_DESTROY, or when mmx stop stops it.
            flags = pathlib.Path(os.environ['FLAGS'])
            (flags / 'restore_started').write_text('')
            def terminated(*ignored):
                (flags / 'term_at').write_text(str(time.time()))
                sys.exit(1)
            signal.signal(signal.SIGTERM, terminated)
            try:
                for _ in range(600):
                    if (flags / 'stopped').exists(): sys.exit(1)
                    if (flags / 'restore01_destroyed').exists() and not os.environ.get('IGNORES_DESTROY'): sys.exit(1)
                    time.sleep(0.05)
                sys.exit('the restore was never stopped')
            finally:
                # What MMX needs before mark-node-work-failed: this process has exited.
                (flags / 'inner_run_ended').write_text('')
        print(json.dumps({'entries':[{'node':'restore01','fleet_stage':'check_the_restored_copy','response':{'outputs':{'answered_the_check_queries_at':'2026-11-02T00:01:00Z','seconds_of_writes_missing_at_most':17}}}]}))
        sys.exit(int(os.environ.get('RESTORE_EXIT', '0')))
    elif args[0] == 'stop':
        if os.environ.get('FLAGS'): pathlib.Path(os.environ['FLAGS'], 'stop_called_at').write_text(str(time.time()))
        if os.environ.get('FLAGS') and not os.environ.get('IGNORES_STOP'): pathlib.Path(os.environ['FLAGS'], 'stopped').write_text('')
        # MMX: exit 3 when work stays unconfirmed, such as restore01's after its destroy.
        sys.exit(int(os.environ.get('STOP_EXIT', '0')))
    elif args[0] == 'mark-node-work-failed':
        assert args == ['mark-node-work-failed', '--node', 'restore01', '--json', '--non-interactive'], args
        # MMX refuses a run whose own mmx process still holds it: exit 4.
        if not pathlib.Path(os.environ['FLAGS'], 'inner_run_ended').exists(): print('the run is held by its own process'); sys.exit(4)
        mark_exit = int(os.environ.get('MARK_EXIT', '0'))
        # MMX's mark-node-work-failed: --json always prints runs and runs_not_recorded; the exit code is the most serious outcome.
        not_recorded = [] if mark_exit == 0 else [{'id': '20261101T000000-aaaa', 'short_id': 'aaaa', 'reason': 'MMX could not judge restore01', 'exit_code': mark_exit}]
        print(json.dumps({'schema_version': 1, 'node': 'restore01', 'reason': 'the team says this server is gone', 'runs': [], 'runs_not_recorded': not_recorded}))
        sys.exit(mark_exit)
    else:
        sys.exit('unexpected mmx arguments')
elif name == 'rclone':
    if 'lsf' in args:
        if not os.environ.get('EMPTY_UPLOADS'): print('customer/sample.txt')
    else:
        assert 'check' in args and '--download' in args and '--b2-version-at=2026-11-02T00:00:00Z' in args
        sys.exit(int(os.environ.get('UPLOAD_EXIT', '0')))
elif name == 'shuf':
    lines=sys.stdin.read().splitlines()
    if lines: print(lines[0])
elif name == 'timeout':
    os.execvp(args[2], args[2:])
elif name == 'ssh':
    sys.stdin.read()  # Like real ssh, send standard input to the remote command.
    if 'wg' in args:
        assert args[:4] == ['-F','ssh/config','root@10.20.0.1','wg'], args
        sys.exit(int(os.environ.get('PEER_REMOVE_EXIT' if args[-1]=='remove' else 'PEER_ADD_EXIT','0')))
    assert args[-2] == 'root@' + os.environ['RESTORE01_PRIVATE_IP'], args
    with open('ssh/known_hosts','a') as file: file.write(os.environ['RESTORE01_PRIVATE_IP'] + ' ssh-ed25519 test-key\n')
elif name == 'rm': pass
else: sys.exit('unexpected command '+name)
'''


def shell_script():
    text = SOURCE.read_text()
    body = re.search(r'          script: \|\n(.*?)          dryrun:', text, re.S)[1]
    return '\n'.join(line[12:] for line in body.splitlines())



class RestoreDrill(unittest.TestCase):
    def run_drill(self, marker=None, marker_line=WAITING_RUN, **settings):
        """marker: None; 'from_start' or 'during_restore', MMHotline waiting and
        rewriting the marker every 0.05 s from the drill's start or from the
        restore's start; or 'stale', a marker left a minute ago."""
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            flags = root / 'flags'; flags.mkdir()
            state = root / 'state'; state.mkdir()
            repo = root / 'repository'; repo.mkdir()
            (repo/'inventories').mkdir(); (repo/'ssh').mkdir(); (repo/'.mmx').mkdir()
            inventory = (TEMPLATE/'inventories/servers.yml').read_text()
            (repo/'inventories/servers.yml').write_text(inventory)
            (repo/'ssh/known_hosts').write_text('original trusted host\n')
            binary = root/'bin'; binary.mkdir()
            provider = repo/'server_management_scripts'; provider.mkdir()
            for name in ('git','mmx','wg','ssh','date','rclone','shuf','rm','timeout','sleep','list_the_servers_at_the_provider','create_a_server_at_the_provider','destroy_a_server_at_the_provider'):
                path = (provider if name.endswith('_at_the_provider') else binary)/name
                path.write_text('#!'+sys.executable+'\n'+FAKE); path.chmod(0o755)
            for name in ('render_server_first_boot','server_first_boot.cloud-config.yml','steps_for_a_server_this_run_creates.bash',
                         'steps_for_reading_the_providers_list.bash'):
                shutil.copy2(TEMPLATE/'server_management_scripts'/name, provider/name)
            uploads = root/'uploads'; uploads.mkdir()
            (uploads/'latest_passed_copy').write_text('2026-11-01T00:00:00Z\n')
            log = root/'commands'
            script = shell_script().replace('/var/lib/restore_drill', str(state)).replace('/var/lib/mmhotline/systems_repository', str(repo)).replace('/var/lib/uploads_backup', str(uploads))
            env = {**os.environ, 'PATH':str(binary)+':'+os.environ['PATH'], 'COMMAND_LOG':str(log),
                   'SERVER_TYPE':'example-size','LOCATION':'example-location','SERVER_IMAGE':'debian-13',
                   'UTIL01_SSH_KEY_NAME':'utility key','APPS':json.dumps({'shop':{'production_uploads_r2_bucket':'shop-uploads'}}),
                   'UPLOADS_BUCKET':'backup-bucket', 'UTIL01_WIREGUARD_PUBLIC_KEY':'urzzcMKwVZ9bM84MmgWUjMRxOTNn2PDtEF5it/uZFQ4=',
                   'RESTORE01_PRIVATE_IP':'10.20.8.1', 'UTIL01_PRIVATE_IP':'10.20.0.1', 'UTIL01_PUBLIC_IPV4_ADDRESS':'203.0.113.1',
                   'FLAGS':str(flags), 'MARKER':marker or '', **settings}
            # The script's /var/lib/mmhotline/systems_repository.lock.waiting.
            waiting_marker = Path(str(repo) + '.lock.waiting')
            drill_ended = threading.Event()
            def mmhotline_waits():
                while not drill_ended.is_set():
                    if marker == 'from_start' or (marker == 'during_restore' and (flags/'restore_started').exists()):
                        waiting_marker.write_text(marker_line + '\n')
                    time.sleep(0.05)
            if marker == 'stale':
                waiting_marker.write_text(marker_line + '\n')
                os.utime(waiting_marker, (time.time() - 60, time.time() - 60))
            writer = threading.Thread(target=mmhotline_waits); writer.start()
            try:
                result = subprocess.run(['bash','-c',script],env=env,text=True,capture_output=True,stdin=subprocess.DEVNULL,timeout=120)
            finally:
                drill_ended.set(); writer.join()
            commands = [json.loads(line) for line in log.read_text().splitlines()]
            markers = {path.name:path.read_text() for path in state.glob('latest*')}
            markers.update({path.name:path.read_text() for path in flags.glob('*_at')})
            self.assertEqual((repo/'inventories/servers.yml').read_text(), inventory)
            self.assertEqual((repo/'ssh/known_hosts').read_text(), 'original trusted host\n')
            return result, commands, markers

    def test_success_records_measurements_after_owned_cleanup(self):
        result, commands, markers = self.run_drill()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(markers['latest_result.json'])['restore_duration_seconds'],60)
        self.assertEqual(json.loads(markers['latest_result.json'])['seconds_of_writes_missing_at_most'],17)
        self.assertIn('latest_passed_drill', markers)
        self.assertIn(['destroy_a_server_at_the_provider','--server-id','owned-123'],commands)
        self.assertTrue(any(c[0]=='rm' for c in commands))

    def test_image_and_key_name_are_the_settings_for_every_new_server(self):
        self.assertIn('SERVER_IMAGE: "{{ .vars.server_image }}"', SOURCE.read_text())
        self.assertIn('UTIL01_SSH_KEY_NAME: "{{ .vars.util01_ssh_key_name_at_the_provider }}"', SOURCE.read_text())

    def test_restore_address_comes_from_inventory_data(self):
        self.assertIn('RESTORE01_PRIVATE_IP: "{{ .vars.restore01_private_ip }}"', SOURCE.read_text())
        result, commands, markers = self.run_drill(RESTORE01_PRIVATE_IP='172.20.8.1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('latest_passed_drill', markers)
        peers = [c for c in commands if c[0] == 'ssh' and 'wg' in c]
        self.assertEqual(peers[0][-2:], ['allowed-ips', '172.20.8.1/32'])

    def test_runtime_peer_is_removed_after_success_or_failure(self):
        for settings in ({},{'CREATE_EXIT':'1'},{'RESTORE_EXIT':'1'},{'PEER_ADD_EXIT':'1'}):
            with self.subTest(settings=settings):
                result, commands, markers = self.run_drill(**settings)
                peers = [c for c in commands if c[0] == 'ssh' and 'wg' in c]
                self.assertEqual(len(peers), 2, (result.stderr, commands))
                self.assertEqual(peers[0][-2:], ['allowed-ips','10.20.8.1/32'])
                self.assertEqual(peers[1][-1], 'remove')
                if settings:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('latest_passed_drill', markers)

    def test_peer_cleanup_failure_cannot_mark_drill_passed(self):
        result, commands, markers = self.run_drill(PEER_REMOVE_EXIT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('latest_passed_drill', markers)

    def test_leftovers_never_create_or_destroy(self):
        for settings in ({'LEFTOVER':'yes'},{'INVENTORY_LEFTOVER':'yes'},{'LIST_EXIT':'1'},{'LIST_WITHOUT_UTIL01':'yes'}):
            with self.subTest(settings=settings):
                result, commands, markers = self.run_drill(**settings)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(any(c[0] in ('create_a_server_at_the_provider','destroy_a_server_at_the_provider') for c in commands))
                self.assertNotIn('latest_passed_drill',markers)

    def test_create_restore_or_upload_failure_still_destroys_owned_server(self):
        for settings in ({'CREATE_EXIT':'1'},{'RESTORE_EXIT':'1'},{'UPLOAD_EXIT':'1'},{'STOP':'yes'}):
            with self.subTest(settings=settings):
                result, commands, markers = self.run_drill(**settings)
                self.assertNotEqual(result.returncode,0,result.stderr)
                self.assertIn(['destroy_a_server_at_the_provider','--server-id','owned-123'],commands)
                self.assertTrue(any(c[0]=='rm' and c[-1].endswith('/project') for c in commands))
                self.assertNotIn('latest_passed_drill',markers)

    def test_empty_upload_sample_is_reported(self):
        result, commands, markers = self.run_drill(EMPTY_UPLOADS='yes')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('shop has no eligible uploaded file; no sample compared', result.stdout)
        self.assertFalse(any(c[0]=='rclone' and 'check' in c for c in commands))

    def test_invalid_receipt_never_selects_another_server(self):
        for receipt in ({'name':'db01'},{'id':''},{'id':None}):
            with self.subTest(receipt=receipt):
                result, commands, markers = self.run_drill(RECEIPT_OVERRIDES=json.dumps(receipt))
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(any(c[0]=='destroy_a_server_at_the_provider' for c in commands))
                self.assertNotIn('latest_passed_drill',markers)

    def test_failed_destruction_preserves_inventory_and_receipt(self):
        result, commands, markers = self.run_drill(DESTROY_EXIT='1')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(c[0]=='rm' and c[-1].endswith('/project') for c in commands))
        self.assertNotIn('latest_passed_drill', markers)
        self.assertFalse(json.loads(markers['latest_result.json'])['passed'])

    # The drill gives way to MMHotline (design E): exit 75, so the scheduled
    # service runs it again later, and gave_way_to names who waited.
    def assert_gave_way(self, result, markers, line):
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertEqual(json.loads(markers['latest_result.json']),
                         {'passed': False, 'started_at': '2026-11-02T00:00:00Z', 'gave_way_to': line})
        self.assertNotIn('latest_passed_drill', markers)

    def test_a_waiting_mmhotline_before_the_start_creates_nothing(self):
        result, commands, markers = self.run_drill(marker='from_start')
        self.assert_gave_way(result, markers, WAITING_RUN)
        self.assertFalse(any(c[0] in ('list_the_servers_at_the_provider', 'create_a_server_at_the_provider',
                                      'destroy_a_server_at_the_provider', 'ssh') for c in commands), commands)

    def test_a_waiting_mmhotline_during_the_restore_destroys_restore01_first(self):
        # mmx stop exits 3 after the destroy: restore01's work stays unconfirmed (expected).
        result, commands, markers = self.run_drill(marker='during_restore', STOP_EXIT='3')
        self.assert_gave_way(result, markers, WAITING_RUN)
        destroy = commands.index(['destroy_a_server_at_the_provider', '--server-id', 'owned-123'])
        peers = [i for i, c in enumerate(commands) if c[0] == 'ssh' and 'wg' in c]
        self.assertEqual(len(peers), 2)
        self.assertEqual(commands[peers[1]][-1], 'remove')
        self.assertLess(destroy, peers[1])
        self.assertEqual(len([c for c in commands if c[0] == 'destroy_a_server_at_the_provider']), 1)
        mark = commands.index(['mmx', 'mark-node-work-failed', '--node', 'restore01', '--json', '--non-interactive'])
        self.assertLess(destroy, mark)
        # The project, which the command runs in, is removed only after the command.
        self.assertLess(mark, max(i for i, c in enumerate(commands) if c[0] == 'rm' and c[-1].endswith('/project')))

    def test_an_inner_run_that_outlives_restore01_is_stopped_after_destruction(self):
        result, commands, markers = self.run_drill(marker='during_restore', IGNORES_DESTROY='yes', STOP_EXIT='3')
        self.assert_gave_way(result, markers, WAITING_RUN)
        destroy = commands.index(['destroy_a_server_at_the_provider', '--server-id', 'owned-123'])
        stop = commands.index(['mmx', 'stop', '--non-interactive'])
        mark = commands.index(['mmx', 'mark-node-work-failed', '--node', 'restore01', '--json', '--non-interactive'])
        self.assertLess(destroy, stop)
        self.assertLess(stop, mark)

    def test_an_inner_run_that_ignores_stop_is_ended_before_mark_node_work_failed(self):
        # The drill sends TERM at once after mmx stop (on test servers the inner run never ended by itself,
        # and a 30 s wait only delayed the lock's release); MMX answers
        # the command with exit 4 while the run's own process lives.
        result, commands, markers = self.run_drill(marker='during_restore', IGNORES_DESTROY='yes',
                                                   IGNORES_STOP='yes', STOP_EXIT='3')
        self.assert_gave_way(result, markers, WAITING_RUN)
        waited = (float(markers['term_at']) - float(markers['stop_called_at'])) * 10  # the stand-in sleep runs ten times faster
        self.assertLess(waited, 15, f'TERM came {waited:.1f} s after mmx stop')

    def test_a_failed_mark_node_work_failed_is_a_failed_cleanup_never_75(self):
        # Exit 2: MMX reached restore01, which the provider says is destroyed. 3: MMX could
        # not tell. 4: a command error. Each leaves the attempt directory and a reason.
        for code in ('2', '3', '4'):
            with self.subTest(exit_code=code):
                result, commands, markers = self.run_drill(marker='during_restore', STOP_EXIT='3', MARK_EXIT=code)
                self.assertEqual(result.returncode, 1, result.stderr)
                saved = json.loads(markers['latest_result.json'])
                self.assertEqual((saved['passed'], saved['gave_way_to']), (False, WAITING_RUN))
                self.assertIn('attempt_dir', saved)
                self.assertIn('mmx mark-node-work-failed --node restore01 exited ' + code, saved['cleanup_failure_reason'])
                self.assertIn('runs not recorded: 20261101T000000-aaaa: MMX could not judge restore01', saved['cleanup_failure_reason'])
                self.assertNotIn('latest_passed_drill', markers)

    def test_mmx_stop_failing_other_than_exit_3_is_a_failed_cleanup(self):
        for code in ('4', '130'):
            with self.subTest(exit_code=code):
                result, commands, markers = self.run_drill(marker='during_restore', IGNORES_DESTROY='yes', STOP_EXIT=code)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('attempt_dir', json.loads(markers['latest_result.json']))

    def test_a_short_hold_counts_as_a_waiter(self):
        # While the drill holds the lock, MMHotline's short fetch waits as long
        # as an MMX run does, such as the fetch that starts a triage agent run.
        result, commands, markers = self.run_drill(marker='during_restore', marker_line=WAITING_FETCH)
        self.assert_gave_way(result, markers, WAITING_FETCH)

    def test_a_marker_mmhotline_no_longer_rewrites_is_ignored(self):
        result, commands, markers = self.run_drill(marker='stale')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('gave_way_to', json.loads(markers['latest_result.json']))
        self.assertIn('latest_passed_drill', markers)

    def test_a_drill_that_gave_way_but_could_not_destroy_restore01_fails(self):
        # No run again later: the leftover restore01 needs a person, and the next drill refuses it.
        result, commands, markers = self.run_drill(marker='during_restore', DESTROY_EXIT='1')
        self.assertEqual(result.returncode, 1, result.stderr)
        saved = json.loads(markers['latest_result.json'])
        self.assertEqual((saved['passed'], saved['gave_way_to']), (False, WAITING_RUN))
        self.assertIn('attempt_dir', saved)
        self.assertEqual([c[-1] for c in commands if c[0] == 'ssh' and 'wg' in c][-1], 'remove')


class ScheduledServerSettingsComparison(unittest.TestCase):
    def run_job(self, job_name='compare_every_server_with_the_repository', only_lock=False, holder='old holder line\n', **settings):
        text=(TEMPLATE/'roles/util_server/main.yml').read_text().split('      name: '+job_name+'\n',1)[1]
        body=re.search(r'      script: \|\n(.*?)      env:',text,re.S)[1]
        script='\n'.join(line[8:] for line in body.splitlines())
        if only_lock:
            script=script.split('changes=$(git status',1)[0]
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root=Path(temporary)
            (root/'systems_repository.lock').write_text(holder)
            (root/'systems_repository').mkdir()
            binary=root/'bin';binary.mkdir()
            for name in ('git','flock','mmx','date','find_the_trusted_commit_of_the_systems_repository'):
                path=binary/name;path.write_text('#!'+sys.executable+'\n'+FAKE);path.chmod(0o755)
            log=root/'commands'
            script=script.replace('/var/lib/mmhotline',str(root)).replace('/var/lib/restore_drill',str(root))
            result=subprocess.run(['bash','-c',script],cwd=root,stdin=subprocess.DEVNULL,
                                  env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],
                                       'COMMAND_LOG':str(log),'JOB_NAME':job_name,
                                       'DRILL_RESULT_PATH':str(root/'latest_result.json'),**settings},
                                  text=True,capture_output=True)
            commands=[json.loads(line) for line in log.read_text().splitlines()]
            lines=(root/'systems_repository.lock').read_text().splitlines()
            if any(c[0]=='flock' and c[-1]=='9' for c in commands):
                self.assertEqual(len(lines),1)
                self.assertTrue(lines[0].startswith(job_name+'; user mmhotline;'),lines)
            return result,commands

    def test_only_complete_unchanged_dryrun_passes(self):
        for status in ('0','1','2','3','4'):
            with self.subTest(status=status):
                result,commands=self.run_job(DRYRUN_EXIT=status)
                self.assertEqual(result.returncode,int(status),result.stderr)
                self.assertIn(['mmx','dryrun','every_server','--non-interactive'],commands)
                # MMHotline's check takes the lock itself, so the job asks before taking the lock.
                self.assertLess(next(i for i,c in enumerate(commands) if c[0]=='find_the_trusted_commit_of_the_systems_repository'),next(i for i,c in enumerate(commands) if c[0]=='flock' and c[-1]=='9'))

    def test_all_three_timers_show_named_or_empty_holders(self):
        for job in ('compare_every_server_with_the_repository','weekly_database_restore_drill','check_for_a_leftover_restore01'):
            for holder in ('mmhotline: a judged playbook run\n',''):
                with self.subTest(job=job,holder=holder):
                    result, commands=self.run_job(job_name=job,only_lock=True,holder=holder,BUSY='1')
                    self.assertEqual(result.returncode,0,result.stderr)
                    expected=holder.strip() or 'another process on util01 (no holder line)'
                    self.assertIn('waiting for the lock holder: '+expected,result.stdout)
                    # Only the lock taken for the job's own work reports the holder; the
                    # comparison and the leftover check first wait until the lock is free.
                    self.assertEqual([c for c in commands if c[0]=='flock' and '--nonblock' in c],[['flock','--nonblock','9']])
                    self.assertEqual(len([c for c in commands if c[0]=='flock']),2 if job=='weekly_database_restore_drill' else 3)

    def test_the_drill_service_exits_75_only_when_this_run_gave_way(self):
        gave_way = json.dumps({'passed':False,'started_at':'2026-11-02T00:00:00Z','gave_way_to':WAITING_RUN})
        older = json.dumps({'passed':False,'started_at':'2026-10-26T03:00:00Z','gave_way_to':WAITING_RUN})
        failed = json.dumps({'passed':False,'started_at':'2026-11-02T00:00:00Z','attempt_dir':'/var/lib/restore_drill/attempt.x'})
        # 2026-11-12 on real servers: a drill that gave way but failed its cleanup exited 75.
        gave_way_and_failed = json.dumps({'passed':False,'started_at':'2026-11-02T00:00:00Z','gave_way_to':WAITING_RUN,
                                          'attempt_dir':'/var/lib/restore_drill/attempt.x'})
        for drill_exit,saved,expected in (('1',gave_way,75),('1',older,1),('1',failed,1),('1',gave_way_and_failed,1),('0','',0)):
            with self.subTest(saved=saved):
                result,commands=self.run_job(job_name='weekly_database_restore_drill',DRILL_EXIT=drill_exit,DRILL_RESULT=saved)
                self.assertEqual(result.returncode,expected,result.stderr)
                self.assertIn(['mmx','run','weekly_database_restore_drill','--non-interactive'],commands)
                if expected==75:
                    self.assertIn('the restore drill gave way to: '+WAITING_RUN,result.stdout)

    def test_the_drill_service_runs_again_2_hours_after_giving_way(self):
        text=(TEMPLATE/'roles/util_server/main.yml').read_text().split('drop_in: 10-run-again-after-giving-way.conf\n',1)[1]
        self.assertIn('        [Service]\n        RestartForceExitStatus=75\n        RestartSec=2h\n',text.split('  - id:',1)[0])

    def run_leftover_check(self, **settings):
        # The job script of check_for_a_leftover_restore01, with a provider script
        # that answers from PROVIDER_SERVER_NAMES and an inventory from INVENTORY_NODE_NAMES.
        text=(TEMPLATE/'roles/util_server/main.yml').read_text().split('      name: check_for_a_leftover_restore01\n',1)[1]
        body=re.search(r'      script: \|\n(.*?)      env:',text,re.S)[1]
        script='\n'.join(line[8:] for line in body.splitlines())
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root=Path(temporary)
            (root/'systems_repository.lock').write_text('')
            repository=root/'systems_repository';(repository/'server_management_scripts').mkdir(parents=True)
            binary=root/'bin';binary.mkdir()
            for path in [binary/n for n in ('git','flock','mmx','date','find_the_trusted_commit_of_the_systems_repository')]+[repository/'server_management_scripts/list_the_servers_at_the_provider']:
                path.write_text('#!'+sys.executable+'\n'+FAKE);path.chmod(0o755)
            shutil.copy2(TEMPLATE/'server_management_scripts/steps_for_reading_the_providers_list.bash',repository/'server_management_scripts')
            log=root/'commands'
            return subprocess.run(['bash','-c',script.replace('/var/lib/mmhotline',str(root))],cwd=root,
                                  env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],'COMMAND_LOG':str(log),
                                       'JOB_NAME':'check_for_a_leftover_restore01','UTIL01_PUBLIC_IPV4_ADDRESS':'203.0.113.1',**settings},
                                  text=True,capture_output=True,stdin=subprocess.DEVNULL)

    def test_every_server_at_the_provider_must_be_in_the_inventory(self):
        ok=self.run_leftover_check(PROVIDER_SERVER_NAMES='util01,db01,app001',INVENTORY_NODE_NAMES='util01,db01,app001,desk01')
        self.assertEqual(ok.returncode,0,ok.stderr)
        for provider,inventory,missing in (('util01,db01,db02','util01,db01','db02'),('util01,app001','util01','app001')):
            with self.subTest(missing=missing):
                result=self.run_leftover_check(PROVIDER_SERVER_NAMES=provider,INVENTORY_NODE_NAMES=inventory)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('not in the inventory: '+missing,result.stderr)

    def test_a_list_without_util01_is_not_believed(self):
        # 2026-11-12 at a real provider: a list script's filter matched no
        # server, and an empty list looks like "no leftover restore01".
        result=self.run_leftover_check(LEFTOVER='yes',LIST_WITHOUT_UTIL01='yes',INVENTORY_NODE_NAMES='util01,db01,app001')
        self.assertNotEqual(result.returncode,0)
        self.assertIn("the provider's list does not hold util01",result.stderr)
        result=self.run_leftover_check(PROVIDER_SERVER_NAMES='db01,app001',LIST_WITHOUT_UTIL01='yes',INVENTORY_NODE_NAMES='util01,db01,app001')
        self.assertNotEqual(result.returncode,0)
        self.assertIn("the provider's list does not hold util01",result.stderr)

    def test_a_job_runs_nothing_without_a_trusted_commit(self):
        for settings in ({'TRUSTED_COMMIT_EXIT':'1'},{'TRUSTED_COMMIT_EXIT':'2'},{'MERGE_BASE_EXIT':'1'}):
            with self.subTest(settings=settings):
                result,commands=self.run_job(**settings)
                self.assertEqual(result.returncode,0 if settings.get('TRUSTED_COMMIT_EXIT')=='2' else 1,result.stderr)
                self.assertFalse(any(c[0]=='mmx' for c in commands))
                # Without a trusted commit the job never takes the lock.
                self.assertEqual(any(c[0]=='flock' and c[-1]=='9' for c in commands),'MERGE_BASE_EXIT' in settings)

if __name__ == '__main__':
    unittest.main()
