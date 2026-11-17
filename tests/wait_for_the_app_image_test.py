#!/usr/bin/env python3
"""server_management_scripts/wait_for_the_app_image: the laptop command that
waits until the registry holds an app image, so a failed or missing build
shows before a deploy.

  python3 tests/wait_for_the_app_image_test.py

Runs the command with a stand-in curl that plays a registry with the
standard token login, and the stand-in clock of desk_waits_test.py.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from desk_waits_test import CLOCK_START, FAKE_DATE, FAKE_SLEEP, printed_lines, seconds_between_lines

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
COMMAND = T/'server_management_scripts/wait_for_the_app_image'
IMAGE = 'ghcr.io/example/shop:0123456789abcdef0123456789abcdef01234567'
LOGIN = 'YWxleDpyZWFkLW9ubHktdG9rZW4='  # base64 of alex:read-only-token

# A stand-in registry. registry.json says whether the image is private and
# the manifest's status; every call is recorded with its command line and
# the configuration curl read from standard input.
FAKE_CURL = '''#!/usr/bin/env python3
import json, os, sys
here = os.path.dirname(os.path.abspath(sys.argv[0]))
registry = json.load(open(os.path.join(here, 'registry.json')))
args = sys.argv[1:]
config = sys.stdin.read() if '-K' in args else ''
url = args[-1]
open(os.path.join(here, 'calls.jsonl'), 'a').write(json.dumps({'args': args, 'config': config}) + '\\n')
if url == 'https://ghcr.io/v2/':
    print('HTTP/2 401\\r\\nwww-authenticate: Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:user/image:pull"\\r\\n')
elif url == 'https://ghcr.io/token':
    if registry['private'] and 'Basic %s' % registry['login'] not in config:
        sys.exit(22)
    print(json.dumps({'token': 'registry-token'}))
elif url == 'https://ghcr.io/v2/example/shop/manifests/0123456789abcdef0123456789abcdef01234567':
    assert 'Bearer registry-token' in config
    print(open(os.path.join(here, 'manifest-status')).read().strip(), end='')
else:
    sys.exit(6)
'''


class WaitForTheAppImage(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.binary = self.root/'bin'
        self.binary.mkdir()
        for name, text in (('curl', FAKE_CURL), ('date', FAKE_DATE), ('sleep', FAKE_SLEEP)):
            (self.binary/name).write_text(text)
            (self.binary/name).chmod(0o755)
        self.home = self.root/'home'
        self.home.mkdir()
        self.registry = {'private': False, 'login': LOGIN}
        self.events = []
        self.set_manifest_status('404')

    def set_manifest_status(self, status):
        (self.binary/'manifest-status').write_text(status)

    def manifest_appears_at(self, seconds):
        self.events.append({'at': CLOCK_START + seconds, 'how': 'write',
                            'path': str(self.binary/'manifest-status'), 'text': '200'})

    def run_command(self, *arguments):
        (self.binary/'registry.json').write_text(json.dumps(self.registry))
        (self.binary/'events.json').write_text(json.dumps(self.events))
        (self.binary/'date.clock').write_text(str(CLOCK_START))
        env = {'HOME': str(self.home), 'PATH': f'{self.binary}:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin'}
        return subprocess.run(['bash', str(COMMAND), *arguments], text=True, capture_output=True, env=env, timeout=120)

    def calls(self):
        return [json.loads(line) for line in (self.binary/'calls.jsonl').read_text().splitlines()]

    def test_wrong_arguments_are_refused_and_nothing_is_asked(self):
        for arguments in ([], ['shop:latest'], ['ghcr.io/example/shop'], ['ghcr.io/example/shop:'],
                          ['https://ghcr.io/example/shop:abc'], ['ghcr.io/example/shop:a b'], [IMAGE, 'extra'],
                          [IMAGE, '--at-most-minutes', '0'], [IMAGE, '--at-most-minutes', 'x'], ['-K', '/etc/passwd']):
            with self.subTest(arguments=arguments):
                result = self.run_command(*arguments)
                self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
                self.assertFalse((self.binary/'calls.jsonl').exists())

    def test_an_image_at_the_registry_is_found_and_the_tests_are_not_claimed(self):
        self.set_manifest_status('200')
        result = self.run_command(IMAGE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('says nothing about whether the app\'s tests ran', result.stdout)

    def test_the_wait_ends_when_the_build_pushes_the_image_with_a_line_every_minute(self):
        self.manifest_appears_at(200)
        result = self.run_command(IMAGE)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('is not at the registry yet', result.stdout)
        self.assertLessEqual(max(seconds_between_lines(result.stdout)), 60)

    def test_a_missing_image_at_the_bound_says_so_and_what_it_means(self):
        result = self.run_command(IMAGE, '--at-most-minutes', '3')
        self.assertEqual(result.returncode, 1)
        last = printed_lines(result.stdout)[-1]
        self.assertIn('is not at the registry after 3 minutes', last)
        self.assertIn('build failed, or still runs', last)
        self.assertIn('deploy nothing with this tag', last)
        self.assertLessEqual(max(seconds_between_lines(result.stdout)), 60)

    def test_a_private_image_is_read_with_the_laptops_saved_login_kept_off_the_command_line(self):
        self.registry['private'] = True
        self.set_manifest_status('200')
        (self.home/'.config/containers').mkdir(parents=True)
        (self.home/'.config/containers/auth.json').write_text(json.dumps({'auths': {'ghcr.io': {'auth': LOGIN}}}))
        result = self.run_command(IMAGE)
        self.assertEqual(result.returncode, 0, result.stdout)
        for call in self.calls():
            self.assertNotIn(LOGIN, ' '.join(call['args']))
            self.assertNotIn('registry-token', ' '.join(call['args']))
        self.assertTrue(any(LOGIN in call['config'] for call in self.calls()))

    def test_a_private_image_without_a_login_says_it_cannot_tell_and_never_says_missing(self):
        self.registry['private'] = True
        (self.home/'.docker').mkdir()
        (self.home/'.docker/config.json').write_text(json.dumps({'auths': {'other.example': {'auth': LOGIN}}}))
        result = self.run_command(IMAGE)
        self.assertEqual(result.returncode, 3)
        self.assertIn('cannot tell whether it was built', result.stdout)
        self.assertIn('not a sign that the build failed', result.stdout)
        self.assertFalse(any(LOGIN in call['config'] for call in self.calls()))


if __name__ == '__main__':
    unittest.main()
