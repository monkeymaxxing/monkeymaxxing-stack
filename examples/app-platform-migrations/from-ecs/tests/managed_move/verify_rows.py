#!/usr/bin/env python3
"""Compare full HTTP acknowledgements, fenced source rows, and fixture objects."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from proof_common import read_settings, write_private
from source_fixture import capture


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def javascript_milliseconds(value):
    instant = timestamp(value)
    return instant.replace(microsecond=(instant.microsecond // 1000) * 1000)


def rows_by_id(rows, label):
    result = {}
    for row in rows:
        if row['id'] in result:
            raise ValueError(label + ': record ID reused: ' + row['id'])
        result[row['id']] = row
    return result


def load_acknowledgements(path):
    rows = []
    results = []
    for line in Path(path).read_text().splitlines():
        value = json.loads(line)
        if value.get('event') == 'write_result':
            results.append(value)
            if value['acknowledged']:
                row = value['row']
                if row.get('title') != value['submitted']['title']:
                    raise ValueError('HTTP acknowledgement differs from submitted title')
                if row.get('description') != '':
                    raise ValueError('POST must return the actual empty description default')
                rows.append(row)
    if not rows:
        raise ValueError('No acknowledged writer rows were recorded')
    return rows_by_id(rows, 'HTTP acknowledgements'), results


def check_http_rows(expected, actual, label):
    indexed = rows_by_id(actual, label)
    for record_id, response in expected.items():
        database_row = indexed.get(record_id)
        if database_row is None:
            raise ValueError(label + ': missing acknowledged record ' + record_id)
        # All fields must match. Only JS Date's documented millisecond loss is normalized.
        if set(database_row) != set(response):
            raise ValueError(label + ': record fields differ for ' + record_id)
        for field, value in response.items():
            matches = (javascript_milliseconds(database_row[field]) == timestamp(value)
                       if field == 'created_at' else database_row[field] == value)
            if not matches:
                raise ValueError(label + ': acknowledged field differs: ' + record_id + '.' + field)


def check_exact_rows(expected, actual, label):
    indexed = rows_by_id(actual, label)
    for record_id, source_row in rows_by_id(expected, 'fenced source').items():
        if indexed.get(record_id) != source_row:
            raise ValueError(label + ': full fenced source row differs: ' + record_id)


def compare(expected, server_facts, source_facts=None, fixture_facts=None):
    if set(server_facts) != {'db01', 'db02'}:
        raise ValueError('Supply exactly db01 and db02 PostgreSQL connections')
    for label, facts in server_facts.items():
        check_http_rows(expected, facts['records'], label)
        if source_facts:
            check_exact_rows(source_facts['records'], facts['records'], label)
        fixture = source_facts['fixture'] if source_facts else fixture_facts
        if fixture is not None and facts['fixture'] != fixture:
            raise ValueError(label + ': schema, sequence, fixture rows, large object, owner, or ACL differs')
    # Compare raw PostgreSQL JSON values, including complete timestamp microseconds.
    first = rows_by_id(server_facts['db01']['records'], 'db01')
    second = rows_by_id(server_facts['db02']['records'], 'db02')
    if first != second:
        raise ValueError('db01/db02 full PostgreSQL rows differ, including raw timestamp precision')
    if server_facts['db01']['fixture'] != server_facts['db02']['fixture']:
        raise ValueError('db01/db02 fixture facts differ')


def pause_summary(results, fence_seconds=None):
    acknowledgements = [row for row in results if row['acknowledged']]
    failures = [row for row in results if not row['acknowledged']]
    consecutive_gaps = [
        (timestamp(right['response_received_at']) - timestamp(left['response_received_at'])).total_seconds()
        for left, right in zip(acknowledgements, acknowledgements[1:])]
    summary = {'acknowledged_write_count': len(acknowledgements),
               'failed_or_uncertain_request_count': len(failures),
               'maximum_acknowledgement_gap_seconds': max(consecutive_gaps, default=0)}
    if fence_seconds is not None:
        after_fence = [row for row in acknowledgements
                       if timestamp(row['request_started_at']).timestamp() >= fence_seconds]
        if not after_fence:
            raise ValueError('No acknowledged request started after the relay fence completed')
        first = after_fence[0]
        summary['relay_fence_completed_unix_seconds'] = fence_seconds
        summary['first_acknowledgement_after_fence'] = first['response_received_at']
        summary['recovery_after_fence_seconds'] = (
            timestamp(first['response_received_at']).timestamp() - fence_seconds)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('settings_file', type=Path)
    args = parser.parse_args()
    settings = read_settings(args.settings_file)
    expected, results = load_acknowledgements(settings['writer_log_file'])
    source_facts = (json.loads(Path(settings['source_frozen_facts_file']).read_text())
                    if settings.get('source_frozen_facts_file') else None)
    initial = (json.loads(Path(settings['fixture_facts_file']).read_text())
               if settings.get('fixture_facts_file') else None)
    if source_facts is None and initial is None:
        parser.error('Supply source_frozen_facts_file or fixture_facts_file')
    server_facts = {name: capture(env, args.settings_file.parent)
                    for name, env in settings['servers'].items()}
    # Save raw reads even when verification fails, for protected examination.
    write_private(settings['observed_facts_file'], json.dumps(server_facts, ensure_ascii=False, indent=2) + '\n')
    compare(expected, server_facts, source_facts, initial['fixture'] if initial else None)
    summary = pause_summary(results, settings.get('relay_fence_completed_unix_seconds'))
    summary.update(verified=True, database_servers=sorted(server_facts),
                   fenced_source_record_count=len(source_facts['records']) if source_facts else None,
                   total_destination_record_count=len(server_facts['db01']['records']),
                   fixture_verified=True, exact_postgresql_timestamp_precision_verified=True)
    write_private(settings['verification_file'], json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
