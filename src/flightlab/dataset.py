"""Read multi-polar exports and a manifest, preserving data and reporting gaps.

ZIP contents are read in memory, never extracted. A missing log is acceptable;
only observed rows are used, and absent alpha points are never fabricated.
"""

import csv
from dataclasses import asdict, dataclass, field
from io import StringIO
from math import isfinite, sqrt
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from .flow5 import Flow5Polar, parse_flow5_csv


@dataclass(frozen=True)
class AeroReference:
    area_m2: float
    chord_m: float

    def __post_init__(self):
        if any(not isfinite(v) or v <= 0 for v in (self.area_m2, self.chord_m)):
            raise ValueError("Aerodynamic reference area/chord must be finite and positive")

    @classmethod
    def from_flow5_template(cls, path: str | Path) -> "AeroReference":
        root = ET.parse(path).getroot()
        required = ("Units/m2_to_area_unit", "Units/meter_to_length_unit",
                    "Polar/Reference_Dimensions/Reference_Area", "Polar/Reference_Dimensions/Reference_Chord_Length")
        if any(root.findtext(key) is None for key in required):
            raise ValueError("Reference XML lacks explicit area/chord values or unit multipliers")
        area_scale = float(root.findtext("Units/m2_to_area_unit"))
        length_scale = float(root.findtext("Units/meter_to_length_unit"))
        area = float(root.findtext("Polar/Reference_Dimensions/Reference_Area")) * area_scale
        chord = float(root.findtext("Polar/Reference_Dimensions/Reference_Chord_Length")) * length_scale
        return cls(area, chord)


@dataclass(frozen=True)
class AnalysisCondition:
    name: str
    altitude_m: float
    speed_m_s: float
    temperature_c: float
    density_kg_m3: float
    nu_m2_s: float

    def __post_init__(self):
        values = (self.altitude_m, self.speed_m_s, self.temperature_c, self.density_kg_m3, self.nu_m2_s)
        if not self.name or not all(map(isfinite, values)):
            raise ValueError("Manifest requires names and finite physical values")
        if min(self.speed_m_s, self.density_kg_m3, self.nu_m2_s) <= 0 or self.temperature_c <= -273.15:
            raise ValueError("Invalid manifest speed, density, viscosity or temperature")

    @property
    def mach(self) -> float:
        return self.speed_m_s / sqrt(1.4 * 287.05287 * (self.temperature_c + 273.15))


@dataclass
class PolarRun:
    filename: str
    condition: AnalysisCondition
    polar: Flow5Polar
    issues: list[str] = field(default_factory=list)
    usable: bool = True
    missing_alpha_deg: list[float] = field(default_factory=list)


@dataclass
class PolarDataset:
    manifest: dict[str, AnalysisCondition]
    runs: list[PolarRun]
    file_errors: dict[str, str]
    unmatched_files: list[str]

    def report(self) -> dict:
        found = {run.condition.name for run in self.runs}
        return {
            "expected_polars": len(self.manifest), "matched_polars": len(self.runs),
            "usable_polars": sum(run.usable for run in self.runs),
            "total_observed_points": sum(len(run.polar.points) for run in self.runs),
            "missing_polars": sorted(set(self.manifest) - found),
            "file_errors": self.file_errors, "unmatched_files": self.unmatched_files,
            "runs": [{"name": run.condition.name, "filename": run.filename, "usable": run.usable,
                      "points": len(run.polar.points), "issues": run.issues,
                      "missing_alpha_deg": run.missing_alpha_deg,
                      "condition": asdict(run.condition)} for run in self.runs],
        }


def parse_manifest(text: str) -> dict[str, AnalysisCondition]:
    result = {}
    for row in csv.DictReader(StringIO(text.lstrip("\ufeff"))):
        # Both previously generated manifest variants are supported.
        nu = row.get("nu_m2_s") or row.get("kinematic_viscosity_m2_s")
        if nu is None:
            raise ValueError("Manifest requires nu_m2_s or kinematic_viscosity_m2_s")
        condition = AnalysisCondition(row["name"].strip(), float(row["altitude_m"]), float(row["speed_m_s"]),
                                      float(row["temperature_c"]), float(row["density_kg_m3"]), float(nu))
        if condition.name in result:
            raise ValueError(f"Duplicate manifest analysis: {condition.name}")
        result[condition.name] = condition
    if not result:
        raise ValueError("Manifest contains no analysis rows")
    return result


