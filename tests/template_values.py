"""Fills the values that the template leaves for the setup to fill.

The template ships each value that only a system's setup can know empty,
with the comment `# the setup fills it`, and `every_server` refuses it
empty. A test that builds a system from a copy of the template fills them
the way the setup's chapters do: each whole line replaced, comment
included. The values are the template's earlier examples, so tests that
read them keep their meaning.
"""
import atexit
import re
import shutil
import tempfile
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'

# (file, key, values in file order): one value per empty line of that key.
VALUES = (
    ('mmx_project_settings.yml', 'project_name', ['example_systems']),
    ('mmx_project_settings.yml', 'status_page_host_name', ['status.example.com']),
    ('mmx_project_settings.yml', 'cloudflare_account_id', ['"0123456789abcdef0123456789abcdef"']),
    ('mmx_project_settings.yml', 'production_bucket', ['example-systems-backups']),
    ('mmx_project_settings.yml', 'uploads_bucket', ['example-systems-uploads-backups']),
    ('mmx_project_settings.yml', 'uploads_r2_s3_endpoint', ['https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com']),
    ('mmx_project_settings.yml', 'container_registry_read_only_username', ['example-registry-reader']),
    ('mmx_project_settings.yml', 'mmhotline', ['ops.example.com']),
    ('mmx_project_settings.yml', 'backup_url_at_the_git_host', ['https://github.com/example/example_systems.git']),
    ('inventories/servers.yml', 'public_ipv4_address', ['203.0.113.91', '203.0.113.1', '203.0.113.11', '203.0.113.21']),
    ('inventories/servers.yml', 'provider_server_id', ['"4242424242"']),
    ('inventories/servers.yml', 'wireguard_public_key', [
        '"urzzcMKwVZ9bM84MmgWUjMRxOTNn2PDtEF5it/uZFQ4="',   # desk01
        '"IUKgB/tUTa5m1zF4S5Q2+YM4Ktdtpv9rBtIiHDfqDC4="',   # desk01's laptop
        '"PFHMlKh61wvN0/mEnwE2mCdTk3PCQmr/u0lh3F8JkT0="',   # util01
        '"ZxyZitx4fq2p2omFOcF+fIsM4eUqdKy8pjgZ99jx1EI="',   # app001
        '"W4MVmeNMv9vw3FJUc9fGBUxhKPQrS17V6L96pYaVUUM="']),  # db01
    ('inventories/servers.yml', 'person_unix_username', ['alex']),
    ('inventories/servers.yml', 'laptop_name', ['work-laptop']),
    ('inventories/servers.yml', 'ssh_public_key',
     ['"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIORZZg3NlYdxJ28janK/DsJ1O0O2YgF7KN2aiEPskegs alex@work-laptop"']),
)
# Its comment is on the lines above it, so the line itself is only the key.
MMHOTLINE_BACKUP_REPLICA_URL = '"s3://example-mmhotline-backup/mmhotline?endpoint=https://s3.eu-central-003.backblazeb2.com&region=eu-central-003"'
DESK_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIR+J8OoEVNHl3P/KSWFruheEQaq8Cgw/PziDAinSTJJ alex on desk01'
UTIL01_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN4Jcw7Fq2URbtI72IZ9N/p0WjdFGpZ0VJcet+YVhxZx util01, the mmhotline user'


def fill_the_values_the_setup_fills(root):
    """Fills every empty value of the copy at root, as the setup does, and
    writes the desk's key, as the desk's start does."""
    root = Path(root)
    for name in ('mmx_project_settings.yml', 'inventories/servers.yml'):
        path = root/name
        text = path.read_text()
        for file, key, values in VALUES:
            if file != name:
                continue
            for value in values:
                text, count = re.subn(r'(?m)^([ \t]*(?:- )?%s:)[ \t]*#[^\n]*the setup fills it[^\n]*$' % re.escape(key),
                                      lambda match: match.group(1) + ' ' + value, text, count=1)
                assert count == 1, (name, key, value)
        if name == 'mmx_project_settings.yml':
            text = text.replace('  root_ssh_public_keys: []\n',
                                '  root_ssh_public_keys:\n    - %s\n    - %s\n' % (DESK_KEY, UTIL01_KEY), 1)
            text = re.sub(r'(?m)^(    mmhotline_backup_replica_url:)[ \t]*$', lambda match: match.group(1) + ' ' + MMHOTLINE_BACKUP_REPLICA_URL, text, count=1)
        else:
            text = re.sub(r'(?m)^(      production_ssh_public_key:)[ \t]*$', lambda match: match.group(1) + ' ' + DESK_KEY, text, count=1)
        assert 'the setup fills it' not in re.sub(r'(?m)^[ \t]*#.*$', '', text), name
        path.write_text(text)


_filled_copy = None


def filled_copy():
    """One filled copy of the template for this test process, for a test
    that runs mmx without changing a file. Removed when the process ends."""
    global _filled_copy
    if _filled_copy is None:
        directory = Path(tempfile.mkdtemp(prefix='filled-template-'))
        atexit.register(shutil.rmtree, directory, True)
        shutil.copytree(TEMPLATE, directory/'systems', ignore=shutil.ignore_patterns('.mmx', '__pycache__'))
        fill_the_values_the_setup_fills(directory/'systems')
        _filled_copy = directory/'systems'
    return _filled_copy
