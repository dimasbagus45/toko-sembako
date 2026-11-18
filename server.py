import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import mysql.connector


ROOT = Path(__file__).resolve().parent
DATABASE_DIR = ROOT / "data"
SQLITE_DATABASE_PATH = DATABASE_DIR / "sembako.sqlite3"
MYSQL_DATABASE = os.environ.get("SEMBAKO_DB_NAME", "sembako_nusa")
SESSION_COOKIE = "sembako_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
MAX_REQUEST_BYTES = 64 * 1024 * 1024
PASSWORD_ITERATIONS = 310_000
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
MIGRATION_LOCK = threading.Lock()

DEFAULT_PRODUCTS = [
    ("beras", "Beras Setra Ramos", "Bahan pokok", "5 kg", 72500, 20, "🍚", "#f1ebda", "Favorit"),
    ("minyak", "Minyak Goreng", "Bahan pokok", "1 liter", 18500, 30, "🫒", "#f4edce", "Pilihan"),
    ("gula", "Gula Pasir Putih", "Bahan pokok", "1 kg", 17500, 24, "🍬", "#f2e9df", ""),
    ("telur", "Telur Ayam Negeri", "Bahan pokok", "1 kg", 29000, 16, "🥚", "#f6ead7", "Segar"),
    ("mie", "Mi Instan Goreng", "Makanan", "5 bungkus", 16000, 40, "🍜", "#f4e9c9", ""),
    ("tepung", "Tepung Terigu", "Bahan pokok", "1 kg", 13500, 18, "🌾", "#ece9da", ""),
    ("susu", "Susu UHT Cokelat", "Minuman", "1 liter", 20500, 12, "🥛", "#eee5dc", "Favorit"),
    ("kopi", "Kopi Bubuk", "Minuman", "200 gram", 15500, 15, "☕", "#ece3dc", ""),
    ("sabun", "Sabun Cuci Piring", "Rumah tangga", "750 ml", 17000, 14, "🧼", "#e5eee7", ""),
    ("garam", "Garam Beryodium", "Bahan pokok", "500 gram", 5000, 25, "🧂", "#e9e8e1", ""),
    ("kecap", "Kecap Manis", "Makanan", "275 ml", 14500, 13, "🍯", "#efe4d4", ""),
    ("sarden", "Sarden Kaleng", "Makanan", "155 gram", 12500, 11, "🐟", "#e5eceb", ""),
]


