from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_system", "updated_at")
    search_fields = ("name", "slug")
    filter_horizontal = ("permissions",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "title", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    filter_horizontal = ("roles", "groups", "user_permissions")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Internal Directory", {"fields": ("title", "phone_number", "org_unit", "roles")}),
    )

