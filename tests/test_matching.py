"""Assistance engine / provider matching against a real (temporary) database."""
import unittest

from tests import support
from assistance import lifecycle
from database.database import execute_query, fetch_all, fetch_one
from provider.provider import find_provider, rank_providers


BBSR = (20.2961, 85.8245)


class MatchingTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()

    def ids(self, ranking):
        return [c["provider"]["id"] for c in ranking["candidates"]]

    def test_correct_specialist_selected(self):
        tyre, _ = support.make_provider("Tyre Pro", "Tyre Service", 20.30, 85.83, 4.0)
        mech, _ = support.make_provider("Mech", "Mechanic", 20.2961, 85.8245, 5.0)
        best, distance = find_provider("tyre_assistance", *BBSR)
        self.assertEqual(best["id"], tyre)
        self.assertIsNotNone(distance)
        self.assertIn(mech, self.ids(rank_providers("tyre_assistance", *BBSR)))  # capable fallback, ranked lower

    def test_incompatible_provider_rejected(self):
        support.make_provider("Battery Only", "Battery Assistance")
        ranking = rank_providers("tyre_assistance", *BBSR)
        self.assertEqual(ranking["candidates"], [])
        self.assertTrue(any("not suitable" in e["reason"] for e in ranking["excluded"]))

    def test_brake_failure_never_goes_to_tyre_or_battery_specialist(self):
        support.make_provider("Tyre Pro", "Tyre Service", rating=5.0)
        support.make_provider("Battery Pro", "Battery Assistance", rating=5.0)
        self.assertIsNone(find_provider("emergency_roadside_assistance", *BBSR))
        tow, _ = support.make_provider("Tow", "Towing / Recovery", rating=3.0)
        self.assertEqual(find_provider("emergency_roadside_assistance", *BBSR)[0]["id"], tow)

    def test_services_that_used_to_crash_return_none(self):
        support.make_provider("Mech", "Mechanic")
        for service in ("emergency_services", "fuel_delivery", "Emergency Services", "Fuel Delivery"):
            self.assertIsNone(find_provider(service, *BBSR), service)

    def test_unavailable_unverified_unlinked_inactive_and_busy_are_excluded(self):
        support.make_provider("Offline", "Mechanic", availability="offline")
        support.make_provider("Pending", "Mechanic", verification="pending")
        support.make_provider("NoLogin", "Mechanic", linked=False)
        _, inactive_user = support.make_provider("Inactive", "Mechanic")
        execute_query("UPDATE users SET is_active = 0 WHERE id = ?", (inactive_user,))
        busy, _ = support.make_provider("Busy", "Mechanic")
        driver = support.make_user("D", "d@example.test")
        req = execute_query(
            "INSERT INTO assistance_requests (user_id, incident_type, priority, recommended_service, status) "
            "VALUES (?, 'engine_failure', 'URGENT', 'mechanic_or_roadside_assistance', 'ASSIGNED')", (driver,))
        execute_query("INSERT INTO service_matches (request_id, provider_id, status) VALUES (?, ?, 'ON_THE_WAY')",
                      (req, busy))
        ranking = rank_providers("mechanic_or_roadside_assistance", *BBSR)
        self.assertEqual(ranking["candidates"], [])
        reasons = " | ".join(e["reason"] for e in ranking["excluded"])
        for expected in ("verification", "no linked provider login", "deactivated", "active job"):
            self.assertIn(expected, reasons)
        self.assertNotIn("Offline", [e["business_name"] for e in ranking["excluded"]])  # not even a candidate

    def test_missing_coordinates_handled(self):
        far, _ = support.make_provider("Known", "Mechanic", 20.40, 85.90, 4.0)
        unknown, _ = support.make_provider("Unknown loc", "Mechanic", None, None, 5.0)
        ranking = rank_providers("mechanic_or_roadside_assistance", *BBSR)
        by_id = {c["provider"]["id"]: c for c in ranking["candidates"]}
        self.assertIsNone(by_id[unknown]["distance_km"])
        self.assertEqual(by_id[unknown]["breakdown"]["distance_note"], "provider location unknown")
        self.assertEqual(self.ids(ranking)[0], far, "a provider with known nearby location ranks first")
        # Request without a location: still matchable, distance never invented.
        ranking = rank_providers("mechanic_or_roadside_assistance", None, None)
        self.assertTrue(all(c["distance_km"] is None for c in ranking["candidates"]))

    def test_outside_radius_excluded(self):
        support.make_provider("Far away", "Mechanic", 28.61, 77.20)  # Delhi
        ranking = rank_providers("mechanic_or_roadside_assistance", *BBSR)
        self.assertEqual(ranking["candidates"], [])
        self.assertIn("outside service radius", ranking["excluded"][0]["reason"])

    def test_emergency_weights_distance_more(self):
        near, _ = support.make_provider("Near unrated", "Mechanic", 20.2965, 85.8250, 0)
        far, _ = support.make_provider("Far top rated", "Mechanic", 20.55, 85.95, 5.0)
        normal = rank_providers("mechanic_or_roadside_assistance", *BBSR, priority="NORMAL")
        emergency = rank_providers("mechanic_or_roadside_assistance", *BBSR, priority="EMERGENCY")
        self.assertEqual(emergency["candidates"][0]["provider"]["id"], near)
        gap_normal = normal["candidates"][0]["score"] - normal["candidates"][1]["score"]
        gap_emergency = emergency["candidates"][0]["score"] - emergency["candidates"][1]["score"]
        self.assertGreater(gap_emergency, gap_normal)

    def test_ranking_is_deterministic(self):
        a, _ = support.make_provider("A", "Mechanic", *BBSR, 4.0)
        b, _ = support.make_provider("B", "Mechanic", *BBSR, 4.0)
        first = self.ids(rank_providers("mechanic_or_roadside_assistance", *BBSR))
        self.assertEqual(first, sorted([a, b]))
        self.assertEqual(first, self.ids(rank_providers("mechanic_or_roadside_assistance", *BBSR)))


class AssignmentTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()
        self.engines = support.engines()
        self.driver = support.make_user("Driver", "driver@example.test")

    def create(self, text="engine is overheating", lat=BBSR[0], lon=BBSR[1], user=None):
        return lifecycle.create_request(user or self.driver, text, None, lat, lon, **self.engines)

    def test_no_eligible_provider_keeps_request_open(self):
        result = self.create("ran out of petrol")
        self.assertFalse(result["assignment"]["assigned"])
        row = fetch_one("SELECT status FROM assistance_requests WHERE id = ?", (result["request_id"],))
        self.assertEqual(row["status"], "REQUESTED")
        self.assertEqual(fetch_all("SELECT * FROM service_matches WHERE request_id = ?", (result["request_id"],)), [])

    def test_assignment_records_score_distance_details_and_tracking(self):
        pid, _ = support.make_provider("Mech", "Mechanic")
        result = self.create()
        a = result["assignment"]
        self.assertTrue(a["assigned"])
        match = fetch_one("SELECT * FROM service_matches WHERE id = ?", (a["match_id"],))
        self.assertEqual(match["provider_id"], pid)
        self.assertEqual(match["status"], "ASSIGNED")
        self.assertIsNotNone(match["match_details"])
        self.assertIsNotNone(match["updated_at"])
        req = fetch_one("SELECT status FROM assistance_requests WHERE id = ?", (result["request_id"],))
        self.assertEqual(req["status"], "ASSIGNED")
        statuses = [r["status"] for r in fetch_all("SELECT status FROM tracking WHERE request_id = ? ORDER BY id",
                                                   (result["request_id"],))]
        self.assertEqual(statuses, ["REQUESTED", "ASSIGNED"])

    def test_duplicate_assignment_prevented(self):
        support.make_provider("Mech 1", "Mechanic")
        support.make_provider("Mech 2", "Mechanic")
        result = self.create()
        again = lifecycle.assign_best_provider(result["request_id"])
        self.assertTrue(again["already_assigned"])
        self.assertEqual(len(fetch_all("SELECT * FROM service_matches WHERE request_id = ?", (result["request_id"],))), 1)
        # Even a direct insert of a second active match is rejected by the database.
        with self.assertRaises(Exception):
            execute_query("INSERT INTO service_matches (request_id, provider_id, status) VALUES (?, ?, 'ASSIGNED')",
                          (result["request_id"], again["provider_id"]))

    def test_one_provider_is_not_given_two_jobs(self):
        support.make_provider("Only mech", "Mechanic")
        first = self.create()
        other_driver = support.make_user("Other", "other@example.test")
        second = self.create(user=other_driver)
        self.assertTrue(first["assignment"]["assigned"])
        self.assertFalse(second["assignment"]["assigned"])

    def test_waiting_emergency_is_assigned_first_when_provider_frees_up(self):
        pid, puser = support.make_provider("Only mech", "Mechanic")
        first = self.create()  # takes the only provider
        d2 = support.make_user("Normal", "normal@example.test")
        d3 = support.make_user("Emergency", "em@example.test")
        normal = lifecycle.create_request(d2, "engine stopped", None, *BBSR, **self.engines)
        emergency = lifecycle.create_request(d3, "smoke is coming from my engine", None, *BBSR, **self.engines)
        for status in ("ON_THE_WAY", "ARRIVED", "IN_PROGRESS", "COMPLETED"):
            lifecycle.transition_match(first["assignment"]["match_id"], status, provider_user_id=puser)
        self.assertEqual(fetch_one("SELECT status FROM assistance_requests WHERE id = ?",
                                   (emergency["request_id"],))["status"], "ASSIGNED")
        self.assertEqual(fetch_one("SELECT status FROM assistance_requests WHERE id = ?",
                                   (normal["request_id"],))["status"], "REQUESTED")


if __name__ == "__main__":
    unittest.main()
