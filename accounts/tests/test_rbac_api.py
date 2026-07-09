from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role
from audits.models import AuditLog
from config.bootstrap import ensure_system_roles
from organizations.models import OrganizationUnit


User = get_user_model()


class RBACAccessTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_system_roles()
        cls.admin_role = Role.objects.get(slug="admin")
        cls.manager_role = Role.objects.get(slug="manager")
        cls.staff_role = Role.objects.get(slug="staff")

        cls.operations = OrganizationUnit.objects.create(name="Operations", code="OPS")
        cls.customer_success = OrganizationUnit.objects.create(
            name="Customer Success",
            code="CS",
            parent=cls.operations,
        )
        cls.finance = OrganizationUnit.objects.create(name="Finance", code="FIN")

        cls.admin_user = cls.create_user(
            username="admin",
            email="admin@example.com",
            password="ChangeMe123!",
            roles=[cls.admin_role],
        )
        cls.manager_user = cls.create_user(
            username="manager",
            email="manager@example.com",
            password="ChangeMe123!",
            org_unit=cls.operations,
            roles=[cls.manager_role],
        )
        cls.same_org_staff = cls.create_user(
            username="ops-staff",
            email="ops-staff@example.com",
            password="ChangeMe123!",
            org_unit=cls.operations,
            roles=[cls.staff_role],
        )
        cls.child_org_staff = cls.create_user(
            username="child-staff",
            email="child-staff@example.com",
            password="ChangeMe123!",
            org_unit=cls.customer_success,
            roles=[cls.staff_role],
        )
        cls.other_org_staff = cls.create_user(
            username="finance-staff",
            email="finance-staff@example.com",
            password="ChangeMe123!",
            org_unit=cls.finance,
            roles=[cls.staff_role],
        )

    @classmethod
    def create_user(cls, username, email, password, roles, org_unit=None):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            org_unit=org_unit,
        )
        user.roles.set(roles)
        return user

    def test_token_endpoint_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("api-token"),
            {"username": "admin", "password": "ChangeMe123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_staff_cannot_list_users(self):
        self.client.force_authenticate(user=self.same_org_staff)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_only_sees_users_in_own_org_unit(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visible_usernames = {item["username"] for item in response.data["results"]}
        self.assertEqual(visible_usernames, {"manager", "ops-staff"})

    def test_manager_cannot_assign_admin_role(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.post(
            reverse("user-list"),
            {
                "username": "new-admin-attempt",
                "email": "new-admin-attempt@example.com",
                "first_name": "New",
                "last_name": "Admin",
                "title": "Ops Lead",
                "org_unit": self.operations.id,
                "role_ids": [self.admin_role.id],
                "is_active": True,
                "is_staff": False,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Managers cannot assign the admin role.", str(response.data))

    def test_manager_cannot_create_user_in_another_org_unit(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.post(
            reverse("user-list"),
            {
                "username": "finance-hire",
                "email": "finance-hire@example.com",
                "first_name": "Finance",
                "last_name": "Hire",
                "title": "Finance Analyst",
                "org_unit": self.finance.id,
                "role_ids": [self.staff_role.id],
                "is_active": True,
                "is_staff": False,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Managers can only manage users inside their own organization unit.", str(response.data))

    def test_user_create_normalizes_email_and_rejects_case_insensitive_duplicates(self):
        self.client.force_authenticate(user=self.admin_user)

        create_response = self.client.post(
            reverse("user-list"),
            {
                "username": "mixed-email",
                "email": "Mixed.Email@Example.COM",
                "first_name": "Mixed",
                "last_name": "Email",
                "title": "Analyst",
                "org_unit": self.operations.id,
                "role_ids": [self.staff_role.id],
                "is_active": True,
                "is_staff": False,
            },
            format="multipart",
        )
        duplicate_response = self.client.post(
            reverse("user-list"),
            {
                "username": "duplicate-email",
                "email": "mixed.email@example.com",
                "first_name": "Duplicate",
                "last_name": "Email",
                "title": "Analyst",
                "org_unit": self.operations.id,
                "role_ids": [self.staff_role.id],
                "is_active": True,
                "is_staff": False,
            },
            format="multipart",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username="mixed-email").email, "mixed.email@example.com")
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user with this email already exists", str(duplicate_response.data))

    def test_user_create_rejects_case_insensitive_username_duplicates(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("user-list"),
            {
                "username": "ADMIN",
                "email": "admin-alias@example.com",
                "first_name": "Admin",
                "last_name": "Alias",
                "title": "Analyst",
                "org_unit": self.operations.id,
                "role_ids": [self.staff_role.id],
                "is_active": True,
                "is_staff": False,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("user with this username already exists", str(response.data))

    def test_admin_sees_only_fixed_system_roles_and_cannot_create_new_ones(self):
        self.client.force_authenticate(user=self.admin_user)

        list_response = self.client.get(reverse("role-list"))
        create_response = self.client.post(
            reverse("role-list"),
            {"name": "Security", "slug": "security", "description": "Should not be created."},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        returned_slugs = {item["slug"] for item in list_response.data["results"]}
        self.assertEqual(returned_slugs, {"admin", "manager", "staff"})
        self.assertEqual(create_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_create_rejects_non_system_role_assignment(self):
        self.client.force_authenticate(user=self.admin_user)
        custom_role = Role.objects.create(name="Security", slug="security", description="Non-system role.")

        response = self.client.post(
            reverse("user-list"),
            {
                "username": "security-user",
                "email": "security-user@example.com",
                "first_name": "Security",
                "last_name": "User",
                "title": "Security Analyst",
                "org_unit": self.operations.id,
                "role_ids": [custom_role.id],
                "is_active": True,
                "is_staff": False,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="security-user").exists())

    def test_manager_csv_import_cannot_bypass_org_scope_or_admin_role(self):
        self.client.force_authenticate(user=self.manager_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "bad-admin,bad-admin@example.com,Bad,Admin,Lead,OPS,admin\n"
                "finance-import,finance-import@example.com,Finance,Import,Analyst,FIN,staff\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(User.objects.filter(email="bad-admin@example.com").exists())
        self.assertFalse(User.objects.filter(email="finance-import@example.com").exists())
        self.assertIn("Managers cannot import admin users.", str(response.data))
        self.assertIn("Managers can only import users into their own organization unit.", str(response.data))

    def test_admin_csv_import_reports_unknown_role_without_writing_rows(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "unknown-role,unknown-role@example.com,Unknown,Role,Analyst,OPS,security\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(User.objects.filter(email="unknown-role@example.com").exists())
        self.assertIn("Unknown roles: security.", str(response.data))

    def test_csv_import_rejects_non_system_role_slug(self):
        self.client.force_authenticate(user=self.admin_user)
        Role.objects.create(name="Security", slug="security", description="Non-system role.")
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "security-import,security-import@example.com,Security,Import,Analyst,OPS,security\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(User.objects.filter(email="security-import@example.com").exists())
        self.assertIn("Unknown roles: security.", str(response.data))

    def test_admin_csv_import_writes_audit_log_for_successful_bulk_change(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "bulk-staff,bulk-staff@example.com,Bulk,Staff,Analyst,OPS,staff\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(email="bulk-staff@example.com").exists())
        audit_log = AuditLog.objects.get(action="imported", target_model="User")
        self.assertEqual(audit_log.actor, self.admin_user)
        self.assertEqual(audit_log.changes, {"record_count": 1})
        self.assertEqual(audit_log.metadata["method"], "POST")
        self.assertEqual(audit_log.metadata["path"], reverse("user-import-users"))

    def test_csv_import_matches_org_unit_code_case_insensitively(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "lower-org,lower-org@example.com,Lower,Org,Analyst,ops,staff\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.get(email="lower-org@example.com").org_unit, self.operations)

    def test_csv_import_matches_role_slugs_case_insensitively(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "upper-role,upper-role@example.com,Upper,Role,Analyst,OPS,STAFF\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.get(email="upper-role@example.com").role_slugs, ["staff"])

    def test_csv_import_updates_existing_user_by_case_insensitive_email(self):
        self.client.force_authenticate(user=self.admin_user)
        existing = self.create_user(
            username="case-import",
            email="case-import@example.com",
            password="ChangeMe123!",
            org_unit=self.operations,
            roles=[self.staff_role],
        )
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "case-import-updated,CASE-IMPORT@EXAMPLE.COM,Case,Import,Lead,OPS,manager\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        existing.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email__iexact="case-import@example.com").count(), 1)
        self.assertEqual(existing.username, "case-import-updated")
        self.assertEqual(existing.email, "case-import@example.com")
        self.assertEqual(existing.role_slugs, ["manager"])

    def test_csv_import_rejects_duplicate_email_inside_same_file(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "first-duplicate,DUPLICATE@EXAMPLE.COM,First,Duplicate,Analyst,OPS,staff\n"
                "second-duplicate,duplicate@example.com,Second,Duplicate,Analyst,OPS,staff\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(User.objects.filter(email__iexact="duplicate@example.com").exists())
        self.assertIn("Duplicate email also appears on row 2.", str(response.data))

    def test_csv_import_rejects_duplicate_username_inside_same_file(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "duplicate-user,first-duplicate-user@example.com,First,Duplicate,Analyst,OPS,staff\n"
                "DUPLICATE-USER,second-duplicate-user@example.com,Second,Duplicate,Analyst,OPS,staff\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(User.objects.filter(email__iexact="first-duplicate-user@example.com").exists())
        self.assertFalse(User.objects.filter(email__iexact="second-duplicate-user@example.com").exists())
        self.assertIn("Duplicate username also appears on row 2.", str(response.data))

    def test_csv_import_rejects_username_assigned_to_another_email(self):
        self.client.force_authenticate(user=self.admin_user)
        upload = SimpleUploadedFile(
            "users.csv",
            (
                "username,email,first_name,last_name,title,org_unit_code,role_slugs\n"
                "admin,admin-conflict@example.com,Admin,Conflict,Analyst,OPS,staff\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(reverse("user-import-users"), {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["processed"], 0)
        self.assertFalse(User.objects.filter(email__iexact="admin-conflict@example.com").exists())
        self.assertIn("Username is already assigned to another user.", str(response.data))

    def test_user_export_writes_audit_log_with_visible_record_count(self):
        self.client.force_authenticate(user=self.manager_user)

        response = self.client.get(reverse("user-export-users"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        audit_log = AuditLog.objects.get(action="exported", target_model="User")
        self.assertEqual(audit_log.actor, self.manager_user)
        self.assertEqual(audit_log.changes, {"record_count": 2})
        self.assertEqual(audit_log.metadata["method"], "GET")
        self.assertEqual(audit_log.metadata["path"], reverse("user-export-users"))

    def test_admin_can_search_audit_logs_for_operational_events(self):
        self.client.force_authenticate(user=self.admin_user)
        AuditLog.objects.create(
            actor=self.admin_user,
            action="exported",
            target_model="User",
            target_repr="User CSV export",
        )
        AuditLog.objects.create(
            actor=self.admin_user,
            action="updated",
            target_model="Role",
            target_repr="Manager role",
        )

        response = self.client.get(reverse("audit-log-list"), {"search": "exported"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        actions = [item["action"] for item in response.data["results"]]
        self.assertEqual(actions, ["exported"])

    def test_audit_log_list_returns_newest_events_first(self):
        self.client.force_authenticate(user=self.admin_user)
        older = AuditLog.objects.create(actor=self.admin_user, action="created", target_model="User")
        newer = AuditLog.objects.create(actor=self.admin_user, action="deleted", target_model="User")

        response = self.client.get(reverse("audit-log-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = [item["id"] for item in response.data["results"][:2]]
        self.assertEqual(returned_ids, [newer.id, older.id])

    def test_admin_can_filter_audit_logs_by_action_and_target_model(self):
        self.client.force_authenticate(user=self.admin_user)
        AuditLog.objects.create(actor=self.admin_user, action="created", target_model="User")
        AuditLog.objects.create(actor=self.admin_user, action="created", target_model="OrganizationUnit")
        AuditLog.objects.create(actor=self.admin_user, action="deleted", target_model="User")

        response = self.client.get(reverse("audit-log-list"), {"action": "created", "target_model": "user"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["action"] for item in response.data["results"]], ["created"])
        self.assertEqual([item["target_model"] for item in response.data["results"]], ["User"])

    def test_admin_can_filter_audit_logs_by_actor_email(self):
        self.client.force_authenticate(user=self.admin_user)
        AuditLog.objects.create(actor=self.admin_user, action="created", target_model="User")
        AuditLog.objects.create(actor=self.manager_user, action="exported", target_model="User")

        response = self.client.get(reverse("audit-log-list"), {"actor_email": "MANAGER@EXAMPLE.COM"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["actor_email"] for item in response.data["results"]], ["manager@example.com"])
