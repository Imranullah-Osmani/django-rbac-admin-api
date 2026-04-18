import uuid

from django.contrib.auth.models import AbstractUser, Permission
from django.db import models


SYSTEM_ROLE_DEFINITIONS = (
    ("admin", "Admin", "Full access to organization, user, and permission administration."),
    ("manager", "Manager", "Team and organization management access for protected operational endpoints."),
    ("staff", "Staff", "Authenticated staff access to view their own profile and assigned resources."),
)


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="rbac_roles")
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    title = models.CharField(max_length=120, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    org_unit = models.ForeignKey(
        "organizations.OrganizationUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="users")

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def role_slugs(self) -> list[str]:
        return list(self.roles.values_list("slug", flat=True))

    def has_role(self, slug: str) -> bool:
        return slug in self.role_slugs

    def has_internal_access(self) -> bool:
        return self.is_staff or self.is_superuser or bool(set(self.role_slugs) & {"admin", "manager", "staff"})

    def is_admin_role(self) -> bool:
        return self.is_superuser or self.has_role("admin")

    def is_manager_role(self) -> bool:
        return self.is_admin_role() or self.has_role("manager")

    def effective_permissions(self) -> list[str]:
        built_in = set(self.user_permissions.values_list("codename", flat=True))
        inherited = set(Permission.objects.filter(rbac_roles__users=self).values_list("codename", flat=True))
        return sorted(built_in | inherited)
