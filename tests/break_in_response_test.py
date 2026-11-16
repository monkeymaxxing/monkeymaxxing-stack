#!/usr/bin/env python3
"""Check rendered containment, session ownership, revocation and evidence behavior."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


EVIDENCE = module('evidence', T/'server_management_scripts/save_break_in_evidence.py')
INITIAL = module('initial', T/'server_management_scripts/start_break_in_lockout.py')
CLOUDFLARE = module('revocation', T/'roles/systems_desk_lockout/files/revoke_cloudflare_access_sessions.py')


class RenderedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX templates.')

    def render_result(self, filename, **changes):
        desks = ['desk01', 'desk02']
        nodes = {'app001': {'vars': {'private_ip': '10.20.1.1', 'wireguard_public_key': 'APP', 'public_ipv4_address': '203.0.113.11'}},
                 'util01': {'vars': {'private_ip': '10.20.0.1', 'wireguard_public_key': 'UTIL', 'public_ipv4_address': '203.0.113.1'}}}
        for n, desk in enumerate(desks, 1):
            nodes[desk] = {'vars': {'private_ip': f'10.20.9.{n}', 'wireguard_public_key': desk.upper(),
                                   'public_ipv4_address': f'203.0.113.{90+n}', 'production_ssh_public_key': 'ssh-ed25519 KEY'+str(n)}}
        values = dict(everyone_locked_out_except_desk='', inventory_nodes=nodes,
                      inventory_groups=dict(systems_desks=desks, app_servers=['app001'], util_server=['util01']),
                      root_ssh_public_keys=['ssh-ed25519 KEY1','ssh-ed25519 KEY2','ssh-ed25519 UTILITY'],
                      triage_ssh_public_key='ssh-ed25519 TRIAGE', database_moving_in={}, allowed_laptops=[],
                      is_systems_desk=False,is_app_server=True,is_database_server=False,is_util_server=False,
                      is_staging_server=False,is_jobs_server=False,is_load_balancer_server=False,
                      tunnel_connector_and_caddy_run_only_on_the_load_balancer_servers=False,
                      requests_go_to_the_new_release=False,send_app_requests_to_the_status_page=False,status_page_host_name='status.example.com',
                      apps={'shop':{'health_url_path':'/up'}},public_host_names={'shop':'shop.example.com'},
                      app_servers_of_the_environment={'app001':{'private_ip':'10.20.1.1','live_web_containers':{'shop':{'web_port':8001}}}})
        values.update(changes)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir(); (root/'playbooks').mkdir()
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'app001':{'address':'127.0.0.1'}})))
            (root/'source.template').write_text((T/filename).read_text().replace('.inputs','.vars'))
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[dict(id='render',file=dict(path='/tmp/rendered',template='source.template',permissions_mode='0600'))])])) )
            return subprocess.run([self.mmx,'explain','render','--json'],cwd=root,text=True,capture_output=True)

    def render(self, filename, **changes):
        result=self.render_result(filename,**changes)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    def test_lock_admits_only_the_desk_that_keeps_access_from_its_address_and_undo_restores_keys(self):
        filename='roles/everyone_locked_out/files/root_authorized_keys'
        locked=self.render(filename,everyone_locked_out_except_desk='desk01')
        self.assertEqual(locked.strip(),'from="10.20.9.1" ssh-ed25519 KEY1')
        self.assertEqual(self.render(filename).splitlines(),['ssh-ed25519 KEY1','ssh-ed25519 KEY2','ssh-ed25519 UTILITY'])
        self.assertEqual(self.render('roles/everyone_locked_out/files/triage_authorized_keys',everyone_locked_out_except_desk='desk01').strip(),'')
        self.assertIn('TRIAGE',self.render('roles/everyone_locked_out/files/triage_authorized_keys'))
        self.assertIn('AllowUsers root@10.20.9.1',self.render('roles/everyone_locked_out/files/sshd_lockout.conf',everyone_locked_out_except_desk='desk01'))
        self.assertNotIn('AllowUsers',self.render('roles/everyone_locked_out/files/sshd_lockout.conf'))

    def test_invalid_desk_that_keeps_access_or_key_fails_before_rendering_an_access_file(self):
        for changes in [dict(everyone_locked_out_except_desk='missing'),dict(everyone_locked_out_except_desk='app001'),
                        dict(everyone_locked_out_except_desk='desk01',root_ssh_public_keys=['ssh-ed25519 UTILITY'])]:
            result=self.render_result('roles/everyone_locked_out/files/root_authorized_keys',**changes)
            self.assertEqual(result.returncode,0,result.stderr)
            rendered=json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]
            self.assertNotIn('text',rendered)
            self.assertIn('Nothing changed',rendered['not_rendered_because'])

    def test_status_page_switch_catches_every_path_and_undo_restores_the_upstream(self):
        filename='roles/tunnel_connector_and_caddy/files/Caddyfile'
        locked=self.render(filename,send_app_requests_to_the_status_page=True)
        self.assertIn('redir https://status.example.com/ 302',locked)
        self.assertIn('header Cache-Control "no-store"',locked)
        self.assertNotIn('reverse_proxy',locked)
        normal=self.render(filename)
        self.assertIn('to 10.20.1.1:8001',normal)
        self.assertNotIn('redir ',normal)


class SessionTermination(unittest.TestCase):
    def invoke(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); binary=root/'bin';binary.mkdir()
            log=root/'commands'
            fake='#!'+sys.executable+'\n'+r"""import json,os,pathlib,sys
