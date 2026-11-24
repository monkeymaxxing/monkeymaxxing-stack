#!/usr/bin/env python3
"""MMHotline's rules follow the team's one answer about the triage agent.

  MMX_BINARY=/path/to/mmx python3 tests/triage_agent_server_work_test.py

what_the_triage_agent_may_do_without_a_person in mmx_project_settings.yml
decides the rules_for_running_agent_playbooks entry of mmhotline_settings.yml.
The test renders mmhotline_settings.yml with MMX for each of the three
answers and reads the entry for the inventory servers: the first answer
renders MMHotline's preset permission_for_every_fix, the second
routine_fixes_without_permission, each with the three replacement playbooks
waiting for a person and one approval covering all three, and the third the
same preset plus the four playbooks of server work, never
every_fix_without_permission. It also
checks that every_server refuses any other answer and the settings of
triage_agent_server_work outside their ranges, before it changes anything.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

T = Path(__file__).resolve().parents[1]/'skills/monkeymaxxing-stack/systems_repository_template'


class MMHotlineRulesFollowTheTeamsAnswer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mmx = os.environ.get('MMX_BINARY') or shutil.which('mmx')
        if not cls.mmx:
            raise RuntimeError('Set MMX_BINARY to render the actual MMX template.')

    def rules_entry(self, answer, pool_minutes=10, replacement_minutes=10, held_warn_minutes=3):
        """The rendered lines of rules_for_running_agent_playbooks, up to the next top-level key."""
        text = self.rendered(answer, pool_minutes, replacement_minutes, held_warn_minutes)
        entry = re.search(r'(?ms)^rules_for_running_agent_playbooks:\n(.*?)^(?=\S)', text)
        self.assertIsNotNone(entry, text)
        # The next top-level line is a comment or a key of its own, never glued to the entry.
        self.assertRegex(text, r'(?m)^# A playbook that starts, stops, restarts, or changes one of these waits for$')
        return [line for line in entry.group(1).splitlines() if line.strip() and not line.lstrip().startswith('#')]

    def rendered(self, answer, pool_minutes=10, replacement_minutes=10, held_warn_minutes=3):
        """The whole of mmhotline_settings.yml as MMX renders it, with stand-in secrets."""
        source = (T/'mmhotline_settings.yml').read_text().replace('.secrets.', '.vars.secret_')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'inventories').mkdir()
            (root/'playbooks').mkdir()
            values = {name: 'stand-in' for name in re.findall(r'\.vars\.(secret_\w+)', source)}
            values.update(everyone_locked_out_except_desk='', triage_ssh_public_key='ssh-ed25519 AAAA stand-in',
                          root_ssh_public_keys=['ssh-ed25519 BBBB stand-in desk'], triage_agent_coding_agent='claude_code',
                          what_the_triage_agent_may_do_without_a_person=answer,
                          triage_agent_server_work={'minutes_between_the_warning_and_adding_or_removing_an_app_server': pool_minutes,
                                                    'sos_waits_for_a_server_replacement_minutes': replacement_minutes,
                                                    'warn_waits_for_the_triage_agent_minutes': held_warn_minutes},
                          util01_private_page_host_names={'mmhotline': 'ops.example.com'}, private_ip='10.20.0.1',
                          cloudflare_account_id='0' * 32, status_page_host_name='status.example.com')
            (root/'mmx_project_settings.yml').write_text(json.dumps(dict(project_name='render_test', default_inventory='servers', vars=values)))
            (root/'inventories/servers.yml').write_text(json.dumps(dict(nodes={'util01': {'address': '127.0.0.1'}})))
            (root/'settings.template').write_text(source)
            (root/'playbooks/render.yml').write_text(json.dumps(dict(fleet_stages=[dict(id='render', nodes='all', node_tasks=[
                dict(id='render', file=dict(path='/tmp/rendered', template='settings.template', permissions_mode='0600'))])])))
            result = subprocess.run([self.mmx, 'explain', 'render', '--json'], cwd=root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)['fleet_stages'][0]['node_tasks'][0]['rendered_templates'][0]['text']

    # With the first two answers, one approval of replace_failed_servers
    # covers the whole replacement (MMHotline's docs/running.md, "One approval
    # for a known sequence"), and its approved run starts the server
    # replacement.
    ONE_APPROVAL_FOR_THE_REPLACEMENT = [
        '    playbooks:',
        '      replace_failed_servers: {rule: get_permission_then_act, approvals_needed: 1, its_approval_also_approves_in_the_same_session: [every_server, destroy_replaced_servers], starts_a_server_replacement: true}',
        '      every_server: {rule: get_permission_then_act, approvals_needed: 1}',
        '      destroy_replaced_servers: {rule: get_permission_then_act, approvals_needed: 1}',
    ]

    # With every answer, the triage agent applies its own set-aside entries to the
    # fleet hub at once and reports: the playbook only quiets the exact findings the
    # agent wrote down in a file its commits may change anyway.
    SET_ASIDE_FINDINGS_RUN_AT_ONCE = ['      apply_set_aside_findings: {rule: act_then_report}']

    def test_every_fix_waits_for_a_person(self):
        self.assertEqual(self.rules_entry('every_fix_waits_for_a_person'), [
            '  servers:',
            '    preset: permission_for_every_fix',
        ] + self.ONE_APPROVAL_FOR_THE_REPLACEMENT + self.SET_ASIDE_FINDINGS_RUN_AT_ONCE)

    def test_routine_fixes_is_the_template_default(self):
        self.assertRegex((T/'mmx_project_settings.yml').read_text(),
                         r'(?m)^  what_the_triage_agent_may_do_without_a_person: routine_fixes$')
        self.assertEqual(self.rules_entry('routine_fixes'), [
            '  servers:',
            '    preset: routine_fixes_without_permission',
        ] + self.ONE_APPROVAL_FOR_THE_REPLACEMENT + self.SET_ASIDE_FINDINGS_RUN_AT_ONCE)

    def test_routine_fixes_and_server_work_lists_the_five_playbooks(self):
        """Reboots for updates are no triage agent work: the automatic weekly maintenance runs them."""
        self.assertEqual(self.rules_entry('routine_fixes_and_server_work', pool_minutes=12), [
            '  servers:',
            '    preset: routine_fixes_without_permission',
            '    playbooks:',
            '      replace_failed_servers: {rule: act_then_report, starts_a_server_replacement: true}',
            '      every_server: {rule: act_then_report}',
            '      destroy_replaced_servers: {rule: act_then_report}',
            '      add_an_app_server_for_the_load: {rule: warn_wait_then_act, warning_wait_minutes: 12}',
            '      remove_server: {rule: warn_wait_then_act, warning_wait_minutes: 12}',
        ] + self.SET_ASIDE_FINDINGS_RUN_AT_ONCE)

    def test_the_covering_key_only_with_get_permission_then_act(self):
        """MMHotline's settings check refuses the key with any other rule, and a named playbook that is not listed."""
        for answer in ('every_fix_waits_for_a_person', 'routine_fixes', 'routine_fixes_and_server_work'):
            with self.subTest(answer=answer):
                entry = self.rules_entry(answer)
                listed = {re.match(r'      (\w+): ', line)[1] for line in entry if line.startswith('      ')}
                for line in entry:
                    if 'its_approval_also_approves_in_the_same_session' in line:
                        self.assertIn('rule: get_permission_then_act', line)
                        named = re.search(r'its_approval_also_approves_in_the_same_session: \[(.*?)\]', line)[1].split(', ')
                        self.assertTrue(set(named) <= listed - {'replace_failed_servers'}, named)

    def test_only_replace_failed_servers_starts_a_server_replacement(self):
        """A load change is no outage, so neither load playbook, nor every_server, carries the mark."""
        for answer in ('every_fix_waits_for_a_person', 'routine_fixes', 'routine_fixes_and_server_work'):
            with self.subTest(answer=answer):
                marked = [line.split(':')[0].strip() for line in self.rules_entry(answer) if 'starts_a_server_replacement: true' in line]
                self.assertEqual(marked, ['replace_failed_servers'])

    def test_the_sos_wait_for_a_replacement_comes_from_the_stack_setting(self):
        text = self.rendered('routine_fixes', replacement_minutes=17)
        section = re.search(r'(?ms)^triage_agent:\n(.*?)^(?=\S)', text).group(1)
        self.assertRegex(section, r'(?m)^  sos_waits_for_the_agent_minutes: 3$')
        self.assertRegex(section, r'(?m)^  sos_waits_for_a_server_replacement_minutes: 17$')
        settings = (T/'mmx_project_settings.yml').read_text()
        self.assertRegex(settings, r'(?m)^    sos_waits_for_a_server_replacement_minutes: 7$')

    def test_the_pinned_mmhotline_knows_the_covering_key(self):
        """The Stack needs an MMHotline that knows the covering key; judges each request at the newest trusted
        commit; leaves /proc/sys visible in its unit, so MMX in MMHotline's runs reads util01's boot ID; knows
        starts_a_server_replacement and sos_waits_for_a_server_replacement_minutes; has its software review send
        the reports the team's task asks for; and holds a warning that starts a triage session for
        triage_agent.warn_waits_for_the_agent_minutes; trusts every commit on origin
        (trusted_commits: every_commit_on_origin, since 0.3.0 under triage_agent, and in systems_repository_commits from 0.5.0);
        publishes the status page with titles, impacts, components, edit/delete, and Atom feed (since 0.6.0); and clears
        the triage agent's home before each run, so a newer coding agent's settings files never carry over (since 0.6.1);
        and holds every warning for the triage agent's report, with a daily run limit that never stops alerts (since 0.7.0);
        and defaults personal contact methods to SOS and Warning only, honors /etc/mmhotline/everyone-locked-out directly,
        and requires --about-alert-id for info reports to take over held warnings (since 0.8.0).
        The pin names the release that does all of this."""
        settings = (T/'mmx_project_settings.yml').read_text()
        version = re.search(r'(?m)^    mmhotline:\n      version: "(.*?)"', settings)[1]
        self.assertEqual(version, '0.8.0')

    def test_the_held_warn_wait_comes_from_the_stack_setting_for_every_answer(self):
        settings = (T/'mmx_project_settings.yml').read_text()
        # 15 by default since MMHotline 0.7.0 holds every warning, also one that joins a running session.
        self.assertRegex(settings, r'(?m)^    warn_waits_for_the_triage_agent_minutes: 15$')
        for answer in ('every_fix_waits_for_a_person', 'routine_fixes', 'routine_fixes_and_server_work'):
            with self.subTest(answer=answer):
                text = self.rendered(answer, held_warn_minutes=7)
                section = re.search(r'(?ms)^triage_agent:\n(.*?)^(?=\S)', text).group(1)
                self.assertRegex(section, r'(?m)^  warn_waits_for_the_agent_minutes: 7$')

    def test_the_run_limit_and_the_start_message_are_set_with_their_defaults(self):
        """MMHotline 0.7.0's run limit and start message, written out with MMHotline's defaults, for every answer."""
        for answer in ('every_fix_waits_for_a_person', 'routine_fixes', 'routine_fixes_and_server_work'):
            with self.subTest(answer=answer):
                section = re.search(r'(?ms)^triage_agent:\n(.*?)^(?=\S)', self.rendered(answer)).group(1)
                self.assertRegex(section, r'(?m)^  most_runs_in_24_hours: 50$')
                self.assertRegex(section, r'(?m)^  send_a_message_when_the_agent_starts_looking: false$')

    def alert_sources(self, text):
        """Each rendered alert source as a mapping of its plain keys."""
        block = re.search(r'(?ms)^alert_sources:\n(.*?)^(?=\S)', text).group(1)
        sources = []
        for line in block.splitlines():
            entry = re.match(r'^  (- |  )(\w+): (.*)$', line)
            if entry:
                if entry[1] == '- ':
                    sources.append({})
                sources[-1][entry[2]] = entry[3]
        return sources

    def test_the_nodes_send_without_the_hub_under_a_source_that_folds_repeats(self):
        """The hub keeps every warning; only the nodes' direct sends during a hub outage fold, under their own source."""
        hub, nodes = self.alert_sources(self.rendered('routine_fixes'))
        self.assertEqual(hub['alert_source_id'], 'mmwatchdog_fleet_hub')
        self.assertEqual(hub['repeated_warnings'], 'keep_each')
        self.assertEqual(nodes['alert_source_id'], 'mmwatchdog_nodes_while_the_hub_is_down')
        self.assertEqual(nodes['repeated_warnings'], 'fold_by_sender_incident_key_and_first_message_line')
        self.assertEqual(nodes['warn_after_no_check_in_for_minutes'], 'off')
        # MMHotline accepts 1 to 60 minutes; nothing checks in on the source, so the value is never used.
        self.assertTrue(1 <= int(nodes['sos_after_no_check_in_for_minutes']) <= 60)
        # Joined nodes already hold the hub's signing secret, so the second source reuses it: no new vault key.
        self.assertEqual(nodes['signing_secrets'], hub['signing_secrets'])
        destinations = (T/'roles/util_server/files/alert_destinations.yml').read_text()
        self.assertIn('    mmhotline:\n'
                      '      mmhotline_url: http://{{ .inputs.private_ip }}:8484\n'
                      '      mmhotline_alert_source_id: mmwatchdog_fleet_hub\n'
                      '      mmhotline_signing_secret_file: /etc/mmwatchdog/secrets/mmhotline-signing-secret\n'
                      '      alert_source_for_nodes_sending_without_the_hub:\n'
                      '        mmhotline_alert_source_id: mmwatchdog_nodes_while_the_hub_is_down\n'
                      '        mmhotline_signing_secret_file: /etc/mmwatchdog/secrets/mmhotline-signing-secret\n', destinations)

    def test_every_server_refuses_other_values_first(self):
        playbook = (T/'playbooks/every_server.yml').read_text()
        answer = re.search(r"matches: \[\"\{\{ \.vars\.what_the_triage_agent_may_do_without_a_person \}\}\", '(.*?)'\]", playbook)[1]
        for value, accepted in (('every_fix_waits_for_a_person', True), ('routine_fixes', True),
                                ('routine_fixes_and_server_work', True), ('nothing_but_checks', False),
                                ('every_fix_without_permission', False), ('routine_fixes ', False), ('', False)):
            with self.subTest(value=value):
                self.assertEqual(bool(re.search(answer, value)), accepted)
        # The stage stops the run before any server changes: it comes before the every_server stage.
        stages = re.findall(r'(?m)^  - id: (\S+)', playbook)
        self.assertLess(stages.index('validate_what_the_triage_agent_may_do_without_a_person'), stages.index('every_server'))
        self.assertIn('on_node_failure: stop_run', playbook.split('- id: validate_what_the_triage_agent_may_do_without_a_person')[1][:200])
        for limit in ('number_at_least: ["{{ .vars.triage_agent_server_work.tries_to_replace_a_failed_server }}", 1]',
                      'number_at_least: ["{{ .vars.triage_agent_server_work.sos_waits_for_a_server_replacement_minutes }}", 0]',
                      'number_at_most: ["{{ .vars.triage_agent_server_work.sos_waits_for_a_server_replacement_minutes }}", 60]',
                      'number_at_least: ["{{ .vars.triage_agent_server_work.warn_waits_for_the_triage_agent_minutes }}", 0]',
                      'number_at_most: ["{{ .vars.triage_agent_server_work.warn_waits_for_the_triage_agent_minutes }}", 30]',
                      'number_at_least: ["{{ .vars.growth_limits.app_servers.smallest_number_of_servers }}", 1]',
                      'number_at_most: ["{{ .vars.growth_limits.app_servers.smallest_number_of_servers }}", "{{ .vars.growth_limits.app_servers.largest_number_of_servers }}"]',
                      'number_at_least: ["{{ .vars.triage_agent_server_work.minutes_between_the_warning_and_adding_or_removing_an_app_server }}", 1]',
                      'number_at_most: ["{{ .vars.triage_agent_server_work.minutes_between_the_warning_and_adding_or_removing_an_app_server }}", 1440]',
                      'number_at_least: ["{{ .vars.triage_agent_server_work.minutes_of_high_load_before_an_app_server_is_added }}", 5]',
                      'number_at_least: ["{{ .vars.triage_agent_server_work.days_of_low_load_before_an_app_server_is_removed }}", 1]',
                      'number_at_most: ["{{ .vars.triage_agent_server_work.days_of_low_load_before_an_app_server_is_removed }}", 7]',
                      'number_at_least: ["{{ .vars.triage_agent_server_work.cpu_percent_below_which_the_app_pool_can_spare_a_server }}", 1]',
                      'number_at_most: ["{{ .vars.triage_agent_server_work.cpu_percent_below_which_the_app_pool_can_spare_a_server }}", 69]'):
            with self.subTest(limit=limit):
                self.assertIn(limit, playbook)

    def test_the_triage_agent_replaces_app_jobs_and_load_balancer_servers_only(self):
        """Database servers, util01 and staging01 always need a person; the template lists the other three."""
        playbook = (T/'playbooks/every_server.yml').read_text()
        pools = re.search(r"""matches: \["\{\{ \.pool \}\}", '(.*?)'\]""", playbook)[1]
        for pool, accepted in (('app_servers', True), ('jobs_servers', True), ('load_balancer_servers', True),
                               ('database_servers', False), ('util_server', False), ('staging_server', False),
                               ('database_restore_servers', False), ('systems_desks', False), ('app_servers ', False)):
            with self.subTest(pool=pool):
                self.assertEqual(bool(re.search(pools, pool)), accepted)
        self.assertIn('loop: "{{ .vars.triage_agent_server_work.pools_whose_failed_servers_the_triage_agent_replaces }}"', playbook)
        settings = (T/'mmx_project_settings.yml').read_text()
        self.assertIn('    pools_whose_failed_servers_the_triage_agent_replaces: [app_servers, jobs_servers, load_balancer_servers]\n', settings)


