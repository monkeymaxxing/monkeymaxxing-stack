import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import connection, transaction
from portal.models import Record, Document, ReportJob
from portal.object_storage import upload
class Command(BaseCommand):
    help = "Create invented test fixtures without replacing existing data"
    def add_arguments(self, parser):
        parser.add_argument("--accounts", type=int, default=2)
    def handle(self, **options):
        if os.environ.get("APP_ENV") not in ("development", "staging"):
            raise CommandError("seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data")
        if options["accounts"] < 2:
            raise CommandError("Usage: seed-test-data [--accounts N], where N is a whole number of at least 2")
        password = os.environ["FIXTURE_PASSWORD"]
        if not 12 <= len(password.encode()) <= 72:
            raise CommandError("FIXTURE_PASSWORD must be 12 to 72 bytes")
        for slug,name,ordinal in (("barbara","Barbara","First"),("michael","Michael","Second")):
            email = slug + "@example.com"
            account = get_user_model().objects.filter(username=email).first()
            if account is None:
                account = get_user_model().objects.create_user(username=email, email=email, password=password)
            Record.objects.get_or_create(account=account, title=name+" invoice", defaults={"description": ordinal+" synthetic record"})
            if not Document.objects.filter(account=account, filename=slug+"-note.txt").exists():
                upload(account, slug+"-note.txt", (name+" synthetic document\n").encode())
            if not ReportJob.objects.filter(account=account).exists():
                ReportJob.objects.create(account=account)
        password_hash = make_password(password)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(20261105)")
            cursor.execute("""INSERT INTO auth_user(password,last_login,is_superuser,username,first_name,last_name,email,is_staff,is_active,date_joined)
                SELECT %s,NULL,false,email,'','',email,false,true,now()
                FROM (SELECT 'test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com' AS email
                      FROM generate_series(3,%s::bigint) AS n) generated
                ON CONFLICT(username) DO NOTHING""", (password_hash, options["accounts"]))
            cursor.execute("""INSERT INTO records(account_id,title,description)
                SELECT a.id,'Test record ' || n::text,'Generated test record'
                FROM generate_series(3,%s::bigint) AS n
                JOIN auth_user a ON a.username='test-account-' || repeat('0',greatest(0,6-length(n::text))) || n::text || '@example.com'
                WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.account_id=a.id)""", (options["accounts"],))
        self.stdout.write("synthetic test fixture ready")
