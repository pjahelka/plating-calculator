"""Run: python -m unittest"""
import unittest

import plating

NICKEL = next(m for m in plating.METALS if m.ion == "Ni²⁺")
SILVER = next(m for m in plating.METALS if m.ion == "Ag⁺")


class FaradayTests(unittest.TestCase):
    def test_nickel_hand_calculation(self):
        # 10 µm Ni on 1 cm² at 10 mA/cm², 100 %: 8.908e-3 g / 58.6934 * 2 * F = 29.29 C -> 2929 s
        r = plating.solve(NICKEL, 1.0, 10.0, 1.0, thickness=10.0)
        self.assertAlmostEqual(r.time, 2928.7, delta=1.0)
        self.assertAlmostEqual(r.current, 0.010)
        self.assertAlmostEqual(r.mass, 8.908e-3)
        # Rule of thumb: Ni at 1 A/dm² deposits ~12.3 µm/h
        self.assertAlmostEqual(r.rate * 3600, 12.29, delta=0.05)

    def test_silver_rule_of_thumb(self):
        # Ag at 1 A/dm² deposits ~38.3 µm/h
        rate = plating.deposition_rate(SILVER, 10.0, 1.0)
        self.assertAlmostEqual(rate * 3600, 38.35, delta=0.1)

    def test_time_and_thickness_round_trip(self):
        forward = plating.solve(NICKEL, 25.0, 20.0, 0.9, thickness=7.5)
        back = plating.solve(NICKEL, 25.0, 20.0, 0.9, time=forward.time)
        self.assertAlmostEqual(back.thickness, 7.5)

    def test_efficiency_scales_time(self):
        full = plating.solve(NICKEL, 1.0, 10.0, 1.0, thickness=10.0)
        half = plating.solve(NICKEL, 1.0, 10.0, 0.5, thickness=10.0)
        self.assertAlmostEqual(half.time, 2 * full.time)
        self.assertAlmostEqual(half.mass, full.mass)

    def test_area_does_not_change_time(self):
        small = plating.solve(NICKEL, 1.0, 10.0, 1.0, thickness=10.0)
        large = plating.solve(NICKEL, 100.0, 10.0, 1.0, thickness=10.0)
        self.assertAlmostEqual(small.time, large.time)
        self.assertAlmostEqual(large.current, 100 * small.current)

    def test_unit_factors(self):
        self.assertAlmostEqual(plating.CURRENT_DENSITY_UNITS["A/ft²"], 1.07639, places=5)
        self.assertAlmostEqual(plating.CURRENT_DENSITY_UNITS["A/dm²"], 10.0)
        self.assertAlmostEqual(plating.THICKNESS_UNITS["mil"], 25.4)
        self.assertAlmostEqual(plating.AREA_UNITS["in²"], 6.4516)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            plating.solve(NICKEL, 0.0, 10.0, 1.0, thickness=10.0)
        with self.assertRaises(ValueError):
            plating.solve(NICKEL, 1.0, 10.0, 1.5, thickness=10.0)
        with self.assertRaises(ValueError):
            plating.solve(NICKEL, 1.0, 10.0, 1.0)
        with self.assertRaises(ValueError):
            plating.solve(NICKEL, 1.0, 10.0, 1.0, thickness=10.0, time=60.0)


if __name__ == "__main__":
    unittest.main()
