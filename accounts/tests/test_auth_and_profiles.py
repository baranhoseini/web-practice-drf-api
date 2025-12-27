# accounts/tests/test_auth_and_profiles.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


def ensure_groups():
    for name in ["CUSTOMER", "CONTRACTOR", "SUPPORT", "ADMIN"]:
        Group.objects.get_or_create(name=name)


def create_user(username, role, phone, password="testpass123", email=None):
    u = User.objects.create(
        username=username,
        email=email or f"{username}@test.com",
        phone=phone,
        role=role,
    )
    u.set_password(password)
    u.save()

    # If you’re using groups in bonus part:
    ensure_groups()
    g, _ = Group.objects.get_or_create(name=role)
    u.groups.add(g)
    return u


class AuthTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.customer = create_user("t_customer", "CUSTOMER", "09120000001")
        cls.contractor = create_user("t_contractor", "CONTRACTOR", "09120000002")
        cls.support = create_user("t_support", "SUPPORT", "09120000003")
        cls.admin = create_user("t_admin", "ADMIN", "09120000004")

    def login(self, identifier, password="testpass123"):
        res = self.client.post(
            "/api/auth/login/",
            {"identifier": identifier, "password": password},
            format="json",
        )
        return res

    def test_login_by_username_email_phone(self):
        # username
        r1 = self.login("t_customer")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("access", r1.data)
        self.assertIn("refresh", r1.data)

        # email
        r2 = self.login(self.customer.email)
        self.assertEqual(r2.status_code, 200)

        # phone
        r3 = self.login(self.customer.phone)
        self.assertEqual(r3.status_code, 200)

    def test_login_invalid(self):
        r = self.login("t_customer", "wrongpass")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields(self):
        r = self.client.post("/api/auth/login/", {"identifier": "x"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_profile_customer(self):
        token = self.login("t_customer").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        r = self.client.get("/api/me/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("user", r.data)
        self.assertIn("ads", r.data)
        self.assertEqual(r.data["user"]["role"], "CUSTOMER")

    def test_me_profile_contractor(self):
        token = self.login("t_contractor").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        r = self.client.get("/api/me/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["user"]["role"], "CONTRACTOR")
