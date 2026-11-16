"""Run with python -m unittest discover -s tests -p 'cache_test.py'."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class AssetCacheTest(unittest.TestCase):
    def test_public_assets_and_private_responses(self):
        with tempfile.TemporaryDirectory(prefix='portal-cache-') as directory:
            directory = Path(directory)
            filename = 'portal.d055d47ecf33.css'
            original = (ROOT / 'assets' / filename).read_bytes()
            (directory / filename).write_bytes(original)
            (directory / 'plain.css').write_text('/* mutable */')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            env = os.environ | {
                'APP_ORIGIN': 'https://portal.example.com',
                'DATABASE_URL': 'postgresql://unused@127.0.0.1:1/unused',
                'TEST_ASSET_DIR': str(directory), 'TEST_PORT': str(port),
            }
            # Keep the production app and middleware. Only the public fixture directory changes.
            script = """import os, app, uvicorn
from starlette.staticfiles import StaticFiles
next(route for route in app.app.routes if route.path == '/assets').app = StaticFiles(directory=os.environ['TEST_ASSET_DIR'])
uvicorn.run(app.app, host='127.0.0.1', port=int(os.environ['TEST_PORT']), workers=1, log_level='error')
"""
            with tempfile.TemporaryFile() as log:
                process = subprocess.Popen([sys.executable, '-c', script], cwd=ROOT, env=env, stdout=log, stderr=log)
                try:
                    base = f'http://127.0.0.1:{port}'
                    def request(path, method='GET', headers=None):
                        try:
                            return urllib.request.urlopen(urllib.request.Request(base + path, method=method, headers=headers or {}), timeout=2)
                        except urllib.error.HTTPError as response:
                            return response
                    for _ in range(100):
                        try:
                            with request('/') as response:
                                self.assertEqual(response.status, 200)
                            break
                        except urllib.error.URLError:
                            if process.poll() is not None:
                                log.seek(0)
                                self.fail(log.read().decode())
                            time.sleep(.05)
                    else:
                        self.fail('Web process did not become ready')
                    with request('/assets/' + filename) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=31536000, immutable')
                        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                        self.assertEqual(response.read(), original)
                    with request('/assets/' + filename, method='HEAD') as response:
                        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=31536000, immutable')
                        self.assertEqual(response.read(), b'')
                    for path in ['/assets/plain.css', '/assets/%2e%2e/app.py', '/assets/missing.123456abcdef.css']:
                        with request(path) as response:
                            self.assertEqual(response.headers['Cache-Control'], 'no-store')
                            if path != '/assets/plain.css':
                                self.assertNotEqual(response.status, 200)
                    with request('/records', method='POST', headers={'Origin': 'https://untrusted.example.com'}) as response:
                        self.assertEqual(response.status, 403)
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                finally:
                    process.terminate()
                    process.wait(timeout=10)
