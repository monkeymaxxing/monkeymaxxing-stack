#!/usr/bin/env python3
"""Render the phone-code lockout settings and the go-live public checks with MMX.

  MMX_BINARY=/path/to/mmx python3 tests/phone_code_lockout_test.py

It proves the project settings reach fail2ban's jail, the desk's first-login
text, and the MMWatchdog alert severities, that a bad value gives a clear
error, and that the public-address (sos) checks exist only after go-live.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
GOOD = dict(wrong_codes_before_lockout=5, lockout_minutes=5, alert_severity_when_a_laptop_is_locked_out='warn')


class Rendered(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def render_result(self, filename, **values):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001': {'address': '127.0.0.1'}})))
            (root/'source.template').write_text((T/filename).read_text().replace('.inputs', '.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]

    def render(self, filename, **values):
        rendered = self.render_result(filename, **values)
        self.assertIn('text', rendered, rendered)
        return rendered['text']

    def lockout(self, **changes):
        return dict(phone_code_lockout=dict(GOOD, **changes), person_unix_username='alex')

    def test_the_jail_uses_the_settings(self):
        jail = self.render('roles/systems_desk/files/phone_code_jail.conf', **self.lockout())
        self.assertIn('maxretry = 5\n', jail)
        self.assertIn('bantime = 300\n', jail)
        jail = self.render('roles/systems_desk/files/phone_code_jail.conf',
                           **self.lockout(wrong_codes_before_lockout=3, lockout_minutes=60))
        self.assertIn('maxretry = 3\n', jail)
        self.assertIn('bantime = 3600\n', jail)

    def test_a_role_input_arrives_as_a_decimal_number(self):
        # MMX passes role inputs as JSON, so a whole number can arrive as 5.0, which Go reads as a float.
        # A run on a real server failed on exactly this.
        for rendered in (self.render_text_of_a_float(),):
            self.assertIn('maxretry = 5\n', rendered)
            self.assertIn('bantime = 300\n', rendered)

    def render_text_of_a_float(self):
        values = self.lockout(wrong_codes_before_lockout=5.0, lockout_minutes=5.0)
        return self.render('roles/systems_desk/files/phone_code_jail.conf', **values)

    def test_bad_values_stop_with_a_clear_error(self):
        for changes, words in [(dict(wrong_codes_before_lockout=0), 'wrong_codes_before_lockout is 0'),
                               (dict(wrong_codes_before_lockout='five'), 'wrong_codes_before_lockout is five'),
                               (dict(lockout_minutes=0), 'lockout_minutes is 0'),
                               (dict(lockout_minutes=-5), 'lockout_minutes is -5'),
                               (dict(lockout_minutes=2.5), 'lockout_minutes is 2.5'),
                               (dict(alert_severity_when_a_laptop_is_locked_out='page'), 'is page. Use info, warn, or sos')]:
            with self.subTest(changes=changes):
                rendered = self.render_result('roles/systems_desk/files/phone_code_jail.conf', **self.lockout(**changes))
                self.assertNotIn('text', rendered)
                self.assertIn(words, rendered['not_rendered_because'])
        rendered = self.render_result('mmwatchdog_checks/systems_desks.yml',
                                      **self.lockout(alert_severity_when_a_laptop_is_locked_out='page'))
        self.assertIn('Use info, warn, or sos', rendered['not_rendered_because'])

    def test_one_wrong_code_is_info_and_the_lockout_has_the_chosen_severity(self):
        for severity in ('info', 'warn', 'sos'):
            checks = self.render('mmwatchdog_checks/systems_desks.yml',
                                 **self.lockout(alert_severity_when_a_laptop_is_locked_out=severity))
            first, rest = checks.split('phone_code_lockouts:')
            self.assertIn('alert_severity: info', first)
            self.assertNotIn('alert_severity: warn', first)
            lockout_group = rest.split('phone_code_file:')[0]
            self.assertIn(r'\[systems-desk-phone-code\] Ban', lockout_group)
            # fail2ban logs bans to this file; its journal holds only start-up lines (seen on a real server).
            self.assertIn('log_file_path: /var/log/fail2ban.log', lockout_group)
            self.assertIn(f'alert_severity: {severity}\n', lockout_group)

    def test_a_wrong_code_counts_for_the_person_and_for_coding_agent(self):
        # coding-agent logs in with the same laptop key and phone code, so a
        # thief with the laptop guesses as either account; both count.
        import re
        values = self.lockout()
        filter_line = [line for line in self.render('roles/systems_desk/files/phone_code_filter.conf', **values).splitlines()
                       if line.startswith('failregex = ')][0]
        # fail2ban's prefix is the journal's own; the rest is the message.
        message = filter_line.split('%(__prefix_line)s', 1)[1].replace('<HOST>', r'(?P<host>\S+)')
        watchdog = re.search(r"fail_when_a_new_line_matches_regex: '(.*Authentication failure.*)'",
                             self.render('mmwatchdog_checks/systems_desks.yml', **values)).group(1)
        for user, counted in (('alex', True), ('coding-agent', True), ('alexander', False), ('root', False)):
            line = 'error: PAM: Authentication failure for %s from 10.20.10.1' % user
            with self.subTest(user=user):
                self.assertEqual(bool(re.match('^' + message, line)), counted)
                self.assertEqual(bool(re.match(watchdog, line)), counted)
                if counted:
                    self.assertEqual(re.match('^' + message, line).group('host'), '10.20.10.1')

    def test_the_desk_checks_alert_while_the_desk_is_not_locked(self):
        checks = self.render('mmwatchdog_checks/systems_desks.yml', **self.lockout())
        lock = checks.split('\n  desk_lock:\n', 1)[1]
        self.assertIn('      the_desk_is_locked:\n        file:\n          path: /etc/systems-desk/locked\n'
                      '        alert_severity: warn\n', lock)
        self.assertIn('      root_login_from_a_laptop_is_closed:\n        file:\n'
                      '          path: /etc/ssh/sshd_config.d/00-systems-desk-root-login-before-the-lock.conf\n'
                      '          must_not_exist: true\n        alert_severity: warn\n', lock)

    def test_first_login_says_the_lockout_once(self):
        script = self.render('roles/systems_desk/files/set-up-the-phone-code', **self.lockout(lockout_minutes=7))
        self.assertEqual(script.count('lock that laptop out'), 1)
        self.assertIn("'5' '7'", script)

    def test_new_emergency_codes_keep_the_phones_secret(self):
        # make-a-new-recovery-bundle needs emergency codes for the new bundle
        # without a new scan: only the code lines change, and the old codes stop working.
        import re
        import stat
        script = self.render('roles/systems_desk/files/set-up-the-phone-code', **self.lockout())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'bin').mkdir()
            (root/'bin/id').write_text('#!/bin/sh\necho 0\n')
            # install as the desk's GNU install runs it here: -o U -g G -m MODE /dev/stdin PATH.
            (root/'bin/install').write_text('#!/bin/sh\nwhile [ "$#" -gt 2 ]; do case $1 in -m) mode=$2; shift;; esac; shift; done\n'
                                            'cat "$1" > "$2" && chmod "$mode" "$2"\n')
            for stub in ('id', 'install'):
                (root/'bin'/stub).chmod(0o755)
            (root/'desk').mkdir()
            (root/'set-up-the-phone-code').write_text(script.replace('/etc/systems-desk', str(root/'desk')))
            code_file = root/'desk/phone-code'
            kept = 'JBSWY3DPEHPK3PXP\n" RATE_LIMIT 3 30 1700000000\n" WINDOW_SIZE 3\n" DISALLOW_REUSE 56666666\n" TOTP_AUTH\n'
            old_codes = ['11111111', '22222222', '33333333', '44444444', '55555555']
            code_file.write_text(kept + '\n'.join(old_codes) + '\n')
            environment = dict(os.environ, PATH='%s:%s' % (root/'bin', os.environ['PATH']), SUDO_UID=str(os.getuid()), SUDO_GID=str(os.getgid()))

            def run(path):
                return subprocess.run(['bash', str(root/'set-up-the-phone-code'), '--new-emergency-codes-to', str(path)],
                                      env=environment, text=True, capture_output=True)
            result = run(root/'codes')
            self.assertEqual(result.returncode, 0, result.stderr)
            new_codes = (root/'codes').read_text().split()
            self.assertEqual(len(new_codes), 5)
            self.assertTrue(all(re.fullmatch('[1-9][0-9]{7}', code) for code in new_codes), new_codes)
            self.assertFalse(set(new_codes) & set(old_codes))
            self.assertEqual(code_file.read_text(), kept + '\n'.join(new_codes) + '\n')
            self.assertEqual(stat.S_IMODE(code_file.stat().st_mode), 0o400)
            self.assertEqual(stat.S_IMODE((root/'codes').stat().st_mode), 0o600)
            self.assertIn('Your phone keeps working as before', result.stdout)
            # An existing codes file, or a desk with no phone code, changes nothing.
            self.assertEqual(run(root/'codes').returncode, 1)
            self.assertEqual(code_file.read_text(), kept + '\n'.join(new_codes) + '\n')
            code_file.unlink()
            result = run(root/'other-codes')
            self.assertEqual(result.returncode, 1)
            self.assertIn('no phone code yet', result.stderr)
            self.assertEqual(sorted(path.name for path in (root/'desk').iterdir()), [])

    def test_public_site_checks_start_only_after_go_live(self):
        apps = dict(shop=dict(health_url_path='/up'))
        names = dict(production=dict(shop='shop.example.com'))
        before = self.render('mmwatchdog_checks/util_server.yml', apps=apps, public_host_names=names,
                             public_site_checks_run=False, backups=dict(uploads_backup_runs_on=[]), stack_software={},
                            triage_agent_coding_agent='claude_code',
                            app_pool_load_settings=dict(what_the_triage_agent_may_do_without_a_person='routine_fixes'),
                            inventory_nodes={})
        self.assertNotIn('public_sites:', before)
        self.assertNotIn('alert_severity: sos', before)
        after = self.render('mmwatchdog_checks/util_server.yml', apps=apps, public_host_names=names,
                            public_site_checks_run=True, backups=dict(uploads_backup_runs_on=[]), stack_software={},
                            triage_agent_coding_agent='claude_code',
                            app_pool_load_settings=dict(what_the_triage_agent_may_do_without_a_person='routine_fixes'),
                            inventory_nodes={})
        self.assertIn('https://shop.example.com/up', after)
        self.assertIn('alert_severity: sos', after)


if __name__ == '__main__':
    unittest.main()
