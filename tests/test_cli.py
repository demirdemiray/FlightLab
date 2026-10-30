from contextlib import redirect_stdout
from io import StringIO
import json
from math import log
from pathlib import Path
import tempfile
import unittest

from flightlab.cli import main
from flightlab.dataset import AeroReference, parse_manifest


class CliTests(unittest.TestCase):
    def test_manifest_csv_to_family_query_pipeline_with_independent_affine_data(self):
        root = Path(__file__).resolve().parents[1]
        template = root/"data/analysis-templates/T1-user-template.xml"
        reference = AeroReference.from_flow5_template(template)
        all_conditions = parse_manifest((root/"data/analysis-manifests/T1-72-manifest.csv").read_text())
        self.assertEqual(len(all_conditions), 72)
        selected = [c for c in all_conditions.values() if c.altitude_m in (0, 4500) and c.speed_m_s in (100, 250)]
        self.assertEqual(len(selected), 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            manifest = "name,altitude_m,speed_m_s,temperature_c,density_kg_m3,nu_m2_s\n"
            for c in selected:
                manifest += f"{c.name},{c.altitude_m},{c.speed_m_s},{c.temperature_c},{c.density_kg_m3},{c.nu_m2_s}\n"
                lines = ["Synthetic", c.name, "Ctrl,α (°),CL,CD,Cm,V (m/s),Lift (N),Drag (N)"]
                for i in range(73):
                    alpha = -4+i*0.25
                    cl = 0.1+(alpha+4)*0.02
                    re = c.speed_m_s*reference.chord_m/c.nu_m2_s
                    cd = 0.02+0.01*cl+0.001*log(re)+0.005*c.mach
                    q_area = 0.5*c.density_kg_m3*c.speed_m_s**2*reference.area_m2
                    lines.append(f"0,{alpha},{cl},{cd},{-0.02*cl},{c.speed_m_s},{q_area*cl},{q_area*cd}")
                (path/(c.name+".CSV")).write_text("\n".join(lines), encoding="utf-8")
            (path/"manifest.csv").write_text(manifest)
            report = path/"audit.json"
            code = main(["inspect", str(path), "--fit-check", "--reference-template", str(template),
                         "--strict", "--report", str(report)])
            self.assertEqual(code, 0)
            audit = json.loads(report.read_text())
            self.assertEqual(audit["fit_check"]["status"], "built")
            self.assertEqual(audit["fit_check"]["samples"], 292)
            self.assertTrue(all(not row["missing_alpha_deg"] for row in audit["runs"]))
            query = path/"query.json"
            code = main(["query", str(path), "--reference-template", str(template), "--cl", "0.2",
                         "--speed", "100", "--altitude", "0", "--report", str(query)])
            self.assertEqual(code, 0)
            result = json.loads(query.read_text())["query"]
            self.assertAlmostEqual(result["alpha_deg"], 1)
            self.assertAlmostEqual(result["cm"], -0.004)
            c = all_conditions["T1_h00000_V100"]
            expected = 0.02+0.01*0.2+0.001*log(100*reference.chord_m/c.nu_m2_s)+0.005*c.mach
            self.assertAlmostEqual(result["cd"], expected, places=10)

    def test_real_reference_preview_is_explicitly_experimental(self):
        root = Path(__file__).resolve().parents[1]
        stream = StringIO()
        with redirect_stdout(stream):
            code = main(["preview", "--catalog", str(root/"data/catalog.json"),
                         "--reference-template", str(root/"data/analysis-templates/T1-user-template.xml")])
        self.assertEqual(code, 0)
        data = json.loads(stream.getvalue())
        self.assertIn("not_validated", data["classification"])
        point = data["candidates"]["maximum_speed"]
        self.assertEqual(point["limiting_condition"], "model_or_other_envelope_boundary")
        self.assertTrue(point["point"]["warnings"])
        self.assertNotIn("range_km", data)

    def test_inspect_reports_partial_data_without_requiring_a_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"manifest.csv").write_text("name,altitude_m,speed_m_s,temperature_c,density_kg_m3,nu_m2_s\nT1,0,100,15,1.225,1.46e-5\n")
            output = root/"report.json"
            code = main(["inspect", str(root), "--report", str(output), "--strict"])
            self.assertEqual(code, 2)
            data = json.loads(output.read_text())
            self.assertEqual(data["missing_polars"], ["T1"])
