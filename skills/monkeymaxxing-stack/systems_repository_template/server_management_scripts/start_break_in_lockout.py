#!/usr/bin/env python3
"""Enter server containment over SSH before asking a busy MMX node to admit work."""
import concurrent.futures
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def remote(kept_address, kept_key, removed_peers, session_script):
    """Runs on one server; never runs on a systems desk."""
    ipaddress.IPv4Address(kept_address)
    if '\n' in kept_key or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?', kept_key):
        raise RuntimeError('The desk that keeps access needs one production Ed25519 public key.')
    Path('/root/.ssh/authorized_keys').write_text('from="' + kept_address + '" ' + kept_key + '\n')
    Path('/root/.ssh/authorized_keys').chmod(0o600)
    Path('/etc/ssh/sshd_config.d/00-incident-lockout.conf').write_text('AllowUsers root@' + kept_address + '\n')
    subprocess.run(['sshd','-t'],check=True)
    subprocess.run(['systemctl','reload','ssh'],check=True)
    config=Path('/etc/wireguard/wg0.conf')
    sections=re.split(r'(?m)(?=^\[Peer\]\s*$)',config.read_text())
    for peer in removed_peers:
        subprocess.run(['wg','set','wg0','peer',peer,'remove'],check=True)
    retained=[]
    for section in sections:
        match=re.search(r'(?m)^PublicKey\s*=\s*(\S+)',section)
        if match and match[1] in removed_peers:
            continue
        else:
            retained.append(section)
    replacement=config.with_suffix('.conf.incident-new')
    replacement.write_text(''.join(retained));replacement.chmod(0o600);replacement.replace(config)
    # Socket activation must not replace a killed triage run during containment.
    if Path('/etc/systemd/system/mmhotline-triage-agent-run.socket').exists():
        Path('/etc/mmhotline/everyone-locked-out').write_text('The incident response disabled triage runs.\n')
        for unit in ('mmhotline-triage-agent-run.socket','mmhotline-triage-agent-run@.service'):
            dropin=Path('/etc/systemd/system')/(unit+'.d')
            dropin.mkdir(exist_ok=True)
            (dropin/'incident-lockout.conf').write_text('[Unit]\nConditionPathExists=!/etc/mmhotline/everyone-locked-out\n')
        subprocess.run(['systemctl','daemon-reload'],check=True)
        subprocess.run(['systemctl','stop','mmhotline-triage-agent-run.socket'],check=True)
    if subprocess.run(['systemctl','cat','mmx-https-api.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0:
        if subprocess.run(['systemctl','is-active','--quiet','mmx-https-api.service']).returncode == 0:
            subprocess.run(['systemctl','kill','--kill-whom=all','--signal=KILL','mmx-https-api.service'],check=True)
        subprocess.run(['systemctl','stop','mmx-https-api.service'],check=True)
    # Detached MMX jobs hold their worker.lock after their transport disappears.
    active=Path('/var/lib/mmx/active')
    if active.exists():
        job=active.read_text().strip()
        if not re.fullmatch('[a-f0-9]{64}',job):
            raise RuntimeError('The active MMX job ID is invalid. Inspect /var/lib/mmx/active.')
        directory=active.parent/'jobs'/job
        lock=directory/'worker.lock'
        if lock.exists():
            wanted=lock.stat()
            processes={}
            workers=[]
            for process in Path('/proc').iterdir():
                if not process.name.isdigit(): continue
                try:
                    fields=(process/'stat').read_text().rsplit(')',1)[1].split()
                    processes[int(process.name)]=int(fields[1])
                    args=(process/'cmdline').read_bytes().split(b'\0')
                    if len(args) < 4 or args[-3:-1] != [b'worker',job.encode()]: continue
                    held=(process/'fd/3').stat()
                    if (held.st_dev,held.st_ino)==(wanted.st_dev,wanted.st_ino):workers.append(int(process.name))
                except (FileNotFoundError,ProcessLookupError):
                    continue
            (directory/'stop').touch(mode=0o600)
            def end_tree(pid):
                for child,parent in processes.items():
                    if parent==pid:end_tree(child)
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            for pid in workers:
                print('Ending active MMX job '+job+' worker PID '+str(pid),flush=True)
                end_tree(pid)
            # Prove the lock is released without editing MMX's job result.
            with lock.open('rb') as held:
                deadline=time.monotonic()+5
                while True:
                    try:fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:raise RuntimeError('The active MMX worker still holds its lock.')
                        time.sleep(0.05)
    subprocess.run(['bash','-s','--',kept_address],input=session_script,text=True,check=True)


# Exit code 3: some servers failed containment and are named. The playbook
# accepts it and reports it at the end, after the other stages ran. Any
# other failure, a wrong desk that keeps access included, stops the run before MMX
# changes a server.
SOME_SERVERS_FAILED=3


def this_desks_own_identity():
    """The production key, WireGuard address and WireGuard public key this
    desk really has, from files only root writes on this desk, never from
    the pulled repository: the role generated the production key, the last
    desk review wrote wg0, and MMX keeps wg0's private key beside it."""
    key=Path('/etc/systems-desk/production_key.pub').read_text().split()[:2]
    match=re.search(r'(?m)^Address\s*=\s*([0-9.]+)/',Path('/etc/wireguard/wg0.conf').read_text())
    wireguard_public_key=subprocess.run(['wg','pubkey'],input=Path('/etc/wireguard/wg0.private_key').read_text(),
                                        text=True,capture_output=True).stdout.strip()
    if len(key)!=2 or not match or not wireguard_public_key:
        raise SystemExit('This desk has no production key, WireGuard address or WireGuard key to keep. Nothing changed.')
    return ' '.join(key),match[1],wireguard_public_key


def check_that_this_desk_keeps_its_access(nodes, groups, desk, root_ssh_public_keys):
    """Stops, with nothing changed, when what this press installs on the
    servers would not admit this desk, the desk the press runs on: the
    lock-out installs the inventory's address and keys for it, and the undo
    installs root_ssh_public_keys and a WireGuard peer for each systems desk
    of the inventory. Reason (seen on test servers): a press that cuts
    off its own desk loses SSH partway, after some servers changed, and no
    desk can finish it; only the provider's rescue system recovers the
    servers (operating_procedures/respond_to_a_break_in.md, "Recover a
    half-undone lock-out")."""
    if desk not in nodes:
        raise SystemExit(desk+' is not a node of inventories/servers.yml, so this press would take away its WireGuard peer on every server '
                         'and cut this desk off partway. Nothing changed. Put the desk back in inventories/servers.yml, push, and press again.')
    if desk not in groups.get('systems_desks',[]):
        raise SystemExit(desk+' is not in the systems_desks group of inventories/servers.yml. The servers peer only with the desks there, so this '
                         'press would cut this desk off partway. Nothing changed. Put the desk back in systems_desks, push, and press again.')
    kept=nodes[desk].get('vars') or {}
    key,address,wireguard_public_key=this_desks_own_identity()
    # The servers get the inventory's values, so they must be this desk's own.
    if kept.get('production_ssh_public_key','').split()[:2]!=key.split():
        raise SystemExit('nodes.'+desk+'.vars.production_ssh_public_key in the inventory differs from this desk\'s own key, '
                         '/etc/systems-desk/production_key.pub. Nothing changed. Set the inventory value to that key, commit, push, '
                         'and run the lock-out button again.')
    if kept.get('private_ip')!=address:
        raise SystemExit('nodes.'+desk+'.vars.private_ip in the inventory is not this desk\'s WireGuard address, '+address+
                         '. Nothing changed. Set the inventory value to that address, commit, push, and run the lock-out button again.')
    if kept.get('wireguard_public_key')!=wireguard_public_key:
        raise SystemExit('nodes.'+desk+'.vars.wireguard_public_key in the inventory is not this desk\'s WireGuard public key, '+
                         wireguard_public_key+', from /etc/wireguard/wg0.private_key. Nothing changed. Set the inventory value to that key, '
                         'commit, push, and run the lock-out button again.')
    # The whole line, as the lock-out's root_authorized_keys template compares
    # it; the line holds this desk's own key, as checked above.
    if kept['production_ssh_public_key'] not in root_ssh_public_keys:
        raise SystemExit('This desk\'s key, nodes.'+desk+'.vars.production_ssh_public_key, is not in root_ssh_public_keys in '
                         'mmx_project_settings.yml, so this press would take this desk\'s access away on every server partway, '
                         'while the servers admit no other desk. Nothing changed. Keep this desk\'s key in root_ssh_public_keys until '
                         'the desk that replaces it has joined; then remove the key in a commit from that desk '
                         '(operating_procedures/respond_to_a_break_in.md, "Working alone"). Push, and press again.')
    return key,address


def main(arguments=()):
    """--check-only: only check that this desk keeps its access, as the
    first fleet stage of every press does, the undo included."""
    nodes=json.loads(os.environ['INVENTORY_NODES'])
    groups=json.loads(os.environ['INVENTORY_GROUPS'])
    desk=os.environ['DESK_THAT_KEEPS_ACCESS']
    key,address=check_that_this_desk_keeps_its_access(nodes,groups,desk,json.loads(os.environ['ROOT_SSH_PUBLIC_KEYS']))
    if '--check-only' in arguments:
        return
    removed=[nodes[name]['vars']['wireguard_public_key'] for name in groups['systems_desks'] if name!=desk]
    session_script=Path('/usr/local/sbin/end_untrusted_server_sessions').read_text()
    program=Path(__file__).read_text().rsplit("\nif __name__ == '__main__':",1)[0]
    program+='\nremote('+','.join(repr(value) for value in (address,key,removed,session_script))+')\n'
    def isolate(server):
        name,node=server
        # One unresponsive or hostile server must not delay every other lock-out.
        # ConnectTimeout=10 and timeout=45 bound each server, so the person
        # learns within a minute which servers to isolate at the provider
        # (docs/design.md, the lock-out). No measurement is recorded for the
        # two numbers: a lock-out run on test servers should note how long
        # one server's containment takes.
        try:
            result=subprocess.run(['ssh','-F','/etc/systems-desk/incident-ssh.conf','-o','BatchMode=yes',
                '-o','ConnectTimeout=10','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',
                'root@'+node['address'],'python3','-'],input=program,text=True,timeout=45)
        except subprocess.TimeoutExpired:
            print(name+': SSH containment exceeded 45 seconds; isolate this server at the provider',flush=True)
            return name
        if result.returncode:return name
        print(name+': initial containment complete',flush=True)
        return None
    servers=[(name,node) for name,node in sorted(nodes.items()) if name not in groups['systems_desks']]
    with concurrent.futures.ThreadPoolExecutor() as pool:
        failed=[name for name in pool.map(isolate,servers) if name]
    if failed:
        print('Initial containment failed. Isolate these servers at the provider: '+', '.join(failed),file=sys.stderr,flush=True)
        sys.exit(SOME_SERVERS_FAILED)



if __name__ == '__main__':
    main(sys.argv[1:])
