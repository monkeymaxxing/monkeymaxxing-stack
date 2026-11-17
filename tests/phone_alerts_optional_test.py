#!/usr/bin/env python3
"""The first sitting needs no Pushover key; the alerts sitting adds them.

  MMX_BINARY=/path/to/mmx python3 tests/phone_alerts_optional_test.py

phone_alerts_are_set_up is false in mmx_project_settings.yml until the alerts
sitting. While false: `mmx secrets usage` does not ask for
mmwatchdog_pushover_user_or_group_key, and the fleet hub's alert_destinations
file has no push destination (so no alert pretends to reach a phone). While
true, the key is needed and the push destination is there, unchanged.
Templates render with Go's text/template, which the files use only for
`if`, `else`, and `.inputs`.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'
SETTING_OFF = 'phone_alerts_are_set_up: false'
RENDER = '''package main
import ("fmt";"os";"text/template")
func main() {
	t := template.Must(template.New("t").Funcs(template.FuncMap{}).ParseFiles(os.Args[1]))
	data := map[string]any{"inputs": map[string]any{"phone_alerts_are_set_up": os.Args[2] == "true", "private_ip": "10.20.0.1"}}
	if err := t.ExecuteTemplate(os.Stdout, os.Args[1][len(os.Args[1])-len(os.Args[3]):], data); err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(1) }
}
'''


def mmx():
    binary = os.environ.get('MMX_BINARY') or shutil.which('mmx')
    if not binary:
        raise RuntimeError('Set MMX_BINARY to run mmx.')
    return binary


class PhoneAlertsAreOptionalInTheFirstSitting(unittest.TestCase):
    def project(self, phone_alerts_are_set_up):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)/'project'
        shutil.copytree(T, root)
        settings = root/'mmx_project_settings.yml'
        text = settings.read_text()
        self.assertIn(SETTING_OFF, text)
        settings.write_text(text.replace(SETTING_OFF, f'phone_alerts_are_set_up: {str(phone_alerts_are_set_up).lower()}'))
        return root

    def missing(self, root):
        result = subprocess.run([mmx(), 'secrets', 'usage', '--json'], cwd=root, text=True, capture_output=True,
                                env={k: v for k, v in os.environ.items() if k != 'TMPDIR'})
        return json.loads(result.stdout)['referenced_but_not_defined']

    def render(self, name, phone_alerts_are_set_up):
        path = T/'roles/util_server/files'/name
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        program = Path(temporary.name)/'render.go'
        program.write_text(RENDER)
        result = subprocess.run(['go', 'run', str(program), str(path), str(phone_alerts_are_set_up).lower(), name],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_the_vault_needs_no_pushover_key_before_the_alerts_sitting(self):
        self.assertNotIn('mmwatchdog_pushover_user_or_group_key', self.missing(self.project(False)))

    def test_the_vault_needs_the_pushover_key_once_the_alerts_sitting_set_it(self):
        self.assertIn('mmwatchdog_pushover_user_or_group_key', self.missing(self.project(True)))

    def test_both_settings_validate(self):
        for value in (False, True):
            result = subprocess.run([mmx(), 'validate'], cwd=self.project(value), text=True, capture_output=True,
                                    env={k: v for k, v in os.environ.items() if k != 'TMPDIR'})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_hub_has_no_push_destination_before_the_alerts_sitting(self):
        destinations = self.render('alert_destinations.yml', False)
        self.assertNotIn('on_call_push_app', destinations.replace('# ', ''))
        self.assertNotIn('pushover-application-token', destinations)
        self.assertIn('mmhotline_on_call', destinations)
        settings = ''.join(line for line in self.render('mmwatchdog_node_settings.yml', False).splitlines(True)
                           if not line.lstrip().startswith('#'))
        self.assertNotIn('on_call_push_app', settings)

    def test_the_hub_has_the_push_destination_once_the_alerts_sitting_set_it(self):
        destinations = self.render('alert_destinations.yml', True)
        self.assertIn('on_call_push_app:', destinations)
        self.assertIn('application_token_file: /etc/mmwatchdog/secrets/pushover-application-token', destinations)
        self.assertIn('send_silence_alerts_of_this_node_only_to_destinations: [on_call_push_app]',
                      self.render('mmwatchdog_node_settings.yml', True))


if __name__ == '__main__':
    unittest.main()
