#!/usr/bin/env python3
"""Copy retained logs to this desk and verified encrypted copies to the backup bucket."""
import argparse
import configparser
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request

# Retained MMX details can include secrets. All archives stay private and backup copies are encrypted.
COLLECT_FILES = r'''set -eu
paths=()
for path in /var/log /var/lib/mmx /run/mmx/private /var/lib/mmhotline/systems_repository/.mmx /var/lib/servers-mmx/systems_repository/.mmx /var/lib/restore_drill/latest_result.json /var/lib/restore_drill/attempt.*/created_server.json; do
    if [ -e "$path" ]; then paths+=("${path#/}"); else printf 'Not present: %s\n' "$path" >&2; fi
done
# Live log files can grow during collection. tar records that fact on stderr.
if tar -C / -czf - "${paths[@]}"; then
    exit 0
else
    status=$?
    # GNU tar returns 1 when live files changed while read. Read errors return 2.
    [ "$status" -eq 1 ] || exit "$status"
fi
'''


# The SSH settings beside this script. The person runs the copy that the
# last desk review installed, as root, so its SSH settings are the
# reviewed ones too, never the pulled repository's: OpenSSH runs commands
# from SSH settings (ProxyCommand, Match exec). The servers' host keys,
# ssh/known_hosts, still come from the pulled repository, which is data.
SSH_SETTINGS = Path(__file__).resolve().parents[1]/'ssh/config'


def ssh_to(address):
    return ['ssh', '-F', str(SSH_SETTINGS), '-o', 'BatchMode=yes', 'root@' + address]


def run(arguments, **options):
    return subprocess.run(arguments, check=True, **options)


