#!/usr/bin/env python3
"""Exercise an already-running isolated portal. Never starts services or prints cookies.

Run on an assigned integration host. Portal A and B share a database and bucket.
The worker must already be running. Test accounts/objects remain for restore checks.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request


class Client:
    def __init__(self, origin):
        self.origin = origin
        self.cookie = None

    def request(self, base, path, fields=None, body=None, content_type=None, expected=200, origin=None):
        headers = {"Accept": "application/json", "Origin": origin or self.origin}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if fields is not None:
            body = urllib.parse.urlencode(fields).encode()
            content_type = "application/x-www-form-urlencoded"
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(base.rstrip("/") + path, data=body, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == expected, f"{path}: expected {expected}, received {response.status}"
            assert response.headers.get("Cache-Control") == "no-store", path
            cookie = response.headers.get("Set-Cookie")
            if cookie:
                # Deletion cookies contain no token. Django omits HttpOnly/Secure
                # when expiring the empty cookie; live session cookies need both.
                flags = ("SameSite=Lax", "Path=/") if "max-age=0" in cookie.lower() else ("Secure", "HttpOnly", "SameSite=Lax", "Path=/")
                for flag in flags:
                    assert flag.lower() in cookie.lower(), "unsafe cookie"
                self.cookie = cookie.split(";", 1)[0]
            data = response.read()
            if "application/json" in response.headers.get("Content-Type", ""):
                return json.loads(data)
            return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-a", required=True)
    parser.add_argument("--server-b", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    # Never put passwords into command arguments or reports.
    password = os.environ["FIXTURE_PASSWORD"]
    a, b, origin = args.server_a, args.server_b, args.origin
    first, second = Client(origin), Client(origin)
    first.request(a, "/healthz")
    with urllib.request.urlopen(urllib.request.Request(a + "/", headers={"Accept": "text/html"}), timeout=5) as homepage:
        assert homepage.headers.get("Cache-Control") == "no-store"
        page = homepage.read()
    assert re.search(rb'<html\s+[^>]*\blang="en"', page) and b'<title>Private customer portal</title>' in page
    asset = re.search(rb'href="(/assets/[^\"]+\.css)"', page).group(1).decode()
    with urllib.request.urlopen(a + asset, timeout=5) as response:
        assert response.status == 200 and b'font:' in response.read()
    second.request(b, "/records", expected=401)
    suffix = secrets.token_hex(8)
    first_email = f"barbara-{suffix}@example.com"
    for client, email in ((first, first_email), (second, f"michael-{suffix}@example.com")):
        client.request(a, "/register", fields={"email": email, "password": password})
        client.request(b, "/records")  # Same token, another app process.
    first.request(a, "/records", fields={"title": "cross-site"}, origin="https://evil.example.com", expected=403)
    record = first.request(a, "/records", fields={"title": "Original invoice", "description": "Synthetic"}, expected=201)
    identifier = record["id"]
    assert second.request(b, "/records") == []
    second.request(b, f"/records/{identifier}/update", fields={"title": "Stolen"}, expected=404)
    second.request(b, f"/records/{identifier}/delete", body=b"", expected=404)
    first.request(b, f"/records/{identifier}/update", fields={"title": "Updated invoice", "description": "Retained"})
    assert first.request(a, "/records") == [{"id": identifier, "title": "Updated invoice", "description": "Retained"}]
    data = b"Synthetic private document\n"
    boundary = "portal-" + secrets.token_hex(16)
    multipart = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"note.txt\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + data + f"\r\n--{boundary}--\r\n".encode())
    document = first.request(a, "/documents", body=multipart, content_type=f"multipart/form-data; boundary={boundary}", expected=201)
    assert first.request(b, f"/documents/{document['id']}") == data
    second.request(b, f"/documents/{document['id']}", expected=404)
    assert second.request(a, "/documents") == []
    documents = first.request(b, "/documents")
    assert documents[0]["sha256"] == hashlib.sha256(data).hexdigest()
    job = first.request(a, "/reports", body=b"", expected=201)
    deadline = time.monotonic() + 15
    while True:
        reports = first.request(b, "/reports")
        report = next(value for value in reports if value["id"] == job["id"])
        if report["output"] is not None:
            assert report["output"] == "record_count=1\n"
            break
        assert time.monotonic() < deadline, "worker did not finish report within 15 seconds"
        time.sleep(0.25)
    second.request(a, f"/reports/{job['id']}", expected=404)
    assert second.request(a, "/reports") == []
    first.request(a, f"/records/{identifier}/delete", body=b"")
    assert first.request(b, "/records") == []
    # Revocation must be checked using the OLD token, not the cleared browser cookie.
    old_cookie = first.cookie
    first.request(a, "/logout", body=b"")
    first.cookie = old_cookie
    first.request(b, "/records", expected=401)
    first.request(a, "/login", fields={"email": first_email, "password": password})
    first.request(b, "/documents")
    print("PASS: accounts, cross-server sessions/revocation, ownership, CRUD, object bytes/hash, report completion")
    print("Retained synthetic account suffix for restore queries:", suffix)


if __name__ == "__main__":
    main()