def load_dataset(results: str | Path, manifest: str | Path | None = None, *,
                 expected_plane: str | None = None) -> PolarDataset:
    """Inspect a result directory or ZIP, including nested directories.

    Incorrect files stay in the original input; the report identifies why they
    cannot be used for fitting. High Mach never makes a run unusable.
    """
    results = Path(results)
    files: dict[str, str] = {}
    file_errors: dict[str, str] = {}
    if results.is_dir():
        sources = ((str(p.relative_to(results)), p) for p in sorted(results.rglob("*"))
                   if p.is_file() and p.suffix.lower() == ".csv")
        for name, path in sources:
            try:
                files[name] = path.read_text(encoding="utf-8-sig")
            except (UnicodeError, OSError) as error:
                file_errors[name] = str(error)
    else:
        with ZipFile(results) as archive:
            entries = sorted((i for i in archive.infolist() if i.filename.lower().endswith(".csv") and not i.is_dir()),
                             key=lambda i: i.filename)
            if sum(i.file_size for i in entries) > 128 * 1024**2:
                raise ValueError("Uncompressed CSV bundle exceeds 128 MiB")
            for info in entries:
                if info.filename in files:
                    raise ValueError(f"Duplicate ZIP member: {info.filename}")
                try:
                    files[info.filename] = archive.read(info).decode("utf-8-sig")
                except (UnicodeError, OSError, BadZipFile, RuntimeError) as error:
                    file_errors[info.filename] = str(error)
    if manifest is None:
        manifests = [name for name in files if Path(name).name.lower() == "manifest.csv"]
        if len(manifests) != 1:
            raise ValueError("Provide one manifest.csv in the bundle or an explicit manifest path")
        manifest_text = files[manifests[0]]
    else:
        manifest_text = Path(manifest).read_text(encoding="utf-8-sig")
    conditions = parse_manifest(manifest_text)
    runs: list[PolarRun] = []
    unmatched = []
    by_name: dict[str, list[PolarRun]] = {}
    for filename, text in files.items():
        if Path(filename).name.lower() == "manifest.csv":
            continue
        try:
            polar = parse_flow5_csv(text)
        except ValueError as error:
            file_errors[filename] = str(error)
            continue
        names = {line.strip() for line in polar.metadata_lines if line.strip() in conditions}
        if len(names) != 1:
            unmatched.append(filename)
            continue
        name = names.pop()
        condition = conditions[name]
        run = PolarRun(filename, condition, polar)
        if expected_plane is not None and (not polar.metadata_lines or polar.metadata_lines[0] != expected_plane):
            run.usable = False
            run.issues.append("Aircraft name does not match selected aircraft")
        if any(abs(p["V (m/s)"] - condition.speed_m_s) > max(0.02, condition.speed_m_s * 1e-4)
               for p in polar.points):
            run.usable = False
            run.issues.append("CSV speed differs from fixed-speed manifest; wrong analysis or export")
        if any(p["CD"] <= 0 for p in polar.points):
            run.usable = False
            run.issues.append("Nonpositive total CD cannot be fitted")
        if len({p["Ctrl"] for p in polar.points}) != 1:
            run.usable = False
            run.issues.append("Mixed control configurations in one polar")
        if condition.mach > 0.65:
            run.issues.append("Source Mach exceeds trusted 0.65; retained with warning")
        observed = {round(p["α (°)"], 6) for p in polar.points}
        expected = {round(-4 + i * 0.25, 6) for i in range(73)}
        missing = sorted(expected - observed)
        run.missing_alpha_deg = missing
        if missing:
            run.issues.append(f"{len(missing)} alpha points absent from requested -4:0.25:14 sweep; no values filled")
        if len(observed) != len(polar.points):
            run.issues.append("Repeated alpha points; source rows retained")
        if any(not isfinite(v) for p in polar.points for v in p.values()):
            run.issues.append("Undefined auxiliary values retained; core CL/CD/Cm/speed remain finite")
        runs.append(run)
        by_name.setdefault(name, []).append(run)
    for name, duplicates in by_name.items():
        if len(duplicates) > 1:
            for run in duplicates:
                run.usable = False
                run.issues.append("Duplicate export for this manifest name; select one before fitting")
    return PolarDataset(conditions, runs, file_errors, unmatched)
