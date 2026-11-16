import os
from botocore.config import Config
from pathlib import Path
from urllib.parse import urlsplit
from psycopg.conninfo import conninfo_to_dict
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = False
APP_ORIGIN = os.environ["APP_ORIGIN"]
ALLOWED_HOSTS = [urlsplit(APP_ORIGIN).hostname, "127.0.0.1", "localhost"]
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.staticfiles", "portal"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "portal.middleware.PortalMiddleware"]
ROOT_URLCONF = "portal.urls"
WSGI_APPLICATION = "portal.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": []}}]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "portal_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
# Django does not parse DATABASE_URL. Let the installed PostgreSQL driver do it.
params = conninfo_to_dict(os.environ.get("DATABASE_URL", ""))
fields = {name: params.pop(keyword, "") for name,keyword in (("NAME","dbname"),("USER","user"),("PASSWORD","password"),("HOST","host"),("PORT","port"))}
if os.environ.get("PGOPTIONS"):
    params["options"] = os.environ["PGOPTIONS"]
params.update(keepalives=1, keepalives_idle=30, keepalives_interval=5, keepalives_count=3, tcp_user_timeout=10000, prepare_threshold=None)
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", **fields, "OPTIONS": params, "DISABLE_SERVER_SIDE_CURSORS": True, "CONN_MAX_AGE": 600, "CONN_HEALTH_CHECKS": True}}
STATIC_URL = "/assets/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
 "default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {
  "access_key": os.environ.get("R2_ACCESS_KEY_ID"), "secret_key": os.environ.get("R2_SECRET_ACCESS_KEY"),
  "bucket_name": os.environ.get("R2_BUCKET"), "endpoint_url": os.environ.get("R2_ENDPOINT"),
  "region_name": "auto", "signature_version": "s3v4", "addressing_style": "path",
  "default_acl": None, "file_overwrite": False,
  "client_config": Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=3, read_timeout=12, retries={"max_attempts": 0}),
 }},
 "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Bound upload memory to 8 MiB. Private bytes never use public media URLs.
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024 + 64 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
SECURE_CONTENT_TYPE_NOSNIFF = True
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}}, "loggers": {"django.request": {"handlers": ["console"], "level": "CRITICAL", "propagate": False}}}
