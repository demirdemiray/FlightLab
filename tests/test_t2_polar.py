from pathlib import Path
from dataclasses import replace
import json
import unittest

from flightlab.catalog import load_catalog
from flightlab.flow5 import read_flow5_csv
from flightlab.mission import FlightConditions, level_flight_at_fuel
from flightlab.performance import TabulatedPolar

CATALOG = Path(__file__).resolve().parents[1] / "data/catalog.json"


class T2PolarTests(unittest.TestCase):
    def setUp(self):
        # Preserve the old cold-altitude dataset audit after selecting a new polar.
        old = CATALOG.parent / "aircraft/m600-thinsurf-acilar"
        self.aircraft = replace(load_catalog(CATALOG).aircraft["m600-thinsurf-acilar"],
                                performance_polar_file=old / "T2-TriUniform-ThinSurf.csv",
                                polar_metadata_file=old / "T2-conditions.json")
        self.source = read_flow5_csv(self.aircraft.performance_polar_file)
        self.polar = self.source.drag_polar()  # raw source audit includes all 55 rows

    def test_actual_source_range_and_all_exported_drag_coefficients(self):
        self.assertEqual(len(self.source.points), 55)
        self.assertEqual(self.polar.cl_min, 0.019545)
        self.assertEqual(self.polar.cl_max, 0.75944)
        for point in self.source.points:
            self.assertEqual(self.polar.drag_coefficient(point["CL"]), point["CD"])
            self.assertAlmostEqual(point["CD_viscous"] + point["CD_induced"], point["CD"], delta=1e-5)

    def test_reference_area_matches_source_density_and_geometry(self):
        metadata = json.loads(self.aircraft.polar_metadata_file.read_text())
        rho = metadata["air_density_kg_m3"]
        self.assertEqual(rho, 0.723714)
        for point in self.source.points:
            q = 0.5 * rho * point["V (m/s)"]**2
            area = point["Lift (N)"] / (q * point["CL"])
            self.assertAlmostEqual(area, 0.3208322, delta=3e-5)
            self.assertAlmostEqual(q * 0.3208322 * point["CD"], point["Drag (N)"], delta=0.03)
        atmosphere = FlightConditions(7000, temperature_offset_c=-45).atmosphere()
        self.assertAlmostEqual(atmosphere.temperature_k - 273.15, -75.5)
        self.assertAlmostEqual(atmosphere.density_kg_m3, rho, delta=3e-6)
        self.assertAlmostEqual(atmosphere.speed_of_sound_m_s, 281.834, delta=0.001)

    def test_linear_interpolation_and_no_extension_to_aircraft_clmax(self):
        a, b = self.polar.points[10:12]
        self.assertAlmostEqual(self.polar.drag_coefficient((a[0] + b[0])/2), (a[1] + b[1])/2)
        with self.assertRaises(ValueError):
            self.polar.drag_coefficient(0.9)

    def test_fuel_dependent_level_flight_accepts_selected_table(self):
        plan = self.aircraft.fuel_plan(12, 2)
        args = dict(area_m2=0.3208322, speed_m_s=90, conditions=FlightConditions(),
                    limits=self.aircraft.limits, polar=self.polar)
        initial = level_flight_at_fuel(plan, 12, **args)
        final = level_flight_at_fuel(plan, 2, **args)
        self.assertLess(final.cl, initial.cl)
        self.assertLess(final.drag_n, initial.drag_n)

    def test_duplicate_branch_and_single_point_rejected(self):
        for points in (((0.1, 0.02),), ((0.1, 0.02), (0.1, 0.03))):
            with self.subTest(points=points), self.assertRaises(ValueError):
                TabulatedPolar(points)

    def test_selected_model_keeps_all_points_and_reports_source_trust(self):
        selected = self.aircraft.aerodynamic_model()
        self.assertEqual(len(selected.points), 55)
        self.assertEqual(selected.cl_min, 0.019545)
        self.assertEqual(selected.cl_max, 0.75944)
        for point in self.source.points:
            self.assertEqual(selected.drag_coefficient(point["CL"]), point["CD"])
        self.assertTrue(selected.warnings_for_cl(0.019545))
        self.assertFalse(selected.warnings_for_cl(0.75944))

    def test_source_warning_propagates_through_interpolation(self):
        polar = self.aircraft.aerodynamic_model()
        # An interval sharing an unreliable endpoint must not lose the warning.
        boundary = next(i for i, m in enumerate(polar.source_mach) if m <= 0.65)
        a, b = polar.points[boundary - 1:boundary + 1]
        self.assertTrue(polar.warnings_for_cl((a[0] + b[0])/2))
