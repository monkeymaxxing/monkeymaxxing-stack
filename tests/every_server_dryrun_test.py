#!/usr/bin/env python3
"""Check that every_server and the roles it invokes stay idempotent in mmx dryrun.

  MMX_BINARY=/path/to/mmx python3 tests/every_server_dryrun_test.py

On util01, compare_every_server_with_the_repository runs `mmx dryrun every_server`
every day and expects exit 0 when no server differs from the repository. Three
shell-task mistakes break that check on an unchanged system:
  1. A read-only shell task (`changed_when: false`) without `dryrun` or
     `run_script_in_dryrun: true` is skipped as `unknown`, which makes dryrun
     exit 3 (and hides its outputs from later stages).
  2. A shell task in a task_block's `activate` phase with `dryrun: 'true'`
     (or a mutating `dryrun: systemctl daemon-reload`) reports `would_change`
     on every dryrun or mutates the server during dryrun instead of using
     `only_when_tracked_inputs_changed: true`.
  3. A shell task with an unconditional `dryrun: printf ...` and no guard,
     `changed_when` rule, or `when` condition reports `would_change` on every
     dryrun even when the state it creates already exists.
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
import template_values  # noqa: E402

TEMPLATE = template_values.TEMPLATE


def roles_invoked_by_every_server():
    """Return every role name transitively invoked by playbooks/every_server.yml."""
    seen = set()
    queue = [TEMPLATE / 'playbooks/every_server.yml']
    while queue:
        path = queue.pop()
        for role in re.findall(r'^\s*(?:-\s+)?role:\s*([A-Za-z0-9_]+)\s*(?:#.*)?$', path.read_text(), re.M):
            if role not in seen:
                seen.add(role)
                role_file = TEMPLATE / 'roles' / role / 'main.yml'
                if role_file.exists():
                    queue.append(role_file)
    return sorted(seen)


def strip_comment(value):
    """Strip an unquoted trailing YAML comment from a single-line scalar."""
    in_single = False
    in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == '#' and not in_single and not in_double and (index == 0 or value[index - 1].isspace()):
            return value[:index].strip()
    return value.strip()


def unquote_scalar(value):
    """Strip one pair of matching outer YAML quotes from a scalar string."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_inline_mapping(text):
    """Parse a simple single-line YAML mapping `{k: v, ...}` into a dict of strings."""
    inner = text.strip()
    assert inner.startswith('{') and inner.endswith('}'), text
    inner = inner[1:-1].strip()
    fields = {}
    parts = []
    depth = 0
    in_single = False
    in_double = False
    start = 0
    for index, char in enumerate(inner):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if char in '{[':
                depth += 1
            elif char in '}]':
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(inner[start:index])
                start = index + 1
    parts.append(inner[start:])
    for part in parts:
        if ':' not in part:
            continue
        key, val = part.split(':', 1)
        fields[key.strip()] = unquote_scalar(val)
    return fields


