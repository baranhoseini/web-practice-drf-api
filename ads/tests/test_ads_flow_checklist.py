# ads/tests/test_ads_flow_checklist.py
from wsgiref import headers
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.urls import reverse
from rest_framework.test import APIClient
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


class AdsChecklistFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_groups()
        cls.customer = create_user("chk_customer", "CUSTOMER", "09121110001")
        cls.contractorA = create_user("chk_contractorA", "CONTRACTOR", "09121110002")
        cls.contractorB = create_user("chk_contractorB", "CONTRACTOR", "09121110003")
        cls.support = create_user("chk_support", "SUPPORT", "09121110004")
        cls.admin = create_user("chk_admin", "ADMIN", "09121110005")

    def setUp(self):
        self.client = APIClient()
        self.base = ""  # keep empty because your tests already use /api/... paths

        self.customer_token = self._login("chk_customer", "testpass123")
        self.contractorA_token = self._login("chk_contractorA", "testpass123")
        self.contractorB_token = self._login("chk_contractorB", "testpass123")
        self.support_token = self._login("chk_support", "testpass123")
        self.admin_token = self._login("chk_admin", "testpass123")

    DEFAULT_PASSWORD = "testpass123"

    def login(self, username: str, password: str = DEFAULT_PASSWORD) -> str:
       return self._login(username, password)

    def _login(self, identifier: str, password: str) -> str:
        r = self.client.post(
            "/api/auth/login/",
            {"identifier": identifier, "password": password},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        return r.data["access"]

    def as_user(self, username: str):
       token = self.login(username)   # now OK because default password exists
       self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def create_ad_as_customer(self, title="T Ad", desc="desc", category="Test"):
        self.as_user("chk_customer")
        r = self.client.post(
            "/api/ads/",
            {"title": title, "description": desc, "category": category},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["status"], "OPEN")
        return r.data["id"]

    # -------- Entities + CRUD + permission core --------

    def test_customer_can_create_ad_contractor_cannot(self):
        self.as_user("chk_customer")
        r1 = self.client.post("/api/ads/", {"title": "A", "description": "d", "category": "c"}, format="json")
        self.assertEqual(r1.status_code, 201)

        self.as_user("chk_contractorA")
        r2 = self.client.post("/api/ads/", {"title": "B", "description": "d", "category": "c"}, format="json")
        self.assertEqual(r2.status_code, 403)

    # ... your setUp() that creates users + tokens + etc

    def auth_headers(self, token: str) -> dict:
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


    def test_contractor_can_request_open_ad_and_cancel_request(self):
        client = APIClient()

        # 1) Customer creates an OPEN ad
        create_ad_url = reverse("ads-list")  # /api/ads/
        ad_payload = {"title": "T", "description": "D", "category": "C"}
        resp_ad = client.post(
            create_ad_url,
            ad_payload,
            format="json",
            **self.auth_headers(self.customer_token),
        )
        self.assertEqual(resp_ad.status_code, status.HTTP_201_CREATED)
        ad_id = resp_ad.data["id"]

        # 2) Contractor sends work request to that OPEN ad
        req_url = reverse("ads-requests", kwargs={"pk": ad_id})  # /api/ads/{id}/requests/
        resp_wr = client.post(
            req_url,
            {"message": "I want it"},
            format="json",
            **self.auth_headers(self.contractorA_token),
        )
        self.assertEqual(resp_wr.status_code, status.HTTP_201_CREATED)
        wr_id = resp_wr.data["id"]

        # 3) Contractor cancels their work request
        cancel_url = reverse("requests-cancel", kwargs={"pk": wr_id})  # /api/requests/{wr_id}/cancel/
        resp_cancel = client.post(
            cancel_url,
            format="json",
            **self.auth_headers(self.contractorA_token),
        )
        self.assertEqual(resp_cancel.status_code, status.HTTP_200_OK)

        # Optional: confirm it is canceled
        # (depends on what your cancel endpoint returns)
        # self.assertEqual(resp_cancel.data["detail"], "Cancelled")

    def test_only_owner_can_view_all_requests(self):
        ad_id = self.create_ad_as_customer("Req View")

        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/requests/", {"message": "A"}, format="json")

        self.as_user("chk_contractorB")
        self.client.post(f"/api/ads/{ad_id}/requests/", {"message": "B"}, format="json")

        # owner sees all
        self.as_user("chk_customer")
        r = self.client.get(f"/api/ads/{ad_id}/requests/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.data), 2)

        # contractor sees only own
        self.as_user("chk_contractorA")
        r2 = self.client.get(f"/api/ads/{ad_id}/requests/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(r2.data), 1)

    # -------- Part 9: assign contractor --------
    def test_assign_only_open_and_only_owner(self):
        ad_id = self.create_ad_as_customer("Assign Ad")

        # contractors request first
        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/requests/", {"message": "A"}, format="json")
        self.as_user("chk_contractorB")
        self.client.post(f"/api/ads/{ad_id}/requests/", {"message": "B"}, format="json")

        # non-owner cannot assign
        self.as_user("chk_contractorA")
        r_forbidden = self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )
        self.assertEqual(r_forbidden.status_code, 403)

        # owner assigns -> ASSIGNED
        self.as_user("chk_customer")
        r = self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ASSIGNED")
        self.assertEqual(r.data["assigned_contractor_id"], self.contractorA.id)

        # assigning again should fail (not OPEN)
        r2 = self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorB.id, "scheduled_at": "2025-12-30T11:00:00Z", "location": "Tehran"},
            format="json",
        )
        self.assertEqual(r2.status_code, 400)

    # -------- Part 10: contractor done --------
    def test_only_assigned_contractor_can_mark_done(self):
        ad_id = self.create_ad_as_customer("Done Ad")
        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/requests/", {}, format="json")

        self.as_user("chk_customer")
        self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )

        # wrong contractor
        self.as_user("chk_contractorB")
        r_wrong = self.client.post(f"/api/ads/{ad_id}/contractor-done/")
        self.assertEqual(r_wrong.status_code, 404)  # or 403 depending on queryset visibility

        # correct contractor
        self.as_user("chk_contractorA")
        r = self.client.post(f"/api/ads/{ad_id}/contractor-done/")
        self.assertEqual(r.status_code, 200)

    # -------- Part 11: confirm done --------
    def test_owner_confirms_done_after_contractor_marks(self):
        ad_id = self.create_ad_as_customer("Confirm Ad")
        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/requests/", {}, format="json")

        self.as_user("chk_customer")
        self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )

        # cannot confirm before contractor-done
        r_pre = self.client.post(f"/api/ads/{ad_id}/confirm-done/")
        self.assertEqual(r_pre.status_code, 400)

        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/contractor-done/")

        self.as_user("chk_customer")
        r = self.client.post(f"/api/ads/{ad_id}/confirm-done/")
        self.assertEqual(r.status_code, 200)

        # GET should show DONE
        r2 = self.client.get(f"/api/ads/{ad_id}/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["status"], "DONE")

    # -------- Part 12: cancel ad --------
    def test_cancel_rules_and_visibility(self):
        # cancel OPEN -> ok and becomes hidden for others
        ad_id = self.create_ad_as_customer("Cancel Ad")

        self.as_user("chk_customer")
        r = self.client.post(f"/api/ads/{ad_id}/cancel/")
        self.assertEqual(r.status_code, 200)

        # contractor should not see it
        self.as_user("chk_contractorA")
        r2 = self.client.get(f"/api/ads/{ad_id}/")
        self.assertIn(r2.status_code, [404, 403])

    # -------- Part 13: review contractor after DONE --------
    def test_review_once_only_rating_1_to_5_only_after_done(self):
        ad_id = self.create_ad_as_customer("Review Ad")
        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/requests/", {}, format="json")

        self.as_user("chk_customer")
        self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )

        # cannot review before DONE
        r_pre = self.client.post(f"/api/ads/{ad_id}/review/", {"rating": 5, "text": "x"}, format="json")
        self.assertEqual(r_pre.status_code, 400)

        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/contractor-done/")

        self.as_user("chk_customer")
        self.client.post(f"/api/ads/{ad_id}/confirm-done/")

        # valid review
        r = self.client.post(f"/api/ads/{ad_id}/review/", {"rating": 5, "text": "Great"}, format="json")
        self.assertEqual(r.status_code, 201)

        # duplicate review blocked
        r2 = self.client.post(f"/api/ads/{ad_id}/review/", {"rating": 4, "text": "Again"}, format="json")
        self.assertEqual(r2.status_code, 400)

    # -------- Part 14: contractor profile aggregation --------
    def test_contractor_profile_shows_counts_and_reviews(self):
        ad_id = self.create_ad_as_customer("Profile Ad")
        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/requests/", {}, format="json")

        self.as_user("chk_customer")
        self.client.post(
            f"/api/ads/{ad_id}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )
        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad_id}/contractor-done/")
        self.as_user("chk_customer")
        self.client.post(f"/api/ads/{ad_id}/confirm-done/")
        self.client.post(f"/api/ads/{ad_id}/review/", {"rating": 5, "text": "Nice"}, format="json")

        r = self.client.get(f"/api/contractors/{self.contractorA.id}/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("completed_ads_count", r.data)
        self.assertIn("avg_rating", r.data)
        self.assertIn("review_count", r.data)
        self.assertIn("reviews", r.data)

    # -------- Part 16/17: contractor list filtering + ordering --------
    def test_contractor_list_filter_and_order(self):
        self.as_user("chk_customer")
        r = self.client.get("/api/contractors/?min_avg_rating=0&min_review_count=0")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.data, list)

        r2 = self.client.get("/api/contractors/?ordering=-avg_rating,-review_count")
        self.assertEqual(r2.status_code, 200)

    # -------- Bonus 1.3: contractor reviews filter --------
    def test_contractor_reviews_filter_rating(self):
        self.as_user("chk_customer")
        r = self.client.get(f"/api/contractors/{self.contractorA.id}/reviews/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("reviews", r.data)

        r2 = self.client.get(f"/api/contractors/{self.contractorA.id}/reviews/?rating=5")
        self.assertEqual(r2.status_code, 200)

        r_bad = self.client.get(f"/api/contractors/{self.contractorA.id}/reviews/?rating=9")
        self.assertEqual(r_bad.status_code, 400)

    # -------- Bonus 3.3: schedule + conflict --------
    def test_contractor_schedule_endpoint_and_conflict(self):
        # make two ads assigned to contractorA with distinct times
        ad1 = self.create_ad_as_customer("Sch 1")
        ad2 = self.create_ad_as_customer("Sch 2")

        self.as_user("chk_contractorA")
        self.client.post(f"/api/ads/{ad1}/requests/", {}, format="json")
        self.client.post(f"/api/ads/{ad2}/requests/", {}, format="json")

        self.as_user("chk_customer")
        self.client.post(
            f"/api/ads/{ad1}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )
        self.client.post(
            f"/api/ads/{ad2}/assign/",
            {"contractor_id": self.contractorA.id, "scheduled_at": "2025-12-30T11:00:00Z", "location": "Tehran"},
            format="json",
        )

        # contractor schedule list for day
        self.as_user("chk_contractorA")
        r = self.client.get("/api/me/schedule/?date=2025-12-30")
        self.assertEqual(r.status_code, 200)
        self.assertIn("items", r.data)
        self.assertGreaterEqual(r.data["count"], 2)

        # conflict attempt: set ad2 to 10:00 (same as ad1)
        r_conflict = self.client.post(
            f"/api/ads/{ad2}/schedule/",
            {"scheduled_at": "2025-12-30T10:00:00Z", "location": "Tehran"},
            format="json",
        )
        self.assertEqual(r_conflict.status_code, 400)
