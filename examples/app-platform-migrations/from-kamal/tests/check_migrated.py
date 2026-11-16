#!/usr/bin/env python3
"""Populate a synthetic source through HTTP, then check the saved users after each move."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app' / 'tests'))
from check_portal import Client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['populate', 'verify'])
    parser.add_argument('--url', required=True)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--expect-pending', action='store_true')
    args = parser.parse_args()
    password = os.environ['FIXTURE_PASSWORD']
    if args.action == 'populate':
        if args.manifest.exists():
            raise SystemExit('manifest already exists; choose a fresh disposable source')
        users = []
        for name in ('barbara', 'michael'):
            client = Client(args.origin)
            email = f'{name}-{secrets.token_hex(6)}@example.com'
            client.request(args.url, '/register', fields={'email': email, 'password': password})
            row = client.request(args.url, '/records', fields={'title': f'{name} invoice', 'description': 'Preserve ownership'}, expected=201)
            content = f'{name} private migration document\n'.encode()
            boundary = 'migration-' + secrets.token_hex(12)
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}.txt"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + content + f'\r\n--{boundary}--\r\n'.encode())
            document = client.request(args.url, '/documents', body=body, content_type=f'multipart/form-data; boundary={boundary}', expected=201)
            report = client.request(args.url, '/reports', body=b'', expected=201)
            users.append({'email': email, 'record_id': row['id'], 'title': f'{name} invoice', 'document_id': document['id'], 'bytes_hex': content.hex(), 'report_id': report['id'], 'session_cookie': client.cookie})
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        with open(args.manifest, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
            json.dump(users, output)
    else:
        users = json.loads(args.manifest.read_text())
    clients = []
    for user in users:
        client = Client(args.origin)
        client.cookie = user['session_cookie']
        saved_session_rows = client.request(args.url, '/records')
        assert any(row['id'] == user['record_id'] for row in saved_session_rows)
        client.request(args.url, '/login', fields={'email': user['email'], 'password': password})
        records = client.request(args.url, '/records')
        assert any(row['id'] == user['record_id'] and row['title'] == user['title'] for row in records)
        content = client.request(args.url, f"/documents/{user['document_id']}")
        assert content == bytes.fromhex(user['bytes_hex'])
        documents = client.request(args.url, '/documents')
        assert next(row for row in documents if row['id'] == user['document_id'])['sha256'] == hashlib.sha256(content).hexdigest()
        deadline = time.monotonic() + 20
        while True:
            report = client.request(args.url, f"/reports/{user['report_id']}")
            if args.expect_pending:
                assert report['output'] is None
                break
            if report['output'] is not None:
                assert report['output'] == 'record_count=1\n'
                break
            assert time.monotonic() < deadline, 'report did not complete'
            time.sleep(0.2)
        clients.append(client)
    for index, client in enumerate(clients):
        other = users[1 - index]
        client.request(args.url, f"/documents/{other['document_id']}", expected=404)
        client.request(args.url, f"/reports/{other['report_id']}", expected=404)
        client.request(args.url, f"/records/{other['record_id']}/update", fields={'title': 'wrong owner'}, expected=404)
    print('PASS: saved sessions, returning passwords, stable record/document/report IDs, owner isolation, exact private bytes, report state')


if __name__ == '__main__':
    main()
