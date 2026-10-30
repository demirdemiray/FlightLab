from pathlib import Path
import unittest

from flightlab.catalog import load_catalog
from flightlab.mission import FlightConditions, level_flight_at_fuel


class DragFactorTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(Path(__file__).resolve().parents[1] / "data/catalog.json")
        self.config = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n")

    def evaluate(self, config):
        return level_flight_at_fuel(config.aircraft.fuel_plan(12, 2), 12,
                                   area_m2=0.3208322, speed_m_s=90, conditions=FlightConditions(),
                                   limits=config.aircraft.limits, polar=config.aerodynamic_model())

    def test_drag_and_power_scale_while_lift_and_raw_data_stay_fixed(self):
        baseline = self.evaluate(self.config)
        self.assertEqual(self.config.drag_factor, 1)
        for factor in (0.5, 1, 2, 3):
            config = self.catalog.select(self.config.aircraft.id, self.config.engine.id, drag_factor=factor)
            result = self.evaluate(config)
            self.assertEqual(result.cl, baseline.cl)
            self.assertAlmostEqual(result.cd, baseline.cd * factor)
            self.assertAlmostEqual(result.drag_n, baseline.drag_n * factor)
            self.assertAlmostEqual(result.useful_power_w, baseline.useful_power_w * factor)
            # New selection must not multiply the previous selection or source data.
            self.assertEqual(self.evaluate(self.config), baseline)

    def test_bounds_and_no_polar_extrapolation(self):
        for factor in (0.499, 3.001, float("nan"), float("inf"), True):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                self.catalog.select(self.config.aircraft.id, self.config.engine.id, drag_factor=factor)
        config = self.catalog.select(self.config.aircraft.id, self.config.engine.id, drag_factor=0.5)
        with self.assertRaises(ValueError):
            config.aerodynamic_model().drag_coefficient(0.9)

    def test_drag_and_thrust_settings_are_independent(self):
        config = self.catalog.select(self.config.aircraft.id, self.config.engine.id,
                                     drag_factor=3, thrust_factor=0.6)
        self.assertAlmostEqual(self.evaluate(config).drag_n, self.evaluate(self.config).drag_n * 3)
        base = self.config.jet_model().at_krpm(71.1)
        changed = config.jet_model().at_krpm(71.1)
        self.assertAlmostEqual(changed.thrust_n, base.thrust_n * 0.6)
        self.assertEqual(changed.fuel_flow_kg_s, base.fuel_flow_kg_s)

    def test_mach_threshold_warns_without_rejecting_points(self):
        limits = self.config.aircraft.limits
        self.assertEqual(limits.trusted_aerodynamic_mach, 0.65)
        standard = FlightConditions().atmosphere()
        cold = FlightConditions(7000, -30).atmosphere()
        for atmosphere in (standard, cold):
            speed = 0.65 * atmosphere.speed_of_sound_m_s
            limits.check_level_flight(32.1, 0.3208322, speed, atmosphere)
            self.assertEqual(limits.aerodynamic_warnings(speed, atmosphere), ())
            limits.check_level_flight(32.1, 0.3208322, speed + 0.01, atmosphere)
            self.assertTrue(limits.aerodynamic_warnings(speed + 0.01, atmosphere))

    def test_high_mach_level_flight_returns_result_with_warning(self):
        config = self.config
        result = level_flight_at_fuel(config.aircraft.fuel_plan(12, 2), 12,
                                      area_m2=0.3208322, speed_m_s=250, conditions=FlightConditions(),
                                      limits=config.aircraft.limits, polar=config.aerodynamic_model())
        self.assertGreater(result.mach, 0.65)
        self.assertGreater(result.drag_n, 0)
        self.assertTrue(any("Flight Mach" in warning for warning in result.warnings))
        self.assertTrue(any("Source polar" in warning for warning in result.warnings))
