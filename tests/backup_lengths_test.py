#!/usr/bin/env python3
"""Render pgBackRest's settings with the backup lengths of vars.backups, with MMX.

  MMX_BINARY=/path/to/mmx python3 tests/backup_lengths_test.py

It proves pgBackRest keeps full backups by time (keep_database_backups_for_days),
and that each length below its minimum stops the run with a message that names
the reason.
"""
import unittest

from phone_code_lockout_test import Rendered as RenderingTestCase

GOOD = dict(keep_database_backups_for_days=21, lock_backups_against_deletion_for_days=14,
            keep_prior_file_versions_in_buckets_for_days=14)
FILE = 'files_used_by_several_roles/pgbackrest.conf'


class BackupLengths(RenderingTestCase):
    def settings(self, **changes):
        return dict(pgbackrest_settings=dict(
            b2_s3_endpoint='s3.example.com', b2_region='r', bucket_name='b', bucket_key_id='k',
            bucket_application_key='a', repository_cipher_passphrase='p', data_directory='/d', **dict(GOOD, **changes)))

    def test_full_backups_are_kept_by_time(self):
        text = self.render(FILE, **self.settings())
        self.assertIn('repo1-retention-full-type=time\n', text)
        self.assertIn('repo1-retention-full=21\n', text)
        self.assertNotIn('repo1-retention-full-type=count', text)
        text = self.render(FILE, **self.settings(keep_database_backups_for_days=35, lock_backups_against_deletion_for_days=35))
        self.assertIn('repo1-retention-full=35\n', text)

    def test_a_number_that_arrives_as_a_decimal_is_accepted(self):
        text = self.render(FILE, **self.settings(keep_database_backups_for_days=21.0,
                                                 lock_backups_against_deletion_for_days=14.0,
                                                 keep_prior_file_versions_in_buckets_for_days=14.0))
        self.assertIn('repo1-retention-full=21\n', text)

    def test_the_minimums_hold_at_their_edges(self):
        self.render(FILE, **self.settings(keep_database_backups_for_days=14, lock_backups_against_deletion_for_days=8,
                                          keep_prior_file_versions_in_buckets_for_days=1))
        self.render(FILE, **self.settings(keep_database_backups_for_days=14, lock_backups_against_deletion_for_days=14))

    def test_a_length_below_its_minimum_stops_with_its_reason(self):
        cases = [
            (dict(keep_database_backups_for_days=13), 'below the minimum of 14', 'restore drill needs the previous full backup'),
            (dict(lock_backups_against_deletion_for_days=7), 'below the minimum of 8', 'warns at 8 days'),
            (dict(lock_backups_against_deletion_for_days=22), 'more than backups.keep_database_backups_for_days', 'still locked'),
            (dict(keep_prior_file_versions_in_buckets_for_days=0), 'keep_prior_file_versions_in_buckets_for_days is 0', 'at least 1'),
            (dict(keep_database_backups_for_days='three weeks'), 'keep_database_backups_for_days is three weeks', 'whole number'),
        ]
        for changes, words, reason in cases:
            with self.subTest(changes=changes):
                rendered = self.render_result(FILE, **self.settings(**changes))
                self.assertNotIn('text', rendered)
                self.assertIn(words, rendered['not_rendered_because'])
                self.assertIn(reason, rendered['not_rendered_because'])


if __name__ == '__main__':
    unittest.main()
