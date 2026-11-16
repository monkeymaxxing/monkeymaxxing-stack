#!/usr/bin/env python3
"""Check that an app with no background jobs (jobs_command: "") gets no job container.

  MMX_BINARY=/path/to/mmx python3 tests/apps_with_no_jobs_test.py

It reads what `mmx explain` says about:
- the real job-container tasks of the app_server and jobs_server roles, copied
  from the roles' own files into a probe role that has one app with jobs
  (`busy`) and one without (`quiet`);
- the real every_server playbook, for the refusal that follows
  job_containers_run_only_on_the_jobs_servers when no jobs server exists;
- the job containers' MMWatchdog check groups, rendered for both kinds of app.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

T = Path(os.environ.get('STACK_TEMPLATE_DIR') or Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template')

APPS = {'busy': {'jobs_command': 'bin/jobs', 'jobs_connect_directly_to_postgres': False},
        'quiet': {'jobs_command': '', 'jobs_connect_directly_to_postgres': False}}


def task_text(role_file, task_id):
    """The text of one top-level task of a role, from its `  - id:` line to the next task or comment."""
    lines = (T/role_file).read_text().splitlines()
    start = lines.index(f'  - id: {task_id}')
    end = start + 1
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith('   ')):
        end += 1
    return '\n'.join(lines[start:end]).rstrip() + '\n'


class Explained(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def explain(self, playbook, root):
        result = subprocess.run([self.mmx, 'explain', playbook], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def copy_of_template(self, directory):
        root = Path(directory)/'systems'
        shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
        return root

    def render_file(self, template_file, apps, extra_vars=None):
        """Render a template of the systems repository once, with `.inputs` read as `.vars`, and return its text."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(
                project_name='render_test', default_inventory='servers', vars=dict(apps=apps, **(extra_vars or {})))))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001': {'address': '127.0.0.1'}})))
            (root/'source.template').write_text((T/template_file).read_text().replace('.inputs', '.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]
            self.assertIn('text', rendered, rendered)
            return rendered


class JobContainerTasks(Explained):
    def probe(self, role, tasks, **inputs):
        """Run the role's real job-container tasks over the two apps, and return what explain says of them."""
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_of_template(directory)
            (root/'roles/jobs_probe').mkdir()
            body = ''.join(task_text(f'roles/{role}/main.yml', task).replace('.vars.job_containers', '.inputs.job_containers')
                           for task in tasks)
            (root/'roles/jobs_probe/main.yml').write_text(
                'inputs:\n  apps: {type: mapping, required: true}\n  set_up_the_server: {type: boolean, required: true}\n'
                '  job_containers_run_only_on_the_jobs_servers: {type: boolean, required: true}\n'
                '  job_containers: {type: mapping, required: true}\n'
                '  container_registry_username: {type: string, required: true}\n'
                '  container_registry_password: {type: string, required: true, secret: true}\n'
                'node_tasks:\n' + body)
            (root/'playbooks/jobs_probe.yml').write_text(json.dumps({'fleet_stages': [{'id': 'probe', 'nodes': 'app_servers', 'node_tasks': [
                {'role': 'jobs_probe', 'inputs': dict(
                    apps=APPS, job_containers={name: {'image': f'docker.io/library/{name}:1'} for name in APPS},
                    container_registry_username='{{ .vars.container_registry_read_only_username }}',
                    container_registry_password='{{ .secrets.container_registry_read_only_token }}', **inputs)}]}]}))
            return self.explain('jobs_probe', root)

    def states(self, text, task_id):
        """{app: state} for the looped task `task_id`, such as {'busy': 'ready', 'quiet': 'skipped'}."""
        found = {}
        for line in text.splitlines():
            match = re.search(rf'/{task_id}\[(\w+)\]: \w+ \((\w+)\)', line)
            if match:
                found[match.group(1)] = match.group(2)
        return found

    APP_SERVER_TASKS = ('job_container_of_each_app', 'remove_the_job_container_that_the_jobs_servers_run_or_the_app_does_not_need')

    def test_an_app_server_starts_the_job_container_only_of_an_app_with_jobs(self):
        text = self.probe('app_server', self.APP_SERVER_TASKS, set_up_the_server=True, job_containers_run_only_on_the_jobs_servers=False)
        states = self.states(text, 'job_container_of_each_app')
        self.assertEqual(states['quiet'], 'skipped')
        self.assertNotEqual(states['busy'], 'skipped')

    def test_an_app_server_removes_the_job_container_of_an_app_that_has_no_jobs_now(self):
        text = self.probe('app_server', self.APP_SERVER_TASKS, set_up_the_server=True, job_containers_run_only_on_the_jobs_servers=False)
        self.assertEqual(self.states(text, self.APP_SERVER_TASKS[1]), {'busy': 'skipped', 'quiet': 'ready'})

    def test_with_the_jobs_on_the_jobs_servers_an_app_server_removes_every_job_container(self):
        text = self.probe('app_server', self.APP_SERVER_TASKS, set_up_the_server=True, job_containers_run_only_on_the_jobs_servers=True)
        self.assertEqual(self.states(text, 'job_container_of_each_app'), {'busy': 'skipped', 'quiet': 'skipped'})
        self.assertEqual(self.states(text, self.APP_SERVER_TASKS[1]), {'busy': 'ready', 'quiet': 'ready'})

    def test_a_deploy_leaves_an_app_with_no_jobs_alone(self):
        text = self.probe('app_server', self.APP_SERVER_TASKS, set_up_the_server=False, job_containers_run_only_on_the_jobs_servers=False)
        states = self.states(text, 'job_container_of_each_app')
        self.assertEqual(states['quiet'], 'skipped')
        self.assertNotEqual(states['busy'], 'skipped')

    JOBS_SERVER_TASKS = ('job_container_of_each_app', 'remove_the_job_container_of_an_app_with_no_jobs')

    def test_a_jobs_server_starts_the_job_container_only_of_an_app_with_jobs(self):
        text = self.probe('jobs_server', self.JOBS_SERVER_TASKS, set_up_the_server=True, job_containers_run_only_on_the_jobs_servers=True)
        states = self.states(text, 'job_container_of_each_app')
        self.assertEqual(states['quiet'], 'skipped')
        self.assertNotEqual(states['busy'], 'skipped')
        self.assertEqual(self.states(text, self.JOBS_SERVER_TASKS[1]), {'busy': 'skipped', 'quiet': 'ready'})

    def test_the_job_container_file_refuses_an_app_with_no_jobs_command(self):
        for value, words in (('', 'no background jobs'), (None, 'has no jobs_command')):
            with self.subTest(value=value):
                app = {'jobs_connect_directly_to_postgres': False}
                if value is not None:
                    app['jobs_command'] = value
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root/'inventories').mkdir()
                    (root/'playbooks').mkdir()
                    (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=dict(apps={'shop': app}))))
                    (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001': {'address': '127.0.0.1'}})))
                    (root/'source.template').write_text((T/'files_used_by_several_roles/jobs_container.container').read_text().replace('.inputs', '.vars'))
                    (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                        dict(id='render', loop={'shop': dict(image='registry/shop:1')}, **{'as': 'job_container'},
                             file=dict(path='/tmp/rendered', template='source.template', permissions_mode='0600'))])])))
                    result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
                    rendered = json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]
                self.assertNotIn('text', rendered)
                self.assertIn(words, rendered['not_rendered_because'])


