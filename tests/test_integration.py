"""
End-to-end workflow through the HTTP API:

driver reports a breakdown -> AI analyses it -> eligible provider found ->
request + match stored -> provider sees the job -> provider updates status
(including ASSIGNED -> ON_THE_WAY, the transition that used to fail) ->
driver sees synchronized tracking -> service completed -> history, feedback
and reports updated. Plus rejection, cancellation, reassignment, provider
unavailability, invalid transitions and repeated requests.
"""
import unittest

from tests import support
from assistance import lifecycle
from database.database import fetch_all, fetch_one

BBSR = {"latitude": "20.2961", "longitude": "85.8245"}


class WorkflowTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()
        self.driver = support.make_user("Asha Driver", "asha@example.test")
        self.admin = support.make_user("Ops Admin", "ops@example.test", role="admin")
        self.mech_id, self.mech_user = support.make_provider("Raj Auto Care", "Mechanic", 20.2961, 85.8245, 4.8)
        self.tow_id, self.tow_user = support.make_provider("24x7 Recovery", "Towing / Recovery", 20.32, 85.82, 4.9)
        self.dc = support.web_client(self.driver)

    def create(self, description, **extra):
        data = {"description": description, **BBSR, **extra}
        return support.post(self.dc, "/api/assistance/create", data)

    def provider_client(self, user_id):
        return support.web_client(user_id)

    def state(self, request_id):
        req = fetch_one("SELECT status FROM assistance_requests WHERE id = ?", (request_id,))["status"]
        match = fetch_one("SELECT status FROM service_matches WHERE request_id = ? ORDER BY id DESC LIMIT 1",
                          (request_id,))
        last = fetch_one("SELECT status FROM tracking WHERE request_id = ? ORDER BY id DESC LIMIT 1", (request_id,))
        return req, match["status"] if match else None, last["status"]

    def test_full_happy_path(self):
        # Vehicle + analysis
        r = support.post(self.dc, "/api/vehicles", {"registration_number": "od 02 ab 1234", "make": "Hyundai",
                                                    "model": "i20", "year": "2021", "fuel_type": "Petrol"})
        self.assertEqual(r.status_code, 200, r.get_json())
        vehicle_id = r.get_json()["vehicle_id"]
        analysis = support.post(self.dc, "/api/analyze", {"description": "My car was stopped and smoke is coming from the engine", **BBSR}).get_json()
        self.assertEqual(analysis["analysis"]["problem"], "engine_overheating")
        self.assertGreaterEqual(analysis["provider_preview"]["eligible"], 1)

        # Create
        created = self.create("My car was stopped and smoke is coming from the engine", vehicle_id=vehicle_id)
        body = created.get_json()
        self.assertEqual(created.status_code, 200, body)
        rid = body["request_id"]
        self.assertEqual(body["provider"]["business_name"], "Raj Auto Care")
        self.assertEqual(self.state(rid), ("ASSIGNED", "ASSIGNED", "ASSIGNED"))
        self.assertIsNotNone(fetch_one("SELECT id FROM vehicle_health WHERE vehicle_id = ?", (vehicle_id,)))

        # Provider sees the job (the dashboard used to show none)
        pc = self.provider_client(self.mech_user)
        page = pc.get("/provider").get_data(as_text=True)
        self.assertIn("Engine Overheating", page)
        self.assertIn("On the way", page)
        match_id = fetch_one("SELECT id FROM service_matches WHERE request_id = ?", (rid,))["id"]

        # Invalid jump is rejected with a clear message
        bad = support.post(pc, f"/api/provider/job/{match_id}/status", {"status": "COMPLETED"})
        self.assertEqual(bad.status_code, 409)
        self.assertIn("Allowed next steps", bad.get_json()["message"])

        # ASSIGNED -> ON_THE_WAY works, and is idempotent
        for _ in range(2):
            ok = support.post(pc, f"/api/provider/job/{match_id}/status", {"status": "ON_THE_WAY"})
            self.assertEqual(ok.status_code, 200, ok.get_json())
        self.assertEqual(self.state(rid), ("ON_THE_WAY", "ON_THE_WAY", "ON_THE_WAY"))
        self.assertEqual(len(fetch_all("SELECT id FROM tracking WHERE request_id = ? AND status = 'ON_THE_WAY'", (rid,))), 1)

        # Live location reaches the driver's tracking view
        loc = support.post(pc, "/api/provider/location", {"latitude": "20.30", "longitude": "85.83", "accuracy": "12"})
        self.assertTrue(loc.get_json()["tracking_active"])
        tracking = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertEqual(tracking["request"]["status"], "ON_THE_WAY")
        self.assertEqual(tracking["provider"]["status"], "ON_THE_WAY")
        self.assertAlmostEqual(tracking["provider_location"]["latitude"], 20.30)
        self.assertIsNotNone(tracking["live_distance_km"])
        self.assertNotIn("Unknown", tracking["request"]["incident_label"])
        bad_loc = support.post(pc, "/api/provider/location", {"latitude": "200", "longitude": "85"})
        self.assertEqual(bad_loc.status_code, 400)

        for status in ("ARRIVED", "IN_PROGRESS"):
            self.assertEqual(support.post(pc, f"/api/provider/job/{match_id}/status", {"status": status}).status_code, 200)
        # Location is no longer collected once service has started
        self.assertFalse(support.post(pc, "/api/provider/location", {"latitude": "20.31", "longitude": "85.83"}).get_json()["tracking_active"])
        # Driver can no longer cancel after work started
        self.assertEqual(support.post(self.dc, f"/api/requests/{rid}/cancel").status_code, 409)
        done = support.post(pc, f"/api/provider/job/{match_id}/status", {"status": "COMPLETED", "note": "Replaced radiator hose"})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(self.state(rid), ("COMPLETED", "COMPLETED", "COMPLETED"))
        self.assertEqual(support.post(pc, f"/api/provider/job/{match_id}/status", {"status": "ON_THE_WAY"}).status_code, 409)

        # Feedback, history, notifications, reports
        fb = support.post(self.dc, f"/api/requests/{rid}/feedback", {"rating": "4", "comment": "Quick"})
        self.assertEqual(fb.status_code, 200)
        self.assertEqual(support.post(self.dc, f"/api/requests/{rid}/feedback", {"rating": "5"}).status_code, 409)
        self.assertEqual(fetch_one("SELECT rating FROM providers WHERE id = ?", (self.mech_id,))["rating"], 4.0)
        self.assertIn(f"<td>{rid}</td>", self.dc.get("/history").get_data(as_text=True))
        events = {r["event_type"] for r in fetch_all("SELECT event_type FROM notifications WHERE user_id = ?", (self.driver,))}
        self.assertTrue({"REQUEST_CREATED", "PROVIDER_ASSIGNED", "PROVIDER_ON_THE_WAY", "PROVIDER_ARRIVED",
                         "SERVICE_STARTED", "SERVICE_COMPLETED"} <= events, events)
        report = support.web_client(self.admin).get("/admin/reports").get_data(as_text=True)
        self.assertIn("Raj Auto Care", report)
        self.assertIn("100.0%", report)

    def test_driver_sees_provider_base_location_until_live_location_is_shared(self):
        rid = self.create("my engine is overheating").get_json()["request_id"]
        m = fetch_one("SELECT id, provider_id FROM service_matches WHERE request_id = ?", (rid,))
        user = self.mech_user if m["provider_id"] == self.mech_id else self.tow_user
        view = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertIsNone(view["provider_location"])
        self.assertIsNotNone(view["provider_base_location"])
        self.assertFalse(view["provider_base_location"]["is_live"])
        self.assertIsNotNone(view["base_distance_km"])

        pc = self.provider_client(user)
        support.post(pc, f"/api/provider/job/{m['id']}/status", {"status": "ON_THE_WAY"})
        # A typed-in base location is never shown to the driver as a live position.
        r = support.post(pc, "/api/provider/location", {"latitude": "20.31", "longitude": "85.84", "mode": "base"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["tracking_active"])
        view = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertIsNone(view["provider_location"])
        self.assertAlmostEqual(view["provider_base_location"]["latitude"], 20.31)
        # A live GPS update replaces the base location on the driver's page.
        support.post(pc, "/api/provider/location", {"latitude": "20.305", "longitude": "85.835"})
        view = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertAlmostEqual(view["provider_location"]["latitude"], 20.305)
        self.assertIsNone(view["provider_base_location"])
        self.assertIsNotNone(view["live_distance_km"])

    def _assigned(self, description="my engine is overheating"):
        rid = self.create(description).get_json()["request_id"]
        m = fetch_one("SELECT id, provider_id FROM service_matches WHERE request_id = ?", (rid,))
        user = self.mech_user if m["provider_id"] == self.mech_id else self.tow_user
        return rid, m["id"], self.provider_client(user)

    def test_on_the_way_shares_location_with_driver_immediately(self):
        rid, match_id, pc = self._assigned()
        r = support.post(pc, f"/api/provider/job/{match_id}/status",
                         {"status": "ON_THE_WAY", "latitude": "20.31", "longitude": "85.84", "accuracy": "15"})
        body = r.get_json()
        self.assertEqual(r.status_code, 200, body)
        self.assertTrue(body["location_shared"])
        self.assertNotIn("location_error", body)
        view = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertEqual(view["provider"]["status"], "ON_THE_WAY")
        self.assertAlmostEqual(view["provider_location"]["latitude"], 20.31)
        self.assertFalse(view["provider_location"]["stale"])
        self.assertIsNone(view["provider_base_location"])
        self.assertIsNotNone(view["live_distance_km"])
        # The location breadcrumb does not show up as an extra timeline step.
        self.assertEqual([t["status"] for t in view["tracking"]].count("ON_THE_WAY"), 1)

    def test_status_change_without_location_still_works(self):
        rid, match_id, pc = self._assigned()
        r = support.post(pc, f"/api/provider/job/{match_id}/status", {"status": "ON_THE_WAY"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["location_shared"])
        view = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertEqual(view["provider"]["status"], "ON_THE_WAY")
        self.assertIsNone(view["provider_location"])

    def test_bad_location_never_blocks_the_status_change(self):
        rid, match_id, pc = self._assigned()
        r = support.post(pc, f"/api/provider/job/{match_id}/status",
                         {"status": "ON_THE_WAY", "latitude": "200", "longitude": "85"})
        body = r.get_json()
        self.assertEqual(r.status_code, 200, body)
        self.assertFalse(body["location_shared"])
        self.assertIn("location_error", body)
        self.assertEqual(self.state(rid)[0], "ON_THE_WAY")
        self.assertIsNone(self.dc.get(f"/api/tracking/{rid}").get_json()["provider_location"])

    def test_location_sent_with_start_service_is_not_recorded(self):
        rid, match_id, pc = self._assigned()
        for status in ("ON_THE_WAY", "ARRIVED"):
            support.post(pc, f"/api/provider/job/{match_id}/status", {"status": status})
        r = support.post(pc, f"/api/provider/job/{match_id}/status",
                         {"status": "IN_PROGRESS", "latitude": "20.31", "longitude": "85.84"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["location_shared"])
        self.assertIsNone(fetch_one("SELECT id FROM tracking WHERE request_id = ? AND location_source = 'provider'", (rid,)))

    def test_invalid_manual_base_location_rejected(self):
        pc = self.provider_client(self.mech_user)
        for lat, lon in (("100", "85"), ("abc", "85"), ("20.3", "")):
            r = support.post(pc, "/api/provider/location", {"latitude": lat, "longitude": lon, "mode": "base"})
            self.assertEqual(r.status_code, 400, (lat, lon))

    def test_rejection_reassigns_to_next_provider(self):
        rid = self.create("my engine is overheating").get_json()["request_id"]
        first = fetch_one("SELECT id, provider_id FROM service_matches WHERE request_id = ?", (rid,))
        first_user = self.mech_user if first["provider_id"] == self.mech_id else self.tow_user
        r = support.post(self.provider_client(first_user), f"/api/provider/job/{first['id']}/status",
                         {"status": "REJECTED", "note": "Too far"})
        self.assertEqual(r.status_code, 200)
        matches = fetch_all("SELECT provider_id, status FROM service_matches WHERE request_id = ? ORDER BY id", (rid,))
        self.assertEqual(matches[0]["status"], "REJECTED")
        self.assertEqual(matches[1]["status"], "ASSIGNED")
        self.assertNotEqual(matches[1]["provider_id"], first["provider_id"])
        self.assertEqual(self.state(rid)[0], "ASSIGNED")
        # The rejecting provider can no longer see the driver's request
        self.assertEqual(self.provider_client(first_user).get(f"/api/tracking/{rid}").status_code, 404)

    def test_unable_to_complete_requires_reason_and_reassigns(self):
        rid = self.create("my engine is overheating").get_json()["request_id"]
        m = fetch_one("SELECT id, provider_id FROM service_matches WHERE request_id = ?", (rid,))
        user = self.mech_user if m["provider_id"] == self.mech_id else self.tow_user
        pc = self.provider_client(user)
        support.post(pc, f"/api/provider/job/{m['id']}/status", {"status": "ON_THE_WAY"})
        self.assertEqual(support.post(pc, f"/api/provider/job/{m['id']}/status", {"status": "UNABLE_TO_COMPLETE"}).status_code, 400)
        self.assertEqual(support.post(pc, f"/api/provider/job/{m['id']}/status",
                                      {"status": "UNABLE_TO_COMPLETE", "note": "Needs a flatbed"}).status_code, 200)
        self.assertEqual(len(fetch_all("SELECT id FROM service_matches WHERE request_id = ?", (rid,))), 2)

    def test_last_provider_rejecting_leaves_request_waiting(self):
        rid = self.create("engine overheating").get_json()["request_id"]
        for _ in range(2):
            m = fetch_one("SELECT id, provider_id FROM service_matches WHERE request_id = ? AND status = 'ASSIGNED'", (rid,))
            user = self.mech_user if m["provider_id"] == self.mech_id else self.tow_user
            support.post(self.provider_client(user), f"/api/provider/job/{m['id']}/status", {"status": "REJECTED"})
        self.assertEqual(self.state(rid)[0], "REQUESTED")
        view = self.dc.get(f"/api/tracking/{rid}").get_json()
        self.assertIsNone(view["provider"])
        self.assertTrue(view["actions"]["can_cancel"])

    def test_driver_cancellation_syncs_match_and_notifies_provider(self):
        rid = self.create("flat tyre").get_json()["request_id"]
        m = fetch_one("SELECT id, provider_id FROM service_matches WHERE request_id = ?", (rid,))
        r = support.post(self.dc, f"/api/requests/{rid}/cancel", {"reason": "Fixed it myself"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.state(rid), ("CANCELLED", "CANCELLED", "CANCELLED"))
        provider_user = fetch_one("SELECT user_id FROM providers WHERE id = ?", (m["provider_id"],))["user_id"]
        self.assertIsNotNone(fetch_one("SELECT id FROM notifications WHERE user_id = ? AND event_type = 'JOB_CANCELLED'",
                                       (provider_user,)))
        again = support.post(self.dc, f"/api/requests/{rid}/cancel")
        self.assertEqual(again.status_code, 200)  # idempotent
        late = support.post(self.provider_client(provider_user), f"/api/provider/job/{m['id']}/status", {"status": "ON_THE_WAY"})
        self.assertEqual(late.status_code, 409)

    def test_admin_controlled_reassignment(self):
        rid = self.create("engine overheating").get_json()["request_id"]
        current = fetch_one("SELECT provider_id FROM service_matches WHERE request_id = ?", (rid,))["provider_id"]
        target = self.tow_id if current == self.mech_id else self.mech_id
        ac = support.web_client(self.admin)
        # Reason is mandatory
        support.post(ac, f"/admin/requests/{rid}/reassign", {"provider_id": target, "reason": ""})
        self.assertEqual(len(fetch_all("SELECT id FROM service_matches WHERE request_id = ?", (rid,))), 1)
        support.post(ac, f"/admin/requests/{rid}/reassign", {"provider_id": target, "reason": "Provider not answering"})
        matches = fetch_all("SELECT provider_id, status FROM service_matches WHERE request_id = ? ORDER BY id", (rid,))
        self.assertEqual([m["status"] for m in matches], ["REASSIGNED", "ASSIGNED"])
        self.assertEqual(matches[1]["provider_id"], target)
        audit = fetch_one("SELECT action, metadata FROM audit_log WHERE action = 'request.reassign'")
        self.assertIn("Provider not answering", audit["metadata"])

    def test_ineligible_admin_target_changes_nothing(self):
        rid = self.create("engine overheating").get_json()["request_id"]
        offline_id, _ = support.make_provider("Offline Mech", "Mechanic", availability="offline")
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.admin_reassign(rid, self.admin, offline_id, "testing")
        self.assertEqual([m["status"] for m in fetch_all("SELECT status FROM service_matches WHERE request_id = ?", (rid,))],
                         ["ASSIGNED"])

    def test_provider_unavailable_receives_no_jobs_and_retry_assigns_later(self):
        for pid in (self.mech_id, self.tow_id):
            support.post(self.provider_client(self.mech_user if pid == self.mech_id else self.tow_user),
                         "/api/provider/availability", {"availability": "offline"})
        body = self.create("engine overheating").get_json()
        self.assertIsNone(body["provider"])
        self.assertEqual(self.state(body["request_id"])[0], "REQUESTED")
        support.post(self.provider_client(self.mech_user), "/api/provider/availability", {"availability": "available"})
        self.assertEqual(self.state(body["request_id"])[0], "ASSIGNED")

    def test_deactivating_provider_releases_their_job(self):
        rid = self.create("engine overheating").get_json()["request_id"]
        m = fetch_one("SELECT provider_id FROM service_matches WHERE request_id = ?", (rid,))
        user = self.mech_user if m["provider_id"] == self.mech_id else self.tow_user
        support.post(support.web_client(self.admin), f"/admin/users/{user}/status", {"active": "0"})
        statuses = [r["status"] for r in fetch_all("SELECT status FROM service_matches WHERE request_id = ? ORDER BY id", (rid,))]
        self.assertEqual(statuses, ["REASSIGNED", "ASSIGNED"])

    def test_repeated_create_is_blocked_while_one_is_open(self):
        first = self.create("flat tyre")
        second = self.create("flat tyre")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("redirect", second.get_json())
        self.assertEqual(fetch_one("SELECT COUNT(*) AS c FROM assistance_requests")["c"], 1)

    def test_accident_and_fuel_reports_no_longer_crash(self):
        accident = self.create("I had an accident, a truck hit my car")
        self.assertEqual(accident.status_code, 200)
        self.assertEqual(accident.get_json()["provider"]["business_name"], "24x7 Recovery")
        support.post(self.dc, f"/api/requests/{accident.get_json()['request_id']}/cancel")
        fuel = self.create("ran out of petrol")
        self.assertEqual(fuel.status_code, 200)
        self.assertIsNone(fuel.get_json()["provider"])

    def test_tracking_page_escapes_provider_names(self):
        support.fresh_database()
        driver = support.make_user("D", "d2@example.test")
        support.make_provider('<img src=x onerror=alert(1)>', "Mechanic", email="xss@example.test")
        client = support.web_client(driver)
        rid = support.post(client, "/api/assistance/create", {"description": "engine overheating", **BBSR}).get_json()["request_id"]
        html = client.get(f"/tracking/{rid}").get_data(as_text=True)
        self.assertNotIn("<img src=x onerror", html)
        self.assertIn("RSA.esc(p.business_name)", html)


if __name__ == "__main__":
    unittest.main()
