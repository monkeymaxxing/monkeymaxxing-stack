#!/usr/bin/env python3
"""Prepare an UpdateSchedule request from a protected GetSchedule response."""
import json
import os
from pathlib import Path
import sys

if len(sys.argv) != 4 or sys.argv[3] not in ['ENABLED', 'DISABLED']:
    raise SystemExit('Usage: set-schedule-state.py RESPONSE_FILE REQUEST_FILE ENABLED|DISABLED')
os.umask(0o077)
request = json.loads(Path(sys.argv[1]).read_text())
for field in ['Arn', 'CreationDate', 'LastModificationDate']:
    request.pop(field, None)
request['State'] = sys.argv[3]
with Path(sys.argv[2]).open('x') as output:
    json.dump(request, output, indent=2)
    output.write('\n')
