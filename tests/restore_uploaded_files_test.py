#!/usr/bin/env python3
"""Check the uploaded-file restores in operating_procedures/restore_an_uploaded_file.md.

  MMX_BINARY=/path/to/mmx python3 tests/restore_uploaded_files_test.py

The procedure's two one-time playbooks are copied, as written, into a copy of
the template, where `mmx validate` and `mmx explain` must accept them. The
whole-app restore's counting task runs against a stand-in rclone that prints
rclone's --combined report, so the counts, the rule for files added after the
chosen time, and the refusal of an empty backup are checked without a bucket.
A real B2 and R2 must still prove rclone's comparison and the copy itself.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_values  # noqa: E402

T = Path(__file__).resolve().parents[1] / 'skills/monkeymaxxing-stack/systems_repository_template'
PROCEDURE = (T / 'operating_procedures/restore_an_uploaded_file.md').read_text()


def playbook_after(heading):
    section = PROCEDURE.split(heading, 1)[1]
    block = re.search(r'\n   ```yaml\n(   fleet_stages:\n.*?)\n   ```\n', section, re.S)[1]
    return textwrap.dedent(block)


WHOLE_APP = playbook_after('## Restore all of an app\'s uploaded files')
LISTED = playbook_after('## Restore listed files')


def counting_script():
    body = re.search(r'COUNT_WHAT_THE_RESTORE_CHANGES: \|\n(.*?)\n\s+RESTORE_AS_OF:', WHOLE_APP, re.S)[1]
    return textwrap.dedent(body)


RCLONE = '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['RCLONE_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
sys.stdout.write(os.environ.get('REPORT', ''))
sys.exit(int(os.environ.get('RCLONE_EXIT', '0')))
'''


class CountingBeforeTheWholeAppRestore(unittest.TestCase):
    def count(self, report, rule='keep', exit_code=0):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary)
            (root / 'rclone').write_text(RCLONE)
            (root / 'rclone').chmod(0o755)
            log = root / 'rclone.log'
            self.assertIn('script: bash -c "$COUNT_WHAT_THE_RESTORE_CHANGES"', WHOLE_APP)
            self.assertIn('dryrun: bash -c "$COUNT_WHAT_THE_RESTORE_CHANGES"', WHOLE_APP)
            result = subprocess.run(['bash', '-c', counting_script()], text=True, capture_output=True, env={
                **os.environ, 'PATH': f"{root}:{os.environ['PATH']}", 'RCLONE_LOG': str(log),
                'REPORT': report, 'RCLONE_EXIT': str(exit_code),
                'RESTORE_AS_OF': '2026-11-03T14:00:00Z', 'FILES_ADDED_AFTER_THE_TIME': rule,
                'RCLONE_SETTINGS': '/var/lib/mmhotline/uploads_backup_rclone.conf',
                'BACKUP_BUCKET': 'backup-bucket', 'UPLOADS_BUCKET': 'shop-uploads'})
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    # rclone's --combined report: + only in the backup, * different, = the same, - only in R2.
    REPORT = '+ customers/ana/passport.pdf\n+ b\n* c\n= d\n= e\n= f\n- added-later\n'

    def test_keep_prints_only_counts_and_compares_without_writing(self):
        result, calls = self.count(self.REPORT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         'the backup held 6 files of shop at 2026-11-03T14:00:00Z\n'
                         'the restore writes 3 files into R2: 2 missing from R2 and 1 changed since\n'
                         '3 files are the same in R2 and stay as they are\n'
                         '1 files in R2 are not in the backup at that time: the restore keeps them\n')
        self.assertNotIn('passport', result.stdout + result.stderr)
        self.assertEqual(calls, [['--config', '/var/lib/mmhotline/uploads_backup_rclone.conf', 'copy', '--dry-run',
                                  '--quiet', '--use-server-modtime', '--b2-version-at', '2026-11-03T14:00:00Z',
                                  '--combined', '-', 'uploads_backup:backup-bucket/shop', 'uploads_r2:shop-uploads']])

    def test_delete_compares_as_a_sync_and_says_it_deletes(self):
        result, calls = self.count(self.REPORT, rule='delete')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('the restore deletes them', result.stdout)
        self.assertEqual(calls[0][2], 'sync')

    def test_an_empty_backup_refuses(self):
        # With sync, a backup that held nothing at the chosen time would empty the app's bucket.
        for report in ('', '- only-in-r2\n'):
            with self.subTest(report=report):
                result, _ = self.count(report, rule='delete')
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertIn('the backup held no file of shop at 2026-11-03T14:00:00Z', result.stderr)

    def test_a_failed_comparison_and_an_unknown_rule_refuse(self):
        result, _ = self.count(self.REPORT, exit_code=3)
        self.assertEqual(result.returncode, 1)
        self.assertIn('rclone exited 3 while comparing', result.stderr)
        result, calls = self.count(self.REPORT, rule='maybe')
        self.assertEqual(result.returncode, 1)
        self.assertIn('use keep or delete', result.stderr)
        self.assertEqual(calls, [])


class ThePlaybooksAsWritten(unittest.TestCase):
    def test_mmx_accepts_both_playbooks(self):
        mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not mmx:
            self.skipTest('Set MMX_BINARY to validate the playbooks with MMX.')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            root = Path(temporary) / 'systems'
            shutil.copytree(T, root, ignore=shutil.ignore_patterns('.mmx'))
            template_values.fill_the_values_the_setup_fills(root)
            (root / 'one_time_playbooks').mkdir(exist_ok=True)
            for name, text in (('2026-11-03_restore_all_uploaded_files_of_shop_on_util01', WHOLE_APP),
                               ('2026-11-03_restore_uploaded_files_of_shop_on_util01', LISTED)):
                (root / 'one_time_playbooks' / f'{name}.yml').write_text(text)
                for command in (['validate', name], ['explain', name, '--json']):
                    with self.subTest(name=name, command=command[0]):
                        result = subprocess.run([mmx, *command], cwd=root, text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
