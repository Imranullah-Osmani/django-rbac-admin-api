from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "target_model", "target_repr", "actor", "created_at")
    search_fields = ("action", "target_model", "target_repr")
    readonly_fields = ("created_at",)