def checksum(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def signed_request(method, key, config, source=None):
    """S3 Signature Version 4, using the existing bucket-scoped backup identity."""
    endpoint = config['repo1-s3-bucket'] + '.' + config['repo1-s3-endpoint']
    path = '/' + urllib.parse.quote(key, safe='/')
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
    payload_hash = checksum(source) if source else hashlib.sha256(b'').hexdigest()
    headers = {'host': endpoint, 'x-amz-content-sha256': payload_hash, 'x-amz-date': timestamp}
    header_names = ';'.join(sorted(headers))
    canonical = '\n'.join([method, path, '', ''.join(name + ':' + headers[name] + '\n' for name in sorted(headers)), header_names, payload_hash])
    scope = day + '/' + config['repo1-s3-region'] + '/s3/aws4_request'
    message = 'AWS4-HMAC-SHA256\n' + timestamp + '\n' + scope + '\n' + hashlib.sha256(canonical.encode()).hexdigest()
    signing_key = ('AWS4' + config['repo1-s3-key-secret']).encode()
    for value in (day, config['repo1-s3-region'], 's3', 'aws4_request'):
        signing_key = hmac.new(signing_key, value.encode(), hashlib.sha256).digest()
    signature = hmac.new(signing_key, message.encode(), hashlib.sha256).hexdigest()
    headers['Authorization'] = 'AWS4-HMAC-SHA256 Credential=' + config['repo1-s3-key'] + '/' + scope + ', SignedHeaders=' + header_names + ', Signature=' + signature
    if source:
        headers['Content-Length'] = str(source.stat().st_size)
        headers['Content-Type'] = 'application/octet-stream'
        with source.open('rb') as body:
            request = urllib.request.Request('https://' + endpoint + path, data=body, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=60) as response:
                response.read()
    else:
        request = urllib.request.Request('https://' + endpoint + path, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            return hashlib.file_digest(response, 'sha256').hexdigest()


def collect(name, directory, ssh=None, checkout=None):
    directory.mkdir(mode=0o700)
    prefix = ssh or []
    with (directory/'journal.export').open('wb') as output, (directory/'collection.log').open('wb') as errors:
        run([*prefix, 'journalctl', '--no-pager', '--output=export'], stdout=output, stderr=errors)
        with (directory/'retained-files.tar.gz').open('wb') as output:
            if ssh:
                run([*ssh, 'bash', '-s'], input=COLLECT_FILES.encode(), stdout=output, stderr=errors)
            else:
                run(['bash', '-c', COLLECT_FILES], stdout=output, stderr=errors)
    if checkout and (checkout/'.mmx').exists():
        with tarfile.open(directory/'desk-run-records.tar.gz', 'w:gz') as archive:
            archive.add(checkout/'.mmx', arcname='.mmx')
    (directory/'collected-at.txt').write_text(name + '\n' + datetime.datetime.now(datetime.timezone.utc).isoformat() + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desk-name', required=True, help='this inventory desk, such as desk01')
    parser.add_argument('--database-server-with-backup-credentials', required=True, help='a database server, such as db01')
    parser.add_argument('--output-dir', required=True, type=Path, help='private evidence directory outside the Git repository')
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() != 0:
        parser.error('Run as root on the kept systems desk, preserving SSH_AUTH_SOCK.')
    if not Path('/etc/systems-desk/everyone-locked-out').exists():
        parser.error('Press the lock-out button, sudo lock-everyone-out, on this desk before collecting evidence.')
    inventory = json.loads(subprocess.check_output(['mmx', 'nodes', '--json']))
    nodes = {node['name']: node for node in inventory['nodes']}
    if args.desk_name not in inventory['groups']['systems_desks'] or nodes[args.desk_name]['address'] != '127.0.0.1':
        parser.error('--desk-name must name this loopback-managed systems desk.')
    if args.database_server_with_backup_credentials not in inventory['groups']['database_servers']:
        parser.error('--database-server-with-backup-credentials must name a production database server.')
    if not args.output_dir.is_absolute() or args.output_dir.resolve().is_relative_to(Path.cwd().resolve()):
        parser.error('--output-dir must be an absolute path outside the systems repository.')
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'), dir=args.output_dir))
    (attempt/'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    failed = []
    for name, node in nodes.items():
        if 'systems_desks' in node['groups'] and name != args.desk_name:
            continue  # Another desk is preserved through its provider disk snapshot.
        try:
            ssh = None if name == args.desk_name else ssh_to(node['address'])
            collect(name, attempt/name, ssh, Path.cwd() if ssh is None else None)
            print(name + ': logs copied to ' + str(attempt/name), flush=True)
        except (OSError, subprocess.CalledProcessError) as error:
            failed.append(name)
            print(name + ': collection failed: ' + str(error), flush=True)
    # Read credentials into memory only. Never print, persist or pass the values as arguments.
    remote = ssh_to(nodes[args.database_server_with_backup_credentials]['address'])
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(subprocess.check_output([*remote, 'cat', '/etc/pgbackrest/pgbackrest.conf'], text=True))
    backup = config['global']
    manifest = []
    for directory in sorted(path for path in attempt.iterdir() if path.is_dir() and path.name not in failed):
        archive = attempt/(directory.name + '.tar.gz')
        with tarfile.open(archive, 'w:gz') as output:
            output.add(directory, arcname=directory.name)
        encrypted = archive.with_suffix(archive.suffix + '.enc')
        run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-iter', '200000', '-md', 'sha256', '-salt', '-pass', 'stdin', '-in', str(archive), '-out', str(encrypted)],
            input=(backup['repo1-cipher-pass'] + '\n').encode())
        key = 'break_in_evidence/' + attempt.name + '/' + encrypted.name
        signed_request('PUT', key, backup, encrypted)
        if signed_request('GET', key, backup) != checksum(encrypted):
            raise RuntimeError('The backup copy differs: ' + key)
        manifest.append({'node': directory.name, 'archive_sha256': checksum(archive), 'encrypted_sha256': checksum(encrypted),
                         'bucket': backup['repo1-s3-bucket'], 'object_key': key})
        print(directory.name + ': encrypted backup copy verified: ' + key, flush=True)
    manifest_path = attempt/'manifest.json'
    manifest_path.write_text(json.dumps({'copies': manifest, 'failed_nodes': failed}, indent=2) + '\n')
    key = 'break_in_evidence/' + attempt.name + '/manifest.json'
    signed_request('PUT', key, backup, manifest_path)
    if signed_request('GET', key, backup) != checksum(manifest_path):
        raise RuntimeError('The backup manifest differs: ' + key)
    print('Evidence directory: ' + str(attempt), flush=True)
    if failed:
        raise SystemExit('Evidence is incomplete. Snapshot the unavailable servers at the provider: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
