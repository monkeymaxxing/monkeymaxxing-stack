import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None

def connect():
    # libpq consumes the unchanged multi-host URL, including target_session_attrs.
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row,
        options=os.environ.get('PGOPTIONS', ''), keepalives=1)

def open_pool():
    global _pool
    _pool = ConnectionPool(os.environ['DATABASE_URL'], min_size=0, max_size=int(os.environ.get("DATABASE_POOL_MAX_CONNECTIONS", "4")),
        timeout=8, check=ConnectionPool.check_connection,
        kwargs={'row_factory':dict_row, 'keepalives':1,
                'options':os.environ.get('PGOPTIONS','')})

def close_pool():
    if _pool is not None:
        _pool.close()

@contextmanager
def transaction():
    with _pool.connection() as connection:
        # No retry here: COMMIT may succeed even when its reply is lost.
        connection.execute("SET LOCAL statement_timeout = '5s'")
        yield connection
