"""Crema — a small, self-hosted coffee journal."""

import base64
import contextlib
import csv
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone

try:
    import fcntl
except ImportError:  # not available on Windows; the thread lock still applies
    fcntl = None


from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.environ.get("COFFEE_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "crema.sqlite3")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")

COOKIE_NAME = "crema_session"
SESSION_DAYS = 60
MAX_BODY = 14 * 1024 * 1024
MAX_PHOTO = 10 * 1024 * 1024

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")

_init_lock = threading.Lock()
_initialised = False
_backup_started = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    preferences     TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash      TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at      INTEGER NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS beans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    roaster         TEXT NOT NULL DEFAULT '',
    origin          TEXT NOT NULL DEFAULT '',
    process         TEXT NOT NULL DEFAULT '',
    varietal        TEXT NOT NULL DEFAULT '',
    roast_level     TEXT NOT NULL DEFAULT '',
    roast_date      TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    bag_size_g      REAL,
    archived        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_beans_user ON beans(user_id);

CREATE TABLE IF NOT EXISTS shots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bean_id         INTEGER REFERENCES beans(id) ON DELETE SET NULL,
    method          TEXT NOT NULL DEFAULT 'espresso',
    dose_g          REAL,
    yield_g         REAL,
    time_s          REAL,
    grind           TEXT NOT NULL DEFAULT '',
    temp_c          REAL,
    pressure_bar    REAL,
    preinfusion_s   REAL,
    tds             REAL,
    ey              REAL,
    milk_type       TEXT NOT NULL DEFAULT '',
    milk_volume_ml  REAL,
    rating          INTEGER,
    acidity         INTEGER,
    body            INTEGER,
    sweetness       INTEGER,
    bitterness      INTEGER,
    aftertaste      INTEGER,
    flavor_tags     TEXT NOT NULL DEFAULT '[]',
    tasting_notes   TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    machine         TEXT NOT NULL DEFAULT '',
    grinder         TEXT NOT NULL DEFAULT '',
    basket          TEXT NOT NULL DEFAULT '',
    favorite        INTEGER NOT NULL DEFAULT 0,
    is_cafe         INTEGER NOT NULL DEFAULT 0,
    cafe_name       TEXT NOT NULL DEFAULT '',
    drink_name      TEXT NOT NULL DEFAULT '',
    client_id       TEXT NOT NULL DEFAULT '',
    brewed_at       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shots_user ON shots(user_id, brewed_at DESC);

