"""End-to-end smoke tests for Crema.

Run with:  python -m unittest discover -s tests -v
"""

import importlib
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OWNER = "owner@example.com"
STRANGER = "friend@example.com"
PASSWORD = "testing1234"


class CremaSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = tempfile.mkdtemp(prefix="crema-test-")
        os.environ["COFFEE_DATA_DIR"] = cls.data_dir
        os.environ["CREMA_ADMIN_EMAIL"] = OWNER
        os.environ.pop("CREMA_PDF_FOOTER", None)
        cls.app = importlib.import_module("app")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.data_dir, ignore_errors=True)

    def setUp(self):
        self.owner = self.app.app.test_client()
        self.stranger = self.app.app.test_client()
        # Most tests start as the owner. On the first run the account does not
        # exist yet, so the failed login is expected and harmless.
        self.owner.post("/api/auth/login", json={"email": OWNER, "password": PASSWORD})

    def test_01_health(self):
        response = self.owner.get("/api/health")
        self.assertEqual(response.status_code, 200)

    def test_02_owner_registers_active(self):
        response = self.owner.post(
            "/api/auth/register",
            json={"name": "Owner", "email": OWNER, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 201, response.get_json())

        me = self.owner.get("/api/me").get_json()["user"]
        self.assertTrue(me["admin"])
        self.assertTrue(me["registration_approval"])

    def test_03_stranger_waits_for_approval(self):
        response = self.stranger.post(
            "/api/auth/register",
            json={"name": "Friend", "email": STRANGER, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        self.assertTrue(response.get_json()["pending"])

        blocked = self.stranger.post(
            "/api/auth/login", json={"email": STRANGER, "password": PASSWORD}
        )
        self.assertEqual(blocked.status_code, 403)

        listing = self.owner.get("/api/admin/registration").get_json()
        pending = [row for row in listing["pending"] if row["email"] == STRANGER]
        self.assertEqual(len(pending), 1)

        approved = self.owner.post(f"/api/admin/users/{pending[0]['id']}/approve")
        self.assertEqual(approved.status_code, 200)

        allowed = self.stranger.post(
            "/api/auth/login", json={"email": STRANGER, "password": PASSWORD}
        )
        self.assertEqual(allowed.status_code, 200)

    def test_04_regular_user_cannot_administer(self):
        login = self.stranger.post(
            "/api/auth/login", json={"email": STRANGER, "password": PASSWORD}
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.stranger.get("/api/admin/registration").status_code, 404)
        self.assertEqual(self.stranger.post("/api/admin/registration", json={"registration_approval": False}).status_code, 404)

    def test_05_log_a_bean_and_a_shot(self):
        bean = self.owner.post(
            "/api/beans",
            json={"name": "Test Guji", "roaster": "Test Roaster", "origin": "Ethiopia"},
        )
        self.assertEqual(bean.status_code, 201, bean.get_json())
        bean_id = bean.get_json()["bean"]["id"]

        shot = self.owner.post(
            "/api/shots",
            json={
                "bean_id": bean_id,
                "method": "espresso",
                "dose_g": 18,
                "yield_g": 36,
                "time_s": 28,
                "rating": 5,
                "acidity": 4,
                "body": 3,
                "sweetness": 4,
                "bitterness": 2,
                "aftertaste": 4,
                "flavor_tags": ["jasmine", "peach"],
                "tasting_notes": "A test shot.",
                "brewed_at": "2026-01-15T08:00:00Z",
            },
        )
        self.assertEqual(shot.status_code, 201, shot.get_json())

        listing = self.owner.get("/api/shots").get_json()
        self.assertEqual(len(listing["shots"]), 1)

        self.assertEqual(self.owner.get("/api/stats").status_code, 200)
        self.assertEqual(self.owner.get("/api/export.csv").status_code, 200)
        self.assertEqual(self.owner.get("/api/export.json").status_code, 200)
        self.assertEqual(self.owner.get("/api/export.pdf").status_code, 200)

    def test_06_toggle_off_opens_registration(self):
        response = self.owner.post(
            "/api/admin/registration", json={"registration_approval": False}
        )
        self.assertEqual(response.status_code, 200)

        invitee = self.app.app.test_client()
        open_signup = invitee.post(
            "/api/auth/register",
            json={"name": "Open", "email": "open@example.com", "password": PASSWORD},
        )
        self.assertEqual(open_signup.status_code, 201, open_signup.get_json())

        self.owner.post("/api/admin/registration", json={"registration_approval": True})


if __name__ == "__main__":
    unittest.main()
