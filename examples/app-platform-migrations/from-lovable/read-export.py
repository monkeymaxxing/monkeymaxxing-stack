#!/usr/bin/env python3
"""Read pg_restore's COPY sections without executing source SQL."""
import argparse
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


def decode_copy(value):
    if value == r'\N':
        return None
    escapes = {b'b': b'\b', b'f': b'\f', b'n': b'\n', b'r': b'\r', b't': b'\t', b'v': b'\v', b'\\': b'\\'}
    def replace(match):
        value = match[1]
        if value.startswith(b'x'):
            return bytes([int(value[1:], 16)])
        if value[:1] in b'01234567':
            return bytes([int(value, 8)])
        return escapes.get(value, value)
    return re.sub(rb'\\([0-7]{1,3}|x[0-9a-fA-F]{1,2}|.)', replace, value.encode('utf-8')).decode('utf-8')


def copy_tables(sql):
    tables = {}
    lines = iter(sql.splitlines())
    for line in lines:
        match = re.fullmatch(r'COPY ([\w.]+) \(([^)]+)\) FROM stdin;', line)
        if not match:
            continue
        name, columns = match[1], match[2].split(', ')
        if name in tables:
            raise ValueError('Duplicate COPY section: ' + name)
        rows = []
        for line in lines:
            if line == r'\.':
                break
            values = [decode_copy(v) for v in line.split('\t')]
            if len(values) != len(columns):
                raise ValueError('Unexpected COPY column count: ' + name)
            rows.append(dict(zip(columns, values)))
        else:
            raise ValueError('Unterminated COPY section: ' + name)
        tables[name] = rows
    return tables


def read_archive(archive, pg_restore):
    with tempfile.TemporaryDirectory(prefix='lovable-export-') as folder:
        target = Path(archive)
        if zipfile.is_zipfile(target):
            with zipfile.ZipFile(target) as zipped:
                files = [i for i in zipped.infolist() if not i.is_dir()]
                if len(files) != 1 or not files[0].filename.endswith('.backup'):
                    raise ValueError('Expected one PostgreSQL .backup file in the ZIP wrapper')
                target = Path(folder) / 'export.backup'
                target.write_bytes(zipped.read(files[0]))
                target.chmod(0o600)
        result = subprocess.run([pg_restore, '--no-owner', '--no-privileges', '--file=-', str(target)],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError('pg_restore could not read the archive; check the archive and client version')
        return copy_tables(result.stdout)


def export_snapshot(tables):
    required = ['auth.users', 'auth.identities', 'public.records', 'public.documents', 'public.report_jobs',
                'storage.buckets', 'storage.objects', 'cron.job', 'drizzle.__drizzle_migrations']
    for table in required:
        if table not in tables:
            raise ValueError('Missing required COPY section: ' + table)
    # The replacement must not silently bypass a source account's stronger sign-in requirements.
    for table in ('auth.mfa_factors', 'auth.webauthn_credentials'):
        if tables.get(table):
            raise ValueError('MFA or passkeys require an account migration design before conversion')
    if any(row.get('is_sso_user') == 't' or row.get('is_anonymous') == 't' or not row.get('email_confirmed_at')
           for row in tables['auth.users']):
        raise ValueError('SSO, anonymous, or unconfirmed accounts require an account migration design')
    # Keep hashes private. Do not carry provider tokens or active source sessions.
    users = [{key: row.get(key) for key in ('id', 'email', 'encrypted_password', 'email_confirmed_at', 'banned_until')}
             for row in tables['auth.users']]
    if any(not u['encrypted_password'] or not u['encrypted_password'].startswith(('$2a$', '$2b$', '$2y$')) for u in users):
        raise ValueError('This conversion requires bcrypt password accounts; design recovery for other identities')
    if any(row.get('provider') != 'email' for row in tables['auth.identities']):
        raise ValueError('This conversion requires email identities; configure external sign-in providers separately')
    return {'format_version': 1, 'users': users,
            **{name: tables['public.' + name] for name in ('records', 'documents', 'report_jobs')},
            'storage_buckets': tables['storage.buckets'], 'storage_objects': tables['storage.objects'],
            'schedules': tables['cron.job'], 'source_migrations': tables['drizzle.__drizzle_migrations']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('output')
    parser.add_argument('--pg-restore', default='pg_restore')
    args = parser.parse_args()
    snapshot = export_snapshot(read_archive(args.archive, args.pg_restore))
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        json.dump(snapshot, file, indent=2)
        file.write('\n')
    print(json.dumps({'users': len(snapshot['users']), 'records': len(snapshot['records']),
                      'documents': len(snapshot['documents']), 'report_jobs': len(snapshot['report_jobs']),
                      'schedules': len(snapshot['schedules'])}))


if __name__ == '__main__':
    main()
