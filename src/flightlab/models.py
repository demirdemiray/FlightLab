"""Adapters for reference-polar experiments and condition-aware model protocols."""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from .flow5 import Flow5Polar
from .interpolation import AeroCoefficients, ModelDomainError
from .mission import FlightConditions
from .performance import validate_drag_factor
from .rpm import ReferenceRpmEngine


class AerodynamicModel(Protocol):
    def at_flight(self, cl: float, speed_m_s: float, conditions: FlightConditions) -> AeroCoefficients: ...


@dataclass(frozen=True)
class EngineResult:
    thrust_n: float
    fuel_flow_kg_s: float
    warnings: tuple[str, ...] = ()


class FlightEngine(Protocol):
    rpm_bounds: tuple[float, float]
    max_fuel_flow_kg_s: float

    def at_flight(self, krpm: float, speed_m_s: float, conditions: FlightConditions) -> EngineResult: ...
    def krpm_for_thrust(self, thrust_n: float, speed_m_s: float, conditions: FlightConditions) -> float: ...


class ReferencePolarModel:
    """Experimental CL-only transfer; explicitly not a multi-condition family."""

    def __init__(self, source: Flow5Polar, *, drag_factor: float = 1.0,
                 source_sound_speed_m_s: float | None = None):
        validate_drag_factor(drag_factor)
        self.polar = source.drag_polar(trusted_mach=0.65 if source_sound_speed_m_s else None,
                                       speed_of_sound_m_s=source_sound_speed_m_s)
        self.rows = sorted(source.points, key=lambda p: p["CL"])
        self.drag_factor = drag_factor

    def at_flight(self, cl: float, speed_m_s: float, conditions: FlightConditions) -> AeroCoefficients:
        cd = self.polar.drag_coefficient(cl) * self.drag_factor
        from bisect import bisect_left
        i = bisect_left([p["CL"] for p in self.rows], cl)
        a, b = (self.rows[i], self.rows[i]) if self.rows[i]["CL"] == cl else (self.rows[i-1], self.rows[i])
        w = 0 if a is b else (cl-a["CL"])/(b["CL"]-a["CL"])
        warnings = ["Reference CL-only polar transfer: Reynolds/Mach variation is not independently modelled"]
        warnings.extend(self.polar.warnings_for_cl(cl))
        if speed_m_s/conditions.atmosphere().speed_of_sound_m_s > 0.65:
            warnings.append("Flight Mach exceeds trusted 0.65; aerodynamic result is unreliable")
        return AeroCoefficients(cl, cd, (1-w)*a["Cm"]+w*b["Cm"],
                                 (1-w)*a["α (°)"]+w*b["α (°)"], tuple(warnings))


@dataclass(frozen=True)
class ReferenceEngineModel:
    """Explicitly experimental: the graph's fuel curve is authoritative.

    No altitude/Mach correction or invented link to the maximum-RPM map.
    Every output warns, including when used by an optimizer.
    """

    reference: ReferenceRpmEngine

    @property
    def rpm_bounds(self) -> tuple[float, float]:
        return self.reference.krpm_bounds

    @property
    def max_fuel_flow_kg_s(self) -> float:
        low, high = self.rpm_bounds
        values = [self.reference.fuel_g_min.value(low), self.reference.fuel_g_min.value(high)]
        values += [y for x, y in self.reference.fuel_g_min.points if low <= x <= high]
        return max(values)/60000

    def at_flight(self, krpm: float, speed_m_s: float, conditions: FlightConditions) -> EngineResult:
        if not isfinite(speed_m_s) or speed_m_s <= 0:
            raise ModelDomainError("Engine query needs a positive airspeed")
        output = self.reference.at_krpm(krpm)
        return EngineResult(output.thrust_n, output.fuel_flow_kg_s,
                            ("Reference RPM engine: altitude/Mach thrust and fuel corrections are not modelled",))

    def krpm_for_thrust(self, thrust_n: float, speed_m_s: float, conditions: FlightConditions) -> float:
        return self.reference.krpm_for_thrust(thrust_n)