def extract_shell_tasks(path):
    """Extract every `shell:` block in a playbook or role file with its enclosing task context."""
    lines = path.read_text().splitlines()
    tasks = []
    # Track enclosing YAML section headers by indentation: [(indent, key)]
    section_stack = []
    for index, line in enumerate(lines):
        stripped = line.lstrip(' ')
        if not stripped or stripped.startswith('#'):
            continue
        indent = len(line) - len(stripped)
        while section_stack and section_stack[-1][0] >= indent:
            section_stack.pop()

        # Detect `- id:` task boundary or plain key
        key_match = re.match(r'^(?:-\s+)?([A-Za-z0-9_]+):(?:\s*(.*))?$', stripped)
        if key_match:
            key = key_match.group(1)
            rest = strip_comment(key_match.group(2) or '')
            if key == 'shell':
                # Skip `check_new_file:` file validators; they only validate candidate file content.
                if section_stack and section_stack[-1][1] == 'check_new_file':
                    section_stack.append((indent, key))
                    continue

                # Find enclosing list item (`- ...` at indent - 2) for task id and `when:`
                task_start = index
                task_indent = indent - 2
                for back in range(index, -1, -1):
                    back_stripped = lines[back].lstrip(' ')
                    if not back_stripped or back_stripped.startswith('#'):
                        continue
                    back_indent = len(lines[back]) - len(back_stripped)
                    if back_indent == task_indent and back_stripped.startswith('- '):
                        task_start = back
                        break
                    if back_indent < task_indent:
                        break
                task_end = len(lines)
                for fwd in range(index + 1, len(lines)):
                    fwd_stripped = lines[fwd].lstrip(' ')
                    if not fwd_stripped or fwd_stripped.startswith('#'):
                        continue
                    fwd_indent = len(lines[fwd]) - len(fwd_stripped)
                    if fwd_indent <= task_indent:
                        task_end = fwd
                        break

                task_block_lines = lines[task_start:task_end]
                task_id = None
                has_when = False
                for tline in task_block_lines:
                    tstrip = tline.lstrip(' ')
                    tindent = len(tline) - len(tstrip)
                    if tindent == task_indent and tstrip.startswith('- id:'):
                        task_id = strip_comment(tstrip.split(':', 1)[1])
                    elif tindent == indent and tstrip.startswith('id:'):
                        task_id = strip_comment(tstrip.split(':', 1)[1])
                    elif tindent == indent and tstrip.startswith('when:'):
                        has_when = True

                # Parse shell fields
                shell_fields = {}
                if rest.startswith('{') and rest.endswith('}'):
                    shell_fields = parse_inline_mapping(rest)
                else:
                    child_indent = None
                    cur = index + 1
                    while cur < task_end:
                        cline = lines[cur]
                        cstrip = cline.lstrip(' ')
                        if not cstrip or cstrip.startswith('#'):
                            cur += 1
                            continue
                        cindent = len(cline) - len(cstrip)
                        if cindent <= indent:
                            break
                        if child_indent is None:
                            child_indent = cindent
                        if cindent == child_indent:
                            cm = re.match(r'^([A-Za-z0-9_]+):(?:\s*(.*))?$', cstrip)
                            if cm:
                                ckey = cm.group(1)
                                cval = strip_comment(cm.group(2) or '')
                                if cval in ('|', '|-', '>', '>-'):
                                    block_lines = []
                                    cur += 1
                                    block_indent = None
                                    while cur < task_end:
                                        bline = lines[cur]
                                        if not bline.strip():
                                            block_lines.append('')
                                            cur += 1
                                            continue
                                        bindent = len(bline) - len(bline.lstrip(' '))
                                        if bindent <= child_indent:
                                            break
                                        if block_indent is None:
                                            block_indent = bindent
                                        block_lines.append(bline[block_indent:])
                                        cur += 1
                                    shell_fields[ckey] = '\n'.join(block_lines).rstrip('\n')
                                    continue
                                else:
                                    shell_fields[ckey] = unquote_scalar(cval)
                        cur += 1

                phases = [k for _, k in section_stack if k in ('changes', 'validate', 'activate', 'verify', 'on_failure')]
                tasks.append({
                    'file': str(path.relative_to(TEMPLATE)),
                    'line': index + 1,
                    'id': task_id or f'line_{index + 1}',
                    'phase': phases[-1] if phases else None,
                    'has_when': has_when,
                    'fields': shell_fields,
                })
            section_stack.append((indent, key))
    return tasks


def extract_task_field(path, task_id, field):
    """Return the exact script/dryrun value of a named shell task."""
    for task in extract_shell_tasks(TEMPLATE / path):
        if task['id'] == task_id:
            return task['fields'][field]
    raise AssertionError(f'{task_id} not found in {path}')


