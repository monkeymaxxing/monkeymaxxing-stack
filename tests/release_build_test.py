#!/usr/bin/env python3
"""The release build of set-up-outside-services writes its own pin.

  python3 tests/release_build_test.py

Runs set_up_outside_services/build_release_archive.sh in a copy of the
files it reads, with stand-ins for go, tar, gzip and sha256sum, and checks
that it refuses a version other than the template's stack_version and
otherwise writes the archive's version, address and SHA-256 into
stack_software.set_up_outside_services. A real build needs Linux and Go.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = 'skills/monkeymaxxing-stack/systems_repository_template'
SHA256 = 'ab' * 32
STAND_INS = {
    # go build ... -o PATH .
    'go': '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do [ "$1" = -o ] && { echo program > "$2"; }; shift; done\n',
    'tar': '#!/bin/sh\necho archive\n',
    'gzip': '#!/bin/sh\ncat\n',
    'sha256sum': f'#!/bin/sh\necho "{SHA256}  $1"\n',
}


class ReleaseBuild(unittest.TestCase):
    def build(self, version):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'set_up_outside_services').mkdir()
            shutil.copy(ROOT/'set_up_outside_services/build_release_archive.sh', root/'set_up_outside_services')
            shutil.copy(ROOT/'LICENSE', root/'LICENSE')
            (root/TEMPLATE).mkdir(parents=True)
            for name in ('mmx_project_settings.yml', 'monkeymaxxing_stack_checklist.yml'):
                shutil.copy(ROOT/TEMPLATE/name, root/TEMPLATE/name)
            binary = root/'bin'
            binary.mkdir()
            for name, text in STAND_INS.items():
                (binary/name).write_text(text)
                (binary/name).chmod(0o755)
            result = subprocess.run(['bash', str(root/'set_up_outside_services/build_release_archive.sh'), version, str(root/'out')],
                                    text=True, capture_output=True,
                                    env={**os.environ, 'PATH': f"{binary}:{os.environ['PATH']}"})
            settings = (root/TEMPLATE/'mmx_project_settings.yml').read_text()
            built = sorted(path.name for path in (root/'out').glob('*')) if (root/'out').exists() else []
        return result, settings, built

    def stack_version(self):
        return re.search(r'^stack_version: *(\S+)', (ROOT/TEMPLATE/'monkeymaxxing_stack_checklist.yml').read_text(), re.M)[1]

    def test_the_build_writes_the_archives_pin(self):
        version = self.stack_version()
        result, settings, built = self.build(version)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(built, [f'set-up-outside-services-{version}-linux-amd64.tar.gz'])
        pin = re.search(r'^    set_up_outside_services:\n((?:      .*\n)+)', settings, re.M)[1]
        self.assertIn(f'      version: "{version}"\n', pin)
        self.assertIn(f'/{version}/set-up-outside-services-{version}-linux-amd64.tar.gz\n', pin)
        self.assertIn(f'      sha256: "{SHA256}"\n', pin)
        # The other pins are left as they were.
        original = (ROOT/TEMPLATE/'mmx_project_settings.yml').read_text()
        self.assertEqual(settings.replace(pin, ''), re.sub(r'(^    set_up_outside_services:\n)(?:      .*\n)+', r'\1', original, flags=re.M))

    def test_a_version_other_than_stack_version_builds_nothing(self):
        result, settings, built = self.build('1999-01')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stack_version', result.stderr)
        self.assertIn('Nothing was built.', result.stderr)
        self.assertEqual(built, [])
        self.assertEqual(settings, (ROOT/TEMPLATE/'mmx_project_settings.yml').read_text())


if __name__ == '__main__':
    unittest.main()
