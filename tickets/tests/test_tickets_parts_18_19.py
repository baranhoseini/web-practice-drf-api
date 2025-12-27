# tickets/tests/test_tickets_parts_18_19.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


def ensure_groups():
    for name in ["CUSTOMER", "CONTRACTOR", "SUPPORT", "ADMIN"]:
        Group.objects.get_or_create(name=name)


def create_user(username, role, phone, password="testpass123"):
    u = User.objects.create(
        username=username,
        email=f"{username}@test.com",
        phone=phone,
        role=role,
    )
    u.set_password(password)
    u.save()
    ensure_groups()
    u.groups.add(Group.objects.get(name=role))
    return u


class TicketTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.customer = create_user("tix_customer", "CUSTOMER", "09123330001")
        cls.contractor = create_user("tix_contractor", "CONTRACTOR", "09123330002")
        cls.support = create_user("tix_support", "SUPPORT", "09123330003")

    def login_token(self, identifier, password="testpass123"):
        r = self.client.post("/api/auth/login/", {"identifier": identifier, "password": password}, format="json")
        self.assertEqual(r.status_code, 200)
        return r.data["access"]

    def as_user(self, username):
        token = self.login_token(username)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_part18_user_can_create_ticket_customer_and_contractor(self):
        self.as_user("tix_customer")
        r1 = self.client.post("/api/tickets/", {"title": "Help", "message": "Need help", "ad": None}, format="json")
        self.assertEqual(r1.status_code, 201)
        self.assertIn("id", r1.data)
        tid1 = r1.data["id"]

        self.as_user("tix_contractor")
        r2 = self.client.post("/api/tickets/", {"title": "Help2", "message": "Need help", "ad": None}, format="json")
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(tid1, r2.data["id"])

    def test_user_sees_only_own_tickets_support_sees_all(self):
        self.as_user("tix_customer")
        self.client.post("/api/tickets/", {"title": "A", "message": "A", "ad": None}, format="json")
        self.client.post("/api/tickets/", {"title": "B", "message": "B", "ad": None}, format="json")

        self.as_user("tix_customer")
        r = self.client.get("/api/tickets/")
        self.assertEqual(r.status_code, 200)
        for t in r.data:
            self.assertEqual(t["creator_id"], self.customer.id)

        self.as_user("tix_support")
        r2 = self.client.get("/api/tickets/")
        self.assertEqual(r2.status_code, 200)
        self.assertGreaterEqual(len(r2.data), len(r.data))

    def test_part19_only_support_can_reply_once(self):
        # create ticket
        self.as_user("tix_customer")
        t = self.client.post("/api/tickets/", {"title": "R", "message": "R", "ad": None}, format="json")
        self.assertEqual(t.status_code, 201)
        tid = t.data["id"]

        # customer cannot reply
        self.as_user("tix_customer")
        r_forbidden = self.client.post(f"/api/tickets/{tid}/reply/", {"support_reply": "no"}, format="json")
        self.assertEqual(r_forbidden.status_code, 403)

        # support can reply
        self.as_user("tix_support")
        r_ok = self.client.post(f"/api/tickets/{tid}/reply/", {"support_reply": "We got it"}, format="json")
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.data["support_reply"], "We got it")
        self.assertEqual(r_ok.data["status"], "IN_PROGRESS")

        # second reply blocked
        r_again = self.client.post(f"/api/tickets/{tid}/reply/", {"support_reply": "again"}, format="json")
        self.assertEqual(r_again.status_code, 400)

    def test_customer_cannot_set_support_reply_via_update(self):
        self.as_user("tix_customer")
        t = self.client.post("/api/tickets/", {"title": "X", "message": "X", "ad": None}, format="json")
        tid = t.data["id"]

        # try patching support_reply (should be ignored or rejected)
        r = self.client.patch(f"/api/tickets/{tid}/", {"support_reply": "hack"}, format="json")
        # could be 200 but should not change, or 400 depending on serializer
        self.assertIn(r.status_code, [200, 400])

        # fetch and confirm not set
        r2 = self.client.get(f"/api/tickets/{tid}/")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("support_reply", r2.data)
        self.assertNotEqual(r2.data["support_reply"], "hack")
