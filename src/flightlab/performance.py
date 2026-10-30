"""Initial steady, straight, level-flight model.

This analytical polar is a baseline, not a substitute for imported aircraft
Flow5 polars. It excludes compressibility and Reynolds-number variation.
Propulsion and energy models are intentionally not assumed.
"""

from dataclasses import dataclass
from math import isfinite
from bisect import bisect_left
from typing import Protocol

GRAVITY_M_S2 = 9.80665


class DragPolar(Protocol):
    def drag_coefficient(self, cl: float) -> float: ...


DRAG_FACTOR_MIN = 0.5
DRAG_FACTOR_MAX = 3.0
DRAG_FACTOR_DEFAULT = 1.0


def validate_drag_factor(value: float) -> None:
    if isinstance(value, bool) or not isfinite(value) or not DRAG_FACTOR_MIN <= value <= DRAG_FACTOR_MAX:
        raise ValueError("Drag factor must be between 0.5 and 3.0")


@dataclass(frozen=True)
class ScaledDragPolar:
    base: DragPolar
    drag_factor: float = DRAG_FACTOR_DEFAULT

    def __post_init__(self):
        validate_drag_factor(self.drag_factor)

    def drag_coefficient(self, cl: float) -> float:
        # Scaling must not bypass the base polar's interpolation/validity checks.
        return self.base.drag_coefficient(cl) * self.drag_factor

    def warnings_for_cl(self, cl: float) -> tuple[str, ...]:
        assess = getattr(self.base, "warnings_for_cl", None)
        return assess(cl) if assess else ()


@dataclass(frozen=True)
class TabulatedPolar:
    """Reference CL/CD interpolation; not a Reynolds/Mach correction model."""

    points: tuple[tuple[float, float], ...]
    source_mach: tuple[float, ...] = ()
    trusted_mach: float | None = None

    def __post_init__(self):
        if len(self.points) < 2:
            raise ValueError("At least two polar points are required")
        if any(not isfinite(cl) or not isfinite(cd) or cd <= 0 for cl, cd in self.points):
            raise ValueError("Polar requires finite CL and positive finite CD")
        if any(b[0] <= a[0] for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Polar CL must strictly increase; select a single branch")
        if self.source_mach and (len(self.source_mach) != len(self.points) or
                                 any(not isfinite(m) or m < 0 for m in self.source_mach)):
            raise ValueError("Source Mach metadata must match polar points")
        if self.trusted_mach is not None and (not isfinite(self.trusted_mach) or self.trusted_mach <= 0):
            raise ValueError("Trusted Mach must be positive")

    def warnings_for_cl(self, cl: float) -> tuple[str, ...]:
        self.drag_coefficient(cl)  # enforce CL range, independently of trust
        if not self.source_mach or self.trusted_mach is None:
            return ()
        axis = [p[0] for p in self.points]
        i = bisect_left(axis, cl)
        indices = (i,) if axis[i] == cl else (i - 1, i)
        if any(self.source_mach[j] > self.trusted_mach for j in indices):
            return (f"Source polar data above trusted Mach {self.trusted_mach:g}; aerodynamic result is unreliable",)
        return ()

    @property
    def cl_min(self) -> float:
        return self.points[0][0]

    @property
    def cl_max(self) -> float:
        return self.points[-1][0]

    def drag_coefficient(self, cl: float) -> float:
        if not isfinite(cl) or not self.cl_min <= cl <= self.cl_max:
            raise ValueError("Required CL is outside the tabulated polar")
        axis = [point[0] for point in self.points]
        i = bisect_left(axis, cl)
        if axis[i] == cl:
            return self.points[i][1]
        x0, y0 = self.points[i - 1]
        x1, y1 = self.points[i]
        return y0 + (y1 - y0) * (cl - x0) / (x1 - x0)


def _positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class Aircraft:
    mass_kg: float
    reference_area_m2: float

    def __post_init__(self) -> None:
        _positive("mass_kg", self.mass_kg)
        _positive("reference_area_m2", self.reference_area_m2)


@dataclass(frozen=True)
class ParabolicPolar:
    cd0: float
    induced_drag_factor: float
    cl_min: float
    cl_max: float

    def __post_init__(self) -> None:
        _positive("cd0", self.cd0)
        _positive("induced_drag_factor", self.induced_drag_factor)
        if not all(map(isfinite, (self.cl_min, self.cl_max))) or self.cl_min >= self.cl_max:
            raise ValueError("CL limits must be finite and cl_min < cl_max")

    def drag_coefficient(self, cl: float) -> float:
        if not isfinite(cl) or not self.cl_min <= cl <= self.cl_max:
            raise ValueError("Required CL is outside the polar's validity limits")
        return self.cd0 + self.induced_drag_factor * cl**2


@dataclass(frozen=True)
class LevelFlight:
    cl: float
    cd: float
    drag_n: float
    useful_power_w: float
    mach: float | None = None
    warnings: tuple[str, ...] = ()


def level_flight(
    aircraft: Aircraft,
    polar: DragPolar,
    true_airspeed_m_s: float,
    air_density_kg_m3: float,
) -> LevelFlight:
    """Return required thrust and useful propulsive power, D * TAS.

    Power here is neither shaft power nor electrical input power. Flight is
    evaluated without a moment-balance solution. No additional trim drag is
    applied; existing tail/control drag in the supplied polar is retained.
    Invalid CL values raise instead of extrapolating beyond the supplied polar.
    """
    _positive("true_airspeed_m_s", true_airspeed_m_s)
    _positive("air_density_kg_m3", air_density_kg_m3)
    dynamic_pressure = 0.5 * air_density_kg_m3 * true_airspeed_m_s**2
    cl = aircraft.mass_kg * GRAVITY_M_S2 / (dynamic_pressure * aircraft.reference_area_m2)
    cd = polar.drag_coefficient(cl)
    drag = dynamic_pressure * aircraft.reference_area_m2 * cd
    assess = getattr(polar, "warnings_for_cl", None)
    return LevelFlight(cl, cd, drag, drag * true_airspeed_m_s,
                       warnings=assess(cl) if assess else ())
