from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from flightlab.catalog import load_catalog

CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalog.json"


class CatalogTests(unittest.TestCase):
    def test_supplied_aircraft_has_its_own_mass_properties(self):
        catalog = load_catalog(CATALOG)
        plane = catalog.aircraft["m600-thinsurf-acilar"]
        self.assertEqual(plane.mass_properties.mass_kg, 32.1)
        self.assertEqual(plane.mass_properties.cg_m, (0.80819, 0, 0.0018626))
        self.assertEqual(plane.mass_properties.ixz_kg_m2, 0.02017)
        self.assertIsNone(plane.mass_properties.ixy_kg_m2)
        self.assertIn("amt-titan-392n", catalog.engines)
        with self.assertRaises(KeyError):
            catalog.select(plane.id, "missing-engine")

    def test_multiple_aircraft_and_engine_selection_preserves_loading(self):
        data = json.loads(CATALOG.read_text())
        # Absolute fixture paths make this independent of the temporary directory.
        original = data["aircraft"][0]
        original["geometry_file"] = str(CATALOG.parent / original["geometry_file"])
        original["polar_files"] = [str(CATALOG.parent / p) for p in original["polar_files"]]
        for key in ("performance_polar_file", "polar_metadata_file"):
            original[key] = str(CATALOG.parent / original[key])
        other = dict(original, id="synthetic-aircraft", name="Test fixture")
        other["mass_properties"] = dict(original["mass_properties"], mass_kg=20)
        data["aircraft"].append(other)
        data["engines"] = [
            {"id": "test-jet", "name": "Synthetic jet", "propulsion_kind": "jet"},
            {"id": "test-electric", "name": "Synthetic electric", "propulsion_kind": "electric_propeller"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(data))
            catalog = load_catalog(path)
        configuration = catalog.select("synthetic-aircraft", "test-jet")
        self.assertEqual(configuration.aircraft.mass_properties.mass_kg, 20)
        self.assertEqual(configuration.engine.propulsion_kind, "jet")
        self.assertEqual(catalog.select(original["id"], "test-electric").aircraft.mass_properties.mass_kg, 32.1)

    def test_invalid_mass_properties_rejected(self):
        properties = load_catalog(CATALOG).aircraft["m600-thinsurf-acilar"].mass_properties
        for value in (-1, 0, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(properties, mass_kg=value)
