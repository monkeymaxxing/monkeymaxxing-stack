import hashlib,uuid
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from .models import Document
MAX_BYTES = 8 * 1024 * 1024

def upload(account, filename, data):
    if len(data) > MAX_BYTES:
        raise ValueError("file exceeds 8 MiB")
    key = "documents/" + str(account.pk) + "/" + str(uuid.uuid4())
    actual_key = storages["default"].save(key, ContentFile(data))
    # Never delete an object after an uncertain metadata commit. Reconcile by key.
    return Document.objects.create(account=account, filename=filename, object_key=actual_key, sha256=hashlib.sha256(data).hexdigest())

def download(document):
    with storages["default"].open(document.object_key, "rb") as file:
        data = file.read()
    if hashlib.sha256(data).hexdigest() != document.sha256:
        raise IOError("document checksum mismatch")
    return data
