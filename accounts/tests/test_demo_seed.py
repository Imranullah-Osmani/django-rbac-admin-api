from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Role
from config.bootstrap import ensure_demo_workspace
from organizations.models import OrganizationUnit


User = get_user_model()


class DemoWorkspaceSeedTests(TestCase):
    def test_demo_workspace_seed_is_idempotent(self):
        first_summary = ensure_demo_workspace()
        second_summary = ensure_demo_workspace()

        self.assertEqual(first_summary, {"org_units": 3, "demo_users": 3})
        self.assertEqual(second_summary, {"org_units": 3, "demo_users": 3})
        self.assertEqual(OrganizationUnit.objects.filter(code__in=["OPS", "SUP", "FIN"]).count(), 3)
        self.assertEqual(User.objects.filter(username__in=["ops.manager", "support.staff", "finance.staff"]).count(), 3)

    def test_demo_workspace_assigns_expected_roles_and_hierarchy(self):
        ensure_demo_workspace()

        manager = User.objects.get(username="ops.manager")
        support_staff = User.objects.get(username="support.staff")
        support = OrganizationUnit.objects.get(code="SUP")

        self.assertEqual(manager.roles.get().slug, "manager")
        self.assertEqual(support_staff.roles.get().slug, "staff")
        self.assertEqual(support.parent.code, "OPS")
        self.assertTrue(Role.objects.filter(slug__in=["admin", "manager", "staff"], is_system=True).exists())
