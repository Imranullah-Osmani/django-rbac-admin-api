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
        cls.enterprise_support = OrganizationUnit.objects.create(
            name="Enterprise Support",
            code="ENT",
            parent=cls.customer_success,
        )
        cls.finance = OrganizationUnit.objects.create(name="Finance", code="FIN")

        cls.admin_user = cls.create_user("admin", "admin@example.com", [cls.admin_role])
        cls.manager_user = cls.create_user(
            "manager",
            "manager@example.com",
            [cls.manager_role],
            org_unit=cls.operations,
        )
        cls.child_manager_user = cls.create_user(
            "child-manager",
            "child-manager@example.com",
            [cls.manager_role],
            org_unit=cls.customer_success,
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

    def test_manager_only_sees_own_org_branch(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.get(reverse("org-unit-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visible_codes = {item["code"] for item in response.data["results"]}
        self.assertEqual(visible_codes, {"OPS", "CS", "ENT"})

    def test_admin_can_search_org_units_by_manager_identity(self):
        self.customer_success.manager = self.manager_user
        self.customer_success.save(update_fields=["manager", "updated_at"])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse("org-unit-list"), {"search": "manager@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["code"] for item in response.data["results"]], ["CS"])

    def test_tree_action_returns_only_scoped_branch_for_manager(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.get(reverse("org-unit-tree"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "OPS")
        self.assertEqual(response.data[0]["children"], [{"id": self.customer_success.id, "name": "Customer Success", "code": "CS"}])

    def test_tree_action_uses_manager_org_as_branch_root_when_org_has_parent(self):
        self.client.force_authenticate(user=self.child_manager_user)

        response = self.client.get(reverse("org-unit-tree"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["code"], "CS")
        self.assertEqual(response.data[0]["parent"], self.operations.id)

    def test_org_unit_update_rejects_descendant_as_parent(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            reverse("org-unit-detail", args=[self.operations.id]),
            {"parent": self.customer_success.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("descendants as parent", str(response.data))

    def test_org_unit_delete_rejects_units_with_children(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.delete(reverse("org-unit-detail", args=[self.operations.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(OrganizationUnit.objects.filter(id=self.operations.id).exists())
        self.assertTrue(OrganizationUnit.objects.filter(id=self.customer_success.id).exists())
        self.assertIn("child organization units", str(response.data))

    def test_operator_cannot_delete_own_org_unit(self):
        self.client.force_authenticate(user=self.child_manager_user)

        response = self.client.delete(reverse("org-unit-detail", args=[self.customer_success.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(OrganizationUnit.objects.filter(id=self.customer_success.id).exists())
        self.assertIn("cannot delete their own organization unit", str(response.data))

    def test_manager_cannot_create_org_unit_outside_own_branch(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.post(
            reverse("org-unit-list"),
            {"name": "Finance Operations", "code": "FINOPS", "parent": self.finance.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OrganizationUnit.objects.filter(code="FINOPS").exists())
        self.assertIn("under their own organization branch", str(response.data))

    def test_manager_can_create_org_unit_under_descendant_branch(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.post(
            reverse("org-unit-list"),
            {"name": "Enterprise Tier Two", "code": "ENT2", "parent": self.enterprise_support.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrganizationUnit.objects.get(code="ENT2").parent, self.enterprise_support)

    def test_org_unit_create_normalizes_code_and_rejects_case_insensitive_duplicates(self):
        self.client.force_authenticate(user=self.admin_user)

        create_response = self.client.post(
            reverse("org-unit-list"),
            {"name": "  Security Operations  ", "code": " secops "},
            format="multipart",
        )
        duplicate_response = self.client.post(
            reverse("org-unit-list"),
            {"name": "Duplicate Security Operations", "code": "SECOPS"},
            format="multipart",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrganizationUnit.objects.get(name="Security Operations").code, "SECOPS")
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("organization unit with this code already exists", str(duplicate_response.data))

    def test_org_unit_create_accepts_json_payloads(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("org-unit-list"),
            {"name": "Platform Operations", "code": "PLATOPS", "parent": self.operations.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(OrganizationUnit.objects.filter(code="PLATOPS").exists())

    def test_org_unit_rejects_staff_manager_assignment(self):
        staff_role = Role.objects.get(slug="staff")
        staff_user = self.create_user("staff-manager-attempt", "staff-manager-attempt@example.com", [staff_role], org_unit=self.operations)
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("org-unit-list"),
            {"name": "Invalid Manager Unit", "code": "BADMGR", "manager": staff_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OrganizationUnit.objects.filter(code="BADMGR").exists())
        self.assertIn("Organization managers must be active admin or manager users.", str(response.data))

    def test_org_unit_create_rejects_blank_name_after_normalization(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("org-unit-list"),
            {"name": "   ", "code": "BLANKNAME"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OrganizationUnit.objects.filter(code="BLANKNAME").exists())
        self.assertIn("may not be blank", str(response.data))

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

    def test_org_csv_import_rejects_duplicate_codes_inside_same_file(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "org-units.csv",
            (
                "name,code,parent_code\n"
                "Security,sec,\n"
                "Security Duplicate,SEC,\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(OrganizationUnit.objects.filter(code="SEC").exists())
        self.assertIn("Duplicate code also appears on row 2.", str(response.data))

    def test_org_csv_import_rejects_non_utf8_upload_without_server_error(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile("org-units.csv", b"\xff\xfe\x00\x00", content_type="text/csv")

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Upload must be a UTF-8 encoded CSV file.")

    def test_org_csv_import_rejects_oversized_upload_without_reading_rows(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile("org-units.csv", b"x" * (1024 * 1024 + 1), content_type="text/csv")

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "CSV import files must be 1 MB or smaller.")

    def test_org_csv_import_rejects_too_many_data_rows(self):
        self.client.force_authenticate(user=self.admin_user)
        rows = "\n".join(f"Unit {index},UNIT{index},OPS" for index in range(501))
        upload = SimpleUploadedFile(
            "org-units.csv",
            f"name,code,parent_code\n{rows}\n".encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "CSV import files can include at most 500 data rows.")
        self.assertFalse(OrganizationUnit.objects.filter(code="UNIT0").exists())

    def test_manager_org_csv_import_cannot_create_units_outside_own_branch(self):
        self.client.force_authenticate(user=self.manager_user)
        upload = SimpleUploadedFile(
            "org-units.csv",
            (
                "name,code,parent_code\n"
                "Finance Ops,FINOPS,FIN\n"
                "Root Attempt,ROOTATTEMPT,\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(OrganizationUnit.objects.filter(code__in=["FINOPS", "ROOTATTEMPT"]).exists())
        self.assertIn("Managers can only import child organization units", str(response.data))

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

    def test_org_csv_import_sets_manager_by_username(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "org-units.csv",
            (
                "name,code,parent_code,manager_username\n"
                "Managed Support,MSUP,OPS,manager\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        unit = OrganizationUnit.objects.get(code="MSUP")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(unit.manager, self.manager_user)

    def test_org_csv_import_rejects_inactive_manager_username(self):
        self.manager_user.is_active = False
        self.manager_user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "org-units.csv",
            (
                "name,code,parent_code,manager_username\n"
                "Inactive Managed Support,IMSUP,OPS,manager\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("org-unit-import-units"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(OrganizationUnit.objects.filter(code="IMSUP").exists())
        self.assertIn("Manager must be an active admin or manager user.", str(response.data))

    def test_org_export_includes_manager_username(self):
        self.customer_success.manager = self.manager_user
        self.customer_success.save(update_fields=["manager"])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse("org-unit-export-units"))

        exported_csv = response.content.decode("utf-8")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("name,code,parent_code,manager_username", exported_csv)
        self.assertIn("Customer Success,CS,OPS,manager", exported_csv)

    def test_org_export_uses_stable_code_ordering(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse("org-unit-export-units"))

        exported_rows = response.content.decode("utf-8").splitlines()
        self.assertEqual([row.split(",")[1] for row in exported_rows[1:]], ["CS", "ENT", "FIN", "OPS"])

    def test_org_export_escapes_spreadsheet_formula_cells(self):
        self.customer_success.name = "=Customer Success"
        self.customer_success.save(update_fields=["name", "updated_at"])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse("org-unit-export-units"))

        exported_csv = response.content.decode("utf-8")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("'=Customer Success", exported_csv)
