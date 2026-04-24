from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role
from config.bootstrap import ensure_system_roles
from organizations.models import OrganizationUnit


User = get_user_model()


class OrganizationScopingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_system_roles()
        cls.admin_role = Role.objects.get(slug="admin")
        cls.manager_role = Role.objects.get(slug="manager")

        cls.operations = OrganizationUnit.objects.create(name="Operations", code="OPS")
        cls.customer_success = OrganizationUnit.objects.create(
            name="Customer Success",
            code="CS",
            parent=cls.operations,
        )
        cls.finance = OrganizationUnit.objects.create(name="Finance", code="FIN")

        cls.admin_user = cls.create_user("admin", "admin@example.com", [cls.admin_role])
        cls.manager_user = cls.create_user(
            "manager",
            "manager@example.com",
            [cls.manager_role],
            org_unit=cls.operations,
        )

    @classmethod
    def create_user(cls, username, email, roles, org_unit=None):
        user = User.objects.create_user(
            username=username,
            email=email,
            password="ChangeMe123!",
            org_unit=org_unit,
        )
        user.roles.set(roles)
        return user

    def test_manager_only_sees_own_and_child_org_units(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.get(reverse("org-unit-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visible_codes = {item["code"] for item in response.data["results"]}
        self.assertEqual(visible_codes, {"OPS", "CS"})

    def test_tree_action_returns_only_scoped_branch_for_manager(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.get(reverse("org-unit-tree"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "OPS")
        self.assertEqual(response.data[0]["children"], [{"id": self.customer_success.id, "name": "Customer Success", "code": "CS"}])