class EveryServerDryrunIdempotence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to validate the filled-in template with MMX.')
        cls.files = [TEMPLATE / 'playbooks/every_server.yml'] + [
            TEMPLATE / 'roles' / role / 'main.yml' for role in roles_invoked_by_every_server()
        ]
        cls.shell_tasks = [task for path in cls.files for task in extract_shell_tasks(path)]

    def test_filled_template_validates_with_mmx(self):
        root = template_values.filled_copy()
        result = subprocess.run([self.mmx, 'validate'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        explain = subprocess.run([self.mmx, 'explain', 'every_server', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(explain.returncode, 0, explain.stdout + explain.stderr)

    def test_audit_covers_every_server_and_its_roles(self):
        self.assertGreaterEqual(len(self.shell_tasks), 40)
        roles = set(roles_invoked_by_every_server())
        for expected in ('every_server', 'everyone_locked_out', 'util_server', 'validate_database_moving_in'):
            self.assertIn(expected, roles)

    def test_read_only_shell_tasks_run_in_dryrun(self):
        """A changed_when: false shell task must declare dryrun or run_script_in_dryrun: true."""
        missing = []
        for task in self.shell_tasks:
            fields = task['fields']
            if fields.get('changed_when') == 'false':
                if 'dryrun' not in fields and fields.get('run_script_in_dryrun') != 'true':
                    missing.append(f"{task['file']}:{task['line']} ({task['id']})")
        self.assertEqual(missing, [], f'Read-only shell tasks missing dryrun or run_script_in_dryrun: true: {missing}')

    def test_activate_shell_tasks_do_not_use_dryrun_true_or_mutate_in_dryrun(self):
        """A task_block activate shell task must not fake dryrun with `true` or run daemon-reload in dryrun."""
        bad = []
        for task in self.shell_tasks:
            if task['phase'] != 'activate':
                continue
            fields = task['fields']
            dryrun = fields.get('dryrun', '').strip()
            if dryrun == 'true':
                bad.append(f"{task['file']}:{task['line']} ({task['id']}): uses dryrun: 'true' instead of only_when_tracked_inputs_changed: true")
            if 'systemctl daemon-reload' in dryrun:
                bad.append(f"{task['file']}:{task['line']} ({task['id']}): runs systemctl daemon-reload in dryrun instead of only_when_tracked_inputs_changed: true")
        self.assertEqual(bad, [], '\n'.join(bad))

    def test_unconditional_printf_dryrun_tasks_have_a_guard_or_changed_when(self):
        """A shell task whose dryrun unconditionally prints a message must be guarded or declare changed_when."""
        guards = {'run_only_once_marker_file', 'skip_if_this_path_exists',
                  'skip_if_this_command_succeeds', 'run_only_if_this_command_succeeds'}
        bad = []
        for task in self.shell_tasks:
            fields = task['fields']
            dryrun = fields.get('dryrun', '').strip()
            if not dryrun.startswith('printf '):
                continue
            if task['has_when'] or 'changed_when' in fields or (guards & set(fields)):
                continue
            bad.append(f"{task['file']}:{task['line']} ({task['id']})")
        self.assertEqual(bad, [], f'Unconditional dryrun: printf tasks with no guard, when, or changed_when: {bad}')


class RecordSecurityUpdatesMarkerBehavior(unittest.TestCase):
    """Behavior of record_when_each_app_server_installed_its_waiting_security_updates in playbooks/every_server.yml."""

    def test_read_and_write_scripts_pass_bash_n(self):
        for task_id, field in (
            ('read_the_marker_file_time', 'script'),
            ('write_the_time_each_app_server_installed_its_waiting_security_updates', 'script'),
            ('write_the_time_each_app_server_installed_its_waiting_security_updates', 'dryrun'),
        ):
            script = extract_task_field('playbooks/every_server.yml', task_id, field)
            check = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, f'{task_id}.{field}: {check.stderr}')

    def test_read_the_marker_file_time_runs_in_dryrun_and_outputs_json(self):
        task = next(t for t in extract_shell_tasks(TEMPLATE / 'playbooks/every_server.yml')
                    if t['id'] == 'read_the_marker_file_time')
        self.assertEqual(task['fields'].get('run_script_in_dryrun'), 'true')
        self.assertEqual(task['fields'].get('changed_when'), 'false')
        script = task['fields']['script']
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'security_updates_installed_on_a_new_server'
            patched = script.replace('/var/lib/mmx/commands_run_once/security_updates_installed_on_a_new_server', str(marker))
            absent = subprocess.run(['bash', '-c', patched], text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(absent.stdout), {'installed_at': ''})
            marker.write_text('done\n')
            present = subprocess.run(['bash', '-c', patched], text=True, capture_output=True, check=True)
            parsed = json.loads(present.stdout)
            self.assertRegex(parsed['installed_at'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')

    def test_write_the_time_reports_change_only_when_directory_or_file_is_missing(self):
        task = next(t for t in extract_shell_tasks(TEMPLATE / 'playbooks/every_server.yml')
                    if t['id'] == 'write_the_time_each_app_server_installed_its_waiting_security_updates')
        self.assertIn('changed_when', task['fields'])
        script = task['fields']['script']
        dryrun = task['fields']['dryrun']

        def run(code, target_dir, installed_at, app_server='app001'):
            patched = code.replace('/var/lib/app_pool_for_the_load/security_updates_installed', str(target_dir))
            env = dict(os.environ, APP_SERVER=app_server, INSTALLED_AT=installed_at)
            return subprocess.run(['bash', '-c', patched], env=env, text=True, capture_output=True, check=True)

        with tempfile.TemporaryDirectory() as temporary:
            target_dir = Path(temporary) / 'security_updates_installed'
            timestamp = '2026-11-25T09:00:00Z'

            # Before directory or file exist: both dryrun and script report a change.
            self.assertNotEqual(run(dryrun, target_dir, timestamp).stdout, '')
            self.assertFalse(target_dir.exists(), 'dryrun must not create the directory')

            first_run = run(script, target_dir, timestamp)
            self.assertNotEqual(first_run.stdout, '')
            self.assertEqual((target_dir / 'app001').read_text(), timestamp + '\n')

            # Once recorded: both dryrun and script print nothing (unchanged) and never rewrite the file.
            self.assertEqual(run(dryrun, target_dir, '2026-12-01T00:00:00Z').stdout, '')
            self.assertEqual(run(script, target_dir, '2026-12-01T00:00:00Z').stdout, '')
            self.assertEqual((target_dir / 'app001').read_text(), timestamp + '\n')

            # Existing directory, missing app file, empty INSTALLED_AT: nothing to change.
            self.assertEqual(run(dryrun, target_dir, '', app_server='app002').stdout, '')
            self.assertEqual(run(script, target_dir, '', app_server='app002').stdout, '')
            self.assertFalse((target_dir / 'app002').exists())

            # Existing directory, missing app file, non-empty INSTALLED_AT: reports change, dryrun creates nothing.
            self.assertNotEqual(run(dryrun, target_dir, timestamp, app_server='app002').stdout, '')
            self.assertFalse((target_dir / 'app002').exists(), 'dryrun must not create the file')
            self.assertNotEqual(run(script, target_dir, timestamp, app_server='app002').stdout, '')
            self.assertEqual((target_dir / 'app002').read_text(), timestamp + '\n')


if __name__ == '__main__':
    unittest.main()
