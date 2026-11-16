# Administrative aggregate. Counts can lag. Web requests keep the primary.
require_relative "../config/environment"
require "json"
class ReplicaReport < ActiveRecord::Base
  self.abstract_class = true
end
[ ["read", "DATABASE_READ_URL"], ["write", nil] ].each do |purpose, variable|
  settings = if variable
    PG::Connection.conninfo_parse(ENV.fetch(variable)).filter_map { |item| [item[:keyword], item[:val]] if item[:val] }.to_h
  else
    PG::Connection.conninfo_parse(STACK_DATABASE_URL).filter_map { |item| [item[:keyword], item[:val]] if item[:val] }.to_h
  end
  settings["database"] = settings.delete("dbname")
  ReplicaReport.establish_connection(settings.merge("adapter" => "postgresql", "pool" => 1))
  row = ReplicaReport.connection.select_one("select inet_server_addr()::text as database_server_address, pg_is_in_recovery() as is_replica, (select count(*)::int from records) as record_count")
  puts JSON.generate({"connection_purpose" => purpose}.merge(row))
  ReplicaReport.connection_pool.disconnect!
end