class SwitchWithNoJobsServers(Explained):
    SWITCH = 'job_containers_run_only_on_the_jobs_servers: false'

    def refusal(self, jobs_command, switch):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_of_template(directory)
            path = root/'mmx_project_settings.yml'
            settings = path.read_text()
            self.assertIn('jobs_command: bin/jobs', settings)
            self.assertIn(self.SWITCH, settings)
            settings = settings.replace('jobs_command: bin/jobs', f'jobs_command: "{jobs_command}"', 1)
            settings = settings.replace(self.SWITCH, f'job_containers_run_only_on_the_jobs_servers: {switch}', 1)
            path.write_text(settings)
            text = self.explain('every_server', root)
        states = re.findall(r'refuse_to_move_the_jobs_to_no_jobs_server\[shop\]: assert \((\w+)\)', text)
        self.assertEqual(len(states), 1, states)
        return states[0], text

    def test_an_app_with_jobs_is_refused_when_no_jobs_server_exists(self):
        state, text = self.refusal('bin/jobs', 'true')
        self.assertEqual(state, 'ready')
        self.assertIn('nothing would run the jobs of the app shop. Fix it in one of two ways. To keep the jobs on the app servers', text)

    def test_an_app_with_no_jobs_never_trips_the_refusal(self):
        self.assertEqual(self.refusal('', 'true')[0], 'skipped')

    def test_with_the_switch_off_nothing_is_refused(self):
        self.assertEqual(self.refusal('bin/jobs', 'false')[0], 'skipped')


class JobContainerChecks(Explained):
    def test_with_no_app_having_jobs_there_is_no_job_containers_check_group(self):
        text = self.render_file('mmwatchdog_checks/jobs_servers.yml', {'quiet': APPS['quiet']})['text']
        self.assertNotIn('job_containers:', text)
        self.assertNotIn('quiet_jobs_cpu', text)
        self.assertIn('jobs_server_capacity:', text)

    def test_the_jobs_servers_check_the_job_container_only_of_an_app_with_jobs(self):
        text = self.render_file('mmwatchdog_checks/jobs_servers.yml', APPS)['text']
        self.assertIn('busy_jobs_cpu', text)
        self.assertNotIn('quiet_jobs_cpu', text)


if __name__ == '__main__':
    unittest.main()
