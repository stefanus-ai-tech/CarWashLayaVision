import unittest

from carwash.core import crossed, tariff_class, format_time
from carwash.pipeline import scaled_dimensions


class CoreTest(unittest.TestCase):
    def test_crossing_direction_and_first_observation(self):
        self.assertFalse(crossed(None, 40, 50, "up"))
        self.assertTrue(crossed(60, 40, 50, "up"))
        self.assertFalse(crossed(40, 60, 50, "up"))
        self.assertTrue(crossed(40, 60, 50, "down"))

    def test_tariff_rules(self):
        self.assertEqual(tariff_class("motorcycle", "small", False), "MOTORCYCLE")
        self.assertEqual(tariff_class("SUV", "large", False), "LARGE")
        self.assertEqual(tariff_class("pickup", "medium", False), "COMMERCIAL")
        self.assertEqual(tariff_class("other", "", False), "REVIEW")

    def test_time(self):
        self.assertEqual(format_time(221.52), "00:03:41.520")

    def test_resolution_adapts_without_stretching(self):
        self.assertEqual(scaled_dimensions(2160, 3840), (720, 1280))
        self.assertEqual(scaled_dimensions(3840, 2160), (1280, 720))
        self.assertEqual(scaled_dimensions(1080, 1920), (720, 1280))


if __name__ == "__main__":
    unittest.main()
