from django.contrib import admin

from .models import OrganizationUnit


@admin.register(OrganizationUnit)
class OrganizationUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent", "manager", "updated_at")
    search_fields = ("name", "code")

