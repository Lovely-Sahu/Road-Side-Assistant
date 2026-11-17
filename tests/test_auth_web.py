"""Authentication, authorization, session and CSRF protections through the Flask app."""
import io
import re
import unittest

from tests import support
import web
from assistance import lifecycle
from database.database import execute_query, fetch_one


def csrf_from(html):
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return match.group(1) if match else None


class LoginTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()
        self.uid = support.make_user("Driver", "driver@example.test", password="CorrectHorse1")

    def login(self, client, email, password):
        token = csrf_from(client.get("/login").get_data(as_text=True))
        return client.post("/login", data={"email": email, "password": password, "csrf_token": token})

    def test_valid_and_invalid_login(self):
        client = web.app.test_client()
        bad = self.login(client, "driver@example.test", "wrong-password")
        self.assertEqual(bad.status_code, 401)
        good = self.login(client, "driver@example.test", "CorrectHorse1")
        self.assertEqual(good.status_code, 302)
        self.assertTrue(good.headers["Location"].endswith("/dashboard"))
        self.assertEqual(client.get("/dashboard").status_code, 200)

    def test_login_without_csrf_token_is_rejected(self):
        client = web.app.test_client()
        client.get("/login")
        response = client.post("/login", data={"email": "driver@example.test", "password": "CorrectHorse1"})
        self.assertEqual(response.status_code, 400)

    def test_login_rate_limited(self):
        client = web.app.test_client()
        for _ in range(web.settings.login_max_failures):
            self.login(client, "driver@example.test", "nope")
        blocked = self.login(client, "driver@example.test", "CorrectHorse1")
        self.assertEqual(blocked.status_code, 429)

    def test_inactive_account_cannot_log_in_and_existing_session_is_revoked(self):
        client = support.web_client(self.uid)
        self.assertEqual(client.get("/dashboard").status_code, 200)
        execute_query("UPDATE users SET is_active = 0 WHERE id = ?", (self.uid,))
        self.assertEqual(client.get("/dashboard").status_code, 302)
        self.assertEqual(client.get("/api/tracking/1").status_code, 401)
        fresh = web.app.test_client()
        response = self.login(fresh, "driver@example.test", "CorrectHorse1")
        self.assertIn(b"inactive", response.data)

    def test_inactive_message_requires_correct_password(self):
        execute_query("UPDATE users SET is_active = 0 WHERE id = ?", (self.uid,))
        response = self.login(web.app.test_client(), "driver@example.test", "wrong")
        self.assertNotIn(b"inactive", response.data)

    def test_open_redirect_blocked(self):
        for target in ("https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"):
            client = web.app.test_client()
            token = csrf_from(client.get("/login").get_data(as_text=True))
            r = client.post("/login?next=" + target, data={"email": "driver@example.test",
                                                           "password": "CorrectHorse1", "csrf_token": token})
            self.assertTrue(r.headers["Location"].endswith("/dashboard"), target)
        client = web.app.test_client()
        token = csrf_from(client.get("/login").get_data(as_text=True))
        r = client.post("/login?next=/vehicles", data={"email": "driver@example.test", "password": "CorrectHorse1",
                                                       "csrf_token": token})
        self.assertTrue(r.headers["Location"].endswith("/vehicles"))

    def test_logout_requires_post(self):
        client = support.web_client(self.uid)
        self.assertEqual(client.get("/logout").status_code, 200)  # confirmation page only
        self.assertEqual(client.get("/dashboard").status_code, 200)
        support.post(client, "/logout")
        self.assertEqual(client.get("/dashboard").status_code, 302)

    def test_session_cookie_flags(self):
        client = web.app.test_client()
        token = csrf_from(client.get("/login").get_data(as_text=True))
        response = client.post("/login", data={"email": "driver@example.test", "password": "CorrectHorse1",
                                               "csrf_token": token})
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)


class RegistrationTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()

    def register(self, **data):
        client = support.web_client()
        base = {"name": "New Person", "email": "new@example.test", "password": "Password123", "role": "driver"}
        base.update(data)
        return support.post(client, "/register", base)

    def test_cannot_self_register_as_admin(self):
        response = self.register(role="admin")
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(fetch_one("SELECT id FROM users WHERE email = 'new@example.test'"))

    def test_provider_registration_is_pending_verification(self):
        self.register(role="provider", business_name="Fix It", service_type="Mechanic", phone="9876543210")
        provider = fetch_one("SELECT p.verification_status FROM providers p JOIN users u ON u.id = p.user_id "
                             "WHERE u.email = 'new@example.test'")
        self.assertEqual(provider["verification_status"], "pending")

    def test_password_is_hashed(self):
        self.register()
        row = fetch_one("SELECT password_hash FROM users WHERE email = 'new@example.test'")
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))
        self.assertNotIn("Password123", row["password_hash"])

    def test_duplicate_phone_gives_friendly_message(self):
        support.make_user("Existing", "existing@example.test", phone="9876543210")
        response = self.register(phone="9876543210")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b"UNIQUE constraint", response.data)


class AuthorizationTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()
        self.engines = support.engines()
        self.driver_a = support.make_user("Driver A", "a@example.test")
        self.driver_b = support.make_user("Driver B", "b@example.test")
        self.admin = support.make_user("Admin", "admin@example.test", role="admin")
        self.pa, self.provider_a = support.make_provider("Provider A", "Mechanic", email="pa@example.test")
        self.pb, self.provider_b = support.make_provider("Provider B", "Mechanic", 20.31, 85.83,
                                                         email="pb@example.test")
        self.req = lifecycle.create_request(self.driver_a, "engine overheating", None, 20.2961, 85.8245,
                                            **self.engines)
        self.match_id = self.req["assignment"]["match_id"]
        self.assigned_user = self.provider_a if self.req["assignment"]["provider_id"] == self.pa else self.provider_b
        self.other_user = self.provider_b if self.assigned_user == self.provider_a else self.provider_a

    def test_role_protected_pages(self):
        driver = support.web_client(self.driver_a)
        for url in ("/admin", "/admin/users", "/admin/requests", "/provider", "/api/provider/jobs"):
            self.assertEqual(driver.get(url).status_code, 403, url)
        provider = support.web_client(self.assigned_user)
        for url in ("/admin", "/report", "/history"):
            self.assertEqual(provider.get(url).status_code, 403, url)
        self.assertEqual(support.post(provider, "/api/assistance/create", {"description": "flat tyre"}).status_code, 403)

    def test_driver_cannot_see_or_cancel_another_drivers_request(self):
        other = support.web_client(self.driver_b)
        rid = self.req["request_id"]
        self.assertEqual(other.get(f"/tracking/{rid}").status_code, 404)
        self.assertEqual(other.get(f"/api/tracking/{rid}").status_code, 404)
        self.assertEqual(support.post(other, f"/api/requests/{rid}/cancel").status_code, 404)
        self.assertEqual(fetch_one("SELECT status FROM assistance_requests WHERE id = ?", (rid,))["status"], "ASSIGNED")

    def test_provider_cannot_touch_another_providers_job_or_request(self):
        other = support.web_client(self.other_user)
        r = support.post(other, f"/api/provider/job/{self.match_id}/status", {"status": "ON_THE_WAY"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(other.get(f"/api/tracking/{self.req['request_id']}").status_code, 404)
        self.assertEqual(fetch_one("SELECT status FROM service_matches WHERE id = ?", (self.match_id,))["status"],
                         "ASSIGNED")

    def test_driver_cannot_attach_vehicle_of_another_driver(self):
        other_vehicle = execute_query("INSERT INTO vehicles (user_id, registration_number) VALUES (?, 'OD02ZZ9999')",
                                      (self.driver_b,))
        client = support.web_client(self.driver_a)
        support.post(client, f"/api/requests/{self.req['request_id']}/cancel")
        r = support.post(client, "/api/assistance/create", {"description": "flat tyre", "vehicle_id": other_vehicle})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(support.post(client, f"/api/vehicles/{other_vehicle}/delete").status_code, 404)
        self.assertEqual(support.post(client, f"/api/vehicles/{other_vehicle}",
                                      {"registration_number": "HACKED01"}).status_code, 404)

    def test_csrf_required_on_state_changing_api(self):
        client = support.web_client(self.driver_a)
        r = client.post(f"/api/requests/{self.req['request_id']}/cancel")
        self.assertEqual(r.status_code, 400)
        r = client.post(f"/api/requests/{self.req['request_id']}/cancel", headers={"X-CSRF-Token": "forged"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(fetch_one("SELECT status FROM assistance_requests WHERE id = ?",
                                   (self.req["request_id"],))["status"], "ASSIGNED")

    def test_password_hash_never_exposed(self):
        for uid, url in ((self.driver_a, "/dashboard"), (self.driver_a, f"/api/tracking/{self.req['request_id']}"),
                         (self.admin, "/admin/users"), (self.assigned_user, "/provider")):
            body = support.web_client(uid).get(url).get_data(as_text=True)
            self.assertNotIn("pbkdf2_sha256", body, url)

    def test_admin_cannot_lock_out_last_admin(self):
        client = support.web_client(self.admin)
        support.post(client, f"/admin/users/{self.admin}/status", {"active": "0"})
        self.assertEqual(fetch_one("SELECT is_active FROM users WHERE id = ?", (self.admin,))["is_active"], 1)
        second = support.make_user("Admin 2", "admin2@example.test", role="admin")
        client2 = support.web_client(second)
        support.post(client2, f"/admin/users/{self.admin}/status", {"active": "0"})
        self.assertEqual(fetch_one("SELECT is_active FROM users WHERE id = ?", (self.admin,))["is_active"], 0)
        support.post(client, f"/admin/users/{second}/status", {"active": "0"})  # admin 1 is now signed out
        self.assertEqual(fetch_one("SELECT is_active FROM users WHERE id = ?", (second,))["is_active"], 1)

    def test_attachment_access_control_and_validation(self):
        client = support.web_client(self.driver_a)
        rid = self.req["request_id"]
        bad = support.post(client, f"/api/requests/{rid}/attachments",
                           {"photo": (io.BytesIO(b"<script>alert(1)</script>" * 10), "x.png")},
                           content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        ok = support.post(client, f"/api/requests/{rid}/attachments", {"photo": (io.BytesIO(png), "car.png")},
                          content_type="multipart/form-data")
        self.assertEqual(ok.status_code, 200)
        attachment = fetch_one("SELECT id FROM request_attachments WHERE request_id = ?", (rid,))["id"]
        with client.get(f"/attachments/{attachment}") as owner_view:
            self.assertEqual(owner_view.status_code, 200)
        self.assertEqual(support.web_client(self.driver_b).get(f"/attachments/{attachment}").status_code, 404)
        self.assertEqual(support.web_client(self.other_user).get(f"/attachments/{attachment}").status_code, 404)
        with support.web_client(self.assigned_user).get(f"/attachments/{attachment}") as provider_view:
            self.assertEqual(provider_view.status_code, 200)

    def test_security_headers_and_error_pages(self):
        client = support.web_client(self.driver_a)
        response = client.get("/dashboard")
        for header in ("Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"):
            self.assertIn(header, response.headers)
        missing = client.get("/does-not-exist")
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn(b"Traceback", missing.data)


if __name__ == "__main__":
    unittest.main()