class TheRulesTheAgentReads(unittest.TestCase):
    """The sentences that runs on real servers showed to be read the wrong way."""
    rules = (T/'triage_agent_rules.md').read_text()

    def test_the_playbooks_refusals_not_the_returning_fault_rule_decide_a_replacement(self):
        # The agent refused twice, quoting the 24-hour returning-fault rule, against the replacement's own setting.
        flat = ' '.join(self.rules.split())
        self.assertIn("The playbook's own refusals decide whether a failed server is replaced. The rule for a returning fault in "
                      "[When to hand over](#when-to-hand-over) does not apply to it.", flat)
        self.assertIn('This rule and the next one do not cover a failed server of a pool that `replace_failed_servers` replaces', flat)

    def test_a_failure_on_another_server_is_not_a_bad_new_server(self):
        """Real run 2026-11-13: lb01 was also down, and the agent replaced the new jobs server again."""
        flat = ' '.join(self.rules.split())
        self.assertIn('Before you treat a failed `every_server` run as a bad new server, read which server and stage failed.', flat)
        self.assertIn("is that server's problem: replace that server, or report it, and do not replace the new one", flat)

    def test_a_request_is_once_for_its_warning_not_once_for_the_session(self):
        self.assertNotIn('once for the session', ' '.join(self.rules.split()))
        # The add and the removal for the load; reboots for updates are no
        # longer the triage agent's work (the automatic weekly maintenance).
        self.assertEqual(' '.join(self.rules.split()).count('once for this warning'), 2)

    def test_nothing_is_committed_between_a_request_and_its_run(self):
        self.assertIn('**Commit nothing between a request for a run and the run.**', ' '.join(self.rules.split()))

    def test_a_person_can_leave_word_for_a_running_session(self):
        """MMHotline offers a note with Claim, Take over or Resolve, and a reason with a refusal or Stop;
        a committed notes file is read only from the next run."""
        flat = ' '.join(self.rules.split())
        self.assertNotIn('reads only its own prompt', flat)
        self.assertNotIn('waits for the session to end', flat)
        self.assertIn('"Note for the team (optional)"', flat)
        self.assertIn('Read the "Notes from the team" section of your prompt first, and treat each note as a team member\'s own words', flat)
        self.assertIn('MMHotline does not tell you it is new', flat)
        replace = ' '.join((T/'operating_procedures/replace_a_server.md').read_text().split())
        self.assertNotIn('reads only its own prompt', replace)
        self.assertNotIn('wait for the session to end', replace)
        self.assertIn('claim the incident in MMHotline with a note, or give a reason when you refuse an approval or press Stop. The agent reads it at its next step.', replace)

    def test_a_report_names_the_warnings_it_covers(self):
        """MMHotline 0.7.0 holds every warning, and only a report or a told-about request that names it takes it over."""
        flat = ' '.join(self.rules.split())
        self.assertIn('**Name each alert your report or request is about** with `--about-alert-id ALERT_ID`', flat)
        self.assertIn('A playbook that runs at once and reports (`act_then_report`) takes nothing over', flat)
        self.assertIn('**A warning that nothing of your run names reaches people when your run ends,**', flat)
        self.assertIn('a verdict about one server never covers another', flat)

    def test_a_finding_is_set_aside_only_on_evidence_for_every_server(self):
        flat = ' '.join(self.rules.split())
        self.assertIn('Your evidence holds for every server with that exact finding', flat)
        self.assertIn('is allowed only when a Stack role makes that configuration the same on every server: the reason names the role and the setting', flat)
        self.assertIn('`mmhotline triage-agent request-playbook-run --playbook playbooks/apply_set_aside_findings.yml --inventory servers', flat)
        self.assertIn('report at info with `--about-alert-id ALERT_ID` once for each alert the entry covers', flat)
        # The example names a setting the role writes; the rule removes an entry before a change makes its reason false.
        self.assertIn('roles/every_server writes PasswordAuthentication no', flat)
        every_server = (T/'roles/every_server/main.yml').read_text()
        self.assertIn('PasswordAuthentication no', every_server)
        self.assertIn('KbdInteractiveAuthentication no', every_server)
        self.assertIn("removal confirmed on the hub, before that change deploys", flat)

    def test_an_add_or_a_removal_is_reported_only_after_reading_the_runs_result(self):
        """On a real server, the agent wrote "Created a second app server" before reading that the add found nothing to add."""
        flat = ' '.join(self.rules.split())
        self.assertIn("**Report what an add or a removal did only after reading the run's result**", flat)
        self.assertIn('report at info that the run found nothing to add, or nothing to remove, and that nothing changed', flat)

    def test_the_rules_say_the_measured_time_of_a_replacement(self):
        flat = ' '.join(self.rules.split())
        self.assertIn('Your site should answer again in about 3 minutes.", with the new server\'s type and monthly price', flat)
        # One report per completed run: none before a run starts or while it runs.
        self.assertIn('Send no report before a run starts and none while it runs', flat)
        self.assertIn("Take the minutes from when your site answered again", flat)
        self.assertNotIn('about 6 minutes', flat)

    def test_a_load_change_ends_silently_and_warns_only_when_it_fails(self):
        # A scale-up or scale-down is routine work, so one sound, at its start.
        flat = ' '.join(self.rules.split())
        self.assertIn('**Report the steps and the outcome at info; warn only when the change fails or is refused.**', flat)
        self.assertIn('send the outcome as the last report, at info too', flat)
        self.assertIn('Report at warn only when the add or the removal fails or is refused', flat)
        self.assertNotIn('send the outcome as the one report at warn', flat)
        self.assertNotIn('rings once at its start', flat)


if __name__ == '__main__':
    unittest.main()
