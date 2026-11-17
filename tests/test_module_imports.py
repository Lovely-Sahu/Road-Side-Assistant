"""Smoke tests for the established RSA modules."""
import importlib
import unittest


MODULES = [
    "app", "ai", "ai.decision_engine", "ai.diagnosis", "ai.incident_analyzer",
    "ai.safety_risk", "ai.severity", "ai.vehicle_health", "ai.vision",
    "assistance", "assistance.matching", "assistance.requests", "assistance.resolution",
    "assistance.tracking", "authentication", "authentication.auth", "authentication.security",
    "database", "database.models", "driver", "driver.dashboard", "driver.emergency",
    "driver.history", "driver.report_problem", "driver.vehicle", "provider",
    "provider.dashboard", "provider.jobs", "provider.profile", "provider.requests",
    "admin", "admin.analytics", "admin.dashboard", "admin.providers", "admin.users", "vehicle",
]


class ModuleImportTests(unittest.TestCase):
    def test_existing_modules_import(self):
        failures = []
        for module in MODULES:
            try:
                importlib.import_module(module)
            except Exception as exc:  # surfaced as one useful assertion
                failures.append(f"{module}: {type(exc).__name__}: {exc}")
        self.assertEqual(failures, [], "Module import failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
