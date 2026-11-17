"""Regression tests for the provider data-access and matching module."""
import unittest
from unittest.mock import patch

import provider
from provider import provider as provider_module


class ProviderModuleTests(unittest.TestCase):
    def test_package_exports_resolve(self):
        for name in (
            "get_provider_by_id", "get_provider_by_user_id", "get_all_providers",
            "get_available_providers", "create_provider", "update_provider",
            "update_availability", "update_rating", "delete_provider",
        ):
            self.assertTrue(callable(getattr(provider, name)), name)

    def test_normalize_service_aliases(self):
        self.assertEqual(provider_module.normalize_service("Tire Service"), "tyre")
        self.assertEqual(provider_module.normalize_service("Emergency Recovery"), "recovery")
        self.assertEqual(provider_module.normalize_service("Battery Assistance"), "battery")

    def test_haversine_distance(self):
        distance = provider_module.haversine(0, 0, 0, 1)
        self.assertIsNotNone(distance)
        self.assertAlmostEqual(distance, 111.19, delta=0.2)
        self.assertIsNone(provider_module.haversine(None, 0, 0, 0))
        self.assertIsNone(provider_module.haversine(100, 0, 0, 0))

    def test_matching_prefers_compatible_provider(self):
        rows = [
            {"id": 1, "business_name": "Wrong specialty", "service_type": "battery", "availability": "available", "rating": 5, "latitude": 20.2961, "longitude": 85.8245},
            {"id": 2, "business_name": "Tyre specialist", "service_type": "tyre service", "availability": "available", "rating": 4.4, "latitude": 20.3000, "longitude": 85.8250},
        ]
        with patch.object(provider_module, "get_available_providers", return_value=rows):
            result = provider_module.find_provider("tyre puncture", 20.2961, 85.8245)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["id"], 2)
        self.assertIsNotNone(result[1])

    def test_no_compatible_provider_returns_none(self):
        rows = [{"id": 1, "service_type": "battery", "availability": "available", "rating": 5, "latitude": 20.2961, "longitude": 85.8245}]
        with patch.object(provider_module, "get_available_providers", return_value=rows):
            self.assertIsNone(provider_module.find_provider("tyre", 20.2961, 85.8245))


if __name__ == "__main__":
    unittest.main()
