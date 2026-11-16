# Administrative aggregate. Counts can lag. Application sessions keep DATABASE_URL.
import json, os
import psycopg
from psycopg.rows import dict_row
for purpose, variable in [("read", "DATABASE_READ_URL"), ("write", "DATABASE_URL")]:
    with psycopg.connect(os.environ[variable], row_factory=dict_row) as connection:
        row = connection.execute("select inet_server_addr()::text as database_server_address, pg_is_in_recovery() as is_replica, (select count(*) from records) as record_count").fetchone()
        print(json.dumps({"connection_purpose": purpose, **row}))
