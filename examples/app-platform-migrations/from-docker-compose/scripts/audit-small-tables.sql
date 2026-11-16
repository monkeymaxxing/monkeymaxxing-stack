\set QUIET on
\set ON_ERROR_STOP on
\pset tuples_only on
\pset format unaligned
-- The bulk load has a separate byte/hash audit. Compare every row of all other tables.
SELECT format('SELECT jsonb_build_object(''table'',%L,''rows'',coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),''[]''::jsonb)) FROM %I.%I t;',
              schemaname||'.'||tablename,schemaname,tablename)
FROM pg_tables WHERE schemaname IN ('public','migration_history') AND tablename<>'migration_load'
ORDER BY schemaname,tablename
\gexec
