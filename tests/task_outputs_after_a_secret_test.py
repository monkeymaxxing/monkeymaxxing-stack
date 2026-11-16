#!/usr/bin/env python3
"""No resource identifier reads a node task's output that MMX hides because of a secret.

  MMX_BINARY=/path/to/mmx python3 tests/task_outputs_after_a_secret_test.py

What MMX does (MMX's internal/value/secret.go,
Trace, touch and HidesLaterTasks): MMX hides the stdout, stderr, value and
module outputs of a node task that reads a secret, or a value made from one,
such as a set_vars value made from a secret or a hidden node task's output
(internal/protocol/result.go, ResultValue). When such a node task runs
something on the server, MMX also marks the role call or node task block
around it, and every one around that, and every LATER node task in it starts
hidden too, because the secret may be left on the server. A read by
set_vars, show or assert runs nothing on the server and hides no later node
task. A hidden value is refused in a resource identifier, such as a schedule,
a name or a path: "resource identifier must not contain a secret; it reads
.node_tasks.NAME.stdout, which holds a secret: the result of that node task
is hidden because node task ROLE/TASK read a secret before it started"
(internal/config/arguments.go, resolveArgument). The 2026-11-12 real-system
run failed on db01 so: the differential backups' schedule read the stdout of
a shell task that ran after write_the_pgbackrest_settings.

What this test does: it copies the template twice, as written and with
every kind of server (tests/server_connections_test.py's ten servers and
restore01), reads `mmx explain PLAYBOOK --json` for every playbook, and walks
each server's node tasks in order. A node task reads a secret when an
argument reads one (explain's status "secret") or reads a var that holds
one, or when its template file reads `.secrets.`, a role input that the role
call fills with a secret, or a var that holds one. After the first such read
by a node task other than set_vars, show or assert, every later node task of
the same role call or node task block is hidden. It then fails for each reference to
a hidden task's output (any field but status, change, exit_code), directly or
through a set_vars, in a field that is not a condition or a private value.

What it cannot see: a field counts as a resource identifier unless it is in
PRIVATE_FIELDS below, copied from the modules' Private() arguments in MMX, so
a private field missing from the list gives a false failure, never a missed
one. Logins that MMX hands only to a tool do not hide later results
(LOGINS_HANDED_ONLY_TO_A_TOOL, from the modules' notes "a secret in it does
not hide the task's result"); an entry there that is wrong would hide a
fault. A node task that explain does not list for any server of the test
inventory is not checked.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_connections_test import T, make_project, server_block  # noqa: E402

REFERENCE = re.compile(r'\.(node_tasks|vars|inputs|secrets)\.([A-Za-z0-9_]+)(?:\.([A-Za-z0-9_]+))?')
NOT_HIDDEN_RESULT_FIELDS = {'status', 'change', 'exit_code', 'iteration_key', 'outputs'}
PRIVATE_FIELDS = re.compile(r'^(content|env\..*|headers\..*|body|json_body|message|line|username|ssh_known_hosts_lines|'
                            r'basic_auth_username|basic_auth_password|content_filter\.shell\.env\..*|show|password_hash)$')
LOGINS_HANDED_ONLY_TO_A_TOOL = {
    'pg_auto_failover_monitor.autoctl_node_password', 'pg_auto_failover_node.autoctl_node_password',
    'pg_auto_failover_node.replication_password', 'podman_image.registry_username', 'podman_image.registry_password',
    'postgresql_role.password', 'postgresql_role.login_password'}
TEMPLATE_FIELDS = {'file.template', 'wireguard_interface.template', 'systemd_unit.template'}
# These run nothing on the server, so their read of a secret hides no later node task.
RUN_NOTHING_ON_THE_SERVER = {'set_vars', 'show', 'assert'}
PLAYBOOKS = {  # playbook: the command-line vars each explain needs
    'every_server': [], 'deploy': ['environment_name=production'],
    'copy_the_database_moving_in': [], 'switch_to_the_database_moving_in': [],
    'end_connections_that_use_an_old_database_password': ['database_name=shop', 'environment_name=production'],
    'lock_everyone_out': ['desk_name=desk01'], 'systems_desk': ['desk_name=desk01'],
    'reboot_servers_after_updates': [], 'reboot_util01_after_updates': [],
    'remove_server': ['server_name=app002'], 'switch_database_primary': ['server_name=db02'],
    'update_database_servers': [], 'weekly_database_restore_drill': [],
    'replace_failed_servers': [], 'destroy_replaced_servers': [], 'add_an_app_server_for_the_load': [],
    'restore_database': ['restore_mode=copy_on_restore01', 'server_name=restore01',
                         'recover_to=2026-11-03 14:01:00+00', 'read_backup_bucket_as_of=2026-11-03 15:30:00+00'],
    'recover_rows_from_a_restored_copy': ['recover_to=2026-11-03 14:01:00+00', 'read_backup_bucket_as_of=2026-11-03 15:30:00+00',
                                          'database_name=shop', 'table=orders', 'rows_where=id <= 5',
                                          'when_a_primary_key_exists=skip_the_row'],
}


def texts(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from texts(x)
    elif isinstance(v, list):
        for x in v:
            yield from texts(x)


def components(path):
    return tuple(re.sub(r'\[.*\]$', '', part) for part in path.split('/'))


def hidden_outputs_in_identifiers(project, explained):
    """Each (task path, field, reference, first secret read) that MMX would refuse."""
    found = []
    for stage in explained['fleet_stages']:
        per_node = {}
        for task in stage.get('node_tasks') or []:
            # A fleet stage whose nodes MMX resolves during the run (remove_server's hold) has no node yet.
            per_node.setdefault(task.get('node'), []).append(task)
        for tasks in per_node.values():
            secret_inputs = {}   # role call path: names of its inputs that hold a secret
            secret_vars = {}     # role call path: names of its vars that hold a secret
            marked = {}          # role call or block path: the task whose secret read marked it
            hidden_tasks = {}    # (role call path, task id): the first secret read
            hidden_vars = {}     # (role call path, var name): the first secret read
            for task in tasks:
                path = components(task['path'][len(stage['path']) + 1:])
                enclosing = [path[:i] for i in range(1, len(path))]
                role = next((p for p in reversed(enclosing) if p in secret_inputs), ())
                arguments = task.get('arguments') or []
                if task.get('action') == 'role':
                    # A role call only passes its inputs on; it marks nothing itself.
                    secret_inputs[path] = {a['field'][len('inputs.'):] for a in arguments
                                           if a['field'].startswith('inputs.') and a.get('status') == 'secret'}
                    continue
                reads = [a['field'] for a in arguments
                         if a.get('status') == 'secret' and a['field'] not in LOGINS_HANDED_ONLY_TO_A_TOOL]
                # A value made from a secret is a secret too: a var set from one, or a hidden output.
                for a in arguments:
                    for text in texts(a.get('reference')):
                        for kind, name, result_field in REFERENCE.findall(text):
                            if (kind == 'vars' and (name in secret_vars.get(role, ()) or (role, name) in hidden_vars)) or \
                                    (kind == 'node_tasks' and result_field not in NOT_HIDDEN_RESULT_FIELDS
                                     and (role, name) in hidden_tasks):
                                reads.append(a['field'] + ' (' + kind + '.' + name + ')')
                for a in arguments:
                    if a['field'] in TEMPLATE_FIELDS and isinstance(a.get('value'), str):
                        # A role's template path starts at the role's folder, a playbook's at the repository.
                        source = project/Path(task['source']['file']).parent/a['value']
                        if not task['source']['file'].startswith('roles/'):
                            source = project/a['value']
                        for kind, name, _ in REFERENCE.findall(source.read_text()):
                            if kind == 'secrets' or (kind == 'inputs' and name in secret_inputs.get(role, ())) or \
                                    (kind == 'vars' and name in secret_vars.get(role, ())):
                                reads.append(a['field'] + ' (' + kind + '.' + name + ')')
                    if a['field'].startswith('set_vars.') and (a.get('status') == 'secret' or
                                                               any(r.startswith(a['field'] + ' (') for r in reads)):
                        secret_vars.setdefault(role, set()).add(a['field'][len('set_vars.'):])
                first = next((marked[p] for p in enclosing if p in marked), None)
                if reads:
                    if task.get('action') not in RUN_NOTHING_ON_THE_SERVER:
                        for p in enclosing:
                            marked.setdefault(p, task['path'])
                    first = first or task['path']
                for a in arguments:
                    field = a['field']
                    own_field = field.split('.', 1)[1] if field.startswith(task.get('action', '') + '.') else field
                    for text in texts(a.get('reference')):
                        for kind, name, result_field in REFERENCE.findall(text):
                            if kind == 'node_tasks' and result_field not in NOT_HIDDEN_RESULT_FIELDS:
                                source = hidden_tasks.get((role, name))
                            elif kind == 'vars':
                                source = hidden_vars.get((role, name))
                            else:
                                continue
                            if source is None or a.get('status') == 'condition':
                                continue
                            if field.startswith('set_vars.'):
                                hidden_vars[(role, field[len('set_vars.'):])] = source
                            elif not PRIVATE_FIELDS.match(own_field):
                                found.append((task['node'], task['path'], field, text, source))
                if first:
                    hidden_tasks[(role, path[-1])] = first
    return found


def make_project_with_every_kind_of_server(root):
    restore = {'restore01': server_block('restore01', '10.20.8.1')}
    make_project(root, extra_servers=restore, extra_groups={'database_restore_servers': (['restore01'], '')})


class TaskOutputsAfterASecret(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX playbooks.')

    def explain(self, root, playbook, variables=None):
        arguments = [self.mmx, 'explain', playbook, '--json']
        for variable in PLAYBOOKS[playbook] if variables is None else variables:
            arguments += ['--var', variable]
        result = subprocess.run(arguments, cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, playbook + ': ' + result.stderr)
        return json.loads(result.stdout)

    def test_every_playbook_is_checked(self):
        self.assertEqual(set(PLAYBOOKS), {p.stem for p in (T/'playbooks').glob('*.yml')})

    def test_no_identifier_reads_a_hidden_task_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            make_project_with_every_kind_of_server(root)
            for playbook in PLAYBOOKS:
                with self.subTest(playbook=playbook):
                    self.assertEqual(hidden_outputs_in_identifiers(root, self.explain(root, playbook)), [])
        # The template's own inventory, with one database server, selects
        # update_database_servers' stages before the run, so explain lists
        # their node tasks; with two it leaves them to the run.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            for playbook in PLAYBOOKS:
                if playbook in ('restore_database', 'remove_server'):
                    continue  # they need a node the template's inventory does not have
                variables = ['server_name=db01'] if playbook == 'switch_database_primary' else None
                with self.subTest(playbook=playbook, inventory='the template as written'):
                    self.assertEqual(hidden_outputs_in_identifiers(root, self.explain(root, playbook, variables)), [])

    def test_the_check_finds_a_schedule_worked_out_after_a_secret(self):
        # The uploads copy's time, worked out after the rclone settings that read the keys, as before 2026-11-12.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'systems'
            make_project_with_every_kind_of_server(root)
            role = root/'roles/uploads_backup/main.yml'
            text = role.read_text()
            start = text.index('  - id: work_out_the_time_of_the_uploads_copy\n')
            end = text.index('\n\n', start) + 1
            moved = text[start:end]
            text = text[:start] + text[end:]
            anchor = '  - id: copy_the_uploads_to_the_backup_bucket_on_schedule\n'
            role.write_text(text.replace(anchor, moved + anchor))
            found = hidden_outputs_in_identifiers(root, self.explain(root, 'every_server'))
        self.assertIn(('util01', 'uploads_backup/uploads_backup/copy_the_uploads_to_the_backup_bucket_on_schedule',
                       'systemd_scheduled_job.systemd_calendar_schedule',
                       '*-*-* {{ .node_tasks.work_out_the_time_of_the_uploads_copy.stdout }} UTC',
                       'uploads_backup/uploads_backup/write_the_rclone_settings_of_the_uploads_backup'), found)

    def test_a_file_task_with_secrets_hides_later_outputs_and_set_vars_does_not(self):
        # The differential backups' days as a shell task's output. After
        # write_the_pgbackrest_settings, a file task whose template reads secrets, MMX hides the
        # output; after only name_the_pgbackrest_settings, a set_vars, it shows it.
        days = ('  - id: list_the_days_of_the_differential_backups\n'
                '    shell:\n'
                '      script: printf monday,tuesday,wednesday,thursday,friday,saturday\n'
                '      dryrun: printf monday,tuesday,wednesday,thursday,friday,saturday\n'
                '      changed_when: false\n')
        schedule = '{{ .vars.days_other_than[.inputs.weekly_work_day] }} *-*-* {{ .inputs.nightly_work_starts_at }}:00'
        output = '{{ .node_tasks.list_the_days_of_the_differential_backups.stdout }} *-*-* {{ .inputs.nightly_work_starts_at }}:00'
        found = {}
        for anchor in ('  - id: write_the_pgbackrest_settings\n', '  - id: differential_backup_every_other_day\n'):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)/'systems'
                make_project_with_every_kind_of_server(root)
                role = root/'roles/database_server/main.yml'
                text = role.read_text()
                self.assertEqual((text.count(anchor), text.count(schedule)), (1, 1))
                role.write_text(text.replace(anchor, days + anchor).replace(schedule, output))
                found[anchor] = {(node, path, source) for node, path, field, _, source
                                 in hidden_outputs_in_identifiers(root, self.explain(root, 'every_server'))}
        self.assertEqual(found['  - id: write_the_pgbackrest_settings\n'], set())
        self.assertIn(('db01', 'database_server/database_server/differential_backup_every_other_day',
                       'database_server/database_server/write_the_pgbackrest_settings'),
                      found['  - id: differential_backup_every_other_day\n'])


if __name__ == '__main__':
    unittest.main()
