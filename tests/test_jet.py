from pathlib import Path
import tempfile
import unittest

from flightlab.catalog import load_catalog
from flightlab.jet import JetEngine, JetMap, JetOutput, JetPoint, read_jet_column_output

CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


class JetTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(CATALOG)
        self.config = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n")
        self.engine = self.config.source_jet_map_model()

    def test_actual_map_and_source_units(self):
        self.assertEqual(len(self.engine.performance_map.points), 121)
        reference = self.engine.at_case(0)
        self.assertEqual(reference.thrust_n, 400)
        self.assertEqual(reference.fuel_flow_kg_s, 0.015)
        self.assertEqual(reference.fuel_flow_kg_h, 54)
        point = self.engine.performance_map.points[1]
        self.assertEqual(point.altitude_m, -304.8)
        self.assertEqual(point.mach, 0)
        self.assertAlmostEqual(self.engine.at_case(1).thrust_n, 409.26)

    def test_derating_changes_only_thrust_at_every_source_point(self):
        for factor in (0.6, 0.8, 1.0):
            model = self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n",
                                        thrust_factor=factor).source_jet_map_model()
            for point in self.engine.performance_map.points:
                result = model.at_case(point.case_id)
                self.assertAlmostEqual(result.thrust_n, point.output.thrust_n * factor)
                self.assertEqual(result.fuel_flow_kg_s, point.output.fuel_flow_kg_s)
        self.assertEqual(self.engine.at_case(0).thrust_n, 400)

    def test_factor_bounds(self):
        for factor in (0.599, 1.001, float("nan"), float("inf"), True):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                self.catalog.select("m600-thinsurf-acilar", "amt-titan-392n", thrust_factor=factor)

    def test_bilinear_interpolation_and_derating(self):
        # Analytic synthetic affine fields; independent of the actual engine.
        points = tuple(JetPoint(i, h, m, JetOutput(100 + h + 20*m, 0.01 + h/10000 + m/100))
                       for i, (h, m) in enumerate(((0, 0), (0, 1), (100, 0), (100, 1))))
        result = JetEngine(JetMap(points), 0.6).at_conditions(50, 0.5)
        self.assertAlmostEqual(result.thrust_n, 96)
        self.assertAlmostEqual(result.fuel_flow_kg_s, 0.02)

    def test_actual_grid_points_and_no_extrapolation(self):
        for point in self.engine.performance_map.points[1:]:
            result = self.engine.at_conditions(point.altitude_m, point.mach)
            self.assertEqual(result, point.output)
        for h, m in ((-305, 0), (9145, 0), (0, -0.01), (0, 1.11)):
            with self.subTest(h=h, m=m), self.assertRaises(ValueError):
                self.engine.at_conditions(h, m)

    def test_reference_is_separate_from_interpolation_grid(self):
        # Sea-level interpolation uses neighbouring sweep rows, not a special
        # override at Mach zero that would make the interpolant discontinuous.
        points = self.engine.performance_map.points
        h0, h1 = points[1].altitude_m, points[13].altitude_m
        weight = -h0 / (h1 - h0)
        expected = (1 - weight) * points[1].output.thrust_n + weight * points[13].output.thrust_n
        self.assertAlmostEqual(self.engine.at_conditions(0, 0).thrust_n, expected)

    def test_unconverged_or_misaligned_map_rejected(self):
        source = self.config.engine.performance_data_file.read_text()
        lines = source.splitlines()
        broken = []
        for line in lines:
            if line.startswith("converged (-)"):
                line = line.replace("1", "0", 1)
            broken.append(line)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engine.out.csv"
            path.write_text("\n".join(broken))
            with self.assertRaises(ValueError):
                read_jet_column_output(path, altitude_unit="m")
            path.write_text(source.replace("0.0150", "nan", 1))
            with self.assertRaises(ValueError):
                read_jet_column_output(path, altitude_unit="m")
