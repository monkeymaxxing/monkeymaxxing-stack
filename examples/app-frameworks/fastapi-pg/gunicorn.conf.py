import os
bind='0.0.0.0:'+os.environ['PORT']
workers=int(os.environ['WEB_CONCURRENCY'])
if workers<1:raise ValueError('WEB_CONCURRENCY must be positive')
worker_class='uvicorn_worker.UvicornWorker'
graceful_timeout=25
timeout=60
accesslog=None
errorlog='-'
# The Stack runs the container with a read-only file system, and nothing here uses
# the control socket (the gunicornc admin tool), which would be created in
# the home directory. Without this line gunicorn logs an ERROR at every start.
control_socket_disable=True
