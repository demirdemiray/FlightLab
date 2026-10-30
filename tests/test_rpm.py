from dataclasses import replace
from pathlib import Path
import unittest

from flightlab.catalog import load_catalog
from flightlab.rpm import Curve, STANDARD_GRAVITY

CATALOG = Path(__file__).resolve().parents[1] / "data/catalog.json"


class RpmTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(CATALOG)
        self.model = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n").reference_rpm_model()

    def test_graph_units_and_endpoints(self):
        output = self.model.at_krpm(91.4)
        self.assertAlmostEqual(output.thrust_n, 35.77 * 9.80665)
        self.assertAlmostEqual(output.fuel_flow_kg_s, 1000.98 / 60000)
        self.assertAlmostEqual(output.fuel_flow_kg_h, 60.0588)

    def test_selected_model_uses_graph_fuel_instead_of_csv(self):
        config = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n")
        self.assertEqual(config.engine.fuel_source, "rpm_graph")
        selected = config.jet_model()
        self.assertEqual(selected, config.reference_rpm_model())
        output = selected.at_krpm(96.5)
        self.assertAlmostEqual(output.fuel_flow_kg_h, 69.17, places=2)
        self.assertNotAlmostEqual(output.fuel_flow_kg_h, 54)
        derated = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n",
                                      thrust_factor=0.6).jet_model().at_krpm(96.5)
        self.assertEqual(derated.fuel_flow_kg_s, output.fuel_flow_kg_s)

    def test_graph_source_cannot_silently_fall_back_to_csv(self):
        config = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n")
        with self.assertRaises(ValueError):
            replace(config.engine, rpm_data_file=None)

    def test_derating_same_rpm_preserves_fuel_and_increases_effective_tsfc(self):
        rpm = 71.1
        base = self.model.at_krpm(rpm)
        reduced = replace(self.model, thrust_factor=0.6).at_krpm(rpm)
        self.assertAlmostEqual(reduced.thrust_n, base.thrust_n * 0.6)
        self.assertEqual(reduced.fuel_flow_kg_s, base.fuel_flow_kg_s)
        self.assertAlmostEqual(reduced.fuel_flow_kg_s / reduced.thrust_n,
                               base.fuel_flow_kg_s / base.thrust_n / 0.6)

    def test_required_thrust_inverse_roundtrip_and_derating_cost(self):
        target = self.model.at_krpm(71.1).thrust_n
        self.assertAlmostEqual(self.model.krpm_for_thrust(target), 71.1)
        derated = replace(self.model, thrust_factor=0.8)
        rpm = derated.krpm_for_thrust(target)
        self.assertGreater(rpm, 71.1)
        self.assertAlmostEqual(derated.at_krpm(rpm).thrust_n, target)
        self.assertGreater(derated.at_krpm(rpm).fuel_flow_kg_s, self.model.at_krpm(71.1).fuel_flow_kg_s)

    def test_no_rpm_or_thrust_extrapolation(self):
        for rpm in (0, 30.4, 96.6, 100, float("nan")):
            with self.subTest(rpm=rpm), self.assertRaises(ValueError):
                self.model.at_krpm(rpm)
        for thrust in (0, 500):
            with self.subTest(thrust=thrust), self.assertRaises(ValueError):
                self.model.krpm_for_thrust(thrust)

    def test_piecewise_linear_not_high_order_overshoot(self):
        self.assertEqual(Curve(((1, 10), (3, 30))).value(2), 20)

    def test_tsfc_formula_on_independent_exact_data(self):
        model = replace(self.model, fuel_g_min=Curve(((40, 500), (80, 1000))),
                        thrust_kgf=Curve(((40, 10), (80, 20))),
                        tsfc_graph=Curve(((40, 3), (80, 3))))
        for point in model.tsfc_consistency():
            self.assertAlmostEqual(point.relative_difference, 0)
        self.assertAlmostEqual(model.at_krpm(40).thrust_n, 10 * STANDARD_GRAVITY)

    def test_invalid_curve_rejected(self):
        for points in (((1, 1), (1, 2)), ((1, -1), (2, 2))):
            with self.subTest(points=points), self.assertRaises(ValueError):
                Curve(points)
