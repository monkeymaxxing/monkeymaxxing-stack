#!/usr/bin/env python3
"""Checks for the invariants review: names that must be unique, the restore message, the live-port check."""
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'


def script_after(path, marker, key='script'):
    """The shell text of the first `key: |` block that follows marker in a template file, dedented."""
    text = (TEMPLATE / path).read_text().split(marker, 1)[1]
    match = re.search(r'^( *)' + key + r': \|\n((?:\1 +.*\n|\n)+)', text, re.M)
    indent = len(match[1]) + 2
    return '\n'.join(line[indent:] for line in match[2].splitlines())


class UniqueNamesAndAddresses(unittest.TestCase):
    """validate_that_apps_and_servers_are_not_listed_twice, in playbooks/every_server.yml."""

    def run_stage(self, apps, nodes):
        marker = 'no_two_apps_share_a_database_name_and_no_two_servers_share_an_address_or_key'
        text = (TEMPLATE / 'playbooks/every_server.yml').read_text().split(marker, 1)[1]
        script = re.search(r'^ *script: (.*)$', text, re.M)[1]
        self.assertEqual(re.search(r'^ *dryrun: (.*)$', text, re.M)[1], script)
        env = dict(os.environ, APPS=json.dumps(apps), INVENTORY_NODES=json.dumps(nodes),
                   PROGRAM=script_after('playbooks/every_server.yml', marker, 'PROGRAM'))
        return subprocess.run(['bash', '-c', script], env=env, text=True, capture_output=True)

    def nodes(self, **overrides):
        base = {'util01': {'vars': {'private_ip': '10.20.0.1', 'wireguard_public_key': 'key-util'}},
                'app001': {'vars': {'private_ip': '10.20.1.1', 'wireguard_public_key': 'key-app'}},
                'desk01': {'vars': {'private_ip': '10.20.9.1'}}, 'restore': {'vars': {}}}
        for name, values in overrides.items():
            base[name] = {'vars': values}
        return base

    def test_different_names_pass(self):
        result = self.run_stage({'shop': {'database_name': 'shop'}, 'blog': {'database_name': 'blog'}}, self.nodes())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_two_apps_with_one_database_name_are_refused(self):
        result = self.run_stage({'shop': {'database_name': 'shop'}, 'blog': {'database_name': 'shop'}}, self.nodes())
        self.assertEqual(result.returncode, 1)
        self.assertIn('database_name shop is used by shop and blog', result.stderr)
        self.assertIn('Nothing changed.', result.stderr)

    def test_two_servers_with_one_address_or_key_are_refused(self):
        apps = {'shop': {'database_name': 'shop'}}
        result = self.run_stage(apps, self.nodes(app002={'private_ip': '10.20.1.1', 'wireguard_public_key': 'key-app2'}))
        self.assertEqual(result.returncode, 1)
        self.assertIn('private_ip 10.20.1.1 is used by app001 and app002', result.stderr)
        result = self.run_stage(apps, self.nodes(app002={'private_ip': '10.20.1.2', 'wireguard_public_key': 'key-app'}))
        self.assertEqual(result.returncode, 1)
        self.assertIn('wireguard_public_key key-app is used by app001 and app002', result.stderr)


class RestoreOfMMHotlineData(unittest.TestCase):
    """The restore task says whether the backup held a copy (rebuild_the_utility_server_util01.md)."""

    def run_restore(self, backup_holds_a_copy, database_exists_before=False):
        script = script_after('playbooks/every_server.yml', 'id: restore_the_mmhotline_database_from_its_backup')
        script = script.replace('/usr/local/bin/litestream', './litestream').replace('/var/lib/mmhotline', '.')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            fake = Path(temporary) / 'litestream'
            fake.write_text('#!/bin/sh\n' + ('echo data > ./mmhotline.db\n' if backup_holds_a_copy else 'echo "no matching backups found" >&2\n'))
            fake.chmod(0o755)
            return subprocess.run(['bash', '-c', script], cwd=temporary, text=True, capture_output=True,
                                  env=dict(os.environ, MMHOTLINE_BACKUP_REPLICA_URL='s3://bucket/folder'))

    def test_a_restored_database_is_reported(self):
        result = self.run_restore(True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'restored mmhotline.db from the backup at s3://bucket/folder\n')

    def test_the_line_is_shown_although_the_task_reads_the_backups_keys(self):
        # Seen on test servers: MMX showed the line as [redacted],
        # because the task's env holds secrets, and the rebuild page tells the
        # person to read it.
        task = (TEMPLATE/'playbooks/every_server.yml').read_text().split('id: restore_the_mmhotline_database_from_its_backup', 1)[1]
        task = task.split('\n      - id: ', 1)[0]
        self.assertIn('{{ .secrets.', task)
        self.assertIn('\n          output_holds_no_secret: true\n', task)

    def test_an_empty_backup_is_reported_as_an_empty_start(self):
        result = self.run_restore(False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'the backup at s3://bucket/folder holds no copy of mmhotline.db: MMHotline will start with an empty database\n')


