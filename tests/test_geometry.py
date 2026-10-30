from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from flightlab.geometry import read_flow5_geometry

FIXTURE = Path(__file__).parent / "fixtures" / "M-600-ThinSurf-acılar.xml"


class GeometryTests(unittest.TestCase):
    def test_actual_geometry_units_planform_and_mass(self):
        geometry = read_flow5_geometry(FIXTURE)
        self.assertEqual(geometry.name, "M-600-ThinSurf-acılar")
        self.assertEqual(len(geometry.surfaces), 3)
        wing = geometry.surfaces[0]
        metrics = wing.flat_symmetric_planform()
        self.assertAlmostEqual(metrics.span_m, 1)
        self.assertAlmostEqual(metrics.area_m2, 0.3208322)
        self.assertAlmostEqual(metrics.mac_m, 0.37539525116244565)
        self.assertAlmostEqual(metrics.aspect_ratio, 3.1168941272104234)
        self.assertAlmostEqual(geometry.declared_total_mass_kg, 32.1)
        self.assertEqual(geometry.point_masses[0].tag, "fuel")
        self.assertAlmostEqual(geometry.point_masses[0].coordinates_m[0], 0.815)
        self.assertEqual(wing.sections[0].right_foil, "NACA 64-213")

    def test_rectangular_wing_analytical_geometry(self):
        wing = read_flow5_geometry(FIXTURE).surfaces[0]
        wing = replace(wing, sections=(replace(wing.sections[0], chord_m=0.2),
                                       replace(wing.sections[-1], chord_m=0.2)))
        metrics = wing.flat_symmetric_planform()
        self.assertAlmostEqual(metrics.area_m2, 0.2)
        self.assertAlmostEqual(metrics.mac_m, 0.2)
        self.assertAlmostEqual(metrics.aspect_ratio, 5)

    def test_one_sided_fin_is_not_doubled(self):
        fin = read_flow5_geometry(FIXTURE).surfaces[2]
        with self.assertRaises(ValueError):
            fin.flat_symmetric_planform()

    def test_missing_units_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.xml"
            path.write_text("<xflplane><Plane/></xflplane>")
            with self.assertRaises(ValueError):
                read_flow5_geometry(path)
