import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from accounts.models import Role, SYSTEM_ROLE_DEFINITIONS
from organizations.models import OrganizationUnit


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


def ensure_demo_workspace() -> dict[str, int]:
    ensure_system_roles()
    user_model = get_user_model()

    operations, _ = OrganizationUnit.objects.update_or_create(
        code="OPS",
        defaults={"name": "Operations", "metadata": {"region": "global"}},
    )
    support, _ = OrganizationUnit.objects.update_or_create(
        code="SUP",
        defaults={"name": "Support", "parent": operations, "metadata": {"coverage": "24x7"}},
    )
    finance, _ = OrganizationUnit.objects.update_or_create(
        code="FIN",
        defaults={"name": "Finance", "metadata": {"region": "global"}},
    )

    demo_users = [
        {
            "username": "ops.manager",
            "email": "ops.manager@example.com",
            "first_name": "Operations",
            "last_name": "Manager",
            "title": "Operations Manager",
            "org_unit": operations,
            "role": "manager",
        },
        {
            "username": "support.staff",
            "email": "support.staff@example.com",
            "first_name": "Support",
            "last_name": "Staff",
            "title": "Support Specialist",
            "org_unit": support,
            "role": "staff",
        },
        {
            "username": "finance.staff",
            "email": "finance.staff@example.com",
            "first_name": "Finance",
            "last_name": "Staff",
            "title": "Finance Analyst",
            "org_unit": finance,
            "role": "staff",
        },
    ]

    for demo_user in demo_users:
        role = Role.objects.get(slug=demo_user.pop("role"))
        user, _ = user_model.objects.update_or_create(
            username=demo_user["username"],
            defaults={
                "email": demo_user["email"],
                "first_name": demo_user["first_name"],
                "last_name": demo_user["last_name"],
                "title": demo_user["title"],
                "org_unit": demo_user["org_unit"],
                "is_active": True,
                "is_staff": False,
            },
        )
        user.set_password("ChangeMe123!")
        user.save(update_fields=["password"])
        user.roles.set([role])

    return {
        "org_units": OrganizationUnit.objects.filter(code__in=["OPS", "SUP", "FIN"]).count(),
        "demo_users": user_model.objects.filter(username__in=[user["username"] for user in demo_users]).count(),
    }
