"""Level-flight snapshots and bounded candidate speed searches.

Thrust is assumed parallel to airspeed; extra trim drag is neglected as agreed.
Optimized snapshots are not a mission range/endurance prediction.
"""

from dataclasses import dataclass
from math import isfinite

import numpy as np
from scipy.optimize import minimize_scalar

from .dataset import AeroReference
from .mission import FlightConditions, FlightLimits
from .models import AerodynamicModel, FlightEngine


@dataclass(frozen=True)
class SteadyPoint:
    speed_m_s: float
    mass_kg: float
    cl: float
    cd: float
    alpha_deg: float
    drag_n: float
    useful_power_w: float
    krpm: float
    fuel_flow_kg_s: float
    specific_range_m_kg: float
    mach: float
    warnings: tuple[str, ...]


def level_point(mass_kg: float, speed_m_s: float, conditions: FlightConditions,
                limits: FlightLimits, reference: AeroReference,
                aero: AerodynamicModel, engine: FlightEngine) -> SteadyPoint:
    air = conditions.atmosphere()
    cl = limits.check_level_flight(mass_kg, reference.area_m2, speed_m_s, air)
    coefficients = aero.at_flight(cl, speed_m_s, conditions)
    drag = 0.5 * air.density_kg_m3 * speed_m_s**2 * reference.area_m2 * coefficients.cd
    if not isfinite(drag) or drag <= 0:
        raise ValueError("Steady flight requires positive finite drag")
    rpm = engine.krpm_for_thrust(drag, speed_m_s, conditions)
    output = engine.at_flight(rpm, speed_m_s, conditions)
    if abs(output.thrust_n-drag) > max(1e-5, drag*1e-5):
        raise ValueError("Engine inverse does not balance required thrust")
    if not isfinite(output.fuel_flow_kg_s) or output.fuel_flow_kg_s <= 0:
        raise ValueError("A powered steady point requires positive finite fuel flow")
    warnings = tuple(dict.fromkeys(coefficients.warnings + output.warnings +
                                   limits.aerodynamic_warnings(speed_m_s, air)))
    return SteadyPoint(speed_m_s, mass_kg, cl, coefficients.cd, coefficients.alpha_deg,
                       drag, drag*speed_m_s, rpm, output.fuel_flow_kg_s,
                       speed_m_s/output.fuel_flow_kg_s, speed_m_s/air.speed_of_sound_m_s, warnings)


@dataclass(frozen=True)
class SpeedSearch:
    objective: str
    point: SteadyPoint
    grid_points: int
    feasible_grid_points: int
    bounds_m_s: tuple[float, float]
    note: str = "Bounded numerical candidate search; not a proof of a global optimum or a mission prediction"
    limiting_condition: str | None = None
    infeasible_reasons: tuple[str, ...] = ()


def search_level_speed(*, objective: str, mass_kg: float, conditions: FlightConditions,
                        limits: FlightLimits, reference: AeroReference, aero: AerodynamicModel,
                        engine: FlightEngine, speed_bounds: tuple[float, float], grid_points: int = 151) -> SpeedSearch:
    if objective not in {"maximum_speed", "maximum_specific_range", "minimum_fuel_flow"}:
        raise ValueError("Unknown level-flight speed objective")
    low, high = speed_bounds
    if not all(map(isfinite, speed_bounds)) or not 0 < low < high or grid_points < 5:
        raise ValueError("Provide positive ordered speed bounds and at least five grid points")
    low, high = max(low, limits.min_groundspeed_m_s), min(high, limits.max_true_airspeed_m_s)
    if low >= high:
        raise ValueError("Search bounds do not overlap the operational speed envelope")
    cache: dict[float, SteadyPoint | None] = {}
    failures: dict[float, str] = {}

    def evaluate(speed: float) -> SteadyPoint | None:
        speed = float(speed)
        if speed not in cache:
            try:
                cache[speed] = level_point(mass_kg, speed, conditions, limits, reference, aero, engine)
            except ValueError as error:
                cache[speed] = None
                failures[speed] = str(error)
        return cache[speed]

    def score(point: SteadyPoint) -> float:
        if objective == "maximum_speed":
            return -point.speed_m_s
        if objective == "maximum_specific_range":
            return -point.specific_range_m_kg
        return point.fuel_flow_kg_s

    speeds = np.linspace(low, high, grid_points)
    points = [evaluate(v) for v in speeds]
    feasible_count = sum(p is not None for p in points)
    if not feasible_count:
        reasons = "; ".join(sorted(set(failures.values())))
        raise ValueError("No feasible level-flight points in requested bounds/models: " + reasons)
    # Refine every sampled feasible/infeasible boundary. Missing coverage is a
    # boundary too; do not extrapolate to force a larger speed result.
    for a, b, pa, pb in zip(speeds, speeds[1:], points, points[1:]):
        if (pa is None) == (pb is None):
            continue
        valid, invalid = (a, b) if pa else (b, a)
        for _ in range(28):
            middle = (valid+invalid)/2
            if evaluate(middle) is None:
                invalid = middle
            else:
                valid = middle
    if objective != "maximum_speed":
        for i in range(1, len(points)-1):
            a, point, b = points[i-1:i+2]
            if a is None or point is None or b is None:
                continue
            if score(point) <= min(score(a), score(b)):
                def scalar(speed):
                    p = evaluate(speed)
                    return score(p) if p else float("inf")
                minimize_scalar(scalar, bounds=(speeds[i-1], speeds[i+1]), method="bounded",
                                options={"xatol": 1e-4})
    best = min((p for p in cache.values() if p is not None), key=score)
    limiting = None
    if objective == "maximum_speed":
        available = engine.at_flight(engine.rpm_bounds[1], best.speed_m_s, conditions).thrust_n
        if abs(best.speed_m_s-high) < 0.001:
            limiting = "upper_search_bound"
        elif abs(available-best.drag_n) <= max(1e-4, abs(available)*1e-4):
            limiting = "available_thrust"
        else:
            limiting = "model_or_other_envelope_boundary"
    return SpeedSearch(objective, best, grid_points, feasible_count, (low, high), limiting_condition=limiting,
                       infeasible_reasons=tuple(sorted(set(failures.values()))))