class LivePortStillTheOneTheRunStartedWith(unittest.TestCase):
    """check_that_the_live_web_port_is_still_the_one_the_run_started_with, in roles/app_server/main.yml."""

    def run_check(self, recorded, expected, dryrun=False):
        script = script_after('roles/app_server/main.yml', 'id: check_that_the_live_web_port_is_still_the_one_the_run_started_with', 'dryrun' if dryrun else 'script')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            script = script.replace('/var/lib/monkeymaxxing-stack/live_web_ports', temporary)
            if recorded is not None:
                (Path(temporary) / 'shop').write_text(recorded)
            return subprocess.run(['bash', '-c', script], text=True, capture_output=True,
                                  env=dict(os.environ, APP_NAME='shop', EXPECTED_PORT=expected))

    def test_the_same_port_or_no_file_passes(self):
        for dryrun in (False, True):
            self.assertEqual(self.run_check('8001\n', '8001', dryrun).returncode, 0)
            self.assertEqual(self.run_check(None, '8001', dryrun).returncode, 0)

    def test_a_deploy_that_switched_the_port_stops_the_run_before_it_changes_anything(self):
        result = self.run_check('8002\n', '8001')
        self.assertEqual(result.returncode, 1)
        self.assertIn('the live port of shop changed during this run: 8002 now, 8001 when the run started', result.stderr)
        self.assertNotEqual(self.run_check('8002\n', '8001', True).returncode, 0)

    def test_the_check_comes_before_any_change_in_the_role(self):
        role = (TEMPLATE / 'roles/app_server/main.yml').read_text()
        check = role.index('id: check_that_the_live_web_port_is_still_the_one_the_run_started_with')
        for later in ('id: install_podman_and_curl', 'id: settings_and_secrets_of_each_app', 'id: live_web_container_of_each_app',
                      'id: stop_the_old_web_container_of_each_app', 'id: remove_a_new_web_container_that_a_stopped_deploy_left',
                      'id: record_the_live_web_port_of_each_app'):
            self.assertLess(check, role.index(later), later)


class ChecklistAndReview(unittest.TestCase):
    def test_the_vault_checklist_item_is_verified_again_every_week(self):
        text = (TEMPLATE / 'monkeymaxxing_stack_checklist.yml').read_text()
        item = text.split('- id: secrets_in_the_vault_scoped_by_role', 1)[1].split('\n  - id: ', 1)[0]
        self.assertIn('verify_again_every: 7d', item)

    def test_the_weekly_review_scans_the_weeks_commits_for_secrets(self):
        text = (TEMPLATE / 'operating_procedures/do_the_weekly_system_review.md').read_text()
        self.assertIn('Scan the week\'s commits for a secret in clear text', text)
        # The desk installs Debian's gitleaks 8.16 (roles/systems_desk/main.yml),
        # which has `detect` and refuses `git`, a subcommand of 8.19.
        self.assertIn('gitleaks detect --redact --verbose --log-opts="--since=7.days"', text)
        self.assertNotIn('gitleaks git', text)


