#!/usr/bin/env python3
"""Pure checks for data loss, ID reuse, ACL loss, and timestamp truncation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from proof_common import read_settings
from verify_rows import compare, load_acknowledgements, pause_summary


def row(record_id='record-1', title='proof:run:1:nonce', microseconds='123456'):
    return {'id': record_id, 'owner_id': 'owner-1', 'title': title, 'description': '',
            'created_at': '2026-11-06T01:02:03.' + microseconds + '+00:00'}


class ProofChecks(unittest.TestCase):
    def setUp(self):
        self.database_row = row()
        self.http_row = {**self.database_row, 'created_at': '2026-11-06T01:02:03.123Z'}
        self.fixture = {'sequence': {'last_value': 9041, 'is_called': True},
                        'large_objects': [{'oid': 123, 'bytes_hex': '00ff', 'owner': 'portal',
                                           'acl': [{'grantee': 'migration_evidence_reader',
                                                    'privilege_type': 'SELECT'}]}]}
        self.facts = {'records': [self.database_row], 'fixture': self.fixture}
        self.servers = {name: copy.deepcopy(self.facts) for name in ('db01', 'db02')}

    def verify(self, source=None):
        compare({'record-1': self.http_row}, self.servers, source, self.fixture)

    def test_millisecond_http_and_microsecond_postgresql_match(self):
        self.verify(self.facts)

    def test_same_id_wrong_value_is_not_proof(self):
        self.servers['db02']['records'][0]['title'] = 'different write'
        with self.assertRaisesRegex(ValueError, 'acknowledged field differs'):
            self.verify()

    def test_missing_acknowledged_row_fails(self):
        self.servers['db02']['records'] = []
        with self.assertRaisesRegex(ValueError, 'missing acknowledged record'):
            self.verify()

    def test_microseconds_differ_below_http_precision_fails(self):
        self.servers['db02']['records'][0]['created_at'] = '2026-11-06T01:02:03.123457+00:00'
        with self.assertRaisesRegex(ValueError, 'raw timestamp precision'):
            self.verify()

    def test_source_microseconds_lost_on_both_targets_fails(self):
        for facts in self.servers.values():
            facts['records'][0]['created_at'] = '2026-11-06T01:02:03.123000+00:00'
        with self.assertRaisesRegex(ValueError, 'fenced source row differs'):
            self.verify(self.facts)

    def test_source_rows_outside_load_actor_are_preserved(self):
        source = copy.deepcopy(self.facts)
        source['records'].append(row('old-record', 'old source row'))
        with self.assertRaisesRegex(ValueError, 'fenced source row differs'):
            self.verify(source)

    def test_acl_and_large_object_byte_loss_fail(self):
        for field, replacement in [('bytes_hex', '00fe'), ('acl', [])]:
            with self.subTest(field=field):
                servers = copy.deepcopy(self.servers)
                servers['db01']['fixture']['large_objects'][0][field] = replacement
                with self.assertRaisesRegex(ValueError, 'ACL differs'):
                    compare({'record-1': self.http_row}, servers, fixture_facts=self.fixture)

    def test_sequence_is_called_loss_fails(self):
        self.servers['db01']['fixture']['sequence']['is_called'] = False
        with self.assertRaisesRegex(ValueError, 'sequence'):
            self.verify()

    def test_reused_acknowledgement_id_fails(self):
        item = {'event': 'write_result', 'acknowledged': True, 'row': self.http_row,
                'submitted': {'title': self.http_row['title']}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'writer.jsonl'
            path.write_text(json.dumps(item) + '\n' + json.dumps(item) + '\n')
            with self.assertRaisesRegex(ValueError, 'ID reused'):
                load_acknowledgements(path)

    def test_nonempty_post_description_is_refused(self):
        item = {'event': 'write_result', 'acknowledged': True,
                'row': {**self.http_row, 'description': 'not POST behavior'},
                'submitted': {'title': self.http_row['title']}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'writer.jsonl'
            path.write_text(json.dumps(item) + '\n')
            with self.assertRaisesRegex(ValueError, 'empty description'):
                load_acknowledgements(path)

    def test_secret_settings_must_be_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('{}')
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'mode 600'):
                read_settings(path)

    def test_pause_uses_request_started_after_fence(self):
        results = [
            {'acknowledged': True, 'request_started_at': '2026-11-06T01:00:00Z',
             'response_received_at': '2026-11-06T01:00:03Z'},
            {'acknowledged': False, 'request_started_at': '2026-11-06T01:00:03Z',
             'response_received_at': '2026-11-06T01:00:04Z'},
            {'acknowledged': True, 'request_started_at': '2026-11-06T01:00:04Z',
             'response_received_at': '2026-11-06T01:00:05Z'}]
        # The in-flight pre-fence acknowledgement must not claim customer recovery.
        from verify_rows import timestamp
        fence = timestamp('2026-11-06T01:00:02Z').timestamp()
        summary = pause_summary(results, fence)
        self.assertEqual(summary['recovery_after_fence_seconds'], 3)
        self.assertEqual(summary['maximum_acknowledgement_gap_seconds'], 2)
        self.assertEqual(summary['failed_or_uncertain_request_count'], 1)


if __name__ == '__main__':
    unittest.main()
