from django.conf import settings
from django.db import models
class Record(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(default="", db_default="")
    class Meta:
        db_table = "records"
class Document(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    object_key = models.CharField(max_length=512, unique=True)
    sha256 = models.CharField(max_length=64)
    class Meta:
        db_table = "documents"
        constraints = [models.UniqueConstraint(fields=["account", "filename"], name="owned_document_filename")]
class ReportJob(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    output = models.TextField(null=True)
    completed_at = models.DateTimeField(null=True)
    class Meta:
        db_table = "report_jobs"
        indexes = [models.Index(fields=["id"], condition=models.Q(completed_at__isnull=True), name="waiting_reports")]
