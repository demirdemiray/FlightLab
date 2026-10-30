from pathlib import Path
from dataclasses import replace
import json
import unittest

from flightlab.catalog import load_catalog
from flightlab.flow5 import read_flow5_csv
from flightlab.mission import FlightConditions, level_flight_at_fuel

CATALOG = Path(__file__).resolve().parents[1] / "data/catalog.json"


class SeaLevelPolarTests(unittest.TestCase):
    def setUp(self):
        self.config = load_catalog(CATALOG).select("m600-thinsurf-acilar", "amt-titan-392n")
        self.plane = self.config.aircraft

    def test_selected_source_and_user_effective_clmax(self):
        source = read_flow5_csv(self.plane.performance_polar_file)
        model = self.plane.aerodynamic_model()
        self.assertEqual(len(source.points), 55)
        self.assertEqual(len(model.points), 55)
        self.assertEqual(source.points[-1]["α (°)"], 12.25)
        self.assertEqual(model.cl_max, 0.75944)
        self.assertEqual(self.plane.limits.cl_max, model.cl_max)
        self.assertAlmostEqual(model.drag_coefficient(0.75944), 0.30829)
        self.assertTrue(model.warnings_for_cl(model.cl_min))

    def test_force_units_confirm_sea_level_density(self):
        source = read_flow5_csv(self.plane.performance_polar_file)
        atmosphere = FlightConditions().atmosphere()
        for point in source.points:
            implied_rho = 2 * point["Lift (N)"] / (point["V (m/s)"]**2 * point["CL"] * 0.3208322)
            self.assertAlmostEqual(implied_rho, atmosphere.density_kg_m3, delta=0.0002)
        meta = json.loads(self.plane.polar_metadata_file.read_text())
        self.assertEqual(meta["reported_altitude_m"], 0)
        self.assertEqual(meta["reported_temperature_c"], 15)

    def test_previous_source_is_retained_with_distinct_values(self):
        old = next(p for p in self.plane.polar_files if p.name.startswith("T2") and p != self.plane.performance_polar_file)
        previous = read_flow5_csv(old)
        current = read_flow5_csv(self.plane.performance_polar_file)
        self.assertEqual(len(previous.points), 55)
        self.assertEqual(previous.points[-1]["V (m/s)"], 59.763)
        self.assertEqual(current.points[-1]["V (m/s)"], 45.936)
        self.assertNotEqual(previous.points[-1]["CD"], current.points[-1]["CD"])

    def test_new_cl_limit_applies_as_fuel_burns(self):
        plan = self.plane.fuel_plan(12, 2)
        args = dict(area_m2=0.3208322, speed_m_s=44, conditions=FlightConditions(),
                    # Isolate the aerodynamic CL boundary from the newly specified
                    # independent 75 m/s operational minimum.
                    limits=replace(self.plane.limits, min_groundspeed_m_s=0),
                    polar=self.config.aerodynamic_model())
        with self.assertRaises(ValueError):
            level_flight_at_fuel(plan, 12, **args)
        lighter = level_flight_at_fuel(plan, 2, **args)
        self.assertLess(lighter.cl, 0.75944)
