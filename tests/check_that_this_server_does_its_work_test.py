#!/usr/bin/env python3
"""check-that-this-server-does-its-work checks what the reboot playbook's waits checked.

  MMX_BINARY=/path/to/mmx python3 tests/check_that_this_server_does_its_work_test.py

The command replaces the inline waits of reboot_servers_after_updates, so
it must check the same things they checked before (the pin):
- on an app server, each app's live web container answers its health URL
  at the server's private address and live web port, with Host set to the
  app's production host name and X-Forwarded-Proto https;
- where /etc/systemd/system/cloudflared.service exists, cloudflared's
  readiness URL answers, and each app answers through Caddy on 127.0.0.1,
  with production's host names, or staging's on staging01;
- on a jobs server, the job container of each app with a jobs_command runs;
- on a load-balancer server, the tunnel connector's unit exists as well,
  because forwarding is the server's whole work (a replacement by
  replace_failed_servers waits for it).
Any other server passes. Each failure is one line of output.

The test renders the role's settings file with MMX, then runs the command
with bash, jq, and stand-in curl and systemctl, its fixed paths moved into a
temporary directory. It also checks that the reboot playbook waits for the
command, and that the every_server role installs it. It needs Python 3,
bash and jq.
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
COMMAND = T/'roles/every_server/files/check-that-this-server-does-its-work'

STAND_IN_CURL = r'''#!/bin/bash
# Answers from $RESPONSES/<url>|<host>, or 000 like a connection that failed.
host="" url=""
while [ $# -gt 0 ]; do
    case "$1" in
        --header) case "$2" in Host:*) host="${2#Host: }";; esac; shift 2;;
        --output|--write-out|--max-time) shift 2;;
        --silent) shift;;
        *) url="$1"; shift;;
    esac
done
printf '%s|%s\n' "$url" "$host" >> "$RESPONSES/asked"
key=$(printf '%s|%s' "$url" "$host" | tr '/:' '__')
if [ -f "$RESPONSES/$key" ]; then cat "$RESPONSES/$key"; else printf 000; fi
'''

STAND_IN_SYSTEMCTL = r'''#!/bin/bash
# systemctl is-active --quiet UNIT: active when $RESPONSES/active/UNIT exists.
[ "$1 $2" = "is-active --quiet" ] || exit 2
[ -e "$RESPONSES/active/$3" ]
'''

APPS = {
    'shop': {'health_url_path': '/up', 'jobs_command': 'bin/jobs'},
    'blog': {'health_url_path': '/health', 'jobs_command': ''},
}
HOST_NAMES = {'production': {'shop': 'shop.example.com', 'blog': 'blog.example.com'},
              'staging': {'shop': 'shop-staging.example.com', 'blog': 'blog-staging.example.com'}}


class CheckThatThisServerDoesItsWork(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to render the actual settings template.')

    def rendered_settings(self, **flags):
        """the_work_of_this_server.json, rendered by MMX through a stand-in role with the role's input names."""
        inputs = dict(is_app_server=False, is_jobs_server=False, is_load_balancer_server=False, is_staging_server=False)
        inputs.update(flags)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'roles/r/files').mkdir(parents=True)
            shutil.copy(T/'roles/every_server/files/the_work_of_this_server.json', root/'roles/r/files/')
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers')))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={
                'app001': {'address': '127.0.0.1', 'vars': {'private_ip': '10.20.1.1'}},
                'db01': {'address': '127.0.0.2', 'vars': {'private_ip': '10.20.2.1'}}})))
            spec = {name: {'type': 'boolean', 'required': True} for name in inputs}
            spec.update(inventory_nodes={'type': 'mapping', 'required': True}, apps={'type': 'mapping', 'required': True},
                        public_host_names={'type': 'mapping', 'required': True})
            (root/'roles/r/main.yml').write_text(json.dumps(dict(inputs=spec, node_tasks=[dict(id='render', file=dict(
                path='/tmp/rendered', template='files/the_work_of_this_server.json', permissions_mode='0644'))])))
            role_inputs = {name: value for name, value in inputs.items()}
            role_inputs.update(inventory_nodes='{{ .inventory.nodes }}', apps=APPS, public_host_names=HOST_NAMES)
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(
                id='render', nodes='app001', node_tasks=[dict(role='r', inputs=role_inputs)])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = next(task for task in json.loads(result.stdout)['fleet_stages'][0]['node_tasks'] if task.get('rendered_templates'))
        return task['rendered_templates'][0]['text']

    def run_the_command(self, settings_text, responses=(), active=(), live_ports=None, cloudflared=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_directory, answers = root/'bin', root/'responses'
            bin_directory.mkdir()
            (answers/'active').mkdir(parents=True)
            for name, text in (('curl', STAND_IN_CURL), ('systemctl', STAND_IN_SYSTEMCTL), ('hostname', '#!/bin/sh\necho app001\n')):
                (bin_directory/name).write_text(text)
                (bin_directory/name).chmod(0o755)
            for (url, host), code in dict(responses).items():
                (answers/(f'{url}|{host}'.replace('/', '_').replace(':', '_'))).write_text(code)
            for unit in active:
                (answers/'active'/unit).touch()
            (root/'etc').mkdir()
            (root/'etc/the_work_of_this_server.json').write_text(settings_text)
            (root/'live_web_ports').mkdir()
            for app, port in (live_ports or {}).items():
                (root/'live_web_ports'/app).write_text(port)
            if cloudflared:
                (root/'cloudflared.service').touch()
            command = COMMAND.read_text()
            for old, new in (('/etc/monkeymaxxing-stack/the_work_of_this_server.json', root/'etc/the_work_of_this_server.json'),
                             ('/var/lib/monkeymaxxing-stack/live_web_ports', root/'live_web_ports'),
                             ('/etc/systemd/system/cloudflared.service', root/'cloudflared.service')):
                self.assertIn(f'={old}\n', command)
                command = command.replace(f'={old}\n', f'={new}\n')
            (root/'command').write_text(command)
            env = dict(os.environ, PATH=f'{bin_directory}:{os.environ["PATH"]}', RESPONSES=str(answers))
            result = subprocess.run(['bash', str(root/'command')], env=env, text=True, capture_output=True,
                                    stdin=subprocess.DEVNULL)
            asked = (answers/'asked').read_text().splitlines() if (answers/'asked').exists() else []
        return result, asked

    def test_an_app_server_whose_containers_answer_does_its_work(self):
        result, asked = self.run_the_command(self.rendered_settings(is_app_server=True), live_ports={'shop': '8002', 'blog': '8001'},
                                             responses={('http://10.20.1.1:8002/up', 'shop.example.com'): '200',
                                                        ('http://10.20.1.1:8001/health', 'blog.example.com'): '200'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, 'app001 does its work\n')
        self.assertEqual(sorted(asked), ['http://10.20.1.1:8001/health|blog.example.com', 'http://10.20.1.1:8002/up|shop.example.com'])

    def test_a_live_web_container_that_does_not_answer_fails_with_its_line(self):
        result, _ = self.run_the_command(self.rendered_settings(is_app_server=True), live_ports={'shop': '8002', 'blog': '8001'},
                                         responses={('http://10.20.1.1:8002/up', 'shop.example.com'): '502',
                                                    ('http://10.20.1.1:8001/health', 'blog.example.com'): '200'})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "shop's live web container on port 8002 does not answer /up with 200\n")

    def test_an_app_without_a_live_web_port_fails(self):
        result, _ = self.run_the_command(self.rendered_settings(is_app_server=True), live_ports={'blog': '8001'},
                                         responses={('http://10.20.1.1:8001/health', 'blog.example.com'): '200'})
        self.assertEqual(result.returncode, 1)
        self.assertIn('shop has no live web port', result.stdout)

    def test_the_tunnel_connector_and_caddy_with_production_host_names(self):
        responses = {('http://10.20.1.1:8002/up', 'shop.example.com'): '200', ('http://10.20.1.1:8001/health', 'blog.example.com'): '200',
                     ('http://127.0.0.1:20241/ready', ''): '200', ('http://127.0.0.1/up', 'shop.example.com'): '200',
                     ('http://127.0.0.1/health', 'blog.example.com'): '200'}
        settings = self.rendered_settings(is_app_server=True)
        result, _ = self.run_the_command(settings, responses, live_ports={'shop': '8002', 'blog': '8001'}, cloudflared=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        responses[('http://127.0.0.1:20241/ready', '')] = '503'
        responses[('http://127.0.0.1/health', 'blog.example.com')] = '502'
        result, _ = self.run_the_command(settings, responses, live_ports={'shop': '8002', 'blog': '8001'}, cloudflared=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines(), [
            'cloudflared is not connected to Cloudflare: http://127.0.0.1:20241/ready does not answer 200',
            'blog does not answer /health through Caddy here, as blog.example.com'])

    def test_staging01_is_asked_with_staging_host_names(self):
        result, asked = self.run_the_command(self.rendered_settings(is_staging_server=True), cloudflared=True, responses={
            ('http://127.0.0.1:20241/ready', ''): '200', ('http://127.0.0.1/up', 'shop-staging.example.com'): '200',
            ('http://127.0.0.1/health', 'blog-staging.example.com'): '200'})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('http://127.0.0.1/up|shop.example.com', asked)

    def test_a_jobs_server_needs_the_job_container_of_each_app_with_jobs(self):
        settings = self.rendered_settings(is_jobs_server=True)
        result, _ = self.run_the_command(settings, active=['shop-jobs.service'])
        self.assertEqual(result.returncode, 0, result.stdout)
        result, _ = self.run_the_command(settings)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "shop's job container, shop-jobs.service, does not run\n")

    def test_a_load_balancer_server_does_its_work_only_with_its_tunnel_connector(self):
        settings = self.rendered_settings(is_load_balancer_server=True)
        responses = {('http://127.0.0.1:20241/ready', ''): '200', ('http://127.0.0.1/up', 'shop.example.com'): '200',
                     ('http://127.0.0.1/health', 'blog.example.com'): '200'}
        result, asked = self.run_the_command(settings, responses, cloudflared=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(sorted(asked), ['http://127.0.0.1/health|blog.example.com', 'http://127.0.0.1/up|shop.example.com',
                                         'http://127.0.0.1:20241/ready|'])
        # A new load-balancer server whose install stopped before the tunnel connector does not do its work.
        result, asked = self.run_the_command(settings, responses)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stdout.startswith('this load-balancer server has no tunnel connector: '), result.stdout)

    def test_a_server_of_another_pool_has_nothing_to_check(self):
        result, asked = self.run_the_command(self.rendered_settings())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(asked, [])

    def test_without_its_settings_file_the_server_does_not_do_its_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            command = COMMAND.read_text().replace('=/etc/monkeymaxxing-stack/the_work_of_this_server.json\n',
                                                  f'={temporary}/missing.json\n')
            result = subprocess.run(['bash', '-c', command], text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 1)
        self.assertIn('run every_server, which writes it', result.stdout)

    def test_the_reboot_playbook_waits_for_the_command_and_every_server_installs_it(self):
        playbook = (T/'playbooks/reboot_servers_after_updates.yml').read_text()
        self.assertIn('command_succeeds: /usr/local/bin/check-that-this-server-does-its-work', playbook)
        self.assertNotIn('curl', playbook)
        role = (T/'roles/every_server/main.yml').read_text()
        self.assertIn('path: /usr/local/bin/check-that-this-server-does-its-work', role)
        self.assertIn('source: files/check-that-this-server-does-its-work', role)
        self.assertTrue(COMMAND.stat().st_mode & stat.S_IXUSR)


if __name__ == '__main__':
    unittest.main()
