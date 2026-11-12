"""End-to-end smoke tests for Crema.

Run with:  python -m unittest discover -s tests -v
"""

import importlib
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

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
        os.environ["CREMA_BACKUP"] = "0"
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

    def test_07_profile_photo(self):
        # 1x1 JPEG — enough to exercise validation, storage and serving.
        tiny = (
            "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
            "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
            "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
        )

        rejected = self.owner.post("/api/me/avatar", json={"photo": "not-an-image"})
        self.assertEqual(rejected.status_code, 400, rejected.get_json())

        response = self.owner.post(
            "/api/me/avatar", json={"photo": "data:image/jpeg;base64," + tiny}
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        avatar = response.get_json()["user"]["avatar"]
        self.assertIsNotNone(avatar)
        self.assertIn("/api/me/avatar", avatar["url"])

        image = self.owner.get("/api/me/avatar")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/jpeg")
        image.close()

        # The avatar belongs to one account only.
        self.assertEqual(self.stranger.get("/api/me/avatar").status_code, 401)

        removed = self.owner.delete("/api/me/avatar")
        self.assertEqual(removed.status_code, 200, removed.get_json())
        self.assertIsNone(removed.get_json()["user"]["avatar"])
        self.assertEqual(self.owner.get("/api/me/avatar").status_code, 404)

    def test_08_espresso_style_preference(self):
        response = self.owner.patch(
            "/api/me", json={"preferences": {"espresso_style": "ristretto", "dose_g": 18}}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        prefs = response.get_json()["user"]["preferences"]
        self.assertEqual(prefs["espresso_style"], "ristretto")
        self.assertEqual(prefs["dose_g"], 18)

        # Unknown styles are dropped rather than stored.
        response = self.owner.patch(
            "/api/me", json={"preferences": {"espresso_style": "quadruple"}}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("espresso_style", response.get_json()["user"]["preferences"])

    def test_09_bag_size_tracks_what_is_left(self):
        bean = self.owner.post(
            "/api/beans", json={"name": "Stock Test", "bag_size_g": 250}
        )
        self.assertEqual(bean.status_code, 201, bean.get_json())
        bean_id = bean.get_json()["bean"]["id"]
        self.assertEqual(bean.get_json()["bean"]["bag_size_g"], 250)

        for _ in range(2):
            shot = self.owner.post(
                "/api/shots",
                json={"bean_id": bean_id, "method": "espresso", "dose_g": 18},
            )
            self.assertEqual(shot.status_code, 201, shot.get_json())

        rows = self.owner.get("/api/beans").get_json()["beans"]
        stocked = [row for row in rows if row["id"] == bean_id][0]
        self.assertAlmostEqual(stocked["used_g"], 36)
        self.assertAlmostEqual(stocked["remaining_g"], 214)
        self.assertEqual(stocked["shots_left"], 11)

        # A bag without a size simply has no stock figures.
        bare = self.owner.post("/api/beans", json={"name": "No Size"})
        self.assertEqual(bare.status_code, 201)
        rows = self.owner.get("/api/beans").get_json()["beans"]
        bare_row = [row for row in rows if row["id"] == bare.get_json()["bean"]["id"]][0]
        self.assertIsNone(bare_row["bag_size_g"])
        self.assertIsNone(bare_row["remaining_g"])
        self.assertIsNone(bare_row["shots_left"])

    def test_10_cafe_shots_stay_out_of_the_numbers(self):
        before = self.owner.get("/api/stats").get_json()

        cafe = self.owner.post(
            "/api/shots",
            json={
                "method": "flat white",
                "is_cafe": True,
                "cafe_name": "Prufrock",
                "drink_name": "Oat flat white",
                "rating": 5,
                "dose_g": 20,
                "brewed_at": "2026-02-01T10:00:00Z",
            },
        )
        self.assertEqual(cafe.status_code, 201, cafe.get_json())
        entry = cafe.get_json()["shot"]
        self.assertTrue(entry["is_cafe"])
        self.assertEqual(entry["cafe_name"], "Prufrock")
        self.assertEqual(entry["drink_name"], "Oat flat white")

        edited = self.owner.patch(
            f"/api/shots/{entry['id']}",
            json={"drink_name": "Cortado", "favorite": True},
        )
        self.assertEqual(edited.status_code, 200, edited.get_json())
        edited_entry = edited.get_json()["shot"]
        self.assertTrue(edited_entry["is_cafe"])
        self.assertEqual(edited_entry["drink_name"], "Cortado")
        self.assertTrue(edited_entry["favorite"])

        after = self.owner.get("/api/stats").get_json()
        self.assertEqual(after["total_shots"], before["total_shots"])
        self.assertEqual(after["week_shots"], before["week_shots"])
        self.assertEqual(after["cafe_shots"], before["cafe_shots"] + 1)
        self.assertEqual(after["avg_dose"], before["avg_dose"])
        self.assertEqual(
            [row["method"] for row in after["methods"]],
            [row["method"] for row in before["methods"]],
        )

        # It is still part of the journal and the export.
        listing = self.owner.get("/api/shots").get_json()["shots"]
        self.assertTrue(any(shot["id"] == entry["id"] for shot in listing))
        self.assertIn("At a café", self.owner.get("/api/export.csv").get_data(as_text=True))
        self.assertIn("What I ordered", self.owner.get("/api/export.csv").get_data(as_text=True))
        self.assertIn("Cortado", self.owner.get("/api/export.csv").get_data(as_text=True))
        self.assertEqual(self.owner.get("/api/export.pdf").status_code, 200)

        # A place only means something when the shot is marked as a café one.
        plain = self.owner.post(
            "/api/shots",
            json={"method": "espresso", "cafe_name": "Ignored", "drink_name": "Ignored too"},
        )
        self.assertEqual(plain.status_code, 201, plain.get_json())
        self.assertFalse(plain.get_json()["shot"]["is_cafe"])
        self.assertEqual(plain.get_json()["shot"]["cafe_name"], "")
        self.assertEqual(plain.get_json()["shot"]["drink_name"], "")

    def test_11_client_id_makes_retries_safe(self):
        payload = {
            "method": "espresso",
            "dose_g": 18,
            "yield_g": 36,
            "client_id": "offline-test-1",
            "brewed_at": "2026-03-01T09:00:00Z",
        }
        first = self.owner.post("/api/shots", json=payload)
        self.assertEqual(first.status_code, 201, first.get_json())

        retry = self.owner.post("/api/shots", json=payload)
        self.assertEqual(retry.status_code, 200, retry.get_json())
        self.assertTrue(retry.get_json()["duplicate"])
        self.assertEqual(retry.get_json()["shot"]["id"], first.get_json()["shot"]["id"])

        # Even a retry whose bean has disappeared resolves to the first shot.
        stale = self.owner.post(
            "/api/shots", json=dict(payload, bean_id=999999)
        )
        self.assertEqual(stale.status_code, 200, stale.get_json())
        self.assertTrue(stale.get_json()["duplicate"])

        ids = [shot["id"] for shot in self.owner.get("/api/shots").get_json()["shots"]]
        self.assertEqual(ids.count(first.get_json()["shot"]["id"]), 1)

        # The same client id from another account is a different shot.
        self.stranger.post("/api/auth/login", json={"email": STRANGER, "password": PASSWORD})
        theirs = self.stranger.post("/api/shots", json=payload)
        self.assertEqual(theirs.status_code, 201, theirs.get_json())
        self.assertNotEqual(theirs.get_json()["shot"]["id"], first.get_json()["shot"]["id"])

    def test_12_backups_archive_the_journal(self):
        created = self.owner.post("/api/backup")
        self.assertEqual(created.status_code, 201, created.get_json())
        name = created.get_json()["file"]
        self.assertTrue(name.endswith(".zip"))

        # A second run in the same second must not overwrite the first.
        again = self.owner.post("/api/backup")
        self.assertEqual(again.status_code, 201, again.get_json())
        self.assertNotEqual(again.get_json()["file"], name)

        status = self.owner.get("/api/backup").get_json()
        self.assertIsNotNone(status["last_backup_at"])
        names = [row["name"] for row in status["files"]]
        self.assertIn(name, names)
        self.assertIn(again.get_json()["file"], names)

        download = self.owner.get("/api/backup/latest")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(download.get_data())) as bundle:
            names = bundle.namelist()
            self.assertIn("crema.sqlite3", names)
            self.assertIn("README.txt", names)
        download.close()

        # Only the owner administers backups.
        self.stranger.post("/api/auth/login", json={"email": STRANGER, "password": PASSWORD})
        self.assertEqual(self.stranger.get("/api/backup").status_code, 404)

    def test_13_an_older_database_migrates(self):
        with tempfile.TemporaryDirectory(prefix="crema-old-") as old_dir:
            conn = sqlite3.connect(os.path.join(old_dir, "crema.sqlite3"))
            conn.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    preferences TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE beans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    roaster TEXT NOT NULL DEFAULT '',
                    origin TEXT NOT NULL DEFAULT '',
                    process TEXT NOT NULL DEFAULT '',
                    varietal TEXT NOT NULL DEFAULT '',
                    roast_level TEXT NOT NULL DEFAULT '',
                    roast_date TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE shots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    bean_id INTEGER,
                    method TEXT NOT NULL DEFAULT 'espresso',
                    dose_g REAL, yield_g REAL, time_s REAL,
                    grind TEXT NOT NULL DEFAULT '',
                    temp_c REAL, pressure_bar REAL, preinfusion_s REAL,
                    tds REAL, ey REAL,
                    milk_type TEXT NOT NULL DEFAULT '',
                    milk_volume_ml REAL,
                    rating INTEGER,
                    acidity INTEGER, body INTEGER, sweetness INTEGER,
                    bitterness INTEGER, aftertaste INTEGER,
                    flavor_tags TEXT NOT NULL DEFAULT '[]',
                    tasting_notes TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    machine TEXT NOT NULL DEFAULT '',
                    grinder TEXT NOT NULL DEFAULT '',
                    basket TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    brewed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX idx_shots_user ON shots(user_id, brewed_at DESC);
                """
            )
            conn.commit()
            conn.close()

            env = dict(os.environ)
            env.update({
                "COFFEE_DATA_DIR": old_dir,
                "CREMA_ADMIN_EMAIL": "",
                "CREMA_BACKUP": "0",
            })
            result = subprocess.run(
                [sys.executable, "-c",
                 "import app, sqlite3; app.ensure_db(); c = sqlite3.connect(app.DB_PATH); "
                 "print([r[1] for r in c.execute('PRAGMA table_info(beans)')]); "
                 "print([r[1] for r in c.execute('PRAGMA table_info(shots)')]); "
                 "print([r[1] for r in c.execute('PRAGMA index_list(shots)')])"],
                cwd=ROOT, env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("bag_size_g", result.stdout)
            self.assertIn("is_cafe", result.stdout)
            self.assertIn("cafe_name", result.stdout)
            self.assertIn("drink_name", result.stdout)
            self.assertIn("client_id", result.stdout)
            self.assertIn("idx_shots_client", result.stdout)


if __name__ == "__main__":
    unittest.main()
