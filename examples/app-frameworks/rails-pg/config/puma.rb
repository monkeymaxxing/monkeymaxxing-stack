environment ENV.fetch("RAILS_ENV", "production")
raise_exception_on_sigterm false
workers Integer(ENV.fetch("WEB_CONCURRENCY", "1"))
thread_count = Integer(ENV.fetch("WEB_THREADS", "4"))
threads thread_count, thread_count
bind "tcp://0.0.0.0:#{Integer(ENV.fetch('PORT', '8000'))}"
worker_timeout 30
worker_shutdown_timeout 25
force_shutdown_after 25
preload_app!
before_fork { ActiveRecord::Base.connection_pool.disconnect! }
before_worker_boot { ActiveRecord::Base.establish_connection }
