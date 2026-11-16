\set QUIET on
\set ON_ERROR_STOP on
\pset tuples_only on
\pset format unaligned
SELECT jsonb_build_object('kind','relation','name',n.nspname||'.'||c.relname,'owner',pg_get_userbyid(c.relowner),'acl',c.relacl::text)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname IN ('public','migration_history') AND c.relkind IN ('r','S') ORDER BY c.relname;
SELECT jsonb_build_object('kind','large_object','id',m.oid,'owner',pg_get_userbyid(m.lomowner),'acl',m.lomacl::text,
'bytes',octet_length(lo_get(m.oid)),'md5',md5(lo_get(m.oid)))
FROM pg_largeobject_metadata m ORDER BY m.oid;
SELECT jsonb_build_object('kind','default_acl','owner',pg_get_userbyid(d.defaclrole),'schema',n.nspname,'type',d.defaclobjtype,'acl',d.defaclacl::text)
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace ORDER BY 1;