class DryrunOfAProgramTheSameRunInstalls(unittest.TestCase):
    """A dryrun on a new server has not installed the program its stage installs.

    The 2026-11-12 real-system dryrun before app002's and staging01's first
    run ended "failed" (exit 1): find_the_live_and_new_web_ports had a
    changed_when that read its stdout as JSON, and the program was not there
    yet. A shell task whose dryrun runs a program that a file task of the
    same playbook installs must be a check (changed_when: false), so MMX
    reports it not_checked after the install would change the server.
    """

    def test_such_a_task_is_a_check(self):
        tasks_checked = 0
        for playbook in sorted((TEMPLATE / 'playbooks').glob('*.yml')):
            text = playbook.read_text()
            installed = set(re.findall(r'^\s+file:\n\s+path: (/\S+)\n', text, re.M))
            lines = text.splitlines()
            for number, line in enumerate(lines):
                found = re.match(r'^\s+dryrun: (/\S+)', line)
                if not found or found[1] not in installed:
                    continue
                start = max(i for i in range(number) if re.match(r'^\s*- id: ', lines[i]))
                indent = len(lines[start]) - len(lines[start].lstrip())
                end = next((i for i in range(number + 1, len(lines))
                            if re.match(r'^\s*- ', lines[i]) and len(lines[i]) - len(lines[i].lstrip()) <= indent),
                           len(lines))
                task = '\n'.join(lines[start:end])
                tasks_checked += 1
                self.assertIn('changed_when: false', task, f'{playbook.name}:{start + 1}')
        self.assertGreaterEqual(tasks_checked, 6)


class ProgramsAreInstalledBeforeTheirFirstUse(unittest.TestCase):
    """every_server installs jq and Python 3 before any task runs them.

    The 2026-11-12 run at a real provider failed on a fresh Debian 13
    util01 at count_the_root_ssh_public_keys_that_are_the_triage_key,
    "jq: command not found": the checks of the first stages ran jq, and only
    the every_server role installed it, later in the run.
    """

    def test_jq_and_python3_are_installed_on_every_server_before_their_first_use(self):
        text = (TEMPLATE / 'playbooks/every_server.yml').read_text()
        stages = re.split(r'^  - id: ', text.split('\nfleet_stages:\n', 1)[1], flags=re.M)[1:]
        # A stage's text with the text of each role it calls.
        stages = [stage + ''.join((TEMPLATE / 'roles' / role / 'main.yml').read_text()
                                  for role in re.findall(r'role: (\w+)', stage)) for stage in stages]
        uses = {'jq': r'(?<![\w-])jq -', 'python3': r'(?<![\w-])python3 -'}
        for program, use in uses.items():
            first_use = next(index for index, stage in enumerate(stages) if re.search(use, stage))
            installs = [index for index, stage in enumerate(stages) if '{name: ' + program + ',' in stage]
            self.assertTrue(installs and installs[0] < first_use,
                            f'{program} is first used in stage {stages[first_use].split()[0]}, before it is installed')
            self.assertRegex(stages[installs[0]], r'\n    nodes: all\n', f'{program} must be installed on every server')


    def test_a_stage_list_with_util_server_also_names_the_install_stage(self):
        """util_server runs jq, and a fresh server has none: chapter 7's first run must install it.

        The 2026-11-13 end-to-end run failed at a provider whose image has no
        jq, because chapter 7's run 1 listed util_server without
        install_jq_and_python3.
        """
        lists = 0
        for path in TEMPLATE.rglob('*.md'):
            for stages in re.findall(r'--only-fleet-stages ([a-z0-9_,]+)', path.read_text()):
                if 'util_server' in stages.split(','):
                    lists += 1
                    self.assertIn('install_jq_and_python3', stages.split(','), f'{path.name}: {stages}')
        self.assertGreaterEqual(lists, 1)


