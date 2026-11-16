"""Convert a native custom archive for an empty, isolated restore database.

Use a pg_restore version matching the source major version. No source connection
is opened. The existing public schema is preserved; no SQL data is rewritten.
"""
import os
import subprocess
import tempfile
from pathlib import Path

os.umask(0o077)
archive = Path(os.environ['NATIVE_ARCHIVE'])
output = Path(os.environ['PRIVATE_EXPORT_DIR'])
output.mkdir(parents=True, exist_ok=True, mode=0o700)
program = os.environ.get('PG_RESTORE', 'pg_restore')
listing = subprocess.check_output([program, '--list', str(archive)], text=True)
# New databases already have public. Exclude only the redundant schema creation.
selected = '\n'.join(line for line in listing.splitlines() if ' SCHEMA - public ' not in line) + '\n'
with tempfile.TemporaryDirectory() as scratch:
    selection = Path(scratch) / 'archive.list'
    selection.write_text(selected)
    destination = output / 'native.sql'
    if destination.exists():
        raise SystemExit('Use a new private export directory; native.sql already exists')
    subprocess.run([program, '--no-owner', '--no-privileges', '--use-list', str(selection),
                    '--file', str(destination), str(archive)], check=True)
print('Prepared private native.sql. Restore only into the assigned empty scratch database.')
