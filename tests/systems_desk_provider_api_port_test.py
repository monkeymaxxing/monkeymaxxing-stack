#!/usr/bin/env python3
"""The API proxy serves 127.0.0.1:8081 (provider-api-proxy.service) and
127.0.0.1:8082 (cloudflare-api-proxy.service) on a systems desk, each once
its own token file exists, for every value of
systems_desk_provider_api_authentication; no nginx is installed.

  MMX_BINARY=/path/to/mmx python3 tests/systems_desk_provider_api_port_test.py

Reads `mmx explain systems_desk` on a copy of the template with each value of
the setting, and runs the rendered port check with stand-in ss, systemctl and
sleep programs, with its files in a temporary directory.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
SETTING = '  systems_desk_provider_api_authentication: token_in_a_header\n'
# The setting's values where the proxy signs the requests, one per provider
# whose API needs more than a token in a header.
SIGNING_VALUES = ('ovhcloud_signed_requests', 'aws_signed_requests', 'google_cloud_service_account_tokens')


class SystemsDeskProviderApiPort(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test with the actual MMX explain output.')
        cls.explained = {value: cls.explain(value) for value in ('token_in_a_header',) + SIGNING_VALUES}

    @classmethod
    def explain(cls, value):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            template_values.fill_the_values_the_setup_fills(root)
            settings = root/'mmx_project_settings.yml'
            text = settings.read_text()
            assert SETTING in text
            settings.write_text(text.replace(SETTING, '  systems_desk_provider_api_authentication: %s\n' % value))
            explained = subprocess.run([cls.mmx, 'explain', 'systems_desk', '--var', 'desk_name=desk01', '--json'],
                                       cwd=root, text=True, capture_output=True)
            assert explained.returncode == 0, explained.stderr
        return [task for stage in json.loads(explained.stdout)['fleet_stages'] for task in stage['node_tasks']]

    def order(self, value):
        return [task['path'].rsplit('/', 1)[-1] for task in self.explained[value]]

    def task(self, value, name):
        return next(task for task in self.explained[value] if task['path'].endswith('/' + name))

    def test_no_nginx_stays_on_the_desk_and_the_proxy_starts_after_the_files_are_protected(self):
        """The desk role purges nginx, which earlier desks ran, before the
        proxy starts, so nginx lets go of 8081 and 8082 first; each service
        stays stopped while its own file is missing, starts when it exists, and
        the port check comes last. The order is the same for every value; the
        conditions pick the tasks."""
        for value in self.explained:
            with self.subTest(value=value):
                order = self.order(value)
                position = order.index
                nginx_tasks = [name for name in order if 'nginx' in name]
                self.assertEqual(nginx_tasks, ['remove_nginx_which_the_api_proxy_replaced', 'delete_the_nginx_settings_file_the_earlier_role_wrote',
                                               'delete_the_empty_nginx_directories'])
                self.assertLess(position('stop_the_earlier_provider_api_signing_proxy_service'),
                                position('install_the_provider_api_proxy_service'))
                self.assertLess(position('remove_nginx_which_the_api_proxy_replaced'),
                                position('install_the_provider_api_proxy_service'))
                for service in ('provider', 'cloudflare'):
                    self.assertLess(position('protect_cloudflare_api_token_conf'),
                                    position('start_the_%s_api_proxy_when_its_file_is_ready' % service))
                    self.assertLess(position('keep_the_%s_api_proxy_stopped_until_its_file_is_ready' % service),
                                    position('start_the_%s_api_proxy_when_its_file_is_ready' % service))
                    self.assertLess(position('start_the_%s_api_proxy_when_its_file_is_ready' % service),
                                    position('check_which_program_serves_the_api_ports'))
                # A desk from the one-service release frees port 8082 (the
                # provider unit's restart) before the Cloudflare service starts.
                self.assertLess(position('restart_a_running_provider_api_proxy'), position('start_the_cloudflare_api_proxy_when_its_file_is_ready'))

    def test_nginx_is_removed_with_its_settings_and_never_installed(self):
        task = self.task('token_in_a_header', 'remove_nginx_which_the_api_proxy_replaced')
        fields = {argument['field']: argument['value'] for argument in task['arguments']}
        self.assertEqual(fields['apt_package.state'], 'absent')
        self.assertEqual(fields['apt_package.also_delete_its_config_files'], True)
        order = self.order('token_in_a_header')
        self.assertLess(order.index('remove_nginx_which_the_api_proxy_replaced'), order.index('delete_the_nginx_settings_file_the_earlier_role_wrote'))
        self.assertLess(order.index('delete_the_nginx_settings_file_the_earlier_role_wrote'), order.index('delete_the_empty_nginx_directories'))
        packages = [argument['value'] for argument in self.task('token_in_a_header', 'install_the_desk_packages')['arguments']]
        self.assertNotIn('nginx', json.dumps(packages))
        self.assertFalse((T/'roles/systems_desk/files/nginx.conf').exists())

    def test_each_unit_serves_one_port_from_its_own_files_only(self):
        provider = (T/'roles/systems_desk/files/provider-api-proxy.service').read_text()
        cloudflare = (T/'roles/systems_desk/files/cloudflare-api-proxy.service').read_text()
        self.assertIn('provider-api-token:/etc/systems-desk/provider-api-token.conf', provider)
        self.assertIn('provider-api-signing-credential:/etc/systems-desk/provider-api-signing-credential.json', provider)
        self.assertIn('--api server-provider --provider-api-url {{ .inputs.provider_api_url }}', provider)
        self.assertIn('127.0.0.1:8081', provider)
        self.assertNotIn('cloudflare-api-token', provider)
        self.assertNotIn('8082', provider.split('[Unit]')[1])
        self.assertEqual([line for line in cloudflare.splitlines() if line.startswith('LoadCredential=')],
                         ['LoadCredential=cloudflare-api-token:/etc/systems-desk/cloudflare-api-token.conf'])
        self.assertIn('run-the-provider-api-proxy --api cloudflare', cloudflare)
        self.assertIn('127.0.0.1:8082', cloudflare)

    def test_the_desk_keeps_only_the_credential_file_its_setting_uses(self):
        self.assertEqual(self.task('token_in_a_header', 'remove_the_api_signing_credential_when_the_provider_takes_a_token_in_a_header')['status'], 'ready')
        self.assertEqual(self.task('token_in_a_header', 'remove_the_provider_api_token_when_the_provider_signs_requests')['status'], 'skipped')
        for value in SIGNING_VALUES:
            with self.subTest(value=value):
                self.assertEqual(self.task(value, 'remove_the_api_signing_credential_when_the_provider_takes_a_token_in_a_header')['status'], 'skipped')
                self.assertEqual(self.task(value, 'remove_the_provider_api_token_when_the_provider_signs_requests')['status'], 'ready')

    def run_check(self, value, files, listeners, main_pids, nginx_running=False, nginx_conf=False):
        """Runs the rendered port check; returns (exit code, standard error)."""
        arguments = {argument['field']: argument['value'] for argument in self.task(value, 'check_which_program_serves_the_api_ports')['arguments']}
        self.assertEqual(arguments['shell.env.AUTHENTICATION'], value)
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            directory = Path(temporary)
            (directory/'etc').mkdir()
            (directory/'nginx').mkdir()
            if nginx_conf:
                (directory/'nginx'/'nginx.conf').write_text('')
            for name in files:
                (directory/'etc'/name).write_text('')
            stand_ins = {
                'ss': 'printf "%%b\\n" %s | grep -F "127.0.0.1:${2##*:} " || true' % json.dumps(listeners),
                'systemctl': '[ "$1" = is-active ] && exit %d; case "$5" in %s *) echo 0 ;; esac' % (0 if nginx_running else 3, ''.join('%s.service) echo %s ;; ' % item for item in main_pids.items())),
                'sleep': ':',
            }
            for name, body in stand_ins.items():
                (directory/name).write_text('#!/bin/bash\n%s\n' % body)
                (directory/name).chmod(0o755)
            script = arguments['shell.script'].replace('/etc/systems-desk/', str(directory/'etc') + '/').replace('/etc/nginx/', str(directory/'nginx') + '/')
            result = subprocess.run(['bash', '-c', script], text=True, capture_output=True, stdin=subprocess.DEVNULL,
                                    env={'PATH': '%s:/usr/bin:/bin' % directory, 'AUTHENTICATION': value})
        return result.returncode, result.stderr

    ON_8081 = 'LISTEN 0 4096 127.0.0.1:8081 0.0.0.0:* users:(("set-up-outside-",pid=5100,fd=3))'
    ON_8082 = 'LISTEN 0 4096 127.0.0.1:8082 0.0.0.0:* users:(("set-up-outside-",pid=5200,fd=4))'
    BOTH = ON_8081 + '\n' + ON_8082
    PIDS = {'provider-api-proxy': 5100, 'cloudflare-api-proxy': 5200}
    TOKENS = ['cloudflare-api-token.conf', 'provider-api-token.conf']
    CREDENTIAL = ['cloudflare-api-token.conf', 'provider-api-signing-credential.json']

    def test_each_service_on_its_own_port_passes_for_every_setting(self):
        self.assertEqual(self.run_check('token_in_a_header', self.TOKENS, self.BOTH, self.PIDS), (0, ''))
        self.assertEqual(self.run_check('ovhcloud_signed_requests', self.CREDENTIAL, self.BOTH, self.PIDS), (0, ''))

    def test_the_provider_port_passes_alone_before_the_cloudflare_token_exists(self):
        """The setup creates servers through 8081 before the Cloudflare token exists."""
        self.assertEqual(self.run_check('token_in_a_header', ['provider-api-token.conf'], self.ON_8081, self.PIDS), (0, ''))

    def test_a_port_without_its_service_fails_the_run(self):
        for listeners, shown, wanted in ((self.ON_8081, '127.0.0.1:8082', 'cloudflare-api-proxy.service'),
                                         (self.ON_8082, '127.0.0.1:8081', 'provider-api-proxy.service'),
                                         ('', 'the programs there are: none', 'provider-api-proxy.service'),
                                         (self.ON_8081 + '\nLISTEN 0 511 127.0.0.1:8082 0.0.0.0:* users:(("old-program",pid=4020,fd=6))',
                                          'old-program', 'cloudflare-api-proxy.service')):
            with self.subTest(listeners=listeners):
                code, error = self.run_check('token_in_a_header', self.TOKENS, listeners, self.PIDS)
                self.assertEqual(code, 1)
                self.assertIn('should be served by %s (systems_desk_provider_api_authentication is token_in_a_header)' % wanted, error)
                self.assertIn(shown, error)

    def test_no_program_is_expected_on_a_port_while_its_file_is_missing(self):
        for value, files, fine, port in (('token_in_a_header', ['cloudflare-api-token.conf'], self.ON_8082, '8081'),
                                         ('ovhcloud_signed_requests', ['provider-api-signing-credential.json'], self.ON_8081, '8082'),
                                         ('token_in_a_header', [], '', '8081')):
            with self.subTest(value=value, files=files):
                self.assertEqual(self.run_check(value, files, fine, self.PIDS), (0, ''))
                code, error = self.run_check(value, files, self.BOTH, self.PIDS)
                self.assertEqual(code, 1)
                self.assertIn('should have no program yet', error)
                self.assertIn('127.0.0.1:%s' % port, error)

    def test_a_running_nginx_or_its_settings_file_fails_the_run_even_beside_the_proxy(self):
        for value, files in (('token_in_a_header', self.TOKENS), ('ovhcloud_signed_requests', self.CREDENTIAL)):
            for case in ({'nginx_running': True}, {'nginx_conf': True}):
                with self.subTest(value=value, case=case):
                    code, error = self.run_check(value, files, self.BOTH, self.PIDS, **case)
                    self.assertEqual(code, 1)
                    self.assertIn('nginx is still on this desk', error)
                    self.assertIn('remove_nginx_which_the_api_proxy_replaced', error)


if __name__ == '__main__':
    unittest.main()
