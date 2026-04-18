import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from accounts.models import Role, SYSTEM_ROLE_DEFINITIONS


def ensure_default_superuser() -> None:
    username = os.getenv("DJANGO_SUPERUSER_USERNAME")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

    if not username or not email or not password:
        return

    user_model = get_user_model()
    user = user_model.objects.filter(username=username).first()
    if user:
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save(update_fields=["email", "is_staff", "is_superuser", "password"])
        return

    user_model.objects.create_superuser(
        username=username,
        email=email,
        password=password,
    )


def ensure_system_roles() -> None:
    permission_map = {
        "admin": Permission.objects.all(),
        "manager": Permission.objects.filter(codename__in=["view_user", "add_user", "change_user", "view_organizationunit", "add_organizationunit", "change_organizationunit"]),
        "staff": Permission.objects.filter(codename__in=["view_user", "view_organizationunit"]),
    }

    for slug, name, description in SYSTEM_ROLE_DEFINITIONS:
        role, _ = Role.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "is_system": True,
            },
        )
        role.permissions.set(permission_map[slug])
