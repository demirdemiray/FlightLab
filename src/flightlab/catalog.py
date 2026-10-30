"""Independent aircraft/engine records selected by stable IDs.

Aircraft mass properties belong to a named loading condition. Selecting an
engine does not silently change that condition or recompute its CG/inertia.
"""

from dataclasses import dataclass
import json
from math import isfinite, sqrt
from pathlib import Path

from .jet import JetEngine, read_jet_column_output, validate_thrust_factor
from .rpm import ReferenceRpmEngine, read_reference_rpm_engine
from .mission import FlightLimits, FuelPlan, MissionRequirements
from .flow5 import read_flow5_csv
from .performance import TabulatedPolar, ScaledDragPolar, validate_drag_factor


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class MassProperties:
    loading_condition: str
    mass_kg: float
    cg_m: tuple[float, float, float]
    ixx_kg_m2: float
    iyy_kg_m2: float
    izz_kg_m2: float
    ixz_kg_m2: float
    ixy_kg_m2: float | None
    iyz_kg_m2: float | None
    inertia_convention: str
    source: str

    def __post_init__(self):
        for name in ("mass_kg", "ixx_kg_m2", "iyy_kg_m2", "izz_kg_m2"):
            if _finite(getattr(self, name), name) <= 0:
                raise ValueError(f"{name} must be positive")
        if len(self.cg_m) != 3:
            raise ValueError("CG must have three coordinates")
        for coordinate in self.cg_m:
            _finite(coordinate, "CG coordinate")
        _finite(self.ixz_kg_m2, "Ixz")
        for value in (self.ixy_kg_m2, self.iyz_kg_m2):
            if value is not None:
                _finite(value, "cross inertia")


@dataclass(frozen=True)
class AerodynamicAssumptions:
    control_mode: str
    trim_drag_policy: str
    elevator_deflection_deg: float | None = None


@dataclass(frozen=True)
class AircraftRecord:
    id: str
    name: str
    geometry_file: Path
    polar_files: tuple[Path, ...]
    mass_properties: MassProperties
    notes: str
    reference_fuel_kg: float | None = None
    limits: FlightLimits | None = None
    aerodynamic_assumptions: AerodynamicAssumptions | None = None
    performance_polar_file: Path | None = None
    polar_metadata_file: Path | None = None
    mission_requirements: MissionRequirements | None = None

    def aerodynamic_model(self) -> TabulatedPolar:
        if self.performance_polar_file is None:
            raise ValueError("No performance polar selected")
        source = read_flow5_csv(self.performance_polar_file)
        if self.limits is not None and self.limits.trusted_aerodynamic_mach is not None:
            if self.polar_metadata_file is None:
                raise ValueError("Source temperature is required to assess aerodynamic Mach")
            metadata = json.loads(self.polar_metadata_file.read_text(encoding="utf-8"))
            temperature = _finite(metadata["reported_temperature_c"], "source temperature") + 273.15
            if temperature <= 0:
                raise ValueError("Source temperature must be above absolute zero")
            return source.drag_polar(trusted_mach=self.limits.trusted_aerodynamic_mach,
                                     speed_of_sound_m_s=sqrt(1.4 * 287.05287 * temperature))
        return source.drag_polar()

    def fuel_plan(self, initial_fuel_kg: float, reserve_fuel_kg: float) -> FuelPlan:
        if self.reference_fuel_kg is None:
            raise ValueError("Reference loading fuel must be specified")
        nonfuel = self.mass_properties.mass_kg - self.reference_fuel_kg
        return FuelPlan(nonfuel, initial_fuel_kg, reserve_fuel_kg)


@dataclass(frozen=True)
class EngineRecord:
    id: str
    name: str
    propulsion_kind: str
    performance_data_file: Path | None
    notes: str
    performance_format: str | None = None
    altitude_unit: str | None = None
    rpm_data_file: Path | None = None
    fuel_source: str = "column_output"
    continuous_max_krpm: float | None = None
    performance_operating_regime: str | None = None

    def __post_init__(self):
        if self.propulsion_kind not in {"jet", "electric_propeller", "fuel_propeller"}:
            raise ValueError(f"Unsupported propulsion kind: {self.propulsion_kind}")
        if self.fuel_source not in {"column_output", "rpm_graph"}:
            raise ValueError(f"Unsupported fuel source: {self.fuel_source}")
        if self.fuel_source == "rpm_graph" and self.rpm_data_file is None:
            raise ValueError("Graph fuel source requires RPM graph data")
        if self.continuous_max_krpm is not None:
            if _finite(self.continuous_max_krpm, "continuous_max_krpm") <= 0:
                raise ValueError("Continuous RPM limit must be positive")