name=pathlib.Path(sys.argv[0]).name; args=sys.argv[1:]
with open(os.environ['COMMAND_LOG'],'a') as out:out.write(json.dumps([name,*args])+'\n')
if name=='loginctl':
 if args[0]=='list-sessions': print('1 kept\n2 other\n3 console')
 elif args[0]=='show-session': print(('login' if args[1]=='3' else 'sshd') if args[3]=='Service' else ('10.20.9.1' if args[1]=='1' else '10.20.9.2'))
elif name=='ps':
 if args[1]=='triage': print('22222')
"""
            for name in ['loginctl','ss','getent','ps','kill','sleep']:
                (binary/name).write_text(fake);(binary/name).chmod(0o755)
            script=T/'roles/everyone_locked_out/files/end_untrusted_server_sessions'
            env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],'COMMAND_LOG':str(log)}
            result=subprocess.run(['bash','-c','enable -n kill; source "$1" "$2"','test',str(script),'10.20.9.1'],env=env,text=True,capture_output=True)
            return result,[json.loads(line) for line in log.read_text().splitlines()]

    def test_only_untrusted_ssh_scope_and_transports_end(self):
        result,commands=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['loginctl','terminate-session','2'],commands)
        self.assertNotIn(['loginctl','terminate-session','1'],commands)
        self.assertNotIn(['loginctl','terminate-session','3'],commands)
        self.assertIn(['ss','--tcp','--numeric','--no-header','--kill','state','established','( sport = :22 and not dst 10.20.9.1 )'],commands)
        self.assertIn(['kill','-KILL','22222'],commands)


class BusyMmxContainment(unittest.TestCase):
    def private_key(self, temporary):
        key=Path(temporary)/'wg0.private_key'
        key.write_text('PRIVATE\n')
        return key

    def wg_pubkey(self, arguments, public_key, **options):
        # wg pubkey of this desk's own private key, which only root reads.
        self.assertEqual(options['input'],'PRIVATE\n')
        return subprocess.CompletedProcess(arguments,0,stdout=public_key+'\n')

    def test_initial_copy_is_executable_and_never_targets_another_desk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);public=root/'public';public.write_text('ssh-ed25519 KEY1')
            nodes={'desk01':{'address':'127.0.0.1','vars':{'private_ip':'10.20.9.1','wireguard_public_key':'KEPT','production_ssh_public_key':'ssh-ed25519 KEY1'}},
                   'desk02':{'address':'127.0.0.1','vars':{'wireguard_public_key':'OTHER'}},'app001':{'address':'10.20.1.1'}}
            wg0=Path(temporary)/'wg0.conf';wg0.write_text('[Interface]\nAddress = 10.20.9.1/16\nPrivateKey = PRIVATE\n')
            def path(value):
                if str(value)=='/etc/systems-desk/production_key.pub':return public
                if str(value)=='/etc/wireguard/wg0.conf':return wg0
                if str(value)=='/etc/wireguard/wg0.private_key':return self.private_key(temporary)
                if str(value)=='/usr/local/sbin/end_untrusted_server_sessions':return T/'roles/everyone_locked_out/files/end_untrusted_server_sessions'
                return Path(value)
            def invoke(arguments,**options):
                if arguments==['wg','pubkey']:return self.wg_pubkey(arguments,'KEPT',**options)
                self.assertEqual(arguments,['ssh','-F','/etc/systems-desk/incident-ssh.conf','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','root@10.20.1.1','python3','-'])
                self.assertEqual(options['timeout'],45)
                compile(options['input'],'remote containment','exec')
                return subprocess.CompletedProcess(arguments,0)
            env={'INVENTORY_NODES':json.dumps(nodes),'INVENTORY_GROUPS':'{"systems_desks":["desk01","desk02"]}',
                 'DESK_THAT_KEEPS_ACCESS':'desk01','ROOT_SSH_PUBLIC_KEYS':'["ssh-ed25519 KEY1"]'}
            with patch.dict(os.environ,env),patch.object(INITIAL,'Path',side_effect=path),patch.object(INITIAL.subprocess,'run',side_effect=invoke) as called,contextlib.redirect_stdout(io.StringIO()):
                INITIAL.main()
                self.assertEqual(called.call_count,2)

    def test_timed_out_server_is_named_after_other_servers_are_attempted(self):
        with tempfile.TemporaryDirectory() as temporary:
            public=Path(temporary)/'public';public.write_text('ssh-ed25519 KEY1')
            nodes={'desk01':{'address':'127.0.0.1','vars':{'private_ip':'10.20.9.1','wireguard_public_key':'KEPT','production_ssh_public_key':'ssh-ed25519 KEY1'}},
                   'app001':{'address':'10.20.1.1'},'db01':{'address':'10.20.2.1'}}
            wg0=Path(temporary)/'wg0.conf';wg0.write_text('[Interface]\nAddress = 10.20.9.1/16\nPrivateKey = PRIVATE\n')
            def path(value):
                if str(value)=='/etc/systems-desk/production_key.pub':return public
                if str(value)=='/etc/wireguard/wg0.conf':return wg0
                if str(value)=='/etc/wireguard/wg0.private_key':return self.private_key(temporary)
                if str(value)=='/usr/local/sbin/end_untrusted_server_sessions':return T/'roles/everyone_locked_out/files/end_untrusted_server_sessions'
                return Path(value)
            targets=[]
            def invoke(arguments,**options):
                if arguments==['wg','pubkey']:return self.wg_pubkey(arguments,'KEPT',**options)
                target=arguments[-3];targets.append(target)
                if target=='root@10.20.1.1':raise subprocess.TimeoutExpired(arguments,45)
                return subprocess.CompletedProcess(arguments,0)
            env={'INVENTORY_NODES':json.dumps(nodes),'INVENTORY_GROUPS':'{"systems_desks":["desk01"]}',
                 'DESK_THAT_KEEPS_ACCESS':'desk01','ROOT_SSH_PUBLIC_KEYS':'["ssh-ed25519 KEY1"]'}
            errors=io.StringIO()
            with patch.dict(os.environ,env),patch.object(INITIAL,'Path',side_effect=path),patch.object(INITIAL.subprocess,'run',side_effect=invoke),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(errors):
                with self.assertRaises(SystemExit) as stopped:INITIAL.main()
            # 3, the one failure the playbook lets the other stages go on after.
            self.assertEqual(stopped.exception.code,3)
            self.assertIn('app001',errors.getvalue())
            self.assertEqual(set(targets),{'root@10.20.1.1','root@10.20.2.1'})

    def test_a_kept_key_or_address_that_is_not_this_desks_own_stops_before_any_server(self):
        # The kept keys and address come from this desk's own files. Pushed
        # main naming another key or address must stop the button, with an
        # exit code the playbook does not accept, before any SSH to a server.
        with tempfile.TemporaryDirectory() as temporary:
            public=Path(temporary)/'public';public.write_text('ssh-ed25519 KEY1 alex on desk01\n')
            wg0=Path(temporary)/'wg0.conf';wg0.write_text('[Interface]\nAddress = 10.20.9.1/16\n')
            private_key=self.private_key(temporary)
            def path(value):
                return {'/etc/systems-desk/production_key.pub':public,'/etc/wireguard/wg0.conf':wg0,
                        '/etc/wireguard/wg0.private_key':private_key}.get(str(value),Path(value))
            for changed,message in [(dict(production_ssh_public_key='ssh-ed25519 AGENTS'),'differs from this desk'),
                                    (dict(private_ip='10.20.9.7'),"not this desk's WireGuard address"),
                                    (dict(wireguard_public_key='PUSHED'),"not this desk's WireGuard public key, KEPT")]:
                kept={'private_ip':'10.20.9.1','wireguard_public_key':'KEPT','production_ssh_public_key':'ssh-ed25519 KEY1',**changed}
                env={'INVENTORY_NODES':json.dumps({'desk01':{'address':'127.0.0.1','vars':kept},'app001':{'address':'10.20.1.1'}}),
                     'INVENTORY_GROUPS':'{"systems_desks":["desk01"]}','DESK_THAT_KEEPS_ACCESS':'desk01',
                     'ROOT_SSH_PUBLIC_KEYS':json.dumps([kept['production_ssh_public_key']])}
                called=[]
                def invoke(arguments,**options):
                    called.append(arguments)
                    return self.wg_pubkey(arguments,'KEPT',**options)
                with patch.dict(os.environ,env),patch.object(INITIAL,'Path',side_effect=path),patch.object(INITIAL.subprocess,'run',side_effect=invoke):
                    with self.assertRaisesRegex(SystemExit,message) as stopped:INITIAL.main()
                self.assertNotIn(stopped.exception.code,(0,3))
                self.assertEqual(called,[['wg','pubkey']],'no SSH to a server')

    def test_a_press_that_would_cut_off_this_desk_stops_before_any_server(self):
        # Seen on test servers: the undo ran on the old desk after a
        # commit removed that desk's key from root_ssh_public_keys. It wrote
        # the new keys on the servers, then lost its own SSH partway, and only
        # the provider's rescue system recovered the servers. Every press, the
        # undo included, first checks with --check-only, in the playbook's first
        # fleet stage, that what it installs still admits this stand-in desk.
        with tempfile.TemporaryDirectory() as temporary:
            public=Path(temporary)/'public';public.write_text('ssh-ed25519 KEY1 casey on desk03\n')
            wg0=Path(temporary)/'wg0.conf';wg0.write_text('[Interface]\nAddress = 10.20.9.3/16\n')
            private_key=self.private_key(temporary)
            def path(value):
                return {'/etc/systems-desk/production_key.pub':public,'/etc/wireguard/wg0.conf':wg0,
                        '/etc/wireguard/wg0.private_key':private_key}.get(str(value),Path(value))
            own={'private_ip':'10.20.9.3','wireguard_public_key':'KEPT','production_ssh_public_key':'ssh-ed25519 KEY1 casey on desk03'}
            fresh={'private_ip':'10.20.9.4','wireguard_public_key':'FRESH','production_ssh_public_key':'ssh-ed25519 KEY4 dana on desk04'}
            def press(desk=own,desks=('desk03','desk04'),root_keys=('ssh-ed25519 KEY4 dana on desk04','ssh-ed25519 KEY1 casey on desk03')):
                nodes={'desk04':{'address':'127.0.0.1','vars':fresh},'app001':{'address':'10.20.1.1'}}
                if desk is not None:nodes['desk03']={'address':'127.0.0.1','vars':desk}
                env={'INVENTORY_NODES':json.dumps(nodes),'INVENTORY_GROUPS':json.dumps({'systems_desks':list(desks)}),
                     'DESK_THAT_KEEPS_ACCESS':'desk03','ROOT_SSH_PUBLIC_KEYS':json.dumps(list(root_keys))}
                called=[]
                def invoke(arguments,**options):
                    called.append(arguments)
                    return self.wg_pubkey(arguments,'KEPT',**options)
                with patch.dict(os.environ,env),patch.object(INITIAL,'Path',side_effect=path),patch.object(INITIAL.subprocess,'run',side_effect=invoke):
                    try:
                        INITIAL.main(['--check-only'])
                    except SystemExit as stopped:
                        self.assertNotIn(stopped.code,(0,3,None))
                        return str(stopped.code),called
                return None,called
            # The working-alone order: the fresh desk's key added, this desk's key kept.
            self.assertEqual(press(),(None,[['wg','pubkey']]),'the check-only press passes and connects to no server')
            for case,arguments,message in [
                    ("this desk's key removed from root_ssh_public_keys",dict(root_keys=['ssh-ed25519 KEY4 dana on desk04']),
                     'Keep this desk\'s key in root_ssh_public_keys until the desk that replaces it has joined'),
                    ("this desk's key changed in root_ssh_public_keys",dict(root_keys=['ssh-ed25519 KEY4 dana on desk04','ssh-ed25519 KEY9 casey on desk03']),
                     'Keep this desk\'s key in root_ssh_public_keys'),
                    ("this desk's production key changed in the inventory",dict(desk={**own,'production_ssh_public_key':'ssh-ed25519 KEY9'}),
                     'differs from this desk\'s own key'),
                    ("this desk's WireGuard address changed",dict(desk={**own,'private_ip':'10.20.9.9'}),
                     'not this desk\'s WireGuard address, 10.20.9.3'),
                    ("this desk's WireGuard key changed",dict(desk={**own,'wireguard_public_key':'PUSHED'}),
                     'not this desk\'s WireGuard public key, KEPT'),
                    ('this desk dropped from the inventory',dict(desk=None),
                     'desk03 is not a node of inventories/servers.yml'),
                    ('this desk dropped from the systems desks',dict(desks=('desk04',)),
                     'desk03 is not in the systems_desks group')]:
                with self.subTest(case):
                    stopped,called=press(**arguments)
                    self.assertIsNotNone(stopped,'the press must stop')
                    self.assertIn(message,stopped)
                    self.assertIn('Nothing changed',stopped)
                    self.assertTrue(all(command==['wg','pubkey'] for command in called),'no SSH to a server')


    def test_initial_ssh_containment_ends_the_exact_detached_worker_and_retains_serving_peers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for directory in ['root/.ssh','etc/ssh/sshd_config.d','etc/wireguard','var/lib/mmx/jobs/'+('a'*64)]:
                (root/directory).mkdir(parents=True)
            (root/'etc/wireguard/wg0.conf').write_text('[Interface]\nPrivateKey = PRIVATE\n[Peer]\nPublicKey = KEPT\nAllowedIPs = 10.20.9.1/32\n[Peer]\nPublicKey = OTHER\nAllowedIPs = 10.20.9.2/32\n[Peer]\nPublicKey = DATABASE\nAllowedIPs = 10.20.2.1/32\n')
            (root/'var/lib/mmx/active').write_text('a'*64)
            lock=root/('var/lib/mmx/jobs/'+('a'*64)+'/worker.lock')
            ready=root/'ready'
            child=subprocess.Popen([sys.executable,'-c', 'import fcntl,pathlib,sys,time; f=open(sys.argv[1],"a+"); fcntl.flock(f,fcntl.LOCK_EX); pathlib.Path(sys.argv[2]).touch(); time.sleep(30)',str(lock),str(ready)])
            try:
                import time
                deadline=time.monotonic()+5
                while not ready.exists():
                    self.assertLess(time.monotonic(),deadline)
                    time.sleep(.01)
                process=root/'proc'/str(child.pid);(process/'fd').mkdir(parents=True)
                (process/'stat').write_text(str(child.pid)+' (owned worker) S 1 0 0')
                (process/'cmdline').write_bytes(b'/opt/mmx/mmx-runner\0worker\0'+b'a'*64+b'\0')
                (process/'fd/3').symlink_to(lock)
                calls=[]
                def invoke(arguments,**options):
                    calls.append(arguments)
                    return subprocess.CompletedProcess(arguments,1 if arguments[:2]==['systemctl','cat'] else 0)
                with patch.object(INITIAL,'Path',side_effect=lambda value:Path(root/str(value).lstrip('/'))),patch.object(INITIAL.subprocess,'run',side_effect=invoke),contextlib.redirect_stdout(io.StringIO()):
                    INITIAL.remote('10.20.9.1','ssh-ed25519 KEY1',['OTHER'],'echo session termination')
                self.assertEqual(child.wait(timeout=5),-9)
                self.assertTrue((lock.parent/'stop').exists())
                saved=(root/'etc/wireguard/wg0.conf').read_text()
                self.assertNotIn('PublicKey = OTHER',saved)
                self.assertIn('PublicKey = DATABASE',saved)
                self.assertIn('PublicKey = KEPT',saved)
                self.assertIn(['wg','set','wg0','peer','OTHER','remove'],calls)
                self.assertEqual((root/'root/.ssh/authorized_keys').read_text(),'from="10.20.9.1" ssh-ed25519 KEY1\n')
                self.assertFalse(any('postgresql' in ' '.join(command) or 'cloudflared' in ' '.join(command) for command in calls))
            finally:
                if child.poll() is None:child.kill();child.wait()


class CloudflareRevocation(unittest.TestCase):
    def test_pagination_revokes_configured_apps_only_and_missing_apps_fail(self):
        calls=[]
        def response(request,timeout):
            calls.append((request.full_url,request.method))
            if request.method=='POST':data={'success':True,'result':{}}
            elif request.full_url.endswith('page=1'):data={'success':True,'result':[{'id':'other','domain':'unrelated.example.com'}],'result_info':{'total_pages':2}}
            else:data={'success':True,'result':[{'id':'ops','domain':'ops.example.com'}],'result_info':{'total_pages':2}}
            return contextlib.closing(io.BytesIO(json.dumps(data).encode()))
        with patch.object(CLOUDFLARE.urllib.request,'urlopen',side_effect=response),contextlib.redirect_stdout(io.StringIO()):
            CLOUDFLARE.revoke('a'*32,{'ops.example.com'},'SECRET_NOT_TO_PRINT')
            self.assertEqual([url.rsplit('/',2)[-2] for url,method in calls if method=='POST'],['ops'])
            with self.assertRaisesRegex(RuntimeError,'missing.example.com'):
                CLOUDFLARE.revoke('a'*32,{'missing.example.com'},'SECRET_NOT_TO_PRINT')

    def test_cloudflare_api_failure_is_not_reported_as_revocation(self):
        response=lambda *args,**kw:contextlib.closing(io.BytesIO(b'{"success":false,"result":[]}'))
        with patch.object(CLOUDFLARE.urllib.request,'urlopen',side_effect=response):
            with self.assertRaisesRegex(RuntimeError,'refused'):
                CLOUDFLARE.revoke('a'*32,{'ops.example.com'},'SECRET_NOT_TO_PRINT')

    def run_main(self,token_text=None,response=None):
        """main() as the lock-out runs it; the message of its SystemExit."""
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'cloudflare-api-token.conf'
            if token_text is not None:token.write_text(token_text)
            env={'CLOUDFLARE_ACCOUNT_ID':'a'*32,'PRIVATE_HOST_NAMES':'{"mmhotline":"ops.example.com"}',
                 'STAGING_SERVERS':'[]','STAGING_HOST_NAMES':'{}'}
            with patch.dict(os.environ,env),patch.object(CLOUDFLARE,'TOKEN_FILE',token),patch.object(CLOUDFLARE.os,'geteuid',return_value=0),\
                 patch.object(CLOUDFLARE.urllib.request,'urlopen',side_effect=response),self.assertRaises(SystemExit) as stopped:
                CLOUDFLARE.main()
        return str(stopped.exception)

    def test_each_failure_says_what_happened_and_what_the_person_does(self):
        refused=lambda *args,**kw:contextlib.closing(io.BytesIO(b'{"success":false,"result":[]}'))
        for case,message in (('no token file',self.run_main()),
                             ('a token file without a token',self.run_main('# empty\n')),
                             ('Cloudflare refused',self.run_main('proxy_set_header Authorization "Bearer SECRET_NOT_TO_PRINT";\n',refused))):
            with self.subTest(case=case):
                self.assertIn('ops.example.com stay signed in',message)
                self.assertIn('Revoke their sessions now at Cloudflare',message)
                self.assertIn('respond_to_a_break_in.md',message)
                self.assertNotIn('SECRET_NOT_TO_PRINT',message)
        self.assertIn('This desk has no Cloudflare token',self.run_main())
        self.assertIn('run set-up-outside-services cloudflare in your own terminal on this desk',self.run_main())


class EvidenceCopies(unittest.TestCase):
    def test_signed_upload_sends_real_payload_and_download_hashes_received_bytes(self):
        config={'repo1-s3-bucket':'backups','repo1-s3-endpoint':'s3.example.com','repo1-s3-region':'test-region',
                'repo1-s3-key':'identity','repo1-s3-key-secret':'SECRET_NOT_TO_PRINT'}
        calls=[]
        def response(request,timeout):
            if request.method=='PUT':
                self.assertEqual(request.data.read(),b'retained evidence')
                self.assertEqual(request.get_header('Content-length'),'17')
                self.assertEqual(request.get_header('Content-type'),'application/octet-stream')
                self.assertIn('SignedHeaders=host;x-amz-content-sha256;x-amz-date',request.get_header('Authorization'))
                self.assertNotIn('SECRET_NOT_TO_PRINT',request.get_header('Authorization'))
            calls.append((request.full_url,request.method))
            return contextlib.closing(io.BytesIO(b'retained evidence'))
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'logs';path.write_bytes(b'retained evidence')
            with patch.object(EVIDENCE.urllib.request,'urlopen',side_effect=response):
                EVIDENCE.signed_request('PUT','break_in_evidence/incident/desk01.tar.gz.enc',config,path)
                self.assertEqual(EVIDENCE.signed_request('GET','break_in_evidence/incident/desk01.tar.gz.enc',config),hashlib.sha256(b'retained evidence').hexdigest())
        self.assertEqual(calls,[('https://backups.s3.example.com/break_in_evidence/incident/desk01.tar.gz.enc','PUT'),('https://backups.s3.example.com/break_in_evidence/incident/desk01.tar.gz.enc','GET')])

    def test_live_log_changes_are_recorded_but_real_read_errors_fail_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary=Path(temporary)/'tar'
            binary.write_text('#!/bin/sh\nprintf archive-bytes\nexit "$TAR_EXIT_STATUS"\n');binary.chmod(0o755)
            for status in (0,1,2):
                with self.subTest(status=status):
                    result=subprocess.run(['bash','-c',EVIDENCE.COLLECT_FILES],env={**os.environ,'PATH':temporary+':'+os.environ['PATH'],'TAR_EXIT_STATUS':str(status)},text=True,capture_output=True)
                    self.assertEqual(result.stdout,'archive-bytes')
                    self.assertEqual(result.returncode,2 if status==2 else 0)

    def test_remote_read_failure_preserves_the_partial_copy_and_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'db01'
            def failed(*args,**kw):
                kw['stdout'].write(b'partial evidence')
                raise subprocess.CalledProcessError(255,args[0])
            with patch.object(EVIDENCE,'run',side_effect=failed):
                with self.assertRaises(subprocess.CalledProcessError):EVIDENCE.collect('db01',path,['ssh','root@db01'])
            self.assertEqual((path/'journal.export').read_bytes(),b'partial evidence')
            self.assertEqual(path.stat().st_mode & 0o777,0o700)


def commands(text):
    """Each command of a Markdown file's sh blocks, with its continuation
    lines joined."""
    for block in re.findall(r'```sh\n(.*?)```', text, re.S):
        yield from re.sub(r'\\\n\s*', ' ', block).split('\n')


class NoRootRunOfPulledContent(unittest.TestCase):
    """No procedure runs the pulled repository's content as root on a desk.
    The evidence copy runs as root, so it is the reviewed copy."""

    def test_no_procedure_runs_mmx_or_a_pulled_script_as_root_on_the_desk(self):
        found = []
        for path in sorted([*T.glob('operating_procedures/*.md'), *T.glob('initial_setup/*.md'), T/'AGENTS.md']):
            for command in commands(path.read_text()):
                command = command.strip()
                if not command.startswith('sudo') or command.startswith('sudo -n -u servers-mmx run-mmx-on-the-servers'):
                    continue
                # mmx results and status read the run history; every other
                # MMX command loads the pulled playbooks and may connect.
                if re.search(r'\bmmx (?!results|status)\S', command) or re.search(r'\bpython3 server_management_scripts/', command):
                    found.append('%s: %s' % (path.relative_to(T), command))
        self.assertEqual(found, [], 'root runs of the pulled repository on the desk')

    def test_during_a_lock_out_the_coding_agent_runs_every_server_with_its_button_over_ssh(self):
        text = (T/'operating_procedures/respond_to_a_break_in.md').read_text()
        runs = [command.strip() for command in commands(text) if 'every_server' in command]
        self.assertTrue(runs)
        for command in runs:
            self.assertTrue(command.startswith('sudo -n -u servers-mmx run-mmx-on-the-servers run every_server --connection ssh_only'), command)
        self.assertIn('python3 /usr/local/lib/systems-desk/lock-everyone-out/server_management_scripts/save_break_in_evidence.py', text)

    def test_the_evidence_copy_connects_with_the_ssh_settings_beside_it(self):
        command = EVIDENCE.ssh_to('10.20.0.1')
        self.assertEqual(command[:3], ['ssh', '-F', str(T/'ssh/config')])
        role = (T/'roles/systems_desk/main.yml').read_text()
        self.assertIn('path: /usr/local/lib/systems-desk/lock-everyone-out/server_management_scripts/save_break_in_evidence.py, '
                      'source: ../../server_management_scripts/save_break_in_evidence.py', role)


class OnlyTheLockOutButtonStartsOrUndoesALockOut(unittest.TestCase):
    """every_server applies the lock-out state on every run, so its first
    three tasks refuse a lock-out, a change to the desk or keys that keep
    access, or the undo, that the lock-out button did not make on the
    machine that runs MMX. run-mmx-on-the-servers passes the first line of
    the button's record on its desk. MMX's explain output shows which of the
    checks runs in each state, and what each one requires; MMX evaluates
    each check's condition as the when of a probe task."""

    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to test the actual MMX playbooks.')

    def project(self, temporary, desk_that_keeps_access, inventory_changes=()):
        project = Path(temporary)/'systems'
        shutil.copytree(T, project, ignore=shutil.ignore_patterns('.mmx'))
        inventory = project/'inventories/servers.yml'
        text = inventory.read_text()
        if desk_that_keeps_access:
            text = text.replace('vars:\n', 'vars:\n  everyone_locked_out_except_desk: %s\n' % desk_that_keeps_access, 1)
        for old, new in inventory_changes:
            self.assertIn(old, text)
            text = text.replace(old, new)
        inventory.write_text(text)
        return project

    def mmx_explain(self, project, *arguments):
        result = subprocess.run([self.mmx, 'explain', *arguments, '--json'], cwd=project, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def explain(self, desk_that_keeps_access, *arguments):
        with tempfile.TemporaryDirectory() as temporary:
            return self.mmx_explain(self.project(temporary, desk_that_keeps_access), 'every_server', *arguments)

    def record_of_the_press(self, desk_that_keeps_access='desk01'):
        """The first line of the record that playbooks/lock_everyone_out.yml
        writes on the desk at the press, with the template's inventory."""
        with tempfile.TemporaryDirectory() as temporary:
            explained = self.mmx_explain(self.project(temporary, desk_that_keeps_access),
                                         'lock_everyone_out', '--var', 'desk_name=' + desk_that_keeps_access)
        task = next(task for stage in explained['fleet_stages'] for task in stage['node_tasks']
                    if task['path'].endswith('/record_that_the_lock_out_button_ran_on_this_desk'))
        content = next(argument['value'] for argument in task['arguments'] if argument['field'] == 'file.content')
        return content.split('\n', 1)[0]

    def refusing_check(self, desk_that_keeps_access, record, inventory_changes=()):
        """The lock-out check of every_server that refuses a run on util01
        from a desk whose record's first line is record (empty: no record),
        or None. The first failed check stops the node, so it is the one
        whose message the person reads. Each check becomes a probe task
        whose when holds exactly when the check runs and its condition
        fails, so MMX itself evaluates them."""
        record_var = ['--var', 'lock_out_button_record_on_this_desk=' + record]
        with tempfile.TemporaryDirectory() as temporary:
            project = self.project(temporary, desk_that_keeps_access, inventory_changes)
            explained = self.mmx_explain(project, 'every_server', '--only-fleet-stages', 'every_server', '--limit', 'util01', *record_var)
            stage = next(stage for stage in explained['fleet_stages'] if stage['path'] == 'every_server')
            probes = []
            for task in stage['node_tasks']:
                name = task['path'].rsplit('/', 1)[-1]
                if task['node'] != 'util01' or not name.startswith('a_lock_out_'):
                    continue
                arguments = {argument['field']: argument.get('reference') for argument in task['arguments']}
                probes.append({'id': name, 'when': {'all': [arguments['when'], {'not': arguments['assert.that']}]},
                               'assert': {'that': {'equals': ['', '']}}})
            self.assertEqual(len(probes), 3)
            (project/'playbooks/lock_out_checks_probe.yml').write_text(json.dumps({
                'command_line_vars': {'lock_out_button_record_on_this_desk': {'type': 'string', 'default': ''}},
                'fleet_stages': [{'id': 'probe', 'nodes': 'util01', 'node_tasks': probes}]}))
            probed = self.mmx_explain(project, 'lock_out_checks_probe', *record_var)
        return next((task['path'].rsplit('/', 1)[-1] for task in probed['fleet_stages'][0]['node_tasks'] if task['status'] == 'ready'), None)

    def checks(self, explained):
        """The every_server fleet stage's tasks on util01, in order, with
        each check's status and condition."""
        stage = next(stage for stage in explained['fleet_stages'] if stage['path'] == 'every_server')
        tasks = [task for task in stage['node_tasks'] if task['node'] == 'util01']
        return [(task['path'].rsplit('/', 1)[-1], task['status'],
                 next((argument['reference'] for argument in task.get('arguments', []) if argument['field'] == 'assert.that'), None))
                for task in tasks]

    def test_the_checks_come_first_and_require_the_press_exactly_while_the_inventory_sets_the_lock_out(self):
        record = '{{ .vars.lock_out_button_record_on_this_desk }}'
        for desk, expected in [('', [('a_lock_out_starts_only_with_the_lock_out_button', 'skipped'),
                                     ('a_lock_out_keeps_the_desk_and_keys_the_lock_out_button_checked', 'skipped'),
                                     ('a_lock_out_is_undone_only_with_the_lock_out_button', 'ready')]),
                               ('desk01', [('a_lock_out_starts_only_with_the_lock_out_button', 'ready'),
                                           ('a_lock_out_keeps_the_desk_and_keys_the_lock_out_button_checked', 'ready'),
                                           ('a_lock_out_is_undone_only_with_the_lock_out_button', 'skipped')])]:
            with self.subTest(desk=desk):
                checks = self.checks(self.explain(desk, '--limit', 'util01'))
                self.assertEqual([(name, status) for name, status, _ in checks[:3]], expected)
                self.assertEqual(checks[0][2], {'not': {'equals': [record, '']}}, 'a lock-out runs only where the button ran')
                self.assertEqual(checks[2][2], {'equals': [record, '']}, 'an undo runs only where the button left no record')

    def test_the_button_s_record_on_the_desk_that_keeps_access_passes(self):
        self.assertEqual(self.refusing_check('desk01', self.record_of_the_press()), None)
        self.assertEqual(self.refusing_check('', ''), None)

    def test_a_run_from_a_desk_without_the_record_refuses_the_lock_out(self):
        self.assertEqual(self.refusing_check('desk01', ''), 'a_lock_out_starts_only_with_the_lock_out_button')

    def test_a_desk_whose_record_names_another_desk_cannot_hand_over_access(self):
        # The coding agent on desk02, which keeps access, pushes
        # everyone_locked_out_except_desk: desk01 and runs every_server.
        record = 'desk02 10.20.9.2 DESK02WIREGUARDKEY= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDESK02 bo on desk02'
        self.assertEqual(self.refusing_check('desk01', record), 'a_lock_out_keeps_the_desk_and_keys_the_lock_out_button_checked')

    def test_an_undo_without_the_button_refuses_on_a_desk_with_a_record(self):
        # Whichever desk the record names, a desk with a record undoes only
        # with the button. A desk without a record never reaches a locked-out
        # server: only the kept desk's key and address get in.
        for record in [self.record_of_the_press(), 'desk02 10.20.9.2 DESK02WIREGUARDKEY= ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDESK02 bo on desk02',
                       'The person pressed the lock-out button on this desk. The undo of the lock-out button removes this file.']:
            with self.subTest(record=record):
                self.assertEqual(self.refusing_check('', record), 'a_lock_out_is_undone_only_with_the_lock_out_button')

    def test_a_pushed_key_or_address_of_the_desk_that_keeps_access_refuses_during_a_lock_out(self):
        record = self.record_of_the_press()
        for name, change in [
                ('production SSH public key', ('production_ssh_public_key: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIR+J8OoEVNHl3P/KSWFruheEQaq8Cgw/PziDAinSTJJ',
                                               'production_ssh_public_key: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPUSHEDKEY')),
                ('WireGuard address', ('      private_ip: 10.20.9.1\n', '      private_ip: 10.20.9.7\n')),
                ('WireGuard public key', ('wireguard_public_key: "urzzcMKwVZ9bM84MmgWUjMRxOTNn2PDtEF5it/uZFQ4="',
                                          'wireguard_public_key: "PUSHEDzcMKwVZ9bM84MmgWUjMRxOTNn2PDtEF5it/uZ="'))]:
            with self.subTest(changed=name):
                self.assertEqual(self.refusing_check('desk01', record, [change]),
                                 'a_lock_out_keeps_the_desk_and_keys_the_lock_out_button_checked')

    def test_only_fleet_stages_every_server_keeps_the_checks(self):
        checks = self.checks(self.explain('desk01', '--only-fleet-stages', 'every_server', '--limit', 'util01'))
        self.assertEqual(checks[0][:2], ('a_lock_out_starts_only_with_the_lock_out_button', 'ready'))

    def test_the_daily_comparison_on_util01_stops_with_a_message_during_a_lock_out(self):
        """The timer reads the first check's status with jq; ready means the
        inventory sets the lock-out."""
        role = (T/'roles/util_server/main.yml').read_text()
        script = role.split('id: compare_every_server_with_the_repository_every_day', 1)[1].split('\n      env:', 1)[0]
        command = re.search(r"lock_out_check=\$\(mmx (explain [^\\]+?) \\\n\s+\| jq -r '([^']+)'\)", script)
        self.assertIsNotNone(command, script)
        explain_arguments, jq_filter = command.group(1).split()[1:], command.group(2)
        for desk, expected in [('', 'skipped'), ('desk01', 'ready')]:
            with self.subTest(desk=desk):
                explained = json.dumps(self.explain(desk, *explain_arguments[1:]))
                read = subprocess.run(['jq', '-r', jq_filter], input=explained, text=True, capture_output=True, check=True)
                self.assertEqual(read.stdout.strip(), expected)
        stop = script.split('if [ "$lock_out_check" != skipped ]; then', 1)[1].split('fi', 1)[0]
        self.assertIn('util01 compares nothing during the lock-out', stop)
        self.assertIn('exit 0', stop, 'a lock-out is no failure of the daily comparison, so no failed unit alerts')
        self.assertLess(script.index('lock_out_check='), script.index('mmx dryrun every_server'))


if __name__=='__main__':
    unittest.main()
