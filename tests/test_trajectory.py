from dataclasses import dataclass
from math import cos, log, radians, sin, sqrt
import unittest

from flightlab.dataset import AeroReference
from flightlab.interpolation import AeroCoefficients
from flightlab.mission import FlightLimits, FuelPlan
from flightlab.models import EngineResult
from flightlab.trajectory import ControlSegment, FlightState, simulate


class ZeroDragAero:
    def at_flight(self, cl, speed_m_s, conditions):
        return AeroCoefficients(cl, 0, 0, 0)


@dataclass
class ConstantEngine:
    thrust: float = 0
    flow: float = 0.1
    rpm_bounds = (0, 100)

    @property
    def max_fuel_flow_kg_s(self):
        return self.flow

    def at_flight(self, krpm, speed_m_s, conditions):
        return EngineResult(self.thrust, self.flow)


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.initial = FlightState(0, 0, 1000, 100, 0, 5)
        self.args = dict(fuel_plan=FuelPlan(20, 5, 1), limits=FlightLimits(2, 1000, max_load_factor=11),
                         reference=AeroReference(1, 0.5), aero=ZeroDragAero(), engine=ConstantEngine())

    def test_constant_velocity_burn_stops_at_reserve_with_correct_weight(self):
        result = simulate(self.initial, [ControlSegment(60, 50, 1)], step_s=7, **self.args)
        self.assertEqual(result.termination, "fuel_reserve")
        final = result.states[-1]
        self.assertAlmostEqual(final.time_s, 40)
        self.assertAlmostEqual(final.fuel_kg, 1)
        self.assertAlmostEqual(final.distance_m, 4000)
        self.assertAlmostEqual(final.speed_m_s, 100)
        self.assertAlmostEqual(final.altitude_m, 1000)

    def test_arrival_event_between_steps_is_located_and_not_called_parachute(self):
        result = simulate(self.initial, [ControlSegment(60, 50, 1)], step_s=7,
                          target_distance_m=3050, **self.args)
        self.assertEqual(result.termination, "distance_target")
        self.assertAlmostEqual(result.states[-1].time_s, 30.5, places=7)
        self.assertAlmostEqual(result.states[-1].distance_m, 3050, places=6)
        self.assertAlmostEqual(result.states[-1].fuel_kg, 1.95, places=7)

    def test_acceleration_uses_decreasing_mass(self):
        self.args["engine"] = ConstantEngine(thrust=100, flow=0.1)
        result = simulate(self.initial, [ControlSegment(10, 50, 1)], step_s=0.5, **self.args)
        expected_speed = 100 + 100/0.1*log(25/24)
        expected_distance = 100*10 + 100/0.1*(10-24/0.1*log(25/24))
        self.assertEqual(result.termination, "controls_completed")
        self.assertAlmostEqual(result.states[-1].speed_m_s, expected_speed, places=7)
        self.assertAlmostEqual(result.states[-1].distance_m, expected_distance, places=5)

    def test_ballistic_trajectory_matches_projectile_and_conserves_energy(self):
        self.args["engine"] = ConstantEngine(thrust=0, flow=0)
        initial = FlightState(0, 0, 1000, 100, 10, 5)
        result = simulate(initial, [ControlSegment(5, 0, 0)], step_s=0.25, **self.args)
        final = result.states[-1]
        expected_x = 100*cos(radians(10))*5
        expected_h = 1000+100*sin(radians(10))*5-0.5*9.80665*5**2
        expected_v = sqrt((100*cos(radians(10)))**2+(100*sin(radians(10))-9.80665*5)**2)
        self.assertAlmostEqual(final.distance_m, expected_x, places=4)
        self.assertAlmostEqual(final.altitude_m, expected_h, places=4)
        self.assertAlmostEqual(final.speed_m_s, expected_v, places=5)
        initial_energy = 100**2/2+9.80665*1000
        self.assertAlmostEqual(final.speed_m_s**2/2+9.80665*final.altitude_m, initial_energy, places=3)

    def test_violation_is_reported_as_failed_not_completed(self):
        result = simulate(self.initial, [ControlSegment(1, 50, 12)], **self.args)
        self.assertEqual(result.termination, "model_or_envelope_failure")
        self.assertIn("load factor", result.failure_reason)
        self.assertEqual(len(result.states), 1)

    def test_bad_fuel_bound_cannot_silently_overshoot_reserve(self):
        class IncorrectBound(ConstantEngine):
            @property
            def max_fuel_flow_kg_s(self): return 0.01
        self.args["engine"] = IncorrectBound(flow=0.1)
        result = simulate(self.initial, [ControlSegment(1, 50, 1)], **self.args)
        self.assertEqual(result.termination, "model_or_envelope_failure")
        self.assertIn("fuel-flow bound", result.failure_reason)
