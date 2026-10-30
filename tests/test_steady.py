from math import sqrt
import unittest

from flightlab.dataset import AeroReference
from flightlab.interpolation import AeroCoefficients
from flightlab.mission import FlightConditions, FlightLimits
from flightlab.models import EngineResult
from flightlab.steady import level_point, search_level_speed


class AnalyticAero:
    def at_flight(self, cl, speed_m_s, conditions):
        return AeroCoefficients(cl, 0.02+0.05*cl**2, 0, 0)


class LinearFuelEngine:
    rpm_bounds = (1, 10)
    max_fuel_flow_kg_s = 0.1

    def at_flight(self, krpm, speed_m_s, conditions):
        if not self.rpm_bounds[0] <= krpm <= self.rpm_bounds[1]:
            raise ValueError("RPM out of bounds")
        thrust = krpm*10
        return EngineResult(thrust, thrust*0.001)

    def krpm_for_thrust(self, thrust_n, speed_m_s, conditions):
        krpm = thrust_n/10
        self.at_flight(krpm, speed_m_s, conditions)
        return krpm


class SteadyTests(unittest.TestCase):
    def setUp(self):
        self.args = dict(mass_kg=100, conditions=FlightConditions(), limits=FlightLimits(1.5, 130),
                         reference=AeroReference(1, 0.5), aero=AnalyticAero(), engine=LinearFuelEngine())
        rho = self.args["conditions"].atmosphere().density_kg_m3
        self.a = 0.5*rho*0.02
        self.b = 0.05*(100*9.80665)**2/(0.5*rho)

    def test_steady_thrust_balance_and_specific_range(self):
        point = level_point(speed_m_s=60, **self.args)
        self.assertAlmostEqual(point.drag_n, self.a*60**2+self.b/60**2)
        self.assertAlmostEqual(point.krpm*10, point.drag_n)
        self.assertAlmostEqual(point.specific_range_m_kg, 60/point.fuel_flow_kg_s)

    def test_minimum_fuel_and_maximum_specific_range_match_closed_form(self):
        for objective, expected in (("minimum_fuel_flow", (self.b/self.a)**0.25),
                                    ("maximum_specific_range", (3*self.b/self.a)**0.25)):
            with self.subTest(objective=objective):
                result = search_level_speed(objective=objective, speed_bounds=(30, 120), **self.args)
                self.assertAlmostEqual(result.point.speed_m_s, expected, delta=0.005)

    def test_max_speed_respects_available_thrust_not_only_search_bound(self):
        expected = sqrt((100+sqrt(100**2-4*self.a*self.b))/(2*self.a))
        result = search_level_speed(objective="maximum_speed", speed_bounds=(30, 120), **self.args)
        self.assertAlmostEqual(result.point.speed_m_s, expected, delta=0.001)
        self.assertAlmostEqual(result.point.drag_n, 100, delta=1e-4)

    def test_no_feasible_points_is_not_a_success(self):
        with self.assertRaisesRegex(ValueError, "No feasible"):
            search_level_speed(objective="maximum_speed", speed_bounds=(110, 120), **self.args)
