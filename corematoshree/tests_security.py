import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.core.files.base import ContentFile
from django.core.exceptions import SuspiciousFileOperation
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import AuditLog, RateLimitBucket, SocialIdentity, User
from .storage import EncryptedDocumentStorage
from .utils import is_admin, is_superadmin


class SecurityWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_google_oauth_creates_unusable_password_account(self):
        with override_settings(
            GOOGLE_OAUTH_CLIENT_ID="test-client-id",
            GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret",
            GOOGLE_OAUTH_REDIRECT_URI="http://testserver/auth/google/callback/",
        ):
            start = self.client.get(reverse("google_oauth_start"))
            self.assertEqual(start.status_code, 302)
            self.assertIn("accounts.google.com", start["Location"])
            state = next(iter(self.client.session["google_oauth_flows"]))

            token_response = Mock()
            token_response.json.return_value = {"access_token": "mock-access-token", "token_type": "Bearer"}
            token_response.raise_for_status.return_value = None
            userinfo_response = Mock()
            userinfo_response.json.return_value = {
                "sub": "google-subject-123",
                "email": "verified.user@example.test",
                "email_verified": True,
                "given_name": "Verified",
                "family_name": "User",
            }
            userinfo_response.raise_for_status.return_value = None
            with patch("corematoshree.authentication.requests.post", return_value=token_response), patch(
                "corematoshree.authentication.requests.get", return_value=userinfo_response
            ):
                response = self.client.get(reverse("google_oauth_callback"), {"state": state, "code": "mock-code"})

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="verified.user@example.test")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.role, "user")
        self.assertEqual(SocialIdentity.objects.get(user=user).subject, "google-subject-123")
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(user.pk))
        self.assertTrue(AuditLog.objects.filter(action="registration_success", actor=user).exists())

    def test_google_oauth_rejects_missing_or_replayed_state(self):
        response = self.client.get(reverse("google_oauth_callback"), {"state": "unknown", "code": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SocialIdentity.objects.exists())
        self.assertTrue(AuditLog.objects.filter(action="oauth_state_rejected").exists())

    def test_login_post_is_rate_limited_without_throttling_page_loads(self):
        first_get = self.client.get(reverse("login"))
        self.assertEqual(first_get.status_code, 200)
        for index in range(10):
            response = self.client.post(reverse("login"), {"username": "throttle-user", "password": "incorrect"})
            self.assertEqual(response.status_code, 200, msg=f"Unexpected status on attempt {index + 1}")
        blocked = self.client.post(reverse("login"), {"username": "throttle-user", "password": "incorrect"})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked.headers)
        self.assertTrue(RateLimitBucket.objects.exists())

    def test_security_csrf_blocks_login_post_without_token(self):
        strict_client = Client(enforce_csrf_checks=True)
        response = strict_client.post(reverse("login"), {"username": "x", "password": "y"})
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_pass_admin_role_checks(self):
        customer = User.objects.create_user(username="regular", password="StrongPass123!", email="regular@example.test")
        admin = User.objects.create_user(username="center-admin", password="StrongPass123!", role="admin")
        root = User.objects.create_superuser(username="site-root", password="StrongPass123!", email="root@example.test")
        self.assertFalse(is_admin(customer))
        self.assertTrue(is_admin(admin))
        self.assertTrue(is_superadmin(root))

    @override_settings(PAYMENT_GATEWAY="razorpay", RAZORPAY_WEBHOOK_SECRET="test-webhook-secret")
    def test_unsigned_razorpay_webhook_is_rejected(self):
        response = self.client.post(
            reverse("razorpay_webhook"),
            data=json.dumps({"event": "payment.captured"}),
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="invalid",
        )
        self.assertEqual(response.status_code, 401)

    def test_document_storage_encrypts_and_authenticates_bytes(self):
        key = Fernet.generate_key().decode("ascii")
        with tempfile.TemporaryDirectory() as tempdir, override_settings(
            MEDIA_ROOT=tempdir,
            FILE_ENCRYPTION_KEY=key,
            CLOUDINARY_CLOUD_NAME="",
            CLOUDINARY_API_KEY="",
            CLOUDINARY_API_SECRET="",
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        ):
            storage = EncryptedDocumentStorage()
            stored_name = storage.save("security-test/private.pdf", ContentFile(b"private customer document"))
            self.assertTrue(storage.is_encrypted_name(stored_name))
            self.assertTrue(stored_name.endswith(".pdf.enc"))
            stored_bytes = (Path(tempdir) / stored_name).read_bytes()
            self.assertNotIn(b"private customer document", stored_bytes)
            with storage.open(stored_name, "rb") as decrypted:
                self.assertEqual(decrypted.read(), b"private customer document")
            damaged = bytearray(stored_bytes)
            damaged[-1] ^= 1
            (Path(tempdir) / stored_name).write_bytes(damaged)
            with self.assertRaises(SuspiciousFileOperation):
                storage.open(stored_name, "rb")
