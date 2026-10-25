from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from config.bootstrap import ensure_system_roles
from organizations.models import OrganizationUnit


class CSVImportContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_system_roles()
        cls.admin = User.objects.create_user(username="csv-admin", email="csv-admin@example.com", is_superuser=True)

    def setUp(self):
        self.client.force_authenticate(user=self.admin)

    def upload(self, endpoint, content):
        file = SimpleUploadedFile("records.csv", content.encode("utf-8"), content_type="text/csv")
        return self.client.post(reverse(endpoint), {"file": file}, format="multipart")

    def test_malformed_csv_is_rejected_without_writes_on_both_endpoints(self):
        for endpoint, headers, values in (
            ("user-import-users", "username,email", "new-user,new-user@example.com"),
            ("org-unit-import-units", "name,code", "New Unit,NEW"),
        ):
            for content in (
                f"{headers},{headers.split(',')[0]}\n{values},duplicate\n",
                f"{headers}\n{values},extra\n",
                f"{headers}\nonly-one-cell\n",
                f'{headers}\n"unterminated,value\n',
            ):
                with self.subTest(endpoint=endpoint, content=content):
                    response = self.upload(endpoint, content)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(User.objects.count(), 1)
                    self.assertEqual(OrganizationUnit.objects.count(), 0)

    def test_quoted_multiline_cells_are_preserved(self):
        user_response = self.upload(
            "user-import-users", 'username,email,title\nmultiline,multiline@example.com,"Line one\nLine two"\n',
        )
        unit_response = self.upload("org-unit-import-units", 'name,code\n"Customer\nSupport",CS\n')

        self.assertEqual(user_response.status_code, 200)
        self.assertEqual(unit_response.status_code, 200)
        self.assertEqual(User.objects.get(username="multiline").title, "Line one\nLine two")
        self.assertEqual(OrganizationUnit.objects.get(code="CS").name, "Customer\nSupport")

    def test_csv_rejects_nul_bytes_before_any_write(self):
        for endpoint, content in (
            ("user-import-users", "username,email,title\nnew-user,new-user@example.com,Support\x00Lead\n"),
            ("org-unit-import-units", "name,code\nSupport\x00Team,SUP\n"),
        ):
            with self.subTest(endpoint=endpoint):
                response = self.upload(endpoint, content)
                self.assertEqual(response.status_code, 400)
                self.assertIn("NUL", response.data["detail"])
                self.assertEqual(User.objects.count(), 1)
                self.assertEqual(OrganizationUnit.objects.count(), 0)

    def test_user_import_validates_model_fields_before_any_write(self):
        for field, invalid in (
            ("username", "invalid username"), ("username", "x" * 151),
            ("title", "x" * 121), ("phone_number", "x" * 31),
            ("first_name", "x" * 151), ("last_name", "x" * 151),
        ):
            with self.subTest(field=field, invalid=invalid):
                header = ["username", "email"] + ([] if field == "username" else [field])
                valid = ["valid-user", "valid-user@example.com"] + ([] if field == "username" else ["valid"])
                bad = [invalid if field == "username" else "invalid-user", "invalid-user@example.com"]
                if field != "username":
                    bad.append(invalid)
                content = "\n".join(",".join(row) for row in (header, valid, bad)) + "\n"

                response = self.upload("user-import-users", content)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["processed"], 0)
                self.assertTrue(any(error["field"] == field for error in response.data["errors"]))
                self.assertEqual(User.objects.count(), 1)

    def test_org_import_validates_lengths_before_any_write(self):
        for name, code, invalid_field in (("x" * 121, "INVALID", "name"), ("Invalid", "X" * 51, "code")):
            with self.subTest(field=invalid_field):
                response = self.upload(
                    "org-unit-import-units", f"name,code\nValid,VALID\n{name},{code}\n",
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["processed"], 0)
                self.assertTrue(any(error["field"] == invalid_field for error in response.data["errors"]))
                self.assertEqual(OrganizationUnit.objects.count(), 0)
