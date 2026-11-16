#!/usr/bin/env python3
"""Make private settings for a disposable PostgreSQL/container rehearsal."""
import argparse
import os
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument("--settings-dir", type=Path, required=True)
parser.add_argument("--fixture-password-file", type=Path, required=True)
parser.add_argument("--database-port", type=int, required=True)
parser.add_argument("--first-http-port", type=int, required=True)
parser.add_argument("--storage-url", required=True)
parser.add_argument("--bucket-name", required=True)
args = parser.parse_args()
password = secrets.token_hex(24)
fixture_password = args.fixture_password_file.read_text().strip()
args.settings_dir.mkdir(mode=0o700)
values = {
    "postgres-password": password,
    "portal.env": f"""DATABASE_URL=postgresql://portal:{password}@127.0.0.1:{args.database_port}/portal?target_session_attrs=read-write&connect_timeout=2
AWS_ENDPOINT_URL_S3={args.storage_url}
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=synthetic
AWS_SECRET_ACCESS_KEY=synthetic
BUCKET_NAME={args.bucket_name}
S3_FORCE_PATH_STYLE=true
PORT={args.first_http_port}
WEB_CONCURRENCY=2
COOKIE_SECURE=false
NODE_ENV=production
FIXTURE_PASSWORD={fixture_password}
APP_URL=http://127.0.0.1:{args.first_http_port}
SECOND_APP_URL=http://127.0.0.1:{args.first_http_port + 1}
EXPORT_DIR=/export
APP_DIR=/app
""",
}
for name, value in values.items():
    descriptor = os.open(args.settings_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(value)
print("Disposable rehearsal settings saved. Credentials were not printed.")
