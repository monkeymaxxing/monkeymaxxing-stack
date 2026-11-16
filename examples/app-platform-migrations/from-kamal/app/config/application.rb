require_relative "boot"
require "rails"
require "active_record/railtie"
require "action_controller/railtie"
require "action_view/railtie"
Bundler.require(*Rails.groups)
# Rails' generic URI parser rejects host:port,host:port. libpq parses it intact.
STACK_DATABASE_URL = ENV.delete("DATABASE_URL")
module CustomerPortal
  class Application < Rails::Application
    config.load_defaults 8.1
    config.eager_load = true
    config.secret_key_base = ENV.fetch("SECRET_KEY_BASE")
    config.hosts = [URI(ENV.fetch("APP_ORIGIN")).host, "127.0.0.1", "localhost"]
    config.logger = Logger.new($stdout)
    config.log_level = :warn
    config.filter_parameters += [:password, :token, :file]
    config.active_record.dump_schema_after_migration = false
    config.active_record.migration_error = false
    config.action_dispatch.show_exceptions = :none
    config.host_authorization = { exclude: ->(request) { request.path == "/healthz" } }
    config.public_file_server.enabled = true
    config.public_file_server.headers = { "Cache-Control" => "public, max-age=31536000, immutable" }
    config.assume_ssl = true # Public HTTPS terminates at the Stack's ingress.
    config.force_ssl = false
    config.assets.paths << root.join("app/assets/stylesheets")
  end
end
