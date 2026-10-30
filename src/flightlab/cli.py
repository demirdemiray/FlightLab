"""Small command-line interface; frontend-independent JSON outputs."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from zipfile import BadZipFile

from .dataset import AeroReference, load_dataset


def _output(result: dict, path: str | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text+"\n", encoding="utf-8")
    else:
        print(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="FlightLab aircraft performance tools (SI inputs)")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Audit a polar ZIP/directory and manifest; no batch log required")
    query = sub.add_parser("query", help="Fit/query a CL-Re-Mach polar family inside its data domain")
    for command in (inspect, query):
        command.add_argument("results", help="Results ZIP or directory")
        command.add_argument("--manifest", help="Explicit manifest; otherwise read from results")
        command.add_argument("--plane", help="Expected aircraft name in CSV headers")
        command.add_argument("--report", help="Write JSON here instead of stdout")
    inspect.add_argument("--fit-check", action="store_true")
    inspect.add_argument("--reference-template", help="Flow5 XML containing explicit coefficient reference dimensions")
    inspect.add_argument("--strict", action="store_true", help="Nonzero exit for any missing/unusable expected polar")
    query.add_argument("--reference-template", required=True)
    query.add_argument("--cl", type=float, required=True)
    query.add_argument("--speed", type=float, required=True, help="TAS m/s")
    query.add_argument("--altitude", type=float, default=0)
    query.add_argument("--temperature", type=float, help="Actual local temperature C; otherwise ISA")
    query.add_argument("--drag-factor", type=float, default=1)
    preview = sub.add_parser("preview", help="Experimental steady snapshots from the reference T2/RPM models")
    preview.add_argument("--catalog", default="data/catalog.json")
    preview.add_argument("--aircraft", default="m600-thinsurf-acilar")
    preview.add_argument("--engine", default="amt-titan-392n")
    preview.add_argument("--fuel", type=float, default=12)
    preview.add_argument("--reserve", type=float, default=2, help="Preview-only default; user-selected per mission")
    preview.add_argument("--altitude", type=float, default=0)
    preview.add_argument("--temperature", type=float)
    preview.add_argument("--drag-factor", type=float, default=1)
    preview.add_argument("--thrust-factor", type=float, default=1)
    preview.add_argument("--reference-template", default="data/analysis-templates/T1-user-template.xml")
    preview.add_argument("--report")
    args = parser.parse_args(argv)
    try:
        if args.command in {"inspect", "query"}:
            dataset = load_dataset(args.results, args.manifest, expected_plane=args.plane)
            if args.command == "inspect":
                result = dataset.report()
                if args.fit_check:
                    if not args.reference_template:
                        parser.error("--fit-check needs --reference-template")
                    from .interpolation import PolarFamily
                    try:
                        model = PolarFamily(dataset, AeroReference.from_flow5_template(args.reference_template))
                        result["fit_check"] = {"status": "built", **model.summary()}
                    except ValueError as error:
                        result["fit_check"] = {"status": "failed", "reason": str(error)}
                _output(result, args.report)
                incomplete = (result["file_errors"] or result["missing_polars"] or
                              result["usable_polars"] != result["expected_polars"])
                bad_fit = result.get("fit_check", {}).get("status") == "failed"
                return 2 if bad_fit or (args.strict and incomplete) else 0
            from .interpolation import PolarFamily
            from .mission import FlightConditions
            model = PolarFamily(dataset, AeroReference.from_flow5_template(args.reference_template),
                                drag_factor=args.drag_factor)
            result = model.at_flight(args.cl, args.speed, FlightConditions(args.altitude, args.temperature))
            _output({"query": asdict(result), "dataset": dataset.report()}, args.report)
            return 0
        from .catalog import load_catalog
        from .flow5 import read_flow5_csv
        from .mission import FlightConditions
        from .models import ReferenceEngineModel, ReferencePolarModel
        from .steady import search_level_speed
        configuration = load_catalog(args.catalog).select(args.aircraft, args.engine,
                                                          drag_factor=args.drag_factor, thrust_factor=args.thrust_factor)
        aircraft = configuration.aircraft
        if aircraft.performance_polar_file is None or aircraft.polar_metadata_file is None or aircraft.limits is None:
            raise ValueError("Aircraft lacks reference polar metadata/limits")
        metadata = json.loads(aircraft.polar_metadata_file.read_text(encoding="utf-8"))
        temperature = metadata["reported_temperature_c"]+273.15
        source_sound = (1.4*287.05287*temperature)**0.5
        aero = ReferencePolarModel(read_flow5_csv(aircraft.performance_polar_file),
                                   drag_factor=args.drag_factor, source_sound_speed_m_s=source_sound)
        engine = ReferenceEngineModel(configuration.reference_rpm_model())
        plan = aircraft.fuel_plan(args.fuel, args.reserve)
        reference = AeroReference.from_flow5_template(args.reference_template)
        points = {}
        for objective in ("maximum_speed", "minimum_fuel_flow", "maximum_specific_range"):
            try:
                points[objective] = asdict(search_level_speed(objective=objective, mass_kg=plan.initial_mass_kg,
                    conditions=FlightConditions(args.altitude, args.temperature), limits=aircraft.limits,
                    reference=reference, aero=aero, engine=engine,
                    speed_bounds=(max(1, aircraft.limits.min_groundspeed_m_s), aircraft.limits.max_true_airspeed_m_s)))
            except ValueError as error:
                points[objective] = {"status": "unavailable", "reason": str(error)}
        _output({"classification": "experimental_reference_models_not_validated_aircraft_predictions",
                 "mass_kg": plan.initial_mass_kg, "fuel_kg": args.fuel, "reserve_kg": args.reserve,
                 "scope": "Fixed-mass level-flight snapshots, not integrated range/endurance or A-B optimization",
                 "warnings": ["Reference T2 transfer; Reynolds/Mach variation not independently modelled",
                              "Engine reference curves lack altitude/Mach corrections"],
                 "candidates": points}, args.report)
        return 0
    except (ValueError, OSError, KeyError, BadZipFile) as error:
        print(f"FlightLab: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
