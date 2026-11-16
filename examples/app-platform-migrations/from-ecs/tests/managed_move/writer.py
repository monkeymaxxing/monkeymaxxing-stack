#!/usr/bin/env python3
"""Keep HTTP writes running, retaining every full acknowledged record row."""
import argparse
from datetime import datetime, timezone
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request
import uuid

from proof_common import read_settings


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def request_json(base_url, path, body, cookie, timeout):
    headers = {'Content-Type': 'application/json'}
    if cookie:
        headers['Cookie'] = cookie
    request = urllib.request.Request(base_url.rstrip('/') + path,
                                     data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read()), response.headers
    except urllib.error.HTTPError as error:
        # Error pages and headers are deliberately not evidence: headers may hold cookies.
        error.close()
        return error.code, None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('settings_file', type=Path)
    args = parser.parse_args()
    settings = read_settings(args.settings_file)
    run_id = settings['run_id']
    stop_file = Path(settings['stop_file'])
    route_file = Path(settings['route_file']) if settings.get('route_file') else None
    log_file = Path(settings['log_file'])
    interval = float(settings.get('interval_seconds', 0.25))
    timeout = float(settings.get('request_timeout_seconds', 10))
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def base_url():
        return route_file.read_text().strip() if route_file else settings['base_url']

    descriptor = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, 'a') as evidence:
        def record(value):
            evidence.write(json.dumps(value, ensure_ascii=False) + '\n')
            evidence.flush()
            os.fsync(evidence.fileno())

        credentials = {'email': settings['email'], 'password': settings['password']}
        registration_status, _, _ = request_json(base_url(), '/api/register', credentials, None, timeout)
        if registration_status not in (201, 409):
            raise SystemExit('Writer registration failed, HTTP ' + str(registration_status))
        login_status, user, headers = request_json(base_url(), '/api/login', credentials, None, timeout)
        if login_status != 200:
            raise SystemExit('Writer login failed, HTTP ' + str(login_status))
        cookies = SimpleCookie()
        for value in headers.get_all('Set-Cookie', []):
            cookies.load(value)
        if 'portal_session' not in cookies:
            raise SystemExit('Writer login returned no portal session')
        cookie = 'portal_session=' + cookies['portal_session'].value
        record({'event': 'writer_started', 'run_id': run_id, 'pid': os.getpid(),
                'owner_id': user['id'], 'started_at': utc_now()})
        print(json.dumps({'event': 'writer_started', 'pid': os.getpid(), 'run_id': run_id}), flush=True)
        sequence = 0
        while not stopped and not stop_file.exists():
            sequence += 1
            nonce = str(uuid.uuid4())
            submitted = {'title': f'proof:{run_id}:{sequence}:{nonce}',
                         'description': f'proof request {nonce}'}
            started_at = utc_now()
            started_monotonic = time.monotonic()
            item = {'event': 'write_result', 'run_id': run_id, 'request_number': sequence,
                    'nonce': nonce, 'request_started_at': started_at, 'submitted': submitted}
            try:
                status, row, _ = request_json(base_url(), '/api/records', submitted, cookie, timeout)
                item['http_status_code'] = status
                item['acknowledged'] = status == 201
                if status == 201:
                    item['row'] = row
            except (OSError, ValueError) as error:
                # Do not replay an uncertain POST. The next request has a fresh nonce.
                item.update(acknowledged=False, error_type=type(error).__name__)
            item['response_received_at'] = utc_now()
            item['duration_seconds'] = round(time.monotonic() - started_monotonic, 6)
            record(item)
            # Short waits let the parent's stop file end the exact owned process quickly.
            wake = time.monotonic() + interval
            while not stopped and not stop_file.exists() and time.monotonic() < wake:
                time.sleep(min(0.1, max(0, wake - time.monotonic())))
        record({'event': 'writer_stopped', 'run_id': run_id, 'pid': os.getpid(),
                'request_count': sequence, 'stopped_at': utc_now()})
        print(json.dumps({'event': 'writer_stopped', 'pid': os.getpid(),
                          'request_count': sequence}), flush=True)


if __name__ == '__main__':
    main()
