from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from accountssu.models import User
from globalapi.utils.auth import password_reset_token_generator


class RegisterViewTests(APITestCase):
    def test_register_without_role_creates_customer(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "name": "Rahim Ahmed",
                "email": "rahim@example.com",
                "password": "demo1234",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], "customer")
        self.assertEqual(response.data["user"]["source"], "email")
        user = User.objects.get(email="rahim@example.com")
        self.assertEqual(user.role, "customer")
        self.assertEqual(user.source, "email")

    def test_register_with_agent_role_creates_agent(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "name": "Sara Khan",
                "email": "sara@company.com",
                "password": "demo1234",
                "role": "agent",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], "agent")
        user = User.objects.get(email="sara@company.com")
        self.assertEqual(user.role, "agent")

    def test_register_rejects_admin_role(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "name": "Bad Admin",
                "email": "badadmin@company.com",
                "password": "demo1234",
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="badadmin@company.com").exists())

    def test_register_duplicate_email_returns_400(self):
        User.objects.create_user(
            username="rahim@example.com",
            email="rahim@example.com",
            password="demo1234",
            first_name="Existing",
            role="customer",
        )

        response = self.client.post(
            reverse("auth-register"),
            {
                "name": "Rahim Ahmed",
                "email": "rahim@example.com",
                "password": "demo1234",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(
            response.data["email"][0],
            "An account with this email already exists.",
        )

    def test_register_invalid_email_returns_400(self):
        response = self.client.post(
            reverse("auth-register"),
            {
                "name": "Bad Email",
                "email": "not-an-email",
                "password": "demo1234",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertFalse(User.objects.filter(username="not-an-email").exists())


class GoogleLoginViewTests(APITestCase):
    def test_google_login_requires_credential(self):
        response = self.client.post(reverse("auth-google"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("credential", response.data)

    def test_google_login_rejects_invalid_token(self):
        response = self.client.post(
            reverse("auth-google"),
            {"credential": "not-a-real-google-token"},
            format="json",
        )
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_503_SERVICE_UNAVAILABLE))


class PasswordResetViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rahim@example.com",
            email="rahim@example.com",
            password="oldpass123",
            first_name="Rahim",
            role="customer",
        )

    def test_password_reset_request_always_returns_200(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "missing@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

    @override_settings(DEBUG=True)
    def test_password_reset_request_existing_user_includes_debug_url(self):
        response = self.client.post(
            reverse("auth-password-reset"),
            {"email": "rahim@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reset_url", response.data)
        self.assertIn("/reset-password?", response.data["reset_url"])

    def test_password_reset_confirm_updates_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)

        confirm = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "password": "newpass123",
            },
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))
        self.assertFalse(self.user.check_password("oldpass123"))

    def test_password_reset_confirm_rejects_bad_token(self):
        response = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": "invalid",
                "token": "bad-token",
                "password": "newpass123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
