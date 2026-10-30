import csv
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from flightlab.dataset import AeroReference, load_dataset, parse_manifest


def manifest_text():
    text = StringIO()
    writer = csv.writer(text)
    writer.writerow(("name", "altitude_m", "speed_m_s", "temperature_c", "density_kg_m3", "nu_m2_s"))
    writer.writerow(("T1_h00000_V100", 0, 100, 15, 1.225, 1.46065e-5))
    writer.writerow(("T1_h03000_V100", 3000, 100, -4.5, 0.909, 1.88e-5))
    return text.getvalue()


def polar_text(name="T1_h00000_V100", speed=100, plane="Plane"):
    return f"{plane}\n{name}\n\nCtrl,α (°),CL,CD,Cm,V (m/s)\n0,0,0.1,0.02,0,{speed}\n0,1,0.2,0.03,-0.01,{speed}\n"


class DatasetTests(unittest.TestCase):
    def test_zip_matching_uses_metadata_not_export_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"results.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("nested/manifest.csv", manifest_text())
                archive.writestr("nested/arbitrary-export-name.csv", polar_text())
                archive.writestr("unexpected.csv", polar_text("Other"))
            data = load_dataset(path, expected_plane="Plane")
        report = data.report()
        self.assertEqual(report["matched_polars"], 1)
        self.assertEqual(report["usable_polars"], 1)
        self.assertEqual(report["total_observed_points"], 2)
        self.assertEqual(report["missing_polars"], ["T1_h03000_V100"])
        self.assertEqual(report["unmatched_files"], ["unexpected.csv"])
        self.assertTrue(any("alpha points absent" in s for s in data.runs[0].issues))

    def test_mismatched_speed_and_duplicate_exports_are_not_silently_fitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"manifest.csv").write_text(manifest_text())
            (root/"wrong.csv").write_text(polar_text(speed=170))
            (root/"duplicate.csv").write_text(polar_text())
            data = load_dataset(root)
        self.assertEqual(len(data.runs), 2)
        self.assertTrue(all(not r.usable for r in data.runs))
        self.assertTrue(any("CSV speed differs" in issue for r in data.runs for issue in r.issues))

    def test_malformed_and_mixed_aircraft_files_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"manifest.csv").write_text(manifest_text())
            (root/"wrong-plane.csv").write_text(polar_text(plane="Different plane"))
            (root/"empty.csv").write_text("Plane\nPolar\n")
            data = load_dataset(root, expected_plane="Plane")
        self.assertFalse(data.runs[0].usable)
        self.assertIn("empty.csv", data.file_errors)

    def test_zip_members_are_never_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"input.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("manifest.csv", manifest_text())
                archive.writestr("../escape.csv", polar_text())
            data = load_dataset(path)
            self.assertEqual(len(data.runs), 1)
            self.assertFalse((Path(directory)/"escape.csv").exists())

    def test_template_references_are_converted_using_explicit_units(self):
        path = Path(__file__).resolve().parents[1]/"data/analysis-templates/T1-user-template.xml"
        ref = AeroReference.from_flow5_template(path)
        self.assertAlmostEqual(ref.area_m2, 0.320833)
        self.assertAlmostEqual(ref.chord_m, 0.375397)

    def test_duplicate_manifest_identity_rejected(self):
        text = manifest_text()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_manifest(text + text.splitlines()[1] + "\n")
