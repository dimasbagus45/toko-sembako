class handler(SimpleHTTPRequestHandler):
    server_version = "SembakoNusaVercel/1.0"

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
        if not self._valid_origin():
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
        if not self._valid_origin():
            self._json(403, {"error": "Origin tidak diizinkan."})
            return
        self._api_put(urlsplit(self.path).path)

    def do_DELETE(self):
        if not self._valid_origin():
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

    def _valid_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlsplit(origin)
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        return (
            parsed.scheme in {"http", "https"}
            and parsed.netloc.lower() == host.lower()
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


# Inisialisasi database saat cold start di Vercel
try:
    initialize_database()
except Exception as e:
    print(f"Peringatan inisialisasi database: {e}")


if __name__ == "__main__":
    server = LocalServer(("127.0.0.1", 8000), handler)
    print(f"Database MySQL: {MYSQL_DATABASE}")
    print("Toko berjalan di http://127.0.0.1:8000")
    print("Login admin pertama: admin / admin123")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
    finally:
        server.server_close()