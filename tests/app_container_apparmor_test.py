#!/usr/bin/env python3
"""Check the container confinement policy and its server-wide selection."""
from pathlib import Path
import configparser
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
FILES = TEMPLATE / 'roles/every_server/files'
PROFILE = 'monkeymaxxing-app-containers'


class AppContainerAppArmor(unittest.TestCase):
    def test_migrations_select_the_confined_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / 'podman'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o755)
            result = subprocess.run(['bash', str(TEMPLATE / 'roles/app_server/files/run_app_migrations'),
                                     'shop', 'example.com/shop:v1', 'node', 'migrate.mjs'],
                                    env=dict(os.environ, PATH=temporary + os.pathsep + os.environ['PATH']),
                                    text=True, capture_output=True, check=True)
            arguments = result.stdout.splitlines()
            self.assertEqual(arguments[arguments.index('--security-opt') + 1], 'apparmor=' + PROFILE)
            self.assertIn('--userns=auto', arguments)
            self.assertEqual(arguments[-3:], ['example.com/shop:v1', 'node', 'migrate.mjs'])

    def test_signals_match_plain_and_crun_stacked_peers_only(self):
        policy = (FILES / PROFILE).read_text()
        self.assertIn('profile ' + PROFILE + ' flags=(attach_disconnected,mediate_deleted)', policy)
        self.assertNotIn('flags=(unconfined)', policy)
        # The full peer label must match, including a runtime's stacked label.
        # Keep the extra permission limited to this container profile and crun.
        rules = re.findall(r'^\s*signal \(send,receive\) peer=([^\n]+),$', policy, re.M)
        self.assertEqual(rules, ['{' + PROFILE + ',crun//&' + PROFILE + '}'])
        self.assertIn('signal (receive) peer=unconfined,', policy)
        self.assertNotRegex(policy, r'signal\s*[,;]')
        for restriction in ('deny mount,', 'deny @{PROC}/sysrq-trigger rwklx,',
                            'deny @{PROC}/kcore rwklx,', 'deny /sys/kernel/security/** rwklx,'):
            self.assertIn(restriction, policy)


class UserNamespaceSetup(unittest.TestCase):
    def test_every_server_writes_the_containers_range_to_subuid_and_subgid(self):
        text = (TEMPLATE / 'roles/every_server/main.yml').read_text()
        for path in ('/etc/subuid', '/etc/subgid'):
            with self.subTest(path=path):
                task = re.search(r'line:\n\s+path: ' + path + r'\n\s+match: \'\^containers:\'\n'
                                 r'\s+line: "containers:2147483647:2147483648"\n\s+insert_at_end_of_file: true', text)
                self.assertIsNotNone(task)
        # Other lines of the files stay: no task owns the whole file.
        self.assertNotRegex(text, r'path: /etc/sub[ug]id\n\s+(source|content|template)')

    def test_asset_files_are_readable_by_the_container_user(self):
        # A container user the server does not know sees every file as "other".
        script = (TEMPLATE / 'roles/app_server/files/fill_web_asset_directory').read_text()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / 'image/assets'
            (image / 'private').mkdir(parents=True)
            (image / 'private/app.css').write_text('x')
            (image / 'private/app.css').chmod(0o600)
            (image / 'private').chmod(0o700)
            image.chmod(0o700)
            (root / 'state/web_assets').mkdir(parents=True)
            fake = root / 'bin/podman'
            fake.parent.mkdir()
            fake.write_text('#!/bin/sh\nif [ "$2" = mount ]; then echo "' + str(root / 'image') + '"; fi\n')
            fake.chmod(0o755)
            changed = root / 'fill'
            changed.write_text(script.replace('/var/lib/monkeymaxxing-stack', str(root / 'state')))
            subprocess.run(['bash', str(changed)], check=False, text=True, capture_output=True,
                           env=dict(os.environ, PATH=str(fake.parent) + os.pathsep + os.environ['PATH'],
                                    CONTAINER_NAME='shop-web-8001', ASSET_DIRECTORY='/assets',
                                    IMAGE='example.com/shop:v1', PREVIOUS_IMAGE=''))
            result = list(root.glob('state/web_assets/shop-web-8001/private/app.css'))
            self.assertEqual(len(result), 1, 'the asset file was not copied')
            for path in (result[0], result[0].parent, root / 'state/web_assets/shop-web-8001'):
                self.assertTrue(path.stat().st_mode & 0o004, str(path))
            self.assertTrue(result[0].parent.stat().st_mode & 0o001)


class RenderedQuadlets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise unittest.SkipTest('Set MMX_BINARY or put mmx on PATH to render Quadlets.')

    def render(self, filename, **app_settings):
        app = dict(env={'WEB_CONCURRENCY': '2'}, asset_directory='/app/assets', jobs_command='node jobs.mjs',
                   jobs_connect_directly_to_postgres=False, **app_settings)
        values = dict(apps={'shop': app}, web_container=dict(key='shop', value=dict(web_port=8001, image='example.com/shop:v1')),
                      job_container=dict(key='shop', value=dict(image='example.com/shop:v1')))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'inventories').mkdir()
            (root / 'playbooks').mkdir()
            (root / 'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='container_policy_test', default_inventory='servers', vars=values)))
            (root / 'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001': {'address': '127.0.0.1'}})))
            template = (TEMPLATE / filename).read_text().replace('.inputs.', '.vars.').replace('.web_container.', '.vars.web_container.').replace('.job_container.', '.vars.job_container.')
            (root / 'container.template').write_text(template)
            (root / 'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[dict(id='render', file=dict(path='/tmp/rendered', template='container.template', permissions_mode='0644'))])])) )
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    FILES = ('roles/app_server/files/web_container.container', 'files_used_by_several_roles/jobs_container.container')

    def test_web_and_jobs_select_the_profile_without_losing_other_restrictions(self):
        for filename in self.FILES:
            with self.subTest(filename=filename):
                text = self.render(filename)
                config = configparser.ConfigParser(interpolation=None, strict=False)
                config.read_string(text)
                self.assertEqual(config['Container']['PodmanArgs'], '--security-opt=apparmor=' + PROFILE)
                self.assertEqual(config['Container']['NoNewPrivileges'], 'true')
                self.assertEqual(config['Container']['DropCapability'], 'all')
                self.assertEqual(config['Container']['StopTimeout'], '30')

    def test_web_and_jobs_run_in_an_automatic_user_namespace(self):
        # Root in the container maps to an unused, unprivileged user on the server.
        for filename in self.FILES:
            with self.subTest(filename=filename):
                self.assertIn('UserNS=auto', self.render(filename).splitlines())

    def test_web_and_jobs_have_a_read_only_file_system(self):
        # Files an app writes to its own disk would vanish at the next deploy.
        for filename in self.FILES:
            with self.subTest(filename=filename):
                lines = self.render(filename).splitlines()
                self.assertIn('ReadOnly=true', lines)
                self.assertIn('ReadOnlyTmpfs=true', lines)
                self.assertEqual([line for line in lines if line.startswith('Tmpfs=')], [])

    def test_listed_scratch_directories_become_writable_memory_directories(self):
        for filename in self.FILES:
            with self.subTest(filename=filename):
                lines = self.render(filename, writable_temporary_directories=['/app/storage/framework/views', '/data/caddy']).splitlines()
                self.assertIn('ReadOnly=true', lines)
                self.assertEqual([line for line in lines if line.startswith('Tmpfs=')],
                                 ['Tmpfs=/app/storage/framework/views:mode=1777', 'Tmpfs=/data/caddy:mode=1777'])


if __name__ == '__main__':
    unittest.main()
