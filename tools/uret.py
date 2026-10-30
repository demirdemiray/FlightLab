"""Run: python uret.py path/to/T1-template.xml"""
import csv
import math
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

source = Path(sys.argv[1])
parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
template = ET.parse(source, parser=parser).getroot()
assert template.findtext("Polar/Type") == "FIXEDSPEEDPOLAR", "T1 XML gerekli"
assert float(template.findtext("Units/ms_to_speed_unit")) == 1, "Hiz birimi m/s olmali"
out = Path.cwd() / ("FlightLab-T1-72_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
out.mkdir(exist_ok=False)
(out / "analyses_72").mkdir()
(out / "smoke_2").mkdir()
shutil.copy2(source, out / "original_template.xml")
rows = []
for h in (0, 1500, 3000, 4500, 6000, 7500, 9000, 10500):
    t = 288.15 - 0.0065 * h
    p = 101325 * (t / 288.15) ** (9.80665 / (287.05287 * 0.0065))
    rho = p / (287.05287 * t)
    mu = 1.716e-5 * (t / 273.15)**1.5 * (273.15 + 110.4) / (t + 110.4)
    nu = mu / rho
    for v in (50, 75, 100, 125, 150, 175, 200, 225, 250):
        name = f"T1_h{h:05d}_V{v:03d}"
        xml = deepcopy(template)
        for field, value in (("Polar_Name", name), ("Fixed_Velocity", str(v)),
                             ("Fluid/Density", f"{rho:.10g}"),
                             ("Fluid/Viscosity", f"{nu:.10g}")):
            node = xml.find("Polar/" + field)
            if node is None:
                raise ValueError("Eksik XML alani: " + field)
            node.text = value
        ET.indent(xml, space="    ")
        path = out / "analyses_72" / (name + ".xml")
        ET.ElementTree(xml).write(path, encoding="utf-8", xml_declaration=True)
        if h in (0, 3000) and v == 100:
            shutil.copy2(path, out / "smoke_2" / path.name)
        mach = v / math.sqrt(1.4 * 287.05287 * t)
        rows.append((name, h, v, t-273.15, rho, nu, mach, mach > 0.65))
with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(("name", "altitude_m", "speed_m_s", "temperature_c",
                     "density_kg_m3", "nu_m2_s", "mach", "unreliable"))
    writer.writerows(rows)
(out / "KULLANIM.txt").write_text(
    "Mevcut Flow5 projenizi acin. Batch analysis (2), Alt+F7.\n"
    "Ucak: M-600-ThinSurf-acılar. Actions > Change directory: once smoke_2.\n"
    "T12 alfa: -4 ile 14 derece, adim 0.25; tek aktif aralik. Calculate.\n"
    "Iki deneme dogruysa analyses_72 klasorunu secip hepsini calistirin.\n"
    "Mevcut profil/polar verileri projede kalir; bu betik onlari degistirmez.\n"
    "Solver testi burada yapilmadi. Sonuclari ve yakinsemeyen noktalari kontrol edin.\n",
    encoding="utf-8")
archive = shutil.make_archive(str(out), "zip", root_dir=out.parent, base_dir=out.name)
print("72 analiz ve 2 deneme hazir:", out)
print("ZIP:", archive)
