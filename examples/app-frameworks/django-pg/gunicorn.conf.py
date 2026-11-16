import os
bind = "0.0.0.0:" + str(int(os.environ.get("PORT", "8000")))
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.environ.get("WEB_THREADS", "4"))
if threads < 1:
    raise ValueError("WEB_THREADS must be a positive integer")
timeout = 30
graceful_timeout = 25
accesslog = None
errorlog = "-"
# The Stack runs the container with a read-only file system, and nothing here uses
# the control socket (the gunicornc admin tool), which would be created in
# the home directory. Without this line gunicorn logs an ERROR at every start.
control_socket_disable = True
