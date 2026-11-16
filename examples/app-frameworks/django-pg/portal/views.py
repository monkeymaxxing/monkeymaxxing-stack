import functools
from django.contrib.auth import authenticate, get_user_model, login as auth_login, logout as auth_logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction, connection
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed, Http404
from django.shortcuts import render, get_object_or_404
from botocore.exceptions import BotoCoreError, ClientError
from .models import Record, Document, ReportJob
from . import object_storage

def endpoint(methods, public=False):
    def decorate(function):
        @functools.wraps(function)
        def handle(request, **kwargs):
            if request.method not in methods:
                return HttpResponseNotAllowed(methods)
            if not public and not request.user.is_authenticated:
                return JsonResponse({"error": "login required"}, status=401)
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout = '12s'")
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                    return function(request, **kwargs)
            except (ValueError, ValidationError):
                return JsonResponse({"error": "invalid values"}, status=422)
            except (BotoCoreError, ClientError, IOError):
                return JsonResponse({"error": "document storage unavailable"}, status=503)
        return handle
    return decorate

@endpoint(["GET"], public=True)
def home(request):
    return render(request, "home.html")

@endpoint(["GET"], public=True)
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})

@endpoint(["POST"], public=True)
def register(request):
    email = request.POST.get("email", "").strip().lower()
    password = request.POST.get("password", "")
    validate_email(email)
    if not 12 <= len(password.encode()) <= 72:
        raise ValueError("password length")
    if get_user_model().objects.filter(username=email).exists():
        raise ValueError("duplicate account")
    user = get_user_model().objects.create_user(username=email, email=email, password=password)
    auth_login(request, user)
    return JsonResponse({"status": "logged in"})

@endpoint(["POST"], public=True)
def login(request):
    user = authenticate(request, username=request.POST.get("email", "").strip().lower(), password=request.POST.get("password", ""))
    if user is None:
        return JsonResponse({"error": "invalid login"}, status=401)
    auth_login(request, user)
    return JsonResponse({"status": "logged in"})

@endpoint(["POST"])
def logout(request):
    auth_logout(request)
    return JsonResponse({"status": "logged out"})

def record_values(request):
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "")
    if not title or len(title) > 200 or len(description) > 10000:
        raise ValueError("record length")
    return {"title": title, "description": description}

@endpoint(["GET", "POST"])
def records(request):
    if request.method == "POST":
        row = Record.objects.create(account=request.user, **record_values(request))
        return JsonResponse({"id": row.pk}, status=201)
    return JsonResponse(list(Record.objects.filter(account=request.user).order_by("id").values("id", "title", "description")), safe=False)

@endpoint(["POST"])
def update_record(request, identifier):
    row = get_object_or_404(Record, pk=identifier, account=request.user)
    for key,value in record_values(request).items():
        setattr(row, key, value)
    row.save(update_fields=["title", "description"])
    return JsonResponse({"status": "updated"})

@endpoint(["POST"])
def delete_record(request, identifier):
    get_object_or_404(Record, pk=identifier, account=request.user).delete()
    return JsonResponse({"status": "deleted"})

@endpoint(["GET", "POST"])
def documents(request):
    if request.method == "GET":
        return JsonResponse(list(Document.objects.filter(account=request.user).order_by("id").values("id", "filename", "sha256")), safe=False)
    file = request.FILES.get("file")
    if not file or file.size > object_storage.MAX_BYTES:
        raise ValueError("file length")
    row = object_storage.upload(request.user, file.name, file.read())
    return JsonResponse({"id": row.pk}, status=201)

@endpoint(["GET"])
def download(request, identifier):
    row = get_object_or_404(Document, pk=identifier, account=request.user)
    response = HttpResponse(object_storage.download(row), content_type="application/octet-stream")
    from django.utils.http import content_disposition_header
    response["Content-Disposition"] = content_disposition_header(True, row.filename)
    return response

@endpoint(["GET", "POST"])
def reports(request):
    if request.method == "POST":
        return JsonResponse({"id": ReportJob.objects.create(account=request.user).pk}, status=201)
    return JsonResponse(list(ReportJob.objects.filter(account=request.user).order_by("id").values("id", "output")), safe=False)

@endpoint(["GET"])
def report(request, identifier):
    row = get_object_or_404(ReportJob, pk=identifier, account=request.user)
    return JsonResponse({"id": row.pk, "output": row.output})
