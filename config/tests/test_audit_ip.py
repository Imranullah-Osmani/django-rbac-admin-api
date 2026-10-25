from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from accounts.models import User
from audits.utils import create_audit_log


class AuditAddressTests(TestCase):
    def audit(self, remote_address, forwarded="203.0.113.9"):
        request = RequestFactory().post(
            "/api/users/import/", REMOTE_ADDR=remote_address, HTTP_X_FORWARDED_FOR=forwarded,
        )
        request.user = AnonymousUser()
        return create_audit_log(request, "imported", User)

    def test_forwarded_header_does_not_spoof_audit_source(self):
        entry = self.audit("127.0.0.1", "invalid-address, 203.0.113.10")
        self.assertEqual(entry.ip_address, "127.0.0.1")
        self.assertEqual(entry.metadata["path"], "/api/users/import/")

    def test_ipv6_source_is_normalized(self):
        entry = self.audit("2001:0db8:0:0:0:0:0:1")
        self.assertEqual(entry.ip_address, "2001:db8::1")

    def test_invalid_or_absent_source_does_not_break_audit_write(self):
        for remote in ("not-an-ip", "", None):
            with self.subTest(remote=remote):
                entry = self.audit(remote)
                self.assertIsNone(entry.ip_address)
                self.assertIsNotNone(entry.pk)