class ServicesOnAWireGuardAddressStartAfterWireGuard(unittest.TestCase):
    """A service that binds the server's WireGuard address starts after wg0 at boot.

    On 2026-11-12 a real util01's MMWatchdog hub started before wg0 after
    each reboot: "listen tcp 10.20.0.1:8445: bind: cannot assign requested
    address", and systemd started it again 4 seconds later.
    """

    def test_each_such_unit_has_the_drop_in(self):
        for path, unit in (('roles/util_server/main.yml', 'mmwatchdog.service'),
                           ('roles/util_server/main.yml', 'pgautofailover.service'),
                           ('playbooks/every_server.yml', 'mmhotline.service'),
                           ('roles/database_server/main.yml', 'pgautofailover.service'),
                           ('roles/pgbouncer/main.yml', 'pgbouncer.service')):
            with self.subTest(unit=unit, path=path):
                self.assertRegex((TEMPLATE / path).read_text(),
                                 r'name: ' + re.escape(unit) + r'\n\s+drop_in: [\w.-]+\n\s+content: \|\n(?:.*\n){1,3}?'
                                 r'\s+After=wg-quick@wg0\.service\n\s+Wants=wg-quick@wg0\.service\n')


class WireGuardListensAbove1024AndTheRedirectComesFirst(unittest.TestCase):
    """WireGuard's own port is above 1024, and UDP 443 reaches it through a redirect.

    On Ubuntu 26.04 AppArmor confines wg-quick, and its ip profile lacks
    capability net_bind_service: ListenPort = 443 fails with "Could not
    create IPv4 socket". Existing systems must get the redirect and the
    firewall rule before wg0 changes its port, or a peer that keeps sending
    to UDP 443 meets a closed port.
    """

    def test_no_wg_quick_file_or_template_listens_below_1024(self):
        found = 0
        for path in TEMPLATE.rglob('*'):
            if not path.is_file():
                continue
            try:
                text = path.read_text()
            except UnicodeDecodeError:
                continue
            for port in re.findall(r'ListenPort = (\d+|\{\{ \.inputs\.wireguard_listen_port \}\}|%s)', text):
                found += 1
                if port.isdigit():
                    self.assertGreaterEqual(int(port), 1024, f'{path.relative_to(TEMPLATE)} listens on {port}')
                else:
                    self.assertIn(port, ('{{ .inputs.wireguard_listen_port }}', '%s'), f'{path.relative_to(TEMPLATE)}')
        self.assertGreaterEqual(found, 4)
        port = re.search(r'^  wireguard_listen_port: (\d+)', (TEMPLATE / 'inventories/servers.yml').read_text(), re.M)
        self.assertGreaterEqual(int(port[1]), 1024)

    def test_every_server_and_the_desk_apply_the_redirect_and_the_firewall_before_the_wireguard_task(self):
        for role, firewall in (('every_server', 'id: firewall\n'), ('systems_desk', 'id: desk_firewall\n')):
            with self.subTest(role=role):
                text = (TEMPLATE / 'roles' / role / 'main.yml').read_text()
                redirect = text.index('id: wireguard_udp_443_redirect\n')
                admit = text.index(firewall)
                wireguard = text.index('id: join_the_wireguard_network\n')
                self.assertLess(redirect, wireguard)
                self.assertLess(text.index('drop_in: forget_udp_443_flows_after_a_port_change.conf'), wireguard)
                self.assertLess(admit, wireguard)

    def test_first_boot_writes_the_shared_redirect_and_starts_it_before_wg_quick(self):
        cloud = (TEMPLATE / 'server_management_scripts/server_first_boot.cloud-config.yml').read_text()
        def body(text):  # the text after the template comment header
            return text.split('*/ -}}\n', 1)[-1].strip()
        def indented(text):
            return '\n'.join(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(('#', '{{')))
        nft = (TEMPLATE / 'files_used_by_several_roles/wireguard_udp_443_redirect.nft').read_text().replace('{{ .inputs.wireguard_listen_port }}', '@@WIREGUARD_LISTEN_PORT@@')
        unit = (TEMPLATE / 'files_used_by_several_roles/wireguard_udp_443_redirect.service').read_text()
        self.assertIn(indented(body(nft)), indented(cloud))
        self.assertIn(indented(body(unit)), indented(cloud))
        self.assertLess(cloud.index('enable --now wireguard-udp-443-redirect.service'), cloud.index('enable --now wg-quick@wg0'))
        self.assertLess(cloud.index('ufw allow @@WIREGUARD_LISTEN_PORT@@/udp'), cloud.index('enable --now wg-quick@wg0'))


if __name__ == '__main__':
    unittest.main()
