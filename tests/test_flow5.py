from pathlib import Path
import tempfile
import unittest

from flightlab.flow5 import read_flow5_csv


FIXTURE = Path(__file__).parent / "fixtures" / "T7-TriUniform-ThinSurf.csv"


class Flow5ImportTests(unittest.TestCase):
    def parse_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "polar.csv"
            path.write_text(text, encoding="utf-8-sig")
            return read_flow5_csv(path)

    def test_actual_export_with_joined_header(self):
        polar = read_flow5_csv(FIXTURE)
        self.assertEqual(len(polar.columns), 57)
        self.assertEqual(len(polar.points), 1)
        self.assertEqual(polar.metadata_lines[1], "T7-TriUniform-ThinSurf")
        point = polar.points[0]
        self.assertEqual(point["CL"], 0.16563)
        self.assertEqual(point["Cl"], -2.3633e-10)
        self.assertEqual(point["Mass (kg)"], 32.1)
        self.assertEqual(point["CoG_x (cm)"], 80.819)
        self.assertEqual(point["CoG_z (cm)"], 0.18626)
        self.assertEqual(point["V (m/s)"], 128.13)
        self.assertEqual(point["Gamma"], 11.654)

    def test_normal_separate_header_and_multiple_points(self):
        polar = self.parse_text("Plane\nPolar\n\nCtrl,α (°),CL,CD,Cm,V (m/s),\n0,1,0.2,0.03,0,25,\n1,2,0.3,0.04,0,30,\n")
        self.assertEqual(len(polar.points), 2)
        self.assertEqual(polar.points[1]["CL"], 0.3)

    def test_invalid_data_is_rejected(self):
        header = "Ctrl,α (°),CL,CD,Cm,V (m/s)\n"
        for row in ("0,1,0.2,0.03,0", "0,1,,0.03,0,25", "0,1,nan,0.03,0,25", "0,1,0.2,0.03,0,25,99"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.parse_text(header + row)

    def test_missing_header_or_points_is_rejected(self):
        for text in ("", "Plane\nPolar", "Ctrl,α (°),CL,CD,Cm,V (m/s)\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse_text(text)

    def test_undefined_auxiliary_ratio_does_not_drop_negative_cl_row(self):
        polar = self.parse_text("Plane\nPolar\nCtrl,α (°),CL,CD,Cm,V (m/s),1/sqrt(CL)\n0,-4,-0.1,0.02,0,100,nan\n")
        self.assertEqual(polar.points[0]["CL"], -0.1)
        self.assertNotEqual(polar.points[0]["1/sqrt(CL)"], polar.points[0]["1/sqrt(CL)"])