@contextmanager
def connect_db():
    connection = mysql.connector.connect(
        host=os.environ.get("SEMBAKO_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("SEMBAKO_DB_PORT", "3306")),
        user=os.environ.get("SEMBAKO_DB_USER", "root"),
        password=os.environ.get("SEMBAKO_DB_PASSWORD", ""),
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        connection_timeout=5,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def execute(db, statement, params=None):
    cursor = db.cursor(dictionary=True)
    cursor.execute(statement, params or ())
    return cursor


def executemany(db, statement, rows):
    cursor = db.cursor()
    cursor.executemany(statement, rows)
    return cursor


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return salt.hex(), digest.hex()


def initialize_database():
    with connect_db() as db:
        _execute_sqlite_migration(db)


def _execute_sqlite_migration(db):
    imported = execute(
        db, "SELECT value FROM app_meta WHERE `key` = 'sqlite_import_done'"
    ).fetchone()
    if imported:
        return

    if SQLITE_DATABASE_PATH.exists():
        with closing(sqlite3.connect(SQLITE_DATABASE_PATH)) as source:
            source.row_factory = sqlite3.Row
            products = [
                dict(row)
                for row in source.execute("SELECT * FROM products").fetchall()
            ]
            if (
                execute(db, "SELECT COUNT(*) AS total FROM products").fetchone()["total"] == 0
                and all(valid_product(product) for product in products)
            ):
                executemany(
                    db,
                    """
                    INSERT INTO products
                        (id, name, category, unit, price, stock, icon, color, tag, photo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            p["id"], p["name"], p["category"], p["unit"], p["price"],
                            p["stock"], p["icon"], p["color"], p["tag"], p.get("photo"),
                        )
                        for p in products
                    ],
                )

            settings = source.execute(
                "SELECT value FROM settings WHERE key = 'whatsapp'"
            ).fetchone()
            if settings:
                execute(
                    db,
                    """
                    INSERT IGNORE INTO settings (`key`, value) VALUES ('whatsapp', %s)
                    """,
                    (settings["value"],),
                )

            if execute(db, "SELECT COUNT(*) AS total FROM orders").fetchone()["total"] == 0:
                orders = source.execute("SELECT * FROM orders").fetchall()
                for row in orders:
                    order = dict(row)
                    order["createdAt"] = order.pop("created_at")
                    order["items"] = [
                        {
                            "id": item["product_id"],
                            "name": item["name"],
                            "unit": item["unit"],
                            "price": item["price"],
                            "quantity": item["quantity"],
                        }
                        for item in source.execute(
                            "SELECT * FROM order_items WHERE order_id = ? ORDER BY rowid",
                            (order["id"],),
                        ).fetchall()
                    ]
                    if valid_order(order):
                        _insert_order(db, order)

            if execute(db, "SELECT COUNT(*) AS total FROM accounts").fetchone()["total"] == 0:
                accounts = source.execute(
                    "SELECT username, password_salt, password_hash, role FROM accounts"
                ).fetchall()
                executemany(
                    db,
                    """
                    INSERT INTO accounts (username, password_salt, password_hash, role)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [
                        (a["username"], a["password_salt"], a["password_hash"], a["role"])
                        for a in accounts
                    ],
                )

    execute(
        db,
        "INSERT IGNORE INTO app_meta (`key`, value) VALUES ('sqlite_import_done', '1')",
    )


def _store_order(db, order):
    execute(
        db,
        """
        INSERT INTO orders (id, created_at, status, whatsapp, total)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            order["id"], order["createdAt"], order["status"],
            order["whatsapp"], order["total"],
        ),
    )
    executemany(
        db,
        """
        INSERT INTO order_items
            (order_id, product_id, name, unit, price, quantity)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            (
                order["id"], item["id"], item["name"], item["unit"],
                item["price"], item["quantity"],
            )
            for item in order["items"]
        ],
    )


def _store_products(db, products):
    execute(db, "DELETE FROM products")
    executemany(
        db,
        """
        INSERT INTO products
            (id, name, category, unit, price, stock, icon, color, tag, photo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                p["id"], p["name"].strip(), p["category"].strip(),
                p["unit"].strip(), p["price"], p["stock"], p.get("icon"),
                p.get("color"), p["tag"], p.get("photo"),
            )
            for p in products
        ],
    )


def _seed_defaults(db):
    if execute(db, "SELECT COUNT(*) AS total FROM products").fetchone()["total"] == 0:
        executemany(
            db,
            """
            INSERT INTO products
                (id, name, category, unit, price, stock, icon, color, tag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            DEFAULT_PRODUCTS,
        )
    execute(
        db,
        "INSERT IGNORE INTO settings (`key`, value) VALUES ('whatsapp', %s)",
        ("62895396080850",),
    )
    if execute(db, "SELECT COUNT(*) AS total FROM accounts").fetchone()["total"] == 0:
        salt, password_hash = hash_password("admin123")
        execute(
            db,
            """
            INSERT INTO accounts (username, password_salt, password_hash, role)
            VALUES (%s, %s, %s, 'admin')
            """,
            ("admin", salt, password_hash),
        )


def valid_photo(value):
    if not isinstance(value, str) or len(value) > 1_400_000:
        return False
    match = re.fullmatch(
        r"data:image/(?:jpeg|png|webp|gif);base64,([A-Za-z0-9+/]+={0,2})",
        value,
    )
    if not match:
        return False
    try:
        base64.b64decode(match.group(1), validate=True)
        return True
    except (ValueError, base64.binascii.Error):
        return False


def valid_product(product):
    if not isinstance(product, dict):
        return False
    has_photo = valid_photo(product.get("photo"))
    has_legacy_art = (
        isinstance(product.get("icon"), str)
        and len(product["icon"]) > 0
        and isinstance(product.get("color"), str)
        and re.fullmatch(r"#[0-9a-fA-F]{6}", product["color"]) is not None
    )
    return (
        isinstance(product.get("id"), str)
        and re.fullmatch(r"[a-z0-9-]+", product["id"]) is not None
        and isinstance(product.get("name"), str)
        and bool(product["name"].strip())
        and isinstance(product.get("category"), str)
        and bool(product["category"].strip())
        and isinstance(product.get("unit"), str)
        and bool(product["unit"].strip())
        and type(product.get("price")) is int
        and product["price"] > 0
        and type(product.get("stock")) is int
        and product["stock"] >= 0
        and isinstance(product.get("tag"), str)
        and (has_photo or has_legacy_art)
    )


def valid_order(order):
    if not isinstance(order, dict):
        return False
    try:
        datetime.fromisoformat(order.get("createdAt", "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    items = order.get("items")
    return (
        isinstance(order.get("id"), str)
        and bool(order["id"])
        and isinstance(order.get("status"), str)
        and bool(order["status"])
        and isinstance(order.get("whatsapp"), str)
        and re.fullmatch(r"\d{8,15}", order["whatsapp"]) is not None
        and type(order.get("total")) is int
        and order["total"] >= 0
        and isinstance(items, list)
        and bool(items)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and isinstance(item.get("name"), str)
            and bool(item["name"])
            and isinstance(item.get("unit"), str)
            and type(item.get("price")) is int
            and item["price"] > 0
            and type(item.get("quantity")) is int
            and item["quantity"] > 0
            for item in items
        )
        and sum(item["price"] * item["quantity"] for item in items) == order["total"]
    )


def valid_account(account):
    return (
        isinstance(account, dict)
        and isinstance(account.get("username"), str)
        and re.fullmatch(r"[a-zA-Z0-9._-]{3,30}", account["username"]) is not None
        and isinstance(account.get("password"), str)
        and len(account["password"]) >= 6
        and account.get("role") == "admin"
    )


class RequestHandler(SimpleHTTPRequestHandler):
    server_version = "SembakoNusaLocal/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Ukuran data terlalu besar.")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _is_admin(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        token = morsel.value if morsel else ""
        now = time.time()
        with SESSIONS_LOCK:
            expires = SESSIONS.get(token, 0)
            if expires <= now:
                SESSIONS.pop(token, None)
                return False
            SESSIONS[token] = now + SESSION_TTL_SECONDS
            return True

    def _require_admin(self):
        if self._is_admin():
            return True
        self._json(401, {"error": "Silakan masuk sebagai admin."})
        return False

    def _products(self):
        with connect_db() as db:
            rows = execute(db, "SELECT * FROM products ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def _orders(self):
        with connect_db() as db:
            rows = execute(
                db,
                "SELECT * FROM orders ORDER BY created_at DESC"
            ).fetchall()
            orders = []
            for row in rows:
                order = dict(row)
                order["createdAt"] = order.pop("created_at")
                order["items"] = [
                    {
                        "id": item["product_id"],
                        "name": item["name"],
                        "unit": item["unit"],
                        "price": item["price"],
                        "quantity": item["quantity"],
                    }
                    for item in execute(
                        db,
                        "SELECT * FROM order_items WHERE order_id = %s ORDER BY product_id",
                        (order["id"],),
                    ).fetchall()
                ]
                orders.append(order)
        return orders

    def _save_products(self, products):
        if not isinstance(products, list) or not all(valid_product(p) for p in products):
            raise ValueError("Data produk tidak valid.")
        ids = [product["id"] for product in products]
        if len(set(ids)) != len(ids):
            raise ValueError("ID produk tidak boleh duplikat.")
        with connect_db() as db:
            _store_products(db, products)

    def _insert_order(self, order):
        if not valid_order(order):
            raise ValueError("Data pesanan tidak valid.")
        with connect_db() as db:
            _store_order(db, order)

    def _legacy_import(self, data):
        if not isinstance(data, dict):
            raise ValueError("Data migrasi tidak valid.")
        with MIGRATION_LOCK:
            with connect_db() as db:
                done = execute(
                    db, "SELECT value FROM app_meta WHERE `key` = 'legacy_import_done'"
                ).fetchone()
                if done:
                    return False

                products = data.get("products")
                if isinstance(products, list) and all(valid_product(p) for p in products):
                    if execute(db, "SELECT COUNT(*) AS total FROM products").fetchone()["total"] == 0:
                        _store_products(db, products)

                settings = data.get("settings")
                if (
                    isinstance(settings, dict)
                    and isinstance(settings.get("whatsapp"), str)
                    and re.fullmatch(r"\d{8,15}", settings["whatsapp"])
                ):
                    execute(
                        db,
                        "INSERT IGNORE INTO settings (`key`, value) VALUES ('whatsapp', %s)",
                        (settings["whatsapp"],),
                    )

                orders = data.get("orders")
                if isinstance(orders, list) and all(valid_order(order) for order in orders):
                    if execute(db, "SELECT COUNT(*) AS total FROM orders").fetchone()["total"] == 0:
                        for order in orders:
                            _store_order(db, order)

                accounts = data.get("accounts")
                if isinstance(accounts, list) and accounts and all(valid_account(a) for a in accounts):
                    usernames = [account["username"].lower() for account in accounts]
                    account_count = execute(
                        db, "SELECT COUNT(*) AS total FROM accounts"
                    ).fetchone()["total"]
                    if len(set(usernames)) == len(usernames) and account_count == 0:
                        for account in accounts:
                            salt, password_hash = hash_password(account["password"])
                            execute(
                                db,
                                """
                                INSERT INTO accounts
                                    (username, password_salt, password_hash, role)
                                VALUES (%s, %s, %s, 'admin')
                                """,
                                (account["username"], salt, password_hash),
                            )

                _seed_defaults(db)
                execute(
                    db,
                    "INSERT IGNORE INTO app_meta (`key`, value) VALUES ('legacy_import_done', '1')",
                )
                return True

    def _api_get(self, path):
        if path == "/api/products":
            self._json(200, self._products())
        elif path == "/api/settings":
            with connect_db() as db:
                row = execute(
                    db, "SELECT value FROM settings WHERE `key` = 'whatsapp'"
                ).fetchone()
            self._json(200, {"whatsapp": row["value"]})
        elif path == "/api/orders":
            if self._require_admin():
                self._json(200, self._orders())
        elif path == "/api/session":
            self._json(200, {"authenticated": self._is_admin()})
        else:
            self._json(404, {"error": "Endpoint tidak ditemukan."})

    def _api_post(self, path):
        data = self._body()
        if path == "/api/login":
            username = data.get("username") if isinstance(data, dict) else None
            password = data.get("password") if isinstance(data, dict) else None
            if not isinstance(username, str) or not isinstance(password, str):
                self._json(400, {"error": "Nama pengguna dan kata sandi wajib diisi."})
                return
            with connect_db() as db:
                account = execute(
                    db,
                    "SELECT * FROM accounts WHERE username = %s",
                    (username,),
                ).fetchone()
            if not account:
                self._json(401, {"error": "Nama pengguna atau kata sandi tidak sesuai."})
                return
            salt = bytes.fromhex(account["password_salt"])
            _, password_hash = hash_password(password, salt)
            if not hmac.compare_digest(password_hash, account["password_hash"]):
                self._json(401, {"error": "Nama pengguna atau kata sandi tidak sesuai."})
                return
            token = secrets.token_urlsafe(32)
            with SESSIONS_LOCK:
                SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
            self._json(
                200,
                {"authenticated": True},
                {
                    "Set-Cookie": (
                        f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Strict; "
                        f"Path=/; Max-Age={SESSION_TTL_SECONDS}"
                    )
                },
            )
        elif path == "/api/logout":
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get(SESSION_COOKIE)
            if morsel:
                with SESSIONS_LOCK:
                    SESSIONS.pop(morsel.value, None)
            self._json(
                200,
                {"authenticated": False},
                {"Set-Cookie": f"{SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"},
            )
        elif path == "/api/legacy-import":
            try:
                imported = self._legacy_import(data)
            except (ValueError, sqlite3.Error, mysql.connector.Error) as error:
                self._json(400, {"error": str(error)})
                return
            self._json(200, {"imported": imported})
        elif path == "/api/orders":
            try:
                self._insert_order(data)
            except (ValueError, sqlite3.Error, mysql.connector.Error) as error:
                self._json(400, {"error": str(error)})
                return
            self._json(201, {"saved": True})
        else:
            self._json(404, {"error": "Endpoint tidak ditemukan."})

    def _api_put(self, path):
        if not self._require_admin():
            return
        try:
            data = self._body()
            if path == "/api/products":
                self._save_products(data)
                self._json(200, {"saved": True})
            elif path == "/api/settings":
                phone = data.get("whatsapp") if isinstance(data, dict) else None
                if not isinstance(phone, str) or re.fullmatch(r"\d{8,15}", phone) is None:
                    self._json(400, {"error": "Nomor WhatsApp tidak valid."})
                    return
                with connect_db() as db:
                    execute(
                        db,
                        """
                        INSERT INTO settings (`key`, value) VALUES ('whatsapp', %s)
                        ON DUPLICATE KEY UPDATE value = %s
                        """,
                        (phone, phone),
                    )
                self._json(200, {"saved": True})
            else:
                self._json(404, {"error": "Endpoint tidak ditemukan."})
        except (ValueError, mysql.connector.Error) as error:
            self._json(400, {"error": str(error)})

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            self._api_get(path)
        elif self._is_database_path():
            self.send_error(404, "Not found")
        else:
            super().do_GET()

    def do_HEAD(self):
        if self._is_database_path():
            self.send_error(404, "Not found")
        else:
            super().do_HEAD()

    def do_POST(self):
        if not self._valid_host() or not self._valid_origin():
            self._json(403, {"error": "Origin tidak diizinkan."})
            return
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            try:
                self._api_post(path)
            except (ValueError, json.JSONDecodeError) as error:
                self._json(400, {"error": f"Permintaan tidak valid: {error}"})
        else:
            self._json(404, {"error": "Endpoint tidak ditemukan."})

    def do_PUT(self):
        if not self._valid_host() or not self._valid_origin():
            self._json(403, {"error": "Origin tidak diizinkan."})
            return
        self._api_put(urlsplit(self.path).path)

    def do_DELETE(self):
        if not self._valid_host() or not self._valid_origin():
            self._json(403, {"error": "Origin tidak diizinkan."})
            return
        if not self._require_admin():
            return
        path = urlsplit(self.path).path
        prefix = "/api/orders/"
        if path.startswith(prefix):
            order_id = unquote(path[len(prefix):])
            with connect_db() as db:
                execute(db, "DELETE FROM orders WHERE id = %s", (order_id,))
            self._json(200, {"deleted": True})
        else:
            self._json(404, {"error": "Endpoint tidak ditemukan."})

    def _valid_host(self):
        host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        return host in {"localhost", "127.0.0.1"}

    def _valid_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return False
        parsed = urlsplit(origin)
        return (
            parsed.scheme == "http"
            and parsed.netloc.lower() == self.headers.get("Host", "").lower()
            and self._valid_host()
        )

    def _is_database_path(self):
        requested = Path(super().translate_path(self.path)).resolve()
        try:
            requested.relative_to(DATABASE_DIR.resolve())
            return True
        except ValueError:
            return False

    def log_message(self, format_string, *args):
        print(f"[{self.log_date_time_string()}] {format_string % args}")


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    try:
        initialize_database()
    except mysql.connector.Error as error:
        print(f"MySQL belum siap: {error}")
        print("Pastikan MySQL aktif, database.sql sudah diimpor, dan SEMBAKO_DB_* sudah sesuai.")
        raise SystemExit(1) from error
    server = LocalServer(("127.0.0.1", 8000), RequestHandler)
    print(f"Database MySQL: {MYSQL_DATABASE}")
    print("Toko berjalan di http://127.0.0.1:8000")
    print("Login admin pertama: admin / admin123")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
    finally:
        server.server_close()
