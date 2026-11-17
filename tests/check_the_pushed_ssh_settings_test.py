#!/usr/bin/env python3
"""The MMX button's check of pushed main's SSH settings files.

MMX hands a node's ssh_config to ssh with -F, and ssh runs programs that
such a file names, as servers-mmx, which reads the vault passphrase. The
check lets only known-safe keywords through. The inventories here are JSON,
which is YAML, so the tests need no YAML library.
"""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
loader = importlib.machinery.SourceFileLoader('check_ssh', str(T/'roles/systems_desk/files/check-the-pushed-ssh-settings'))
CHECK = importlib.util.module_from_spec(importlib.util.spec_from_loader('check_ssh', loader))
loader.exec_module(CHECK)
JSON_AS_YAML = types.SimpleNamespace(safe_load=json.loads, YAMLError=ValueError)


class PushedSshSettings(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.checkout = Path(directory.name)/'systems_repository'
        shutil.copytree(T/'ssh', self.checkout/'ssh')
        (self.checkout/'inventories').mkdir()
        self.nodes = {'desk01': {'address': '127.0.0.1', 'ssh_config': 'ssh/desk01'},
                      'util01': {'address': '10.20.0.1', 'ssh_config': 'ssh/config'}}
        patcher = patch.dict(sys.modules, {'yaml': JSON_AS_YAML})
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self):
        (self.checkout/'inventories/servers.yml').write_text(json.dumps({'nodes': self.nodes}))
        CHECK.check(str(self.checkout))

    def refused(self, pattern):
        with self.assertRaisesRegex(CHECK.Stop, pattern):
            self.check()

    def test_the_templates_own_ssh_settings_pass(self):
        # Every ssh_config the template's inventory names is one of these files.
        named = set(re.findall(r'(?m)^\s+ssh_config: (\S+)', (T/'inventories/servers.yml').read_text()))
        self.assertEqual(named, {'ssh/config', 'ssh/desk01'})
        self.check()

    def test_a_program_or_code_in_a_settings_file_is_refused(self):
        for line in ('ProxyCommand sh -c "cat /etc/systems-desk/vault-passphrase"', '  proxycommand=nc %h %p',
                     'LocalCommand id', 'PermitLocalCommand yes', 'KnownHostsCommand /bin/true', 'ProxyJump app001',
                     'PKCS11Provider /tmp/x.so', 'SecurityKeyProvider /tmp/x.so', 'ControlPath /tmp/x', 'ControlMaster auto',
                     'NoSuchKeyword yes', '"ProxyCommand" x'):
            with self.subTest(line=line):
                (self.checkout/'ssh/config').write_text((T/'ssh/config').read_text() + line + '\n')
                self.refused(r'ssh/config, line \d+, uses .*which the MMX button does not allow')

    def test_include_and_match_are_refused(self):
        for line in ('Include /home/coding-agent/x', 'Match exec "cat /etc/shadow"', 'MATCH all'):
            with self.subTest(line=line):
                (self.checkout/'ssh/desk01').write_text((T/'ssh/desk01').read_text() + line + '\n')
                self.refused(r'ssh/desk01, line \d+, uses')

    def test_a_node_ssh_config_outside_the_repository_is_refused(self):
        for value in ('/etc/ssh/evil', '~/.ssh/config', '../outside', 'ssh/../../outside'):
            with self.subTest(value=value):
                self.nodes['app001'] = {'address': '10.20.1.1', 'ssh_config': value}
                self.refused('a path outside the systems repository')

    def test_a_linked_settings_file_is_refused(self):
        outside = self.checkout.parent/'outside'
        outside.write_text('ProxyCommand x\n')
        (self.checkout/'ssh/app').symlink_to(outside)
        self.nodes['app001'] = {'address': '10.20.1.1', 'ssh_config': 'ssh/app'}
        self.refused('not a regular file')

    def test_the_command_exits_64_with_one_sentence(self):
        (self.checkout/'ssh/config').write_text('ProxyCommand x\n')
        (self.checkout/'inventories/servers.yml').write_text(json.dumps({'nodes': self.nodes}))
        self.assertEqual(CHECK.main([str(self.checkout)]), 64)


if __name__ == '__main__':
    unittest.main()
