# accounts/tests/test_dynamic_roles_bonus.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


def ensure_groups():
    for name in ["CUSTOMER", "CONTRACTOR", "SUPPORT", "ADMIN"]:
        Group.objects.get_or_create(name=name)


def create_user(username, role, phone, password="testpass123"):
    u = User.objects.create(username=username, email=f"{username}@t.com", phone=phone, role=role)
    u.set_password(password)
    u.save()
    ensure_groups()
    u.groups.add(Group.objects.get(name=role))
    return u


class DynamicRolesBonusTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.admin = create_user("role_admin", "ADMIN", "09124440001")
        cls.customer = create_user("role_customer", "CUSTOMER", "09124440002")

    def login(self, identifier):
        r = self.client.post("/api/auth/login/", {"identifier": identifier, "password": "testpass123"}, format="json")
        self.assertEqual(r.status_code, 200)
        return r.data["access"]

    def test_only_admin_can_change_roles(self):
        # admin changes
        token_admin = self.login("role_admin")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_admin}")
        r = self.client.post(
            f"/api/users/{self.customer.id}/roles/",
            {"roles": ["SUPPORT"]},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("roles", r.data)

        # non-admin blocked
        token_cust = self.login("role_customer")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_cust}")
        r2 = self.client.post(
            f"/api/users/{self.customer.id}/roles/",
            {"roles": ["ADMIN"]},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)