CREATE TABLE IF NOT EXISTS settings (
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shot_photos (
    shot_id         INTEGER PRIMARY KEY REFERENCES shots(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    full_file       TEXT NOT NULL,
    thumb_file      TEXT NOT NULL DEFAULT '',
    mime            TEXT NOT NULL DEFAULT 'image/jpeg',
    thumb_mime      TEXT NOT NULL DEFAULT '',
    width           INTEGER,
    height          INTEGER,
    created_at      TEXT NOT NULL
);
"""

METHODS = {"espresso", "latte", "cappuccino", "flat white", "filter", "cold brew", "other"}
ROAST_LEVELS = {"", "light", "medium-light", "medium", "medium-dark", "dark"}
DEFAULT_DOSE_G = 18.0

ADMIN_EMAIL = os.environ.get("CREMA_ADMIN_EMAIL", "").strip().lower()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_db() -> None:
    global _initialised
    if _initialised:
        return
    with _init_lock:
        if _initialised:
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(PHOTO_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=20)
        try:
            conn.executescript(SCHEMA)

            def add_missing(table: str, wanted: dict) -> None:
                current = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                for column, definition in wanted.items():
                    if column not in current:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

            add_missing("users", {
                "status": "TEXT NOT NULL DEFAULT 'active'",
                "avatar_file": "TEXT NOT NULL DEFAULT ''",
                "avatar_mime": "TEXT NOT NULL DEFAULT ''",
                "avatar_updated_at": "TEXT NOT NULL DEFAULT ''",
            })
            add_missing("beans", {"bag_size_g": "REAL"})
            add_missing("shots", {
                "is_cafe": "INTEGER NOT NULL DEFAULT 0",
                "cafe_name": "TEXT NOT NULL DEFAULT ''",
                "drink_name": "TEXT NOT NULL DEFAULT ''",
                "client_id": "TEXT NOT NULL DEFAULT ''",
            })
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_shots_client "
                "ON shots(user_id, client_id) WHERE client_id != ''"
            )
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('registration_approval', ?)",
                ("1" if ADMIN_EMAIL else "0",),
            )
            conn.commit()
        finally:
            conn.close()
        _initialised = True
        start_backup_thread()


def db() -> sqlite3.Connection:
    if "db" not in g:
        ensure_db()
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 20000")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ---------------------------------------------------------------- helpers

def fail(message: str, status: int = 400):
    return jsonify({"error": message}), status


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def clean_text(value, limit=2000) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def clean_number(value, minimum=None, maximum=None):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Expected a number")
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError("Expected a number")
    if minimum is not None and number < minimum:
        raise ValueError(f"Value must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"Value must be at most {maximum}")
    return round(number, 3)


def clean_rating(value):
    if value is None or value == "" or value == 0 or value == "0":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("Rating must be a whole number")
    return max(1, min(5, number))


def clean_bool(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, str):
        return 1 if value.lower() in {"1", "true", "yes", "on"} else 0
    return 1 if value else 0


def clean_iso_datetime(value) -> str:
    if not value:
        return iso(utcnow())
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid date")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed > utcnow() + timedelta(days=1):
        raise ValueError("Date cannot be in the future")
    return iso(parsed)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_user():
    if "user" in g:
        return g.user
    token = request.cookies.get(COOKIE_NAME)
    g.user = None
    if token:
        row = db().execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ? AND u.status = 'active'",
            (token_hash(token), int(time.time())),
        ).fetchone()
        if row:
            g.user = row
    return g.user


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return fail("Please sign in", 401)
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return fail("Please sign in", 401)
        if not is_admin(user):
            return fail("Not found", 404)
        return view(*args, **kwargs)

    return wrapped


def is_admin(row) -> bool:
    return bool(row) and (row["email"] or "").lower() == ADMIN_EMAIL


def app_setting(key: str, default: str = "") -> str:
    row = db().execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_app_setting(key: str, value: str) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def registration_approval() -> bool:
    if not ADMIN_EMAIL:
        # Without an owner account nobody could approve requests, so never gate sign-ups.
        return False
    return app_setting("registration_approval", "1") == "1"


def pending_users():
    return db().execute(
        "SELECT id, name, email, created_at FROM users "
        "WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()


def me_payload(row) -> dict:
    payload = user_payload(row)
    if is_admin(row):
        payload["admin"] = True
        payload["registration_approval"] = registration_approval()
    return payload


def set_session_cookie(response, token: str):
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
        path="/",
    )


def user_payload(row) -> dict:
    try:
        prefs = json.loads(row["preferences"] or "{}")
    except (ValueError, TypeError):
        prefs = {}
    keys = row.keys()
    avatar = None
    if "avatar_updated_at" in keys and row["avatar_updated_at"]:
        version = re.sub(r"[^0-9]", "", str(row["avatar_updated_at"]))[-14:]
        avatar = {
            "url": f"/api/me/avatar?v={version}",
            "added_at": row["avatar_updated_at"],
        }
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "preferences": prefs,
        "avatar": avatar,
        "created_at": row["created_at"],
    }


def bean_payload(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "roaster": row["roaster"],
        "origin": row["origin"],
        "process": row["process"],
        "varietal": row["varietal"],
        "roast_level": row["roast_level"],
        "roast_date": row["roast_date"],
        "notes": row["notes"],
        "bag_size_g": row["bag_size_g"] if "bag_size_g" in row.keys() else None,
        "archived": bool(row["archived"]),
        "created_at": row["created_at"],
    }


def shot_payload(row) -> dict:
    try:
        tags = json.loads(row["flavor_tags"] or "[]")
        if not isinstance(tags, list):
            tags = []
    except (ValueError, TypeError):
        tags = []

    keys = row.keys()
    photo = None
    if "photo_created_at" in keys and row["photo_created_at"]:
        version = re.sub(r"[^0-9]", "", str(row["photo_created_at"]))[-14:]
        photo = {
            "url": f"/api/shots/{row['id']}/photo?v={version}",
            "thumb_url": f"/api/shots/{row['id']}/photo?thumb=1&v={version}",
            "width": row["photo_width"],
            "height": row["photo_height"],
            "added_at": row["photo_created_at"],
        }

    return {
        "id": row["id"],
        "bean_id": row["bean_id"],
        "bean_name": row["bean_name"] if "bean_name" in row.keys() else None,
        "bean_roaster": row["bean_roaster"] if "bean_roaster" in row.keys() else None,
        "method": row["method"],
        "dose_g": row["dose_g"],
        "yield_g": row["yield_g"],
        "time_s": row["time_s"],
        "grind": row["grind"],
        "temp_c": row["temp_c"],
        "pressure_bar": row["pressure_bar"],
        "preinfusion_s": row["preinfusion_s"],
        "tds": row["tds"],
        "ey": row["ey"],
        "milk_type": row["milk_type"],
        "milk_volume_ml": row["milk_volume_ml"],
        "rating": row["rating"],
        "acidity": row["acidity"],
        "body": row["body"],
        "sweetness": row["sweetness"],
        "bitterness": row["bitterness"],
        "aftertaste": row["aftertaste"],
        "flavor_tags": tags,
        "tasting_notes": row["tasting_notes"],
        "notes": row["notes"],
        "machine": row["machine"],
        "grinder": row["grinder"],
        "basket": row["basket"],
        "favorite": bool(row["favorite"]),
        "is_cafe": bool(row["is_cafe"]) if "is_cafe" in keys else False,
        "cafe_name": row["cafe_name"] if "cafe_name" in keys else "",
        "drink_name": row["drink_name"] if "drink_name" in keys else "",
        "brewed_at": row["brewed_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "photo": photo,
    }


SHOT_SELECT = """
SELECT s.*, b.name AS bean_name, b.roaster AS bean_roaster,
       p.created_at AS photo_created_at, p.width AS photo_width, p.height AS photo_height
FROM shots s
LEFT JOIN beans b ON b.id = s.bean_id
LEFT JOIN shot_photos p ON p.shot_id = s.id
"""


# ---------------------------------------------------------------- photos

DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.*)$", re.S)


def detect_image(raw: bytes):
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if len(raw) > 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def decode_photo(value, limit: int):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Photo data missing")
    text = value.strip()
    match = DATA_URL_RE.match(text)
    if match:
        text = match.group(2)
    text = re.sub(r"\s+", "", text)
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        raise ValueError("That photo could not be read")
    if not raw:
        raise ValueError("That photo is empty")
    if len(raw) > limit:
        raise ValueError("That photo is too large — try a smaller one")
    found = detect_image(raw)
    if not found:
        raise ValueError("Use a JPEG, PNG or WebP photo")
    return raw, found[0], found[1]


def clean_dimension(value):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if 0 < number < 20000 else None


def photo_path(name: str) -> str:
    return os.path.join(PHOTO_DIR, name)


def remove_photo_files(names):
    for name in names:
        if not name:
            continue
        try:
            os.remove(photo_path(name))
        except OSError:
            pass


def photo_row(shot_id: int, user_id: int):
    return db().execute(
        "SELECT p.* FROM shot_photos p JOIN shots s ON s.id = p.shot_id "
        "WHERE p.shot_id = ? AND s.user_id = ?",
        (shot_id, user_id),
    ).fetchone()


# ---------------------------------------------------------------- auth

_login_attempts: dict[str, list[float]] = {}
_login_lock = threading.Lock()


def rate_limited(key: str) -> bool:
    now = time.time()
    with _login_lock:
        attempts = [t for t in _login_attempts.get(key, []) if now - t < 600]
        _login_attempts[key] = attempts
        return len(attempts) >= 12


def note_attempt(key: str):
    with _login_lock:
        _login_attempts.setdefault(key, []).append(time.time())


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/auth/register")
def register():
    data = body()
    name = clean_text(data.get("name"), 80)
    email = clean_text(data.get("email"), 160).lower()
    password = data.get("password") or ""

    if not name:
        return fail("Please enter your name")
    if not EMAIL_RE.match(email):
        return fail("Please enter a valid email address")
    if not isinstance(password, str) or len(password) < 8:
        return fail("Password must be at least 8 characters")
    if len(password) > 200:
        return fail("Password is too long")

    conn = db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return fail("An account with that email already exists", 409)

    now = iso(utcnow())
    approval = registration_approval()
    if approval:
        waiting = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
        if waiting >= 25:
            return fail("There are already a lot of requests waiting. Please try again later.", 429)

    # The owner must never be stuck waiting for their own approval.
    needs_approval = approval and email != ADMIN_EMAIL
    status = "pending" if needs_approval else "active"
    try:
        cur = conn.execute(
            "INSERT INTO users (email, name, password_hash, created_at, status) VALUES (?, ?, ?, ?, ?)",
            (email, name, generate_password_hash(password), now, status),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return fail("An account with that email already exists", 409)

    if needs_approval:
        return jsonify({
            "pending": True,
            "message": "Your request has been sent. You’ll be able to sign in once it’s approved.",
        }), 202

    user_id = cur.lastrowid
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token_hash(token), user_id, int(time.time()) + SESSION_DAYS * 86400, now),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    response = jsonify({"user": user_payload(row)})
    set_session_cookie(response, token)
    return response, 201


@app.post("/api/auth/login")
def login():
    data = body()
    email = clean_text(data.get("email"), 160).lower()
    password = data.get("password") or ""
    key = f"{request.remote_addr}:{email}"
    if rate_limited(key):
        return fail("Too many attempts. Please wait a few minutes.", 429)

    row = db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not isinstance(password, str) or not check_password_hash(row["password_hash"], password):
        note_attempt(key)
        return fail("Email or password is incorrect", 401)

    if row["status"] == "pending":
        return fail("Your account is waiting for approval. You’ll be able to sign in once it’s approved.", 403)
    if row["status"] != "active":
        return fail("This account is not active.", 403)

    now = iso(utcnow())
    token = secrets.token_urlsafe(32)
    conn = db()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token_hash(token), row["id"], int(time.time()) + SESSION_DAYS * 86400, now),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
    conn.commit()

    response = jsonify({"user": user_payload(row)})
    set_session_cookie(response, token)
    return response


@app.post("/api/auth/logout")
def logout():
    token = request.cookies.get(COOKIE_NAME)
    if token:
        conn = db()
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        conn.commit()
    response = jsonify({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/api/me")
@login_required
def me():
    user = current_user()
    return jsonify({"user": me_payload(user)})


@app.patch("/api/me")
@login_required
def update_me():
    user = current_user()
    data = body()
    conn = db()
    fields, values = [], []

    if "name" in data:
        name = clean_text(data.get("name"), 80)
        if not name:
            return fail("Name cannot be empty")
        fields.append("name = ?")
        values.append(name)

    if "preferences" in data:
        prefs = data.get("preferences")
        if not isinstance(prefs, dict):
            return fail("Invalid preferences")
        allowed = {"machine", "grinder", "basket", "dose_g", "yield_g", "milk_type", "temp_c",
                   "espresso_style"}
        styles = {"", "ristretto", "single", "double", "lungo"}
        cleaned = {}
        for key, value in prefs.items():
            if key not in allowed:
                continue
            if key in {"dose_g", "yield_g", "temp_c"}:
                try:
                    cleaned[key] = clean_number(value, 0, 2000)
                except ValueError:
                    continue
            elif key == "espresso_style":
                style = clean_text(value, 20)
                if style not in styles:
                    continue
                cleaned[key] = style
            else:
                cleaned[key] = clean_text(value, 120)
        fields.append("preferences = ?")
        values.append(json.dumps(cleaned))

    if "password" in data:
        # A session alone should not be enough to take the account over.
        current = data.get("current_password")
        if not isinstance(current, str) or not check_password_hash(user["password_hash"], current):
            return fail("Enter your current password to change it", 403)
        password = data.get("password")
        if not isinstance(password, str) or len(password) < 8:
            return fail("Password must be at least 8 characters")
        if len(password) > 200:
            return fail("Password is too long")
        fields.append("password_hash = ?")
        values.append(generate_password_hash(password))
        conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                     (user["id"], token_hash(request.cookies.get(COOKIE_NAME) or "")))

    if fields:
        values.append(user["id"])
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()

    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify({"user": me_payload(row)})


@app.post("/api/me/avatar")
@login_required
def upload_avatar():
    user = current_user()
    data = body()
    try:
        raw, ext, mime = decode_photo(data.get("photo"), MAX_PHOTO)
    except ValueError as exc:
        return fail(str(exc))

    conn = db()
    filename = f"avatar-{user['id']}-{secrets.token_hex(8)}.{ext}"
    written = False
    try:
        with open(photo_path(filename), "wb") as fh:
            fh.write(raw)
        written = True
        conn.execute(
            "UPDATE users SET avatar_file = ?, avatar_mime = ?, avatar_updated_at = ? WHERE id = ?",
            (filename, mime, iso(utcnow()), user["id"]),
        )
        conn.commit()
    except (OSError, sqlite3.Error) as exc:
        if written:
            remove_photo_files([filename])
        return fail(f"Could not save the photo: {exc}", 500)

    stale = user["avatar_file"] if "avatar_file" in user.keys() else ""
    if stale:
        remove_photo_files([stale])

    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    g.user = row
    return jsonify({"user": me_payload(row)}), 201


@app.get("/api/me/avatar")
@login_required
def get_avatar():
    user = current_user()
    filename = user["avatar_file"] if "avatar_file" in user.keys() else ""
    if not filename or not os.path.isfile(photo_path(filename)):
        return fail("Photo not found", 404)
    mime = (user["avatar_mime"] if "avatar_mime" in user.keys() else "") or "image/jpeg"
    response = send_from_directory(PHOTO_DIR, filename, mimetype=mime, max_age=31536000)
    response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return response


@app.delete("/api/me/avatar")
@login_required
def delete_avatar():
    user = current_user()
    filename = user["avatar_file"] if "avatar_file" in user.keys() else ""
    if not filename:
        return fail("Photo not found", 404)
    conn = db()
    conn.execute(
        "UPDATE users SET avatar_file = '', avatar_mime = '', avatar_updated_at = '' WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    remove_photo_files([filename])
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    g.user = row
    return jsonify({"user": me_payload(row)})


# ---------------------------------------------------------------- admin

@app.get("/api/admin/registration")
@admin_required
def admin_registration():
    return jsonify({
        "registration_approval": registration_approval(),
        "pending": [dict(row) for row in pending_users()],
    })


@app.post("/api/admin/registration")
@admin_required
def admin_registration_update():
    data = body()
    value = data.get("registration_approval")
    if not isinstance(value, bool):
        return fail("Expected true or false")
    set_app_setting("registration_approval", "1" if value else "0")
    return jsonify({"registration_approval": value})


@app.post("/api/admin/users/<int:user_id>/approve")
@admin_required
def admin_approve_user(user_id: int):
    conn = db()
    cur = conn.execute(
        "UPDATE users SET status = 'active' WHERE id = ? AND status = 'pending'",
        (user_id,),
    )
    conn.commit()
    if cur.rowcount == 0:
        return fail("That request is no longer waiting", 404)
    return jsonify({"ok": True})


@app.post("/api/admin/users/<int:user_id>/reject")
@admin_required
def admin_reject_user(user_id: int):
    conn = db()
    cur = conn.execute(
        "DELETE FROM users WHERE id = ? AND status = 'pending'",
        (user_id,),
    )
    conn.commit()
    if cur.rowcount == 0:
        return fail("That request is no longer waiting", 404)
    return jsonify({"ok": True})


# ---------------------------------------------------------------- beans

@app.get("/api/beans")
@login_required
def list_beans():
    rows = db().execute(
        "SELECT b.*, "
        "(SELECT COUNT(*) FROM shots s WHERE s.bean_id = b.id AND s.is_cafe = 0) AS shot_count, "
        "(SELECT COALESCE(SUM(s.dose_g), 0) FROM shots s WHERE s.bean_id = b.id AND s.is_cafe = 0) AS used_g, "
        "(SELECT COALESCE(AVG(s.dose_g), 0) FROM shots s WHERE s.bean_id = b.id AND s.is_cafe = 0 AND s.dose_g > 0) AS avg_dose "
        "FROM beans b WHERE b.user_id = ? ORDER BY b.archived ASC, b.created_at DESC",
        (current_user()["id"],),
    ).fetchall()
    beans = []
    for row in rows:
        item = bean_payload(row)
        item["shot_count"] = row["shot_count"]
        used = round(row["used_g"] or 0, 1)
        item["used_g"] = used
        size = item["bag_size_g"]
        if size:
            remaining = max(0.0, round(float(size) - used, 1))
            per_shot = row["avg_dose"] or DEFAULT_DOSE_G
            item["remaining_g"] = remaining
            item["shots_left"] = int(remaining // per_shot) if remaining >= per_shot else 0
        else:
            item["remaining_g"] = None
            item["shots_left"] = None
        beans.append(item)
    return jsonify({"beans": beans})


def read_bean(data: dict) -> dict:
    name = clean_text(data.get("name"), 120)
    if not name:
        raise ValueError("Bean name is required")
    roast_level = clean_text(data.get("roast_level"), 40).lower()
    if roast_level not in ROAST_LEVELS:
        raise ValueError("Unknown roast level")
    roast_date = clean_text(data.get("roast_date"), 40)
    if roast_date:
        try:
            datetime.strptime(roast_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Roast date must be a date")
    return {
        "name": name,
        "roaster": clean_text(data.get("roaster"), 120),
        "origin": clean_text(data.get("origin"), 160),
        "process": clean_text(data.get("process"), 120),
        "varietal": clean_text(data.get("varietal"), 120),
        "roast_level": roast_level,
        "roast_date": roast_date,
        "notes": clean_text(data.get("notes"), 1000),
        "bag_size_g": clean_number(data.get("bag_size_g"), 1, 5000),
    }


@app.post("/api/beans")
@login_required
def create_bean():
    try:
        values = read_bean(body())
    except ValueError as exc:
        return fail(str(exc))
    conn = db()
    cur = conn.execute(
        "INSERT INTO beans (user_id, name, roaster, origin, process, varietal, roast_level, roast_date, notes, bag_size_g, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (current_user()["id"], values["name"], values["roaster"], values["origin"],
         values["process"], values["varietal"], values["roast_level"], values["roast_date"],
         values["notes"], values["bag_size_g"], iso(utcnow())),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM beans WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"bean": bean_payload(row)}), 201


@app.patch("/api/beans/<int:bean_id>")
@login_required
def update_bean(bean_id: int):
    user = current_user()
    conn = db()
    row = conn.execute("SELECT * FROM beans WHERE id = ? AND user_id = ?", (bean_id, user["id"])).fetchone()
    if row is None:
        return fail("Bean not found", 404)

    data = body()
    if "archived" in data and len(data) == 1:
        conn.execute("UPDATE beans SET archived = ? WHERE id = ?", (clean_bool(data.get("archived")), bean_id))
        conn.commit()
        updated = conn.execute("SELECT * FROM beans WHERE id = ?", (bean_id,)).fetchone()
        return jsonify({"bean": bean_payload(updated)})

    merged = {
        "name": data.get("name", row["name"]),
        "roaster": data.get("roaster", row["roaster"]),
        "origin": data.get("origin", row["origin"]),
        "process": data.get("process", row["process"]),
        "varietal": data.get("varietal", row["varietal"]),
        "roast_level": data.get("roast_level", row["roast_level"]),
        "roast_date": data.get("roast_date", row["roast_date"]),
        "notes": data.get("notes", row["notes"]),
        "bag_size_g": data.get("bag_size_g", row["bag_size_g"]),
    }
    try:
        values = read_bean(merged)
    except ValueError as exc:
        return fail(str(exc))
    conn.execute(
        "UPDATE beans SET name = ?, roaster = ?, origin = ?, process = ?, varietal = ?, "
        "roast_level = ?, roast_date = ?, notes = ?, bag_size_g = ? WHERE id = ?",
        (values["name"], values["roaster"], values["origin"], values["process"], values["varietal"],
         values["roast_level"], values["roast_date"], values["notes"], values["bag_size_g"], bean_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM beans WHERE id = ?", (bean_id,)).fetchone()
    return jsonify({"bean": bean_payload(updated)})


@app.delete("/api/beans/<int:bean_id>")
@login_required
def delete_bean(bean_id: int):
    conn = db()
    cur = conn.execute("DELETE FROM beans WHERE id = ? AND user_id = ?", (bean_id, current_user()["id"]))
    conn.commit()
    if cur.rowcount == 0:
        return fail("Bean not found", 404)
    return jsonify({"ok": True})


# ---------------------------------------------------------------- shots

SHOT_TEXT_FIELDS = {
    "grind": 120, "milk_type": 60, "tasting_notes": 3000, "notes": 3000,
    "machine": 120, "grinder": 120, "basket": 120,
}
SHOT_NUMBER_FIELDS = {
    "dose_g": (0, 2000), "yield_g": (0, 5000), "time_s": (0, 7200),
    "temp_c": (0, 200), "pressure_bar": (0, 30), "preinfusion_s": (0, 600),
    "tds": (0, 50), "ey": (0, 100), "milk_volume_ml": (0, 2000),
}
TASTE_FIELDS = ("acidity", "body", "sweetness", "bitterness", "aftertaste")


def read_shot(data: dict, user_id: int, existing=None) -> dict:
    def pick(key, default=None):
        if key in data:
            return data.get(key)
        if existing is not None:
            return existing[key]
        return default

    method = clean_text(pick("method", "espresso"), 40).lower()
    if method not in METHODS:
        raise ValueError("Unknown brew method")

    bean_id = pick("bean_id")
    if bean_id in ("", None):
        bean_id = None
    else:
        try:
            bean_id = int(bean_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid bean")
        owned = db().execute("SELECT id FROM beans WHERE id = ? AND user_id = ?", (bean_id, user_id)).fetchone()
        if owned is None:
            raise ValueError("Invalid bean")

    if "flavor_tags" in data:
        tags = data.get("flavor_tags")
    elif existing is not None:
        try:
            tags = json.loads(existing["flavor_tags"] or "[]")
        except (ValueError, TypeError):
            tags = []
    else:
        tags = []
    if tags is None:
        tags = []
    if not isinstance(tags, list):
        raise ValueError("Flavor tags must be a list")
    cleaned_tags = []
    for tag in tags[:12]:
        text = clean_text(tag, 40)
        if text and text not in cleaned_tags:
            cleaned_tags.append(text)

    values = {
        "bean_id": bean_id,
        "method": method,
        "grind": clean_text(pick("grind", ""), 120),
        "milk_type": clean_text(pick("milk_type", ""), 60),
        "tasting_notes": clean_text(pick("tasting_notes", ""), 3000),
        "notes": clean_text(pick("notes", ""), 3000),
        "machine": clean_text(pick("machine", ""), 120),
        "grinder": clean_text(pick("grinder", ""), 120),
        "basket": clean_text(pick("basket", ""), 120),
        "is_cafe": clean_bool(pick("is_cafe", 0)),
        "cafe_name": clean_text(pick("cafe_name", ""), 120),
        "drink_name": clean_text(pick("drink_name", ""), 160),
        "flavor_tags": json.dumps(cleaned_tags),
        "favorite": clean_bool(pick("favorite", 0)),
        "brewed_at": clean_iso_datetime(pick("brewed_at")),
    }
    if not values["is_cafe"]:
        values["cafe_name"] = ""
        values["drink_name"] = ""
    for field, (minimum, maximum) in SHOT_NUMBER_FIELDS.items():
        values[field] = clean_number(pick(field), minimum, maximum)
    values["rating"] = clean_rating(pick("rating"))
    for field in TASTE_FIELDS:
        values[field] = clean_rating(pick(field))
    return values


@app.get("/api/shots")
@login_required
def list_shots():
    user_id = current_user()["id"]
    try:
        limit = max(1, min(1000, int(request.args.get("limit", 300))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return fail("Invalid pagination")

    where = ["s.user_id = ?"]
    params = [user_id]
    query = clean_text(request.args.get("q"), 120)
    if query:
        like = f"%{query}%"
        where.append("(COALESCE(b.name,'') LIKE ? OR COALESCE(b.roaster,'') LIKE ? OR s.method LIKE ? "
                     "OR s.tasting_notes LIKE ? OR s.notes LIKE ? OR s.grind LIKE ? OR s.machine LIKE ? "
                     "OR s.flavor_tags LIKE ?)")
        params.extend([like] * 8)
    if request.args.get("favorite") == "1":
        where.append("s.favorite = 1")
    if request.args.get("bean_id"):
        try:
            where.append("s.bean_id = ?")
            params.append(int(request.args["bean_id"]))
        except ValueError:
            return fail("Invalid bean filter")
    if request.args.get("method"):
        where.append("s.method = ?")
        params.append(clean_text(request.args["method"], 40).lower())

    sql = SHOT_SELECT + " WHERE " + " AND ".join(where) + " ORDER BY s.brewed_at DESC, s.id DESC LIMIT ? OFFSET ?"
    params.extend([limit + 1, offset])
    rows = db().execute(sql, params).fetchall()
    has_more = len(rows) > limit
    shots = [shot_payload(row) for row in rows[:limit]]
    return jsonify({"shots": shots, "has_more": has_more})


@app.post("/api/shots")
@login_required
def create_shot():
    user = current_user()
    data = body()
    conn = db()

    # The offline queue retries posts it could not confirm; a client id keeps
    # that retry from logging the same shot twice. Check it before validation so
    # a retry still matches even if its bean has since been removed.
    client_id = clean_text(data.get("client_id"), 60)
    if client_id:
        existing = conn.execute(
            SHOT_SELECT + " WHERE s.user_id = ? AND s.client_id = ?", (user["id"], client_id)
        ).fetchone()
        if existing is not None:
            return jsonify({"shot": shot_payload(existing), "duplicate": True}), 200

    try:
        values = read_shot(data, user["id"])
    except ValueError as exc:
        return fail(str(exc))
    if client_id:
        values["client_id"] = client_id

    now = iso(utcnow())
    columns = list(values.keys()) + ["user_id", "created_at", "updated_at"]
    params = list(values.values()) + [user["id"], now, now]
    placeholders = ", ".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO shots ({', '.join(columns)}) VALUES ({placeholders})", params
    )
    conn.commit()
    row = conn.execute(SHOT_SELECT + " WHERE s.id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"shot": shot_payload(row)}), 201


@app.get("/api/shots/<int:shot_id>")
@login_required
def get_shot(shot_id: int):
    row = db().execute(SHOT_SELECT + " WHERE s.id = ? AND s.user_id = ?",
                       (shot_id, current_user()["id"])).fetchone()
    if row is None:
        return fail("Shot not found", 404)
    return jsonify({"shot": shot_payload(row)})


@app.patch("/api/shots/<int:shot_id>")
@login_required
def update_shot(shot_id: int):
    user = current_user()
    conn = db()
    existing = conn.execute("SELECT * FROM shots WHERE id = ? AND user_id = ?", (shot_id, user["id"])).fetchone()
    if existing is None:
        return fail("Shot not found", 404)
    try:
        values = read_shot(body(), user["id"], existing)
    except ValueError as exc:
        return fail(str(exc))
    values["updated_at"] = iso(utcnow())
    assignments = ", ".join(f"{key} = ?" for key in values)
    conn.execute(f"UPDATE shots SET {assignments} WHERE id = ?", list(values.values()) + [shot_id])
    conn.commit()
    row = conn.execute(SHOT_SELECT + " WHERE s.id = ?", (shot_id,)).fetchone()
    return jsonify({"shot": shot_payload(row)})


@app.delete("/api/shots/<int:shot_id>")
@login_required
def delete_shot(shot_id: int):
    user = current_user()
    conn = db()
    existing_photo = conn.execute(
        "SELECT full_file, thumb_file FROM shot_photos WHERE shot_id = ? AND user_id = ?",
        (shot_id, user["id"]),
    ).fetchone()
    cur = conn.execute("DELETE FROM shots WHERE id = ? AND user_id = ?", (shot_id, user["id"]))
    conn.commit()
    if cur.rowcount == 0:
        return fail("Shot not found", 404)
    if existing_photo:
        remove_photo_files([existing_photo["full_file"], existing_photo["thumb_file"]])
    return jsonify({"ok": True})


@app.post("/api/shots/<int:shot_id>/photo")
@login_required
def upload_photo(shot_id: int):
    user = current_user()
    conn = db()
    shot = conn.execute("SELECT id FROM shots WHERE id = ? AND user_id = ?",
                        (shot_id, user["id"])).fetchone()
    if shot is None:
        return fail("Shot not found", 404)

    data = body()
    try:
        full_raw, full_ext, full_mime = decode_photo(data.get("full"), MAX_PHOTO)
        if data.get("thumb"):
            thumb_raw, thumb_ext, thumb_mime = decode_photo(data.get("thumb"), MAX_PHOTO)
        else:
            thumb_raw, thumb_ext, thumb_mime = full_raw, full_ext, full_mime
    except ValueError as exc:
        return fail(str(exc))

    width = clean_dimension(data.get("width"))
    height = clean_dimension(data.get("height"))
    existing = conn.execute(
        "SELECT full_file, thumb_file FROM shot_photos WHERE shot_id = ?", (shot_id,)
    ).fetchone()

    token = secrets.token_hex(8)
    full_name = f"{user['id']}-{shot_id}-{token}.{full_ext}"
    thumb_name = f"{user['id']}-{shot_id}-{token}-thumb.{thumb_ext}"
    written = []
    try:
        with open(photo_path(full_name), "wb") as fh:
            fh.write(full_raw)
        written.append(full_name)
        with open(photo_path(thumb_name), "wb") as fh:
            fh.write(thumb_raw)
        written.append(thumb_name)

        conn.execute(
            """
            INSERT INTO shot_photos (shot_id, user_id, full_file, thumb_file, mime, thumb_mime, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shot_id) DO UPDATE SET
                user_id = excluded.user_id,
                full_file = excluded.full_file,
                thumb_file = excluded.thumb_file,
                mime = excluded.mime,
                thumb_mime = excluded.thumb_mime,
                width = excluded.width,
                height = excluded.height,
                created_at = excluded.created_at
            """,
            (shot_id, user["id"], full_name, thumb_name, full_mime, thumb_mime,
             width, height, iso(utcnow())),
        )
        conn.commit()
    except (OSError, sqlite3.Error) as exc:
        remove_photo_files(written)
        return fail(f"Could not save the photo: {exc}", 500)

    if existing:
        remove_photo_files([existing["full_file"], existing["thumb_file"]])

    row = conn.execute(SHOT_SELECT + " WHERE s.id = ?", (shot_id,)).fetchone()
    return jsonify({"shot": shot_payload(row)}), 201


@app.get("/api/shots/<int:shot_id>/photo")
@login_required
def get_photo(shot_id: int):
    row = photo_row(shot_id, current_user()["id"])
    if row is None:
        return fail("Photo not found", 404)
    wants_thumb = request.args.get("thumb") == "1" and row["thumb_file"]
    filename = row["thumb_file"] if wants_thumb else row["full_file"]
    mime = (row["thumb_mime"] or row["mime"]) if wants_thumb else row["mime"]
    if not filename or not os.path.isfile(photo_path(filename)):
        return fail("Photo not found", 404)
    response = send_from_directory(PHOTO_DIR, filename, mimetype=mime or "image/jpeg", max_age=31536000)
    response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return response


@app.delete("/api/shots/<int:shot_id>/photo")
@login_required
def delete_photo(shot_id: int):
    user = current_user()
    conn = db()
    row = conn.execute(
        "SELECT full_file, thumb_file FROM shot_photos WHERE shot_id = ? AND user_id = ?",
        (shot_id, user["id"]),
    ).fetchone()
    if row is None:
        return fail("Photo not found", 404)
    conn.execute("DELETE FROM shot_photos WHERE shot_id = ? AND user_id = ?", (shot_id, user["id"]))
    conn.commit()
    remove_photo_files([row["full_file"], row["thumb_file"]])
    return jsonify({"ok": True})


# ---------------------------------------------------------------- stats & export

@app.get("/api/stats")
@login_required
def stats():
    user_id = current_user()["id"]
    conn = db()
    # Café entries are part of the journal but not part of the brewing record:
    # they never move the averages, the streak, or the dial-in advice.
    home = "user_id = ? AND is_cafe = 0"
    total = conn.execute(f"SELECT COUNT(*) AS c FROM shots WHERE {home}", (user_id,)).fetchone()["c"]
    cafe_total = conn.execute("SELECT COUNT(*) AS c FROM shots WHERE user_id = ? AND is_cafe = 1",
                              (user_id,)).fetchone()["c"]
    week_ago = iso(utcnow() - timedelta(days=7))
    week = conn.execute(f"SELECT COUNT(*) AS c FROM shots WHERE {home} AND brewed_at >= ?",
                        (user_id, week_ago)).fetchone()["c"]
    avg_row = conn.execute(f"SELECT AVG(rating) AS r FROM shots WHERE {home} AND rating IS NOT NULL",
                           (user_id,)).fetchone()
    recipe_row = conn.execute(
        f"SELECT AVG(dose_g) AS d, AVG(yield_g) AS y, AVG(time_s) AS t "
        f"FROM shots WHERE {home} AND method = 'espresso'", (user_id,)).fetchone()
    if recipe_row["d"] is None and recipe_row["y"] is None and recipe_row["t"] is None:
        recipe_row = conn.execute(
            f"SELECT AVG(dose_g) AS d, AVG(yield_g) AS y, AVG(time_s) AS t "
            f"FROM shots WHERE {home}", (user_id,)).fetchone()
    bean_count = conn.execute("SELECT COUNT(*) AS c FROM beans WHERE user_id = ? AND archived = 0",
                              (user_id,)).fetchone()["c"]

    series = []
    for offset in range(13, -1, -1):
        day = (utcnow() - timedelta(days=offset)).date()
        start = iso(datetime(day.year, day.month, day.day, tzinfo=timezone.utc))
        end = iso(datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1))
        count = conn.execute(
            f"SELECT COUNT(*) AS c FROM shots WHERE {home} AND brewed_at >= ? AND brewed_at < ?",
            (user_id, start, end)).fetchone()["c"]
        series.append({"date": day.isoformat(), "count": count})

    methods = [dict(row) for row in conn.execute(
        f"SELECT method, COUNT(*) AS count FROM shots WHERE {home} GROUP BY method ORDER BY count DESC",
        (user_id,)).fetchall()]

    tag_counts: dict[str, int] = {}
    for row in conn.execute(f"SELECT flavor_tags FROM shots WHERE {home}", (user_id,)).fetchall():
        try:
            for tag in json.loads(row["flavor_tags"] or "[]"):
                if isinstance(tag, str):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        except (ValueError, TypeError):
            continue
    top_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:8]

    favorite_bean = conn.execute(
        "SELECT b.name, b.roaster, COUNT(*) AS count FROM shots s JOIN beans b ON b.id = s.bean_id "
        "WHERE s.user_id = ? AND s.is_cafe = 0 GROUP BY b.id ORDER BY count DESC LIMIT 1",
        (user_id,)).fetchone()

    best = conn.execute(
        SHOT_SELECT + " WHERE s.user_id = ? AND s.is_cafe = 0 AND s.rating IS NOT NULL "
        "ORDER BY s.rating DESC, s.brewed_at DESC LIMIT 1", (user_id,)).fetchone()

    return jsonify({
        "total_shots": total,
        "cafe_shots": cafe_total,
        "week_shots": week,
        "avg_rating": round(avg_row["r"], 2) if avg_row["r"] is not None else None,
        "avg_dose": round(recipe_row["d"], 1) if recipe_row["d"] is not None else None,
        "avg_yield": round(recipe_row["y"], 1) if recipe_row["y"] is not None else None,
        "avg_time": round(recipe_row["t"], 1) if recipe_row["t"] is not None else None,
        "bean_count": bean_count,
        "series": series,
        "methods": methods,
        "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
        "favorite_bean": dict(favorite_bean) if favorite_bean else None,
        "best_shot": shot_payload(best) if best else None,
    })


def export_rows(user_id: int):
    rows = db().execute(SHOT_SELECT + " WHERE s.user_id = ? ORDER BY s.brewed_at DESC", (user_id,)).fetchall()
    return [shot_payload(row) for row in rows]


@app.get("/api/export.csv")
@login_required
def export_csv():
    shots = export_rows(current_user()["id"])
    columns = [
        ("brewed_at", "Brewed at"), ("method", "Method"), ("bean_name", "Bean"),
        ("bean_roaster", "Roaster"), ("dose_g", "Dose (g)"), ("yield_g", "Yield (g)"),
        ("time_s", "Time (s)"), ("grind", "Grind"), ("temp_c", "Temp (°C)"),
        ("pressure_bar", "Pressure (bar)"), ("preinfusion_s", "Pre-infusion (s)"),
        ("tds", "TDS (%)"), ("ey", "Extraction yield (%)"), ("milk_type", "Milk"),
        ("milk_volume_ml", "Milk volume (ml)"), ("rating", "Rating"),
        ("acidity", "Acidity"), ("body", "Body"), ("sweetness", "Sweetness"),
        ("bitterness", "Bitterness"), ("aftertaste", "Aftertaste"),
        ("flavor_tags", "Flavor tags"), ("tasting_notes", "Tasting notes"),
        ("notes", "Notes"), ("machine", "Machine"), ("grinder", "Grinder"),
        ("basket", "Basket"), ("favorite", "Favorite"), ("is_cafe", "At a café"),
        ("cafe_name", "Place"), ("drink_name", "What I ordered"),
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in columns])
    for shot in shots:
        line = []
        for key, _ in columns:
            value = shot.get(key)
            if isinstance(value, list):
                value = ", ".join(value)
            line.append("" if value is None else value)
        writer.writerow(line)
    stamp = utcnow().strftime("%Y-%m-%d")
    return app.response_class(
        buffer.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="crema-shots-{stamp}.csv"'},
    )


@app.get("/api/export.json")
@login_required
def export_json():
    user = current_user()
    payload = {
        "exported_at": iso(utcnow()),
        "user": {"name": user["name"], "email": user["email"]},
        "shots": export_rows(user["id"]),
        "beans": [bean_payload(row) for row in db().execute(
            "SELECT * FROM beans WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)).fetchall()],
    }
    stamp = utcnow().strftime("%Y-%m-%d")
    return app.response_class(
        json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="crema-export-{stamp}.json"'},
    )


@app.get("/api/export.pdf")
@login_required
def export_pdf():
    user = current_user()
    user_id = user["id"]
    shots = export_rows(user_id)
    beans = [bean_payload(row) for row in db().execute(
        "SELECT * FROM beans WHERE user_id = ? ORDER BY archived, created_at DESC", (user_id,)).fetchall()]

    photos = {}
    for row in db().execute(
        "SELECT p.shot_id, p.thumb_file, p.thumb_mime FROM shot_photos p "
        "JOIN shots s ON s.id = p.shot_id WHERE s.user_id = ?", (user_id,)
    ).fetchall():
        if row["thumb_file"] and row["thumb_mime"] in ("image/jpeg", "image/png"):
            photos[row["shot_id"]] = os.path.join(PHOTO_DIR, row["thumb_file"])

    try:
        from pdf_export import build_pdf
        pdf_bytes = build_pdf(
            {"name": user["name"], "email": user["email"]},
            shots,
            beans,
            photos,
        )
    except Exception:
        app.logger.exception("PDF export failed for user %s", user_id)
        return fail("Could not build the PDF just now. Please try again.", 500)

    stamp = utcnow().strftime("%Y-%m-%d")
    return app.response_class(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="crema-journal-{stamp}.pdf"'},
    )


@app.get("/api/health")
def health():
    try:
        db().execute("SELECT 1").fetchone()
    except sqlite3.Error:
        return jsonify({"status": "error"}), 500
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------- backups

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
try:
    BACKUP_HOURS = float(os.environ.get("CREMA_BACKUP_HOURS", "24") or 24)
except ValueError:
    BACKUP_HOURS = 24.0
try:
    BACKUP_KEEP = max(1, int(os.environ.get("CREMA_BACKUP_KEEP", "14") or 14))
except ValueError:
    BACKUP_KEEP = 14
BACKUP_LOCK = threading.Lock()


@contextlib.contextmanager
def backup_guard():
    """Serialise archive writes across threads and gunicorn workers.

    Two workers each run a backup thread. The file lock means only one of them
    builds an archive, and the second sees the fresh last_backup_at afterwards.
    """
    with BACKUP_LOCK:
        handle = open(os.path.join(DATA_DIR, ".backup.lock"), "w")
        try:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()


def list_backups() -> list:
    if not os.path.isdir(BACKUP_DIR):
        return []
    names = [name for name in os.listdir(BACKUP_DIR) if name.endswith(".zip")]
    return sorted(names, reverse=True)


def prune_backups(keep: int = None) -> None:
    keep = BACKUP_KEEP if keep is None else keep
    for name in list_backups()[max(0, keep):]:
        try:
            os.remove(os.path.join(BACKUP_DIR, name))
        except OSError:
            pass


def record_backup(name: str) -> None:
    stamp = iso(utcnow())
    conn = sqlite3.connect(DB_PATH, timeout=20)
    try:
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('last_backup_at', ?)", (stamp,))
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('last_backup_file', ?)", (name,))
        conn.commit()
    finally:
        conn.close()


def last_backup_at():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    try:
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'last_backup_at'").fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
    except ValueError:
        return None


def backup_due() -> bool:
    if BACKUP_HOURS <= 0:
        return False
    last = last_backup_at()
    if last is None:
        return True
    return (utcnow() - last).total_seconds() >= BACKUP_HOURS * 3600


def write_backup(reason: str) -> str:
    """Write one zip with a consistent copy of the database plus the photos.

    Callers must hold backup_guard().
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    base = utcnow().strftime("%Y%m%d-%H%M%S")
    name = f"crema-{base}.zip"
    counter = 2
    while os.path.exists(os.path.join(BACKUP_DIR, name)):
        name = f"crema-{base}-{counter}.zip"
        counter += 1
    target = os.path.join(BACKUP_DIR, name)
    partial = target + ".part"
    dump = partial + ".sqlite3"
    try:
        source = sqlite3.connect(DB_PATH, timeout=20)
        try:
            snapshot = sqlite3.connect(dump)
            try:
                source.backup(snapshot)
            finally:
                snapshot.close()
        finally:
            source.close()
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(dump, "crema.sqlite3")
            for entry in sorted(os.listdir(PHOTO_DIR)):
                path = os.path.join(PHOTO_DIR, entry)
                if os.path.isfile(path):
                    bundle.write(path, f"photos/{entry}")
            bundle.writestr("README.txt",
                            f"Crema backup ({reason})\ncreated: {iso(utcnow())}\n\n"
                            "crema.sqlite3 is the whole journal; photos/ holds shot and profile images.\n"
                            "To restore: stop Crema, replace the database file in COFFEE_DATA_DIR,\n"
                            "copy photos/ into COFFEE_DATA_DIR/photos, then start Crema again.\n")
        os.replace(partial, target)
        try:
            # The archive holds every account and photo; keep it owner-only.
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        for leftover in (partial, dump):
            if os.path.exists(leftover):
                try:
                    os.remove(leftover)
                except OSError:
                    pass
    prune_backups()
    record_backup(name)
    return name


def create_backup(reason: str = "manual") -> str:
    with backup_guard():
        return write_backup(reason)


def scheduled_backup():
    """Create the nightly archive only if one is due, re-checking under the lock."""
    with backup_guard():
        if not backup_due():
            return None
        return write_backup("nightly")


def backup_loop() -> None:
    # Give the worker time to finish starting, then check twice an hour.
    time.sleep(90)
    while True:
        try:
            scheduled_backup()
        except Exception:
            app.logger.exception("Automatic backup failed")
        time.sleep(1800)


@app.get("/api/backup")
@admin_required
def backup_status():
    files = [{"name": name, "bytes": os.path.getsize(os.path.join(BACKUP_DIR, name))} for name in list_backups()]
    last = last_backup_at()
    return jsonify({
        "last_backup_at": iso(last) if last else None,
        "files": files[:BACKUP_KEEP],
        "keep": BACKUP_KEEP,
        "hours": BACKUP_HOURS,
        "enabled": os.environ.get("CREMA_BACKUP", "1") != "0" and BACKUP_HOURS > 0,
        "directory": BACKUP_DIR,
    })


@app.post("/api/backup")
@admin_required
def backup_now():
    try:
        name = create_backup("manual")
    except (OSError, sqlite3.Error) as exc:
        return fail(f"Could not write the backup: {exc}", 500)
    return jsonify({"ok": True, "file": name, "files": list_backups()[:BACKUP_KEEP]}), 201


@app.get("/api/backup/latest")
@admin_required
def backup_download():
    files = list_backups()
    if not files:
        return fail("No backup yet", 404)
    return send_from_directory(BACKUP_DIR, files[0], as_attachment=True)


def start_backup_thread() -> None:
    global _backup_started
    if os.environ.get("CREMA_BACKUP", "1") == "0" or _backup_started:
        return
    _backup_started = True
    thread = threading.Thread(target=backup_loop, name="crema-backup", daemon=True)
    thread.start()


# ---------------------------------------------------------------- static SPA

@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()"
    )
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
        "media-src 'self' blob:; object-src 'none'; "
        "frame-ancestors 'self'; base-uri 'self'; form-action 'self'",
    )
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/")
@app.get("/<path:path>")
def spa(path: str = ""):
    if path.startswith("api/"):
        return fail("Not found", 404)
    if path:
        candidate = os.path.normpath(os.path.join(STATIC_DIR, path))
        if candidate.startswith(STATIC_DIR + os.sep) and os.path.isfile(candidate):
            return send_from_directory(STATIC_DIR, path, max_age=0)
    response = send_from_directory(STATIC_DIR, "index.html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return fail("Not found", 404)
    return spa("")


@app.errorhandler(413)
def too_large(_error):
    return fail("Request is too large", 413)


if __name__ == "__main__":
    ensure_db()
    app.run(host="127.0.0.1", port=8787, debug=os.environ.get("CREMA_DEBUG") == "1")
