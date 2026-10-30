import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from flightlab.batch import create_batch_bundle, create_gui_batch_bundle

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "data/analysis-templates/T1-user-template.xml"
GEOMETRY = ROOT / "data/aircraft/m600-thinsurf-acilar/geometry.xml"


class BatchTests(unittest.TestCase):
    def test_gui_bundle_keeps_all_settings_except_four_requested_fields(self):
        def signature(node):
            return (node.tag, sorted(node.attrib.items()), (node.text or "").strip(),
                    tuple(signature(child) for child in node))
        original = ET.parse(TEMPLATE).getroot()
        changed = ("Polar/Polar_Name", "Polar/Fixed_Velocity", "Polar/Fluid/Density", "Polar/Fluid/Viscosity")
        with tempfile.TemporaryDirectory() as directory:
            out = create_gui_batch_bundle(TEMPLATE, Path(directory)/"gui")
            files = list((out/"analyses_72").glob("*.xml"))
            self.assertEqual(len(files), 72)
            self.assertFalse((out/"foils").exists())
            self.assertFalse((out/"prepare.py").exists())
            for path in files:
                tree = ET.parse(path).getroot()
                for key in changed:
                    tree.find(key).text = original.findtext(key)
                self.assertEqual(signature(tree), signature(original))
            sea = ET.parse(out/"analyses_72/T1_h00000_V100.xml").getroot()
            self.assertAlmostEqual(float(sea.findtext("Polar/Fluid/Density")), 1.225, places=5)
            self.assertEqual(sea.findtext("Polar/Fixed_Velocity"), "100")
            self.assertEqual(sea.findtext("Polar/Reference_Dimensions/Reference_Dimensions"), "PROJECTED")
            self.assertEqual(sea.findtext("Polar/Use_plane_inertia"), "true")
            for path in (out/"smoke_2").glob("*.xml"):
                self.assertEqual(path.read_bytes(), (out/"analyses_72"/path.name).read_bytes())
            self.assertEqual(len(list((out/"smoke_2").glob("*.xml"))), 2)
            with self.assertRaises(FileExistsError):
                create_gui_batch_bundle(TEMPLATE, out)
            extended = create_gui_batch_bundle(TEMPLATE, Path(directory)/"gui81", include_10700=True)
            self.assertEqual(len(list((extended/"analyses_81").glob("*.xml"))), 81)

    def test_full_matrix_preserves_physics_settings_and_source_files(self):
        before = TEMPLATE.read_bytes()
        source = ET.parse(TEMPLATE).getroot()
        changed = {"Polar/Polar_Name", "Polar/Fixed_Velocity", "Polar/Fluid/Density",
                   "Polar/Fluid/Viscosity", "Polar/Reference_Dimensions/Reference_Dimensions",
                   "Polar/Use_plane_inertia"}
        def leaves(node, prefix=""):
            path = prefix + node.tag
            if not list(node):
                return {path: node.text.strip() if node.text else ""}
            result = {}
            for child in node:
                result.update(leaves(child, path + "/"))
            return result
        expected = leaves(source)
        with tempfile.TemporaryDirectory() as directory:
            out = create_batch_bundle(TEMPLATE, GEOMETRY, Path(directory)/"bundle")
            files = list((out/"analyses").glob("*.xml"))
            self.assertEqual(len(files), 72)
            for file in files:
                actual = leaves(ET.parse(file).getroot())
                for path, value in expected.items():
                    if path.removeprefix(source.tag + "/") not in changed:
                        self.assertEqual(actual[path], value, path)
            sea = ET.parse(out/"analyses/T1_h00000_V100.xml").getroot()
            self.assertAlmostEqual(float(sea.findtext("Polar/Fluid/Density")), 1.225, places=5)
            self.assertAlmostEqual(float(sea.findtext("Polar/Fluid/Viscosity")), 1.4607e-5, delta=2e-8)
            high = ET.parse(out/"analyses/T1_h10500_V250.xml").getroot()
            self.assertLess(float(high.findtext("Polar/Fluid/Density")), 0.4)
            with (out/"manifest.csv").open() as stream:
                manifest = list(csv.DictReader(stream))
            self.assertEqual(len(manifest), 72)
            self.assertEqual(manifest[-1]["trust"], "unreliable")
            smoke = ET.parse(out/"scripts/smoke.template.xml").getroot()
            names = [n.text for n in smoke.findall("Plane_analysis/Plane_Analysis_Files/Analysis_File_Name")]
            self.assertEqual(names, ["T1_h00000_V100.xml", "T1_h03000_V100.xml"])
            self.assertEqual(smoke.findtext("Plane_analysis/Plane_Analysis_Data/T12_Range"), "-4, 14, 0.25")
            self.assertEqual((out/"templates/T1-original.xml").read_bytes(), before)
            with self.assertRaises(FileExistsError):
                create_batch_bundle(TEMPLATE, GEOMETRY, out)
        self.assertEqual(TEMPLATE.read_bytes(), before)

    def test_local_prepare_requires_assets_then_resolves_portable_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            out = create_batch_bundle(TEMPLATE, GEOMETRY, Path(directory)/"bundle", include_10700=True)
            self.assertEqual(len(list((out/"analyses").glob("*.xml"))), 81)
            missing = subprocess.run([sys.executable, str(out/"prepare.py")], capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("Missing", missing.stderr)
            # Synthetic asset files exercise presence/name checks only, not Flow5.
            assets = json.loads((out/"required-assets.json").read_text())
            self.assertEqual(len(assets), 4)
            for asset in assets:
                (out/"foils"/asset["filename"]).write_text(asset["required_internal_name"] + "\n0 0\n1 0\n")
            (out/"foil_polars/test.txt").write_text("synthetic placeholder, not valid solver data")
            result = subprocess.run([sys.executable, str(out/"prepare.py")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            script = ET.parse(out/"scripts/full.xml").getroot()
            self.assertEqual(script.findtext("Metadata/Directories/foil_files_dir"), (out/"foils").as_posix())
            self.assertNotIn("__BUNDLE_ROOT__", (out/"scripts/full.xml").read_text())
