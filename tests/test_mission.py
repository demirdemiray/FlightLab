from dataclasses import replace
from math import log
from pathlib import Path
import unittest

from flightlab.catalog import load_catalog
from flightlab.mission import (FlightConditions, FuelPlan, integrate_fuel_until_reserve,
                               level_flight_at_fuel)
from flightlab.performance import ParabolicPolar


class MissionTests(unittest.TestCase):
    def setUp(self):
        catalog = load_catalog(Path(__file__).resolve().parents[1] / "data/catalog.json")
        self.aircraft = catalog.aircraft["m600-thinsurf-acilar"]

    def test_sea_level_standard_atmosphere(self):
        atmosphere = FlightConditions().atmosphere()
        self.assertEqual(atmosphere.temperature_k, 288.15)
        self.assertEqual(atmosphere.pressure_pa, 101325)
        self.assertAlmostEqual(atmosphere.density_kg_m3, 1.225, places=5)
        self.assertAlmostEqual(atmosphere.speed_of_sound_m_s, 340.294, places=3)

    def test_altitude_and_local_temperature_independent_inputs(self):
        standard = FlightConditions(10000).atmosphere()
        self.assertAlmostEqual(standard.temperature_k, 223.15)
        self.assertAlmostEqual(standard.pressure_pa, 26436.24, places=1)
        warm = FlightConditions(10000, 0).atmosphere()
        self.assertEqual(standard.pressure_pa, warm.pressure_pa)
        self.assertLess(warm.density_kg_m3, standard.density_kg_m3)

    def test_temperature_offset_matches_actual_temperature_and_disallows_ambiguity(self):
        offset = FlightConditions(7000, temperature_offset_c=-45).atmosphere()
        actual = FlightConditions(7000, temperature_c=-75.5).atmosphere()
        self.assertAlmostEqual(offset.temperature_k, actual.temperature_k)
        self.assertAlmostEqual(offset.density_kg_m3, 0.723716, places=5)
        with self.assertRaises(ValueError):
            FlightConditions(7000, temperature_c=-30, temperature_offset_c=-45)
        with self.assertRaises(ValueError):
            FlightConditions(7000, temperature_offset_c=-300)

    def test_loading_substitutes_reference_fuel_without_double_counting(self):
        self.assertAlmostEqual(self.aircraft.fuel_plan(12, 2).initial_mass_kg, 32.1)
        plan = self.aircraft.fuel_plan(6, 1)
        self.assertAlmostEqual(plan.initial_mass_kg, 26.1)
        self.assertAlmostEqual(plan.mass_at_fuel(1), 21.1)

    def test_reserve_retained_and_last_time_step_shortened(self):
        plan = self.aircraft.fuel_plan(6, 1)
        states = integrate_fuel_until_reserve(plan, lambda state: 0.02, step_s=7)
        self.assertAlmostEqual(states[-1].time_s, 250)
        self.assertEqual(states[-1].fuel_kg, 1)
        self.assertAlmostEqual(states[-1].mass_kg, 21.1)
        self.assertTrue(all(a.mass_kg > b.mass_kg for a, b in zip(states, states[1:])))

    def test_mass_dependent_flow_is_recomputed_with_convergent_time_steps(self):
        plan = self.aircraft.fuel_plan(12, 2)
        expected = log(32.1 / 22.1) / 0.001
        coarse = integrate_fuel_until_reserve(plan, lambda s: 0.001 * s.mass_kg, step_s=2)
        fine = integrate_fuel_until_reserve(plan, lambda s: 0.001 * s.mass_kg, step_s=0.5)
        self.assertLess(abs(fine[-1].time_s - expected), abs(coarse[-1].time_s - expected))
        self.assertAlmostEqual(fine[-1].time_s, expected, delta=0.2)

    def test_fuel_burn_changes_required_lift_and_drag(self):
        plan = self.aircraft.fuel_plan(12, 2)
        args = dict(area_m2=0.3208322, speed_m_s=90, conditions=FlightConditions(),
                    limits=self.aircraft.limits, polar=ParabolicPolar(0.03, 0.1, 0, 0.9))
        initial = level_flight_at_fuel(plan, 12, **args)
        final = level_flight_at_fuel(plan, 2, **args)
        self.assertAlmostEqual(final.cl / initial.cl, 22.1 / 32.1)
        self.assertLess(final.drag_n, initial.drag_n)
        self.assertLess(final.useful_power_w, initial.useful_power_w)

    def test_aircraft_limits_and_polar_limits_remain_separate(self):
        plan = self.aircraft.fuel_plan(12, 2)
        args = dict(area_m2=0.3208322, conditions=FlightConditions(), limits=self.aircraft.limits,
                    polar=ParabolicPolar(0.03, 0.1, 0, 0.9))
        for speed in (20, 301):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                level_flight_at_fuel(plan, 12, speed_m_s=speed, **args)
        args["polar"] = ParabolicPolar(0.03, 0.1, 0, 0.1)
        with self.assertRaises(ValueError):
            level_flight_at_fuel(plan, 12, speed_m_s=90, **args)

    def test_mission_targets_and_fixed_max_rpm_regime_are_saved(self):
        targets = self.aircraft.mission_requirements
        self.assertEqual(targets.launch_method, "catapult")
        self.assertEqual(targets.recovery_method, "parachute")
        self.assertAlmostEqual(targets.target_cruise_groundspeed_m_s, 180.5555555556)
        self.assertEqual(targets.altitude_capability_target_m, 10668)
        self.assertIsNone(targets.parachute_deployment_altitude_m)
        self.assertEqual(targets.catapult_exit_speed_m_s, 90)
        self.assertEqual(targets.catapult_exit_pitch_deg, 10)
        self.assertIsNone(targets.catapult_exit_flight_path_angle_deg)
        self.assertFalse(targets.model_parachute)
        engine = load_catalog(Path(__file__).resolve().parents[1] / "data/catalog.json").engines["amt-titan-392n"]
        self.assertEqual(engine.performance_operating_regime, "fixed_maximum_rpm")

    def test_minimum_speed_and_normal_load_limit(self):
        limits = self.aircraft.limits
        atmosphere = FlightConditions().atmosphere()
        with self.assertRaisesRegex(ValueError, "operational minimum"):
            limits.check_level_flight(32.1, 0.3208322, 74.9, atmosphere)
        limits.check_level_flight(32.1, 0.3208322, 75, atmosphere)
        cl = limits.check_flight_state(32.1, 0.3208322, 250, atmosphere, load_factor=11)
        self.assertLess(cl, limits.cl_max)
        with self.assertRaisesRegex(ValueError, "load factor"):
            limits.check_flight_state(32.1, 0.3208322, 250, atmosphere, load_factor=11.01)
        # Structural 11g does not make 11g aerodynamically available at every speed.
        with self.assertRaisesRegex(ValueError, "CLmax"):
            limits.check_flight_state(32.1, 0.3208322, 75, atmosphere, load_factor=4)

    def test_groundspeed_is_horizontal_and_not_tas_during_climb(self):
        limits = self.aircraft.limits
        atmosphere = FlightConditions().atmosphere()
        # 80 m/s TAS at gamma=30 deg has horizontal groundspeed ~69.3 m/s.
        with self.assertRaisesRegex(ValueError, "Horizontal groundspeed"):
            limits.check_flight_state(32.1, 0.3208322, 80, atmosphere,
                                      load_factor=1, flight_path_angle_deg=30)
        limits.check_flight_state(32.1, 0.3208322, 90, atmosphere,
                                  load_factor=1, flight_path_angle_deg=10)

    def test_altitude_goal_is_not_claimed_to_be_a_feasible_ceiling(self):
        high = FlightConditions(10668).atmosphere()
        with self.assertRaisesRegex(ValueError, "CLmax"):
            self.aircraft.limits.check_level_flight(32.1, 0.3208322, 75, high)
        cruise = self.aircraft.mission_requirements.target_cruise_groundspeed_m_s
        self.assertLess(cruise/high.speed_of_sound_m_s, 0.65)
        self.aircraft.limits.check_level_flight(32.1, 0.3208322, cruise, high)

    def test_continuous_rpm_limit_does_not_extrapolate_graph(self):
        config = load_catalog(Path(__file__).resolve().parents[1] / "data/catalog.json").select(
            "m600-thinsurf-acilar", "amt-titan-392n")
        self.assertEqual(config.engine.continuous_max_krpm, 97)
        model = config.jet_model()
        self.assertEqual(model.krpm_bounds[1], 96.5)
        with self.assertRaises(ValueError):
            model.at_krpm(97)
        limited = replace(model, continuous_max_krpm=90)
        with self.assertRaises(ValueError):
            limited.at_krpm(91)

    def test_invalid_inputs_and_incomplete_burn_are_rejected(self):
        for fuel, reserve in ((-1, 0), (1, 2), (1, -1)):
            with self.subTest(fuel=fuel, reserve=reserve), self.assertRaises(ValueError):
                FuelPlan(20.1, fuel, reserve)
        with self.assertRaises(ValueError):
            FlightConditions(20000)
        with self.assertRaises(ValueError):
            FlightConditions(0, -273.15)
        with self.assertRaises(ValueError):
            integrate_fuel_until_reserve(FuelPlan(20.1, 12, 2), lambda s: 0.01, max_duration_s=10)
