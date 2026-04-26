from __future__ import annotations

from django.contrib import admin
from django.db import OperationalError, ProgrammingError, connection
from django.http import JsonResponse
from django.shortcuts import render

from accounts.models import Role, User
from audits.models import AuditLog
from organizations.models import OrganizationUnit


admin.site.site_header = "Internal Admin Control Plane"
admin.site.site_title = "Admin Control Plane"
admin.site.index_title = "Operations Workspace"


ENDPOINTS = [
    {"method": "POST", "path": "/api/auth/token/", "summary": "Exchange username and password for a JWT access and refresh token pair."},
    {"method": "GET", "path": "/api/users/me/", "summary": "Inspect the authenticated operator profile and effective permissions."},
    {"method": "GET", "path": "/api/users/", "summary": "List or search users within the caller's allowed organization scope."},
    {"method": "PATCH", "path": "/api/roles/{id}/", "summary": "Update one of the fixed system roles: admin, manager, or staff."},
    {"method": "GET", "path": "/api/org-units/tree/", "summary": "Inspect the org hierarchy in a browser-friendly tree response."},
    {"method": "GET", "path": "/api/audit-logs/", "summary": "Review the operational audit trail for create, update, import, and export events."},
]


def _dashboard_context() -> dict:
    try:
        stats = {
            "users": User.objects.count(),
            "roles": Role.objects.count(),
            "org_units": OrganizationUnit.objects.count(),
            "audit_logs": AuditLog.objects.count(),
        }
        recent_logs = list(
            AuditLog.objects.select_related("actor").order_by("-created_at")[:6]
        )
        system_ready = True
    except (OperationalError, ProgrammingError):
        stats = {"users": 0, "roles": 0, "org_units": 0, "audit_logs": 0}
        recent_logs = []
        system_ready = False

    return {
        "stats": stats,
        "recent_logs": recent_logs,
        "system_ready": system_ready,
        "endpoints": ENDPOINTS,
        "capabilities": [
            "JWT-secured internal APIs with fixed admin, manager, and staff system roles",
            "Operational audit logging for create, update, delete, import, and export workflows",
            "Org hierarchy modeling for departments, sub-teams, and management ownership",
            "CSV import/export paths designed for operations teams and back-office staff",
        ],
    }


def home(request):
    return render(request, "home.html", _dashboard_context())


def health_live(request):
    return JsonResponse({"status": "ok"})


def health_ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": "ok"})
    except (OperationalError, ProgrammingError):
        return JsonResponse({"status": "degraded", "database": "error"}, status=503)
