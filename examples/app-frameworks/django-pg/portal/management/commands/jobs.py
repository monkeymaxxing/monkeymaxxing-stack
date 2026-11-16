import signal,time
from django.core.management.base import BaseCommand
from django.db import transaction, connection, DatabaseError, close_old_connections
from django.utils import timezone
from portal.models import Record, ReportJob
class Command(BaseCommand):
    help = "Complete PostgreSQL report jobs with transaction row locks"
    def handle(self, **options):
        stopping = False
        def stop(*args):
            nonlocal stopping
            stopping = True
        for value in (signal.SIGTERM, signal.SIGINT):
            signal.signal(value, stop)
        while not stopping:
            worked = False
            try:
                close_old_connections()
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout = '12s'")
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                    job = ReportJob.objects.filter(completed_at__isnull=True).order_by("id").select_for_update(skip_locked=True).first()
                    if job:
                        job.output = "record_count=" + str(Record.objects.filter(account_id=job.account_id).count()) + "\n"
                        job.completed_at = timezone.now()
                        job.save(update_fields=["output", "completed_at"])
                        worked = True
            except DatabaseError:
                connection.close()
                self.stderr.write("report transaction failed; pending work remains available")
            if not worked and not stopping:
                time.sleep(.25)
