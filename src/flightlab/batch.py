"""Generate inspectable Flow5 T1 batch inputs from a user's exported template.

Only input generation is verified here; Flow5 is not installed in this workspace.
Source XML and assets are never rewritten. Preserve the user's viscous method.
"""

import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from .mission import FlightConditions

ALTITUDES_M = (0, 1500, 3000, 4500, 6000, 7500, 9000, 10500)
SPEEDS_M_S = (50, 75, 100, 125, 150, 175, 200, 225, 250)


def create_gui_batch_bundle(template: Path, destination: Path, *, include_10700: bool = False) -> Path:
    """GUI Batch analysis (2): use the already open project and its foil data.

    One valid xflPlanePolar per XML file; the GUI reads a directory, not a
    fabricated multi-polar root. Preserve every setting except name/speed/fluid.
    The alpha range is set in the GUI's T12 table, not these definition files.
    """
    root = ET.parse(template, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))).getroot()
    if root.tag.lower() != "xflplanepolar" or root.findtext("Polar/Type") != "FIXEDSPEEDPOLAR":
        raise ValueError("Expected an exported Flow5 T1 definition")
    if float(root.findtext("Units/ms_to_speed_unit")) != 1:
        raise ValueError("Template speed units must be m/s")
    for field in ("Polar/Polar_Name", "Polar/Plane_Name", "Polar/Fixed_Velocity",
                  "Polar/Fluid/Density", "Polar/Fluid/Viscosity"):
        if root.find(field) is None:
            raise ValueError(f"Missing template field: {field}")
    destination.mkdir(parents=True, exist_ok=False)
    for subdir in ("analyses_72" if not include_10700 else "analyses_81", "smoke_2"):
        (destination / subdir).mkdir()
    analyses = destination / ("analyses_81" if include_10700 else "analyses_72")
    shutil.copy2(template, destination / "original_template.xml")
    manifest = []
    for altitude in ALTITUDES_M + ((10700,) if include_10700 else ()):
        atmosphere = FlightConditions(altitude).atmosphere()
        t = atmosphere.temperature_k
        mu = 1.716e-5 * (t / 273.15)**1.5 * (273.15 + 110.4)/(t + 110.4)
        for speed in SPEEDS_M_S:
            name = f"T1_h{altitude:05d}_V{speed:03d}"
            copy = deepcopy(root)
            _set(copy, "Polar/Polar_Name", name)
            _set(copy, "Polar/Fixed_Velocity", speed)
            _set(copy, "Polar/Fluid/Density", f"{atmosphere.density_kg_m3:.10g}")
            _set(copy, "Polar/Fluid/Viscosity", f"{mu/atmosphere.density_kg_m3:.10g}")
            path = analyses / (name + ".xml")
            _write_xml(copy, path)
            if altitude in (0, 3000) and speed == 100:
                shutil.copy2(path, destination / "smoke_2" / path.name)
            manifest.append(dict(name=name, altitude_m=altitude, speed_m_s=speed,
                                 temperature_c=t-273.15, density_kg_m3=atmosphere.density_kg_m3,
                                 kinematic_viscosity_m2_s=mu/atmosphere.density_kg_m3,
                                 mach=speed/atmosphere.speed_of_sound_m_s,
                                 reliability="unreliable" if speed/atmosphere.speed_of_sound_m_s>0.65 else "accepted"))
    with (destination / "manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    (destination / "KULLANIM.txt").write_text(GUI_README, encoding="utf-8")
    return destination


GUI_README = '''FlightLab - mevcut Flow5 projesinde T1 toplu analiz

1. Mevcut .fl5 projenizi Flow5'te acin. Ucak ve hazir 2D polarlar projede kalsin.
   Bu paket icin profil koordinati veya 2D polar dosyasi disa aktarmaniz gerekmez.
2. Once projeyi farkli adla kaydedin; uretilen yeni polarlar bu kopyaya eklensin.
3. Ucak analiz modulunde "Batch analysis (2)" ekranini acin (Alt+F7).
   Bu menu/kisayol resmi main kaynak kodundan kontrol edildi; surumunuzde
   farkli gorunuyorsa pencere ekran goruntusunu paylasin.
4. Solda yalniz M-600-ThinSurf-acılar ucagini secin.
5. Analiz tarafindaki Actions > Change directory ile once smoke_2 klasorunu secin.
   Gerekirse Refresh list, sonra Select all. original_template.xml dosyasinin
   bulundugu ust klasoru secmeyin; yalniz analiz klasorunu secin.
6. T12 sekmesinde tek aktif alfa araligi tanimlayin:
       baslangic = -4 derece, bitis = 14 derece, adim = 0.25 derece.
   Bu aralik XML analiz taniminda yer almaz, batch penceresinde ayarlanir.
   Mevcut diger aktif T12 araliklarini kapatin ki ek noktalar eklenmesin.
7. Calculate. Once bu iki denemeyi kontrol edin: deniz seviyesi/100 m/s ve
   3000 m/100 m/s. Gercek sonuc satirlari, hiz, viskoz/solver ayarlari ve
   yakinsememe mesajlarini inceleyin. Ayni GUI T1 ile deniz seviyesi sonucunu
   karsilastirin. Bos polar veya kayip satirlar basari sayilmaz.
8. Deneme dogruysa Actions > Change directory ile analyses_72 (veya 81)
   klasorunu secin; Refresh list > Select all; ayni T12 araligiyla Calculate.
9. Sonuclari tum CSV satirlariyla, yakinsemeyen bolgelerin loglariyla ve
   manifest.csv ile birlikte paylasin. Hicbir yuksek-Mach verisi silinmedi.

Hizlar: 50,75,100,125,150,175,200,225,250 m/s.
Irtifalar: 0,1500,3000,4500,6000,7500,9000,10500 m (ISA ofseti 0 C).
Opsiyonel 81'lik pakette 10700 m de bulunur.
Alfa araligini degistirmeniz gerekiyorsa sonucu aktarirken belirtin.
ISA yogunlugu ve Sutherland kuru-hava viskozitesi manifestte yazilidir.

Orijinal XML ile sadece Polar_Name, Fixed_Velocity, Fluid/Density ve
Fluid/Viscosity alanlari farklidir. PROJECTED referans modu, Use_plane_inertia,
TRIUNIFORM, NCrit=8, From_CL=true, XFoil_OnTheFly=false, flap=0 ayarlari,
govde surtunmesi, ek surukleme ve wake ayarlari korunmustur. Sonuclarin mevcut
2D polar veri tabaninizin kapsamina sigdigini Flow5 loglarindan kontrol edin;
bu paket veri tabaninizi degistirmez veya yeniden uretmez.

Bu pakette tek bir birlesik XML yerine klasor icinde ayri analiz XML'leri var;
Flow5 Batch analysis (2) bunlari topluca okur. Komut satiri -s scripti DEGILDIR.
Bu ortamda Flow5 kurulu degil: solver calistirilmadi. XML/ayar/matris uretimi
test edildi; sizin surumunuzde gercek calisma iki analizlik denemeyle dogrulanir.

Kaynak kontrolu: techwinder/flow5 main:
flow5-app/modules/xplane/analysis/batchxmldlg.cpp (onAnalyze, onListDirAnalyses)
flow5-app/modules/xplane/menus/xplaneactions.cpp (Batch analysis (2), Alt+F7)
'''


def _write_xml(root: ET.Element, path: Path) -> None:
    ET.indent(root, space="    ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _set(root: ET.Element, path: str, value: object) -> None:
    node = root.find(path)
    if node is None:
        raise ValueError(f"Missing template field: {path}")
    node.text = str(value)


def create_batch_bundle(template: Path, geometry: Path, destination: Path, *,
                        include_10700: bool = False) -> Path:
    """Create a new bundle, refusing to overwrite any existing directory."""
    # Validate before creating outputs. Templates must be real T1 exports.
    root = ET.parse(template).getroot()
    plane = ET.parse(geometry).getroot()
    if root.tag.lower() != "xflplanepolar" or root.findtext("Polar/Type") != "FIXEDSPEEDPOLAR":
        raise ValueError("Expected a Flow5 T1 polar template")
    if root.findtext("Polar/Plane_Name") != plane.findtext("Plane/Name"):
        raise ValueError("Template and geometry plane names differ")
    if root.findtext("Polar/Viscous_Analysis/XFoil_OnTheFly").lower() != "false":
        raise ValueError("This bundle workflow requires the supplied interpolated-viscous template")
    for path in ("Polar/Fixed_Velocity", "Polar/Fluid/Density", "Polar/Fluid/Viscosity",
                 "Polar/Reference_Dimensions/Reference_Dimensions", "Polar/Use_plane_inertia"):
        if root.find(path) is None:
            raise ValueError(f"Missing template field: {path}")
    # The provided reference/inertia values are retained in their source units.
    if float(root.findtext("Units/ms_to_speed_unit")) != 1:
        raise ValueError("This generator currently requires speed values in m/s")
    foils = sorted({node.text.strip() for node in plane.findall(".//Left_Side_FoilName") +
                    plane.findall(".//Right_Side_FoilName") if node.text})
    destination.mkdir(parents=True, exist_ok=False)
    for directory in ("analyses", "templates", "planes", "foils", "foil_polars", "scripts", "results"):
        (destination / directory).mkdir()
    shutil.copy2(template, destination / "templates" / "T1-original.xml")
    shutil.copy2(geometry, destination / "planes" / "aircraft.xml")
    assets = [{"filename": f"foil_{i:02}.dat", "required_internal_name": name}
              for i, name in enumerate(foils, 1)]
    rows = []
    altitudes = ALTITUDES_M + ((10700,) if include_10700 else ())
    for altitude in altitudes:
        atmosphere = FlightConditions(altitude).atmosphere()
        # Sutherland dry-air viscosity (SI); no guessed density/altitude scaling.
        temperature = atmosphere.temperature_k
        mu = 1.716e-5 * (temperature / 273.15)**1.5 * (273.15 + 110.4) / (temperature + 110.4)
        nu = mu / atmosphere.density_kg_m3
        for speed in SPEEDS_M_S:
            name = f"T1_h{altitude:05d}_V{speed:03d}"
            analysis = deepcopy(root)
            _set(analysis, "Polar/Polar_Name", name)
            _set(analysis, "Polar/Fixed_Velocity", speed)
            _set(analysis, "Polar/Fluid/Density", f"{atmosphere.density_kg_m3:.10g}")
            _set(analysis, "Polar/Fluid/Viscosity", f"{nu:.10g}")
            # Script executor may not derive PROJECTED references automatically.
            # Pin the exact reference values already exported by the GUI.
            _set(analysis, "Polar/Reference_Dimensions/Reference_Dimensions", "CUSTOM")
            # Pin the user's exported mass/CG/inertia, rather than recomputing
            # them from geometry that may not carry all 3D foil information.
            _set(analysis, "Polar/Use_plane_inertia", "false")
            _write_xml(analysis, destination / "analyses" / f"{name}.xml")
            rows.append(dict(name=name, altitude_m=altitude, speed_m_s=speed,
                             temperature_c=temperature-273.15, density_kg_m3=atmosphere.density_kg_m3,
                             kinematic_viscosity_m2_s=nu, mach=speed/atmosphere.speed_of_sound_m_s,
                             trust="unreliable" if speed/atmosphere.speed_of_sound_m_s > 0.65 else "accepted"))
    with (destination / "manifest.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (destination / "required-assets.json").write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
    for mode, names in (("smoke", ["T1_h00000_V100", "T1_h03000_V100"]),
                        ("full", [row["name"] for row in rows])):
        script = ET.Element("xflscript", version="1.0")
        metadata = ET.SubElement(script, "Metadata")
        for tag, value in (("make_project_file", "true"), ("project_file_name", f"FlightLab_{mode}.fl5"),
                           ("polar_text_output_format", "csv"), ("Double_Precision", "true")):
            ET.SubElement(metadata, tag).text = value
        directories = ET.SubElement(metadata, "Directories")
        for tag, directory in (("output_dir", "results"), ("plane_definition_xml_dir", "planes"),
                               ("plane_analysis_xml_dir", "analyses"), ("foil_files_dir", "foils"),
                               ("xfoil_polars_dir", "foil_polars")):
            ET.SubElement(directories, tag).text = f"__BUNDLE_ROOT__/{directory}"
        ET.SubElement(directories, "recursive_scan").text = "false"
        threading = ET.SubElement(metadata, "MultiThreading")
        for tag, value in (("Allow_Multithreading", "true"), ("max_threads", "2"), ("Thread_Priority", "Normal")):
            ET.SubElement(threading, tag).text = value
        run = ET.SubElement(script, "Plane_analysis")
        output = ET.SubElement(run, "Plane_Analysis_Output")
        for tag, value in (("make_polars_text_file", "true"), ("make_oppoints", "false"),
                           ("make_oppoints_text_file", "false"), ("Compute_derivatives", "false")):
            ET.SubElement(output, tag).text = value
        files = ET.SubElement(run, "Foil_Dat_Files")
        for asset in assets:
            ET.SubElement(files, "Foil_File_Name").text = asset["filename"]
        planes = ET.SubElement(run, "Plane_Definition_Files")
        ET.SubElement(planes, "Plane_File_Name").text = "aircraft.xml"
        analyses = ET.SubElement(run, "Plane_Analysis_Files")
        for name in names:
            ET.SubElement(analyses, "Analysis_File_Name").text = f"{name}.xml"
        sweep = ET.SubElement(run, "Plane_Analysis_Data")
        ET.SubElement(sweep, "T12_Range").text = "-4, 14, 0.25"
        _write_xml(script, destination / "scripts" / f"{mode}.template.xml")
    (destination / "prepare.py").write_text(PREPARE_SCRIPT, encoding="utf-8")
    (destination / "README.txt").write_text(BUNDLE_README, encoding="utf-8")
    return destination


PREPARE_SCRIPT = '''"""Resolve local paths; check required assets. Does not run Flow5."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
assets = json.loads((root / "required-assets.json").read_text(encoding="utf-8"))
errors = []
for asset in assets:
    path = root / "foils" / asset["filename"]
    if not path.is_file():
        errors.append("Missing " + str(path) + " : " + asset["required_internal_name"])
    else:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        if not lines or lines[0].strip() != asset["required_internal_name"]:
            errors.append("Airfoil internal name mismatch: " + str(path))
if not list((root / "foil_polars").glob("*.txt")):
    errors.append("Missing exported XFoil-format 2D polar .txt files in foil_polars/")
if errors:
    raise SystemExit("\\n".join(errors))
for mode in ("smoke", "full"):
    tree = ET.parse(root / "scripts" / (mode + ".template.xml"))
    for node in tree.getroot().iter():
        if node.text and node.text.startswith("__BUNDLE_ROOT__/"):
            node.text = (root / node.text.split("/", 1)[1]).as_posix()
    path = root / "scripts" / (mode + ".xml")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("Prepared:", path)
print("Asset presence checked, not Reynolds/alpha coverage or solver compatibility.")
print("Run smoke first. Exit code zero alone does not establish solver success.")
'''

BUNDLE_README = '''FlightLab Flow5 batch input bundle (not solver-validated)

1. Put the original airfoil .dat files in foils/ using required-assets.json.
   The first-line internal foil names must match exactly. Preserve the original
   profiles; do not substitute similarly named NACA profiles.
2. Put existing 2D foil polars exported in XFoil text format (.txt) in
   foil_polars/. Preserve NCrit=8, transition and original profile definitions.
   Re and local CL coverage must span the requested matrix, including tails/tips.
3. Run: python prepare.py  (on Windows: py prepare.py)
4. Use your installed Flow5: flow5 -s "<bundle>/scripts/smoke.xml"
   The executable may need its full path. Check version with flow5 --version.
5. Inspect logs and the two resulting polar tables: h00000/V100 and h03000/V100.
   Both must contain new, nonempty results with the expected plane/polar names,
   constant speed, intended fluid properties and preserved drag settings.
   Compare h00000/V100 with the same analysis in the GUI before running full.xml.
6. Only after that comparison run: flow5 -s "<bundle>/scripts/full.xml"

No actual Flow5 execution was possible in the generating workspace.
Runtime, platform and solver version compatibility are unverified.
The generator retains all source settings except: names, speed and ISA fluid
properties; references are pinned CUSTOM to their exported values; inertia is
pinned to the supplied explicit block (Use_plane_inertia=false). Reference
numbers and inertia block values themselves are preserved. Templates are kept.
ISA density uses the pressure-altitude profile; viscosity uses Sutherland's law.
Alpha sweep is -4 to 14 deg, step 0.25 deg, including unsuccessful regions.
Failed points must be reported, not filled or silently discarded.
Mach>0.65 points remain requested and are marked unreliable in manifest.csv.

With XFoil_OnTheFly=false, the geometry and polar XML alone are insufficient.
This package does not synthesize missing airfoil coordinates or 2D polar data.
Two-dimensional foil generation is intentionally not combined with this 3D run.
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--gui", action="store_true", help="Use existing project through GUI Batch analysis (2)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-10700", action="store_true")
    args = parser.parse_args()
    if args.gui:
        create_gui_batch_bundle(args.template, args.output, include_10700=args.include_10700)
    else:
        if args.geometry is None:
            parser.error("--geometry is required for the standalone workflow")
        create_batch_bundle(args.template, args.geometry, args.output, include_10700=args.include_10700)


if __name__ == "__main__":
    main()