@dataclass(frozen=True)
class FlightConfiguration:
    aircraft: AircraftRecord
    engine: EngineRecord
    thrust_factor: float = 1.0
    drag_factor: float = 1.0
    # Compatibility and loading must be reviewed before performance simulation.
    # Catalog selection alone does not establish either.

    def __post_init__(self):
        validate_thrust_factor(self.thrust_factor)
        validate_drag_factor(self.drag_factor)

    def aerodynamic_model(self) -> ScaledDragPolar:
        return ScaledDragPolar(self.aircraft.aerodynamic_model(), self.drag_factor)

    def jet_model(self) -> JetEngine | ReferenceRpmEngine:
        """Return the selected calculation model, never silently fall back.

        Graph fuel is RPM-based. Until a flight-condition/RPM mapping exists,
        it cannot supply altitude/Mach queries from the old column-output map.
        """
        if self.engine.fuel_source == "rpm_graph":
            return self.reference_rpm_model()
        return self.source_jet_map_model()

    def source_jet_map_model(self) -> JetEngine:
        """Raw column-output model for source inspection, not a fuel override."""
        if (self.engine.propulsion_kind != "jet" or
                self.engine.performance_format != "jet_column_output" or
                self.engine.performance_data_file is None or
                self.engine.altitude_unit is None):
            raise ValueError("Engine lacks a supported jet performance map")
        return JetEngine(read_jet_column_output(self.engine.performance_data_file,
                         altitude_unit=self.engine.altitude_unit), self.thrust_factor)

    def reference_rpm_model(self) -> ReferenceRpmEngine:
        if self.engine.propulsion_kind != "jet" or self.engine.rpm_data_file is None:
            raise ValueError("Engine lacks reference RPM data")
        return read_reference_rpm_engine(self.engine.rpm_data_file, thrust_factor=self.thrust_factor,
                                         continuous_max_krpm=self.engine.continuous_max_krpm)


@dataclass
class Catalog:
    aircraft: dict[str, AircraftRecord]
    engines: dict[str, EngineRecord]

    def select(self, aircraft_id: str, engine_id: str, *, thrust_factor: float = 1.0,
               drag_factor: float = 1.0) -> FlightConfiguration:
        return FlightConfiguration(self.aircraft[aircraft_id], self.engines[engine_id], thrust_factor, drag_factor)


def _unique_insert(records: dict, record) -> None:
    if not record.id.strip() or record.id in records:
        raise ValueError(f"Empty or duplicate catalog ID: {record.id!r}")
    records[record.id] = record


def load_catalog(path: str | Path) -> Catalog:
    """Load a catalog, resolving asset paths relative to its JSON file."""
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported catalog schema version")

    def asset(value: str) -> Path:
        resolved = (path.parent / value).resolve()
        if not resolved.is_file():
            raise ValueError(f"Catalog asset does not exist: {value}")
        return resolved

    aircraft: dict[str, AircraftRecord] = {}
    engines: dict[str, EngineRecord] = {}
    for entry in data["aircraft"]:
        properties = dict(entry["mass_properties"])
        properties["cg_m"] = tuple(properties["cg_m"])
        record = AircraftRecord(
            entry["id"], entry["name"], asset(entry["geometry_file"]),
            tuple(asset(p) for p in entry["polar_files"]),
            MassProperties(**properties), entry.get("notes", ""),
            entry.get("reference_fuel_kg"),
            FlightLimits(**entry["limits"]) if entry.get("limits") else None,
            AerodynamicAssumptions(**entry["aerodynamic_assumptions"])
            if entry.get("aerodynamic_assumptions") else None,
            asset(entry["performance_polar_file"]) if entry.get("performance_polar_file") else None,
            asset(entry["polar_metadata_file"]) if entry.get("polar_metadata_file") else None,
            MissionRequirements(**entry["mission_requirements"]) if entry.get("mission_requirements") else None,
        )
        _unique_insert(aircraft, record)
    for entry in data["engines"]:
        record = EngineRecord(
            entry["id"], entry["name"], entry["propulsion_kind"],
            asset(entry["performance_data_file"]) if entry.get("performance_data_file") else None,
            entry.get("notes", ""),
            entry.get("performance_format"), entry.get("altitude_unit"),
            asset(entry["rpm_data_file"]) if entry.get("rpm_data_file") else None,
            entry.get("fuel_source", "column_output"),
            entry.get("continuous_max_krpm"),
            entry.get("performance_operating_regime"),
        )
        _unique_insert(engines, record)
    return Catalog(aircraft, engines)
