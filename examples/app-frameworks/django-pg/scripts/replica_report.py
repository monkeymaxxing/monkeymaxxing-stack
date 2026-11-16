# Explicit ORM alias for an administrative aggregate. Web/session routing stays unchanged.
import json, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portal.settings")
import django
django.setup()
from django.db import connections
from psycopg.conninfo import conninfo_to_dict
from portal.models import Record
params = conninfo_to_dict(os.environ["DATABASE_READ_URL"])
fields = {name: params.pop(key, "") for name, key in [("NAME", "dbname"), ("USER", "user"), ("PASSWORD", "password"), ("HOST", "host"), ("PORT", "port")]}
connections.databases["replica"] = {**connections.databases["default"], **fields, "OPTIONS": params}
for purpose, alias in [("read", "replica"), ("write", "default")]:
    with connections[alias].cursor() as cursor:
        cursor.execute("select inet_server_addr()::text, pg_is_in_recovery()")
        address, replica = cursor.fetchone()
    print(json.dumps({"connection_purpose": purpose, "database_server_address": address, "is_replica": replica, "record_count": Record.objects.using(alias).count()}))
    connections[alias].close()
