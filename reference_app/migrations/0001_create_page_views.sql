-- Each view of the home page: which app server served it, and which
-- database server took the write. The database server fills in its own IP
-- address, with inet_server_addr(), which is empty for a connection through
-- a Unix socket.
create table page_views (
  id bigserial primary key,
  viewed_at timestamptz not null default now(),
  app_server_host_name text not null,
  database_server_ip_address inet
);
