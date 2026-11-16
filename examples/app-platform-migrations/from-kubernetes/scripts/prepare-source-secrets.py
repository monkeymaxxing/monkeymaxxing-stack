#!/usr/bin/env python3
"""Generate credentials for the isolated synthetic source, without printing values."""
import os
from pathlib import Path
import secrets
import sys

directory = Path(sys.argv[1])
directory.mkdir(mode=0o700)
password = secrets.token_hex(24)
values = {
    "postgres-password": password,
    "database-url": f"postgresql://portal:{password}@postgres:5432/portal?target_session_attrs=read-write",
    "fixture-password": secrets.token_urlsafe(24),
}
for name, value in values.items():
    descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(value)
print("Synthetic source credentials saved in the requested protected directory.")
