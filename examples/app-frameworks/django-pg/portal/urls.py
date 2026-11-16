from django.urls import path
from . import views
urlpatterns = [
 path("", views.home), path("healthz", views.health),
 path("register", views.register), path("login", views.login), path("logout", views.logout),
 path("records", views.records), path("records/<int:identifier>/update", views.update_record), path("records/<int:identifier>/delete", views.delete_record),
 path("documents", views.documents), path("documents/<int:identifier>", views.download),
 path("reports", views.reports), path("reports/<int:identifier>", views.report),
]
