from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_org_unit_update_rejects_descendant_as_parent(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            reverse("org-unit-detail", args=[self.operations.id]),
            {"parent": self.customer_success.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("descendants as parent", str(response.data))

    def test_org_csv_import_rejects_parent_cycles_without_writing_rows(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "org-units.csv",
            (
                "name,code,parent_code\n"
                "Risk,RISK,AUDIT\n"
                "Audit,AUDIT,RISK\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(OrganizationUnit.objects.filter(code__in=["RISK", "AUDIT"]).exists())
        self.assertIn("parent cycle", str(response.data))

    def test_org_csv_import_links_parent_created_in_same_file(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "org-units.csv",
            (
                "name,code,parent_code\n"
                "Security,SEC,\n"
                "AppSec,APPSEC,SEC\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["processed"], 2)
        self.assertEqual(OrganizationUnit.objects.get(code="APPSEC").parent.code, "SEC")
