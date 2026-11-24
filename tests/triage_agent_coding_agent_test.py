#!/usr/bin/env python3
"""util01 installs Codex only when the team chooses Codex for the triage agent.

  MMX_BINARY=/path/to/mmx python3 tests/triage_agent_coding_agent_test.py

The test copies the systems repository template, sets
vars.triage_agent_coding_agent, and reads what `mmx explain every_server`
plans for util01, so MMX itself evaluates the role's conditions. With codex,
util01 unpacks the release pinned in stack_software.codex and links codex,
codex-code-mode-host, and rg into /usr/local/bin, where MMHotline looks for
them. With claude_code, every Codex task is skipped. Claude Code is installed
either way. mmhotline_settings.yml renders triage_agent.coding_agent from the
same setting. The proof on a real util01 is recorded in docs/testing.md.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
SETTING = re.compile(r'(?m)^  triage_agent_coding_agent: \w+$')


def argument(task, field):
    for item in task.get('arguments') or []:
        if item['field'] == field:
            return item['value']
    raise AssertionError(f'{task["path"]} has no argument {field}')


class CodexOnlyWhenChosen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX playbooks.')

    def util01_tasks(self, coding_agent):
        """The util01 node tasks that `mmx explain every_server` plans, by path."""
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)/'systems'
            shutil.copytree(T, project, ignore=shutil.ignore_patterns('.mmx'))
            template_values.fill_the_values_the_setup_fills(project)
            settings = project/'mmx_project_settings.yml'
            text = settings.read_text()
            self.assertEqual(len(SETTING.findall(text)), 1, 'the template sets triage_agent_coding_agent once')
            settings.write_text(SETTING.sub(f'  triage_agent_coding_agent: {coding_agent}', text))
            result = subprocess.run([self.mmx, 'explain', 'every_server', '--json', '--limit', 'util01'],
                                    cwd=project, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        tasks = {}
        for stage in json.loads(result.stdout)['fleet_stages']:
            for task in stage.get('node_tasks') or []:
                tasks[task['path']] = task
        return tasks

    def codex_tasks(self, tasks):
        # every_server's first stage checks every pin, codex's too, and installs nothing.
        return {path: task for path, task in tasks.items() if 'codex' in path and '/no_pin_has_a_sha256_of_zeros[' not in path}

    def test_codex_installs_the_pinned_release_where_mmhotline_looks(self):
        tasks = self.codex_tasks(self.util01_tasks('codex'))
        self.assertTrue(tasks)
        for path, task in tasks.items():
            self.assertEqual(task['status'], 'ready', path)
        unpack = next(task for path, task in tasks.items() if path.endswith('/unpack_the_codex_release'))
        pin = re.search(r'(?ms)^    codex:\n      version: "([^"]+)"\n      download_url: (\S+)\n      sha256: "([0-9a-f]{64})"',
                        (T/'mmx_project_settings.yml').read_text())
        self.assertIsNotNone(pin, 'stack_software.codex pins version, download_url, and sha256')
        version, url, sha256 = pin.groups()
        self.assertNotEqual(sha256, '0' * 64)
        self.assertEqual(argument(unpack, 'unpack_archive.url'), url)
        self.assertEqual(argument(unpack, 'unpack_archive.sha256'), sha256)
        release = f'/usr/local/lib/codex/releases/{version}'
        self.assertEqual(argument(unpack, 'unpack_archive.path'), release)
        links = {argument(task, 'symlink.path'): argument(task, 'symlink.target')
                 for task in tasks.values() if task.get('action') == 'symlink'}
        self.assertEqual(links, {
            '/usr/local/bin/codex': release + '/bin/codex',
            '/usr/local/bin/codex-code-mode-host': release + '/bin/codex-code-mode-host',
            '/usr/local/bin/rg': release + '/codex-path/rg',
        })

    def test_claude_code_installs_nothing_for_codex(self):
        tasks = self.codex_tasks(self.util01_tasks('claude_code'))
        self.assertTrue(tasks)
        for path, task in tasks.items():
            self.assertEqual(task['status'], 'skipped', path)

    def test_mmhotline_runs_the_coding_agent_util01_installs(self):
        """mmhotline_settings.yml takes triage_agent.coding_agent from the same setting."""
        source = (T/'mmhotline_settings.yml').read_text().replace('.secrets.', '.vars.secret_')
        for coding_agent in ('claude_code', 'codex'):
            with self.subTest(coding_agent=coding_agent), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root/'inventories').mkdir()
                (root/'playbooks').mkdir()
                values = {name: 'stand-in' for name in re.findall(r'\.vars\.(secret_\w+)', source)}
                values.update(everyone_locked_out_except_desk='', triage_ssh_public_key='ssh-ed25519 AAAA stand-in',
                              root_ssh_public_keys=['ssh-ed25519 BBBB stand-in desk'],
                              triage_agent_coding_agent=coding_agent,
                              what_the_triage_agent_may_do_without_a_person='routine_fixes',
                              triage_agent_server_work={'sos_waits_for_a_server_replacement_minutes': 10, 'warn_waits_for_the_triage_agent_minutes': 3},
                              util01_private_page_host_names={'mmhotline': 'ops.example.com'},
                              private_ip='10.20.0.1', cloudflare_account_id='0' * 32, status_page_host_name='status.example.com')
                (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
                (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'util01': {'address': '127.0.0.1'}})))
                (root/'settings.template').write_text(source)
                (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                    dict(id='render', file=dict(path='/tmp/rendered', template='settings.template', permissions_mode='0600'))])])))
                result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']
                self.assertEqual(re.findall(r'(?m)^  coding_agent: (.*)$', text), [coding_agent])

    def test_claude_code_is_installed_with_either_choice(self):
        for coding_agent in ('claude_code', 'codex'):
            with self.subTest(coding_agent=coding_agent):
                tasks = self.util01_tasks(coding_agent)
                install = next(task for path, task in tasks.items() if path.endswith('/install_claude_code_for_the_triage_agent'))
                self.assertEqual(install['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
