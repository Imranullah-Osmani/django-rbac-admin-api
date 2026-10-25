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
