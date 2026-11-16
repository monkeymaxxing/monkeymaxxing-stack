#!/usr/bin/env python3
"""Copy and switch the inventory's old database. Run as postgres on copy_onto."""
import json
import hashlib
import csv
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ERROR_FILE = Path('/var/lib/postgresql/database_moving_in_error.txt')
# This catalog is shared by the cluster. Several databases can each have a
# subscription with this name; worker statistics must use its database's OID.
SUBSCRIPTION_ID_QUERY = "SELECT oid FROM pg_subscription WHERE subname='database_moving_in' AND subdbid=(SELECT oid FROM pg_database WHERE datname=current_database())"


def literal(value):
    return "E'" + str(value).replace('\\','\\\\').replace("'", "''") + "'"


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def database_argument(database):
    # libpq treats an unquoted database name containing '=' as a connection
    # string. Keep every database name inside one quoted dbname parameter.
    return "dbname='"+database.replace('\\','\\\\').replace("'", "\\'")+"'"


def execute(arguments, *, env=None, input=None, timeout=None):
    try:
        result = subprocess.run(arguments, input=input, env=env, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError('The PostgreSQL command exceeded its time limit.') from None
    if result.returncode:
        # Schema errors can quote function bodies. Keep PostgreSQL's raw
        # detail private while MMX displays safe progress and pause numbers.
        ERROR_FILE.write_text(result.stderr)
        ERROR_FILE.chmod(0o600)
        raise RuntimeError(Path(arguments[0]).name+' failed. Private PostgreSQL details on copy_onto: '+str(ERROR_FILE))
    return result.stdout.strip()


def sql(database, text, source=False, timeout=5):
    arguments = ['psql', '-XqAt', '--no-password', '-v', 'ON_ERROR_STOP=1', '-d', database_argument(database)]
    if source:
        arguments[arguments.index('-d')+1] = database_argument(source_database(database))
        arguments += ['-h', moving['wireguard_address'], '-p', str(moving['postgres_port']), '-U', 'postgres']
    return execute(arguments, env=connection_env, input=text, timeout=timeout)


def slot(database):
    # Database names can use all 63 bytes or characters forbidden in slot
    # names. The digest gives each database a stable, legal source slot.
    return 'database_moving_in_' + hashlib.sha256(database.encode()).hexdigest()[:32]


def source_database(database):
    # The app entry is disabled at the fence. Copy/replication/admin reads
    # retain a separate route to the same provider database.
    return slot(database) if moving.get('through_relay', False) and database in databases else database


def relay_admin(command, *, csv_output=False):
    arguments = ['psql', '-X', '--no-password', '-v', 'ON_ERROR_STOP=1',
                 '-h', moving['wireguard_address'], '-p', str(moving['postgres_port']),
                 '-U', 'database_moving_in_relay_admin', '-d', 'pgbouncer']
    arguments += ['--csv'] if csv_output else ['-qAt']
    # PgBouncer requires one command per simple-query message.
    return execute(arguments, env=dict(connection_env,PGPASSFILE='/var/lib/postgresql/database_moving_in_relay_admin.pgpass'), input=command, timeout=5)


def relay_fence():
    for database in databases:
        relay_admin('DISABLE '+identifier(database))
    for database in databases:
        relay_admin('KILL '+identifier(database))


def reopen_relay():
    # KILL can leave an entry paused. Do not issue RESUME for an entry
    # that is not paused: PgBouncer reports that as an error.
    entries = {row['name']: row for row in csv.DictReader(io.StringIO(relay_admin('SHOW DATABASES', csv_output=True)))}
    for database in databases:
        relay_admin('ENABLE '+identifier(database))
        if entries[database]['paused'] == '1':
            relay_admin('RESUME '+identifier(database))


def subscription_connection(database):
    return ' '.join(key+"='"+str(value).replace('\\','\\\\').replace("'", "\\'")+"'" for key,value in {
        'host':moving['wireguard_address'], 'port':moving['postgres_port'], 'dbname':source_database(database),
        'user':'database_moving_in_replication', 'passfile':str(passfile),
        'connect_timeout':3, 'application_name':slot(database)}.items())


def source_setting(database):
    return sql(database, 'SHOW default_transaction_read_only', True)


def fence(setting):
    for database in databases:
        command = 'SET default_transaction_read_only = on' if setting == 'on' else 'RESET default_transaction_read_only'
        sql('postgres', 'ALTER DATABASE '+identifier(database)+' '+command, True)


def end_app_sessions(source=False):
    role_list = ','.join(literal(database) for database in databases)
    pids = json.loads(sql('postgres', 'SELECT coalesce(json_agg(pid),\'[]\') FROM pg_stat_activity WHERE usename IN ('+role_list+') AND pid<>pg_backend_pid()', source))
    if not pids:
        return
    pid_list = ','.join(str(int(pid)) for pid in pids)
    # The one-argument form also works on older logical-replication sources.
    # A signal is not proof of exit: poll the captured backends before LSNs.
    sql('postgres','SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid IN ('+pid_list+')',source)
    deadline = time.monotonic()+5
    while True:
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise RuntimeError('An app session did not exit within five seconds. Every captured session must exit before proceeding.')
        if sql('postgres','SELECT count(*) FROM pg_stat_activity WHERE pid IN ('+pid_list+')',source,timeout=min(3,remaining)) == '0':
            return
        time.sleep(0.05)


def ready(database):
    subscription = sql(database, "SELECT subenabled AND subslotname="+literal(slot(database))+
                       " AND subpublications=ARRAY['database_moving_in']::text[] AND subconninfo="+
                       literal(subscription_connection(database))+" FROM pg_subscription WHERE oid=("+SUBSCRIPTION_ID_QUERY+")")
    tables = sql(database, "SELECT count(*) FILTER (WHERE srsubstate<>'r') FROM pg_subscription_rel WHERE srsubid=("+SUBSCRIPTION_ID_QUERY+")")
    stream = sql(database, "SELECT count(*) FROM pg_stat_subscription WHERE subid=("+SUBSCRIPTION_ID_QUERY+") AND relid IS NULL AND pid IS NOT NULL AND received_lsn IS NOT NULL")
    connection = sql('postgres', "SELECT count(*) FROM pg_replication_slots s JOIN pg_stat_replication r ON r.pid=s.active_pid WHERE s.slot_name="+literal(slot(database))+" AND r.state='streaming'", True)
    if subscription != 't' or tables != '0' or stream != '1' or connection != '1':
        raise RuntimeError(database+': the subscription must be streaming with every table ready. The old database remains writable.')


def copy_database(database):
    unsupported = sql(database, "SELECT coalesce(string_agg(quote_ident(n.nspname)||'.'||quote_ident(c.relname),', '),'') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE (c.relpersistence='u' OR c.relkind IN ('m','f')) AND n.nspname NOT IN ('pg_catalog','pg_toast','information_schema') AND n.nspname !~ '^pg_(temp|toast_temp)_'", True)
    if unsupported:
        raise RuntimeError(database+': logical replication does not copy the stored rows of these relations: '+unsupported+'. Convert unlogged tables to logged tables, or plan the materialized-view/foreign-table data separately before using this procedure.')
    existing = sql(database, "SELECT count(*) FROM pg_subscription WHERE oid=("+SUBSCRIPTION_ID_QUERY+")")
    if existing == '1':
        ready(database)
        print(database+': the existing subscription is streaming with every table ready.')
        return
    if sql(database, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p','S','v','m','f') AND n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'") != '0':
        raise RuntimeError(database+': the Stack database is not empty. Do not overwrite app data. Inspect the database before starting a new copy.')
    if sql(database, "SELECT count(*) FROM pg_publication WHERE pubname='database_moving_in' AND puballtables", True) != '1':
        raise RuntimeError(database+': create the old database publication database_moving_in FOR ALL TABLES first.')
    replication_arguments = ['psql','-XqAt','--no-password','-v','ON_ERROR_STOP=1',
             '-h',moving['wireguard_address'],'-p',str(moving['postgres_port']),
             '-U','database_moving_in_replication']
    # Probe the permission itself: managed providers can grant replication
    # through a provider role instead of PostgreSQL's REPLICATION flag.
    execute(replication_arguments+['-d',database_argument(source_database(database))+' replication=database'],
            env=connection_env,input='IDENTIFY_SYSTEM',timeout=5)
    complete_rows = execute(replication_arguments+['-d',database_argument(source_database(database))],
            env=connection_env,input="SELECT rolbypassrls OR rolsuper OR NOT EXISTS (SELECT 1 FROM pg_class WHERE relrowsecurity) FROM pg_roles WHERE rolname=current_user",timeout=5)
    if complete_rows != 't':
        raise RuntimeError(database+': database_moving_in_replication needs BYPASSRLS when source tables use row security. Row security must not silently filter the initial copy.')
    # The source's SELECT/USAGE grants appear in its schema dump. Preserve
    # the grants without giving this source-only account a Stack login.
    if sql('postgres', "SELECT count(*) FROM pg_roles WHERE rolname='database_moving_in_replication'") == '0':
        sql('postgres','CREATE ROLE database_moving_in_replication NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION')
    dump = execute(['pg_dump','--schema-only','--no-publications','--no-subscriptions','--no-password',
                    '-h',moving['wireguard_address'],'-p',str(moving['postgres_port']),'-U','postgres','-d',database_argument(source_database(database))], env=connection_env)
    execute(['psql','-Xq','--single-transaction','-v','ON_ERROR_STOP=1','-d',database_argument(database)], env=connection_env, input=dump)
    # No password enters pg_subscription or the command line.
    sql(database, 'CREATE SUBSCRIPTION database_moving_in CONNECTION '+literal(subscription_connection(database))+
        ' PUBLICATION database_moving_in WITH (copy_data=true, synchronous_commit=on, slot_name='+literal(slot(database))+')',timeout=None)
    print(database+': schema loaded. The subscription is copying. Wait for every table to become ready before switching.')


def sequence_values(database):
    sequences = json.loads(sql(database, "SELECT coalesce(json_agg(json_build_array(n.nspname,c.relname)), '[]') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S'", True))
    for schema, name in sequences:
        qualified = identifier(schema)+'.'+identifier(name)
        value, called = sql(database, 'SELECT last_value,is_called FROM '+qualified, True).split('|')
        sql(database, 'SELECT pg_catalog.setval('+literal(qualified)+'::regclass,'+str(int(value))+','+('true' if called=='t' else 'false')+')')
    return len(sequences)


def large_objects(database):
    # Only the large objects, with their OIDs, owners and ACLs. The pattern
    # '*.*' excludes every table's and sequence's data in every schema; a bare
    # '*' matches only the search path's schemas, and pg_restore would reload
    # rows the subscription already copied (duplicate key) in any other schema.
    archive = working / (slot(database)+'.large_objects.dump')
    execute(['pg_dump','--format=custom','--data-only','--large-objects','--exclude-table-data=*.*',
             '--no-publications','--no-subscriptions','--no-password',
             '-h',moving['wireguard_address'],'-p',str(moving['postgres_port']),'-U','postgres','-d',database_argument(source_database(database)),'-f',str(archive)], env=connection_env)
    # The logical copy contains no large objects. Refuse an unexpected local
    # object rather than replacing an independently written object.
    if sql(database,'SELECT count(*) FROM pg_largeobject_metadata') != '0':
        raise RuntimeError(database+': the Stack copy already has large objects. Inspect before retrying the switch.')
    execute(['pg_restore','--exit-on-error','--single-transaction','-d',database_argument(database),str(archive)],env=connection_env)


def switch():
    # Check the old fence first: after a failed cleanup the old database is
    # already read-only, and ready() would wrongly say that it remains writable.
    if any(source_setting(database) != 'off' for database in databases):
        raise RuntimeError('An old app database is already read-only. Inspect the earlier switch before retrying.')
    for database in databases:
        ready(database)
    role_list = ','.join(literal(database) for database in databases)
    overrides = sql('postgres', "SELECT count(*) FROM pg_db_role_setting s CROSS JOIN LATERAL unnest(s.setconfig) c WHERE c LIKE 'default_transaction_read_only=%' AND (s.setrole IN (SELECT oid FROM pg_roles WHERE rolname IN ("+role_list+")) OR s.setdatabase IN (SELECT oid FROM pg_database WHERE datname IN ("+role_list+")))", True)
    if overrides != '0':
        raise RuntimeError('The old app roles or databases override default_transaction_read_only. Save and reset those overrides before switching, so the database fence reaches every app login.')
    through_relay = moving.get('through_relay', False)
    phase = 'before_subscription_cleanup'
    started = time.monotonic()
    parts = {}
    try:
        if through_relay:
            relay_fence()
            parts['relay_fence_completed_unix_seconds'] = round(time.time(),6)
        fence('on')
        end_app_sessions(source=True)
        # Insertion includes commits still in WAL buffers when the source uses
        # asynchronous commits. A write-position LSN can lag those commits.
        fenced_lsn = sql('postgres','SELECT pg_current_wal_insert_lsn()',True)
        parts['fence_seconds'] = round(time.monotonic()-started,3)
        waiting = time.monotonic()
        deadline = waiting+15
        for database in databases:
            while True:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('Subscriptions did not receive and durably apply the fenced LSN '+fenced_lsn+' within 15 seconds.')
                # replay_lsn is feedback from the logical apply worker, not
                # the origin's last published transaction or a receive-only LSN.
                applied = sql('postgres', 'SELECT coalesce(bool_and(r.write_lsn>='+literal(fenced_lsn)+
                              '::pg_lsn AND r.flush_lsn>='+literal(fenced_lsn)+'::pg_lsn AND r.replay_lsn>='+literal(fenced_lsn)+
                              '::pg_lsn),false) FROM pg_replication_slots s JOIN pg_stat_replication r ON r.pid=s.active_pid WHERE s.slot_name='+literal(slot(database)),True,timeout=min(3,remaining))
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('Subscriptions did not receive and durably apply the fenced LSN '+fenced_lsn+' within 15 seconds.')
                received = sql(database,"SELECT coalesce(bool_and(received_lsn>="+literal(fenced_lsn)+"::pg_lsn),false) FROM pg_stat_subscription WHERE subid=("+SUBSCRIPTION_ID_QUERY+") AND relid IS NULL",timeout=min(3,remaining))
                if applied == 't' and received == 't':
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError('Subscriptions did not receive and durably apply the fenced LSN '+fenced_lsn+' within 15 seconds.')
                time.sleep(0.05)
        parts['catch_up_seconds'] = round(time.monotonic()-waiting,3)
        copying = time.monotonic()
        for database in databases:
            sequence_values(database)
        parts['sequence_seconds'] = round(time.monotonic()-copying,3)
        copying = time.monotonic()
        for database in databases:
            large_objects(database)
        parts['large_object_seconds'] = round(time.monotonic()-copying,3)
        cleaning = time.monotonic()
        if through_relay:
            # Keep subscriptions until the Stack opens, so every earlier
            # failure can restore the old writer without losing replication.
            phase = 'disabling_subscriptions'
            for database in databases:
                sql(database,'ALTER SUBSCRIPTION database_moving_in DISABLE')
            parts['subscription_disable_seconds'] = round(time.monotonic()-cleaning,3)
        else:
            # Preserve the self-hosted switch's cleanup boundary.
            phase = 'removing_subscriptions'
            for database in databases:
                sql(database,'DROP SUBSCRIPTION database_moving_in')
            parts['subscription_cleanup_seconds'] = round(time.monotonic()-cleaning,3)
        opening = time.monotonic()
        if through_relay:
            phase = 'opening_stack'
        sql('postgres','BEGIN;\n'+'\n'.join('ALTER ROLE '+identifier(database)+' RESET default_transaction_read_only;' for database in databases)+'\nCOMMIT;')
        phase = 'stack_open'
        # PgBouncer can retain a read-only backend after its frontend closes.
        # Fresh backends must load the newly writable role defaults.
        end_app_sessions()
        parts['open_stack_seconds'] = round(time.monotonic()-opening,3)
        parts['write_pause_seconds'] = round(time.monotonic()-started,3)
        if through_relay:
            cleaning = time.monotonic()
            for database in databases:
                sql(database,'DROP SUBSCRIPTION database_moving_in')
            parts['subscription_cleanup_seconds'] = round(time.monotonic()-cleaning,3)
        print(json.dumps(parts,sort_keys=True))
        print('The Stack accepts writes. The old app databases remain read-only and any moving relay app entries remain disabled. Remove database_moving_in before the next every_server run. Measure customer recovery separately with your HTTP writer.')
    except BaseException:
        if phase == 'opening_stack':
            # A lost COMMIT reply can still mean roles opened. Reopen the
            # source only after confirming every Stack role remains fenced.
            try:
                still_closed = sql('postgres', "SELECT count(*)="+str(len(databases))+
                    " AND coalesce(bool_and('default_transaction_read_only=on'=ANY(coalesce(rolconfig,ARRAY[]::text[]))),false) FROM pg_roles WHERE rolname IN ("+role_list+")") == 't'
                phase = 'disabling_subscriptions' if still_closed else 'stack_may_be_open'
            except BaseException:
                phase = 'stack_may_be_open'
        if phase in ('before_subscription_cleanup','disabling_subscriptions'):
            try:
                if phase == 'disabling_subscriptions':
                    for database in databases:
                        sql(database,'ALTER SUBSCRIPTION database_moving_in ENABLE')
                fence('off')
                if through_relay:
                    reopen_relay()
            except BaseException as error:
                raise RuntimeError('Switch stopped, and the old fence could not be undone. The old database may remain read-only or the relay may remain disabled. Stack roles remain read-only. Restore the old server connection, re-enable disabled subscriptions, run ALTER DATABASE ... RESET default_transaction_read_only for each moving database, and ENABLE and RESUME moving relay entries if needed. Verify a fresh app login before retrying. '+str(error)) from error
            print('Switch stopped. The old database fence was undone and moving relay entries were enabled when configured. Stack app roles remain read-only. Subscriptions remain. Fix the cause before retrying.',file=sys.stderr)
        else:
            print('Switch stopped after the Stack may have opened or subscription cleanup began. The old database and any moving relay entries remain fenced. Keep database_moving_in set. Inspect subscriptions and Stack role settings before changing either side.',file=sys.stderr)
        raise


if __name__ == '__main__':
    os.umask(0o077)
    moving = json.loads(os.environ['DATABASE_MOVING_IN'])
    apps = json.loads(os.environ['APPS'])
    databases = list(dict.fromkeys(apps[app]['database_name'] for app in moving['apps']))
    with tempfile.TemporaryDirectory(prefix='database-moving-in-') as temporary:
        working = Path(temporary)
        # Subscription workers need this password file after the copy command
        # ends. The copy playbook writes it to a stable postgres-owned path.
        passfile = Path('/var/lib/postgresql/database_moving_in.pgpass')
        connection_env = dict(os.environ,PGCONNECT_TIMEOUT='3',PGPASSFILE=str(passfile))
        if sql('postgres','SELECT pg_is_in_recovery()') != 'f':
            sys.exit('copy_onto is not the live primary. Switch the formation primary to copy_onto before copying or switching.')
        try:
            if sys.argv[1]=='copy':
                for database in databases:
                    copy_database(database)
            elif sys.argv[1] in ('switch','switch_through_relay'):
                if moving.get('through_relay', False) and sys.argv[1]!='switch_through_relay':
                    sys.exit('Run switch_to_the_database_moving_in for database_moving_in.through_relay: true: its relay fleet stage passes the relay administrator password from the vault.')
                switch()
            else:
                sys.exit('Use copy, switch, or switch_through_relay.')
        except (RuntimeError,ValueError) as error:
            sys.exit(str(error))
