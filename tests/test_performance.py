import math
import unittest

from flightlab import Aircraft, ParabolicPolar, level_flight
from flightlab.performance import GRAVITY_M_S2


class LevelFlightTests(unittest.TestCase):
    def setUp(self):
        # Synthetic fixtures only; these do not represent the user's aircraft.
        self.aircraft = Aircraft(mass_kg=10, reference_area_m2=1)
        self.polar = ParabolicPolar(0.03, 0.05, -0.5, 1.5)

    def test_lift_balances_weight_and_drag_matches_lift_to_drag_ratio(self):
        result = level_flight(self.aircraft, self.polar, 20, 1.225)
        self.assertAlmostEqual(result.cl * 245, 10 * GRAVITY_M_S2)
        self.assertAlmostEqual(result.drag_n, 10 * GRAVITY_M_S2 / (result.cl / result.cd))
        self.assertAlmostEqual(result.useful_power_w, result.drag_n * 20)

    def test_analytical_minimum_drag_condition(self):
        optimum_cl = math.sqrt(self.polar.cd0 / self.polar.induced_drag_factor)
        speed = math.sqrt(2 * 10 * GRAVITY_M_S2 / (1.225 * optimum_cl))
        optimum = level_flight(self.aircraft, self.polar, speed, 1.225)
        for factor in (0.9, 1.1):
            self.assertLess(optimum.drag_n, level_flight(self.aircraft, self.polar, speed * factor, 1.225).drag_n)

    def test_outside_polar_is_rejected(self):
        with self.assertRaises(ValueError):
            level_flight(self.aircraft, self.polar, 2, 1.225)

    def test_invalid_inputs_are_rejected(self):
        for invalid in (0, -1, float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    level_flight(self.aircraft, self.polar, invalid, 1.225)
                with self.assertRaises(ValueError):
                    Aircraft(invalid, 1)


if __name__ == "__main__":
    unittest.main()
