"""Reference RPM curves digitized from graphs, separate from flight maps."""

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path

from .jet import JetOutput, _bracket, validate_thrust_factor

STANDARD_GRAVITY = 9.80665  # kgf -> N, not aircraft mass


@dataclass(frozen=True)
class Curve:
    points: tuple[tuple[float, float], ...]

    def __post_init__(self):
        if len(self.points) < 2:
            raise ValueError("At least two curve points are required")
        if any(not isfinite(x) or not isfinite(y) or y <= 0 for x, y in self.points):
            raise ValueError("Curve values must be finite and ordinates positive")
        if any(b[0] <= a[0] for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Curve abscissae must strictly increase")

    def value(self, x: float) -> float:
        low, high, weight = _bracket([p[0] for p in self.points], x)
        values = dict(self.points)
        return (1 - weight) * values[low] + weight * values[high]


@dataclass(frozen=True)
class TsfcCheck:
    krpm: float
    derived_kg_kgf_h: float
    graph_kg_kgf_h: float

    @property
    def relative_difference(self) -> float:
        return self.derived_kg_kgf_h / self.graph_kg_kgf_h - 1


@dataclass(frozen=True)
class ReferenceRpmEngine:
    fuel_g_min: Curve
    thrust_kgf: Curve
    tsfc_graph: Curve
    thrust_factor: float = 1.0
    continuous_max_krpm: float | None = None

    def __post_init__(self):
        validate_thrust_factor(self.thrust_factor)
        if self.continuous_max_krpm is not None and (not isfinite(self.continuous_max_krpm) or self.continuous_max_krpm <= 0):
            raise ValueError("Continuous RPM limit must be finite and positive")
        if any(b[1] <= a[1] for a, b in zip(self.thrust_kgf.points, self.thrust_kgf.points[1:])):
            raise ValueError("Thrust must increase with RPM to invert the reference curve")
        if self.krpm_bounds[0] >= self.krpm_bounds[1]:
            raise ValueError("Fuel and thrust RPM domains do not overlap")

    @property
    def krpm_bounds(self) -> tuple[float, float]:
        high = min(self.fuel_g_min.points[-1][0], self.thrust_kgf.points[-1][0])
        if self.continuous_max_krpm is not None:
            high = min(high, self.continuous_max_krpm)
        return (max(self.fuel_g_min.points[0][0], self.thrust_kgf.points[0][0]), high)

    def at_krpm(self, krpm: float) -> JetOutput:
        low, high = self.krpm_bounds
        if not isfinite(krpm) or not low <= krpm <= high:
            raise ValueError("RPM outside the shared graph domain")
        return JetOutput(self.thrust_kgf.value(krpm) * STANDARD_GRAVITY * self.thrust_factor,
                         self.fuel_g_min.value(krpm) / 60000)

    def krpm_for_thrust(self, thrust_n: float) -> float:
        """Invert effective thrust; no engine-off or sub-idle extrapolation."""
        low, high = self.krpm_bounds
        rpm_points = [low] + [x for x, _ in self.thrust_kgf.points if low < x < high] + [high]
        inverse = Curve(tuple((self.at_krpm(rpm).thrust_n, rpm) for rpm in rpm_points))
        return inverse.value(thrust_n)

    def tsfc_consistency(self) -> tuple[TsfcCheck, ...]:
        """Compare raw graph readings, before derating; never overwrite curves.

        Reference TSFC = (fuel_g_min * 0.06) / thrust_kgf.
        Derated effective TSFC would increase by 1/thrust_factor at fixed RPM.
        """
        low, high = self.krpm_bounds
        low = max(low, self.tsfc_graph.points[0][0])
        high = min(high, self.tsfc_graph.points[-1][0])
        if low > high:
            return ()
        samples = sorted({low, high} | {rpm for rpm, _ in self.tsfc_graph.points if low <= rpm <= high})
        return tuple(TsfcCheck(rpm, self.fuel_g_min.value(rpm) * 0.06 / self.thrust_kgf.value(rpm),
                              self.tsfc_graph.value(rpm)) for rpm in samples)


def read_reference_rpm_engine(path: str | Path, *, thrust_factor: float = 1.0,
                              continuous_max_krpm: float | None = None) -> ReferenceRpmEngine:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("quality") != "approximate_graph_digitization":
        raise ValueError("Unsupported RPM graph format")
    curves = data["curves"]

    def curve(name: str, unit: str) -> Curve:
        if curves[name]["unit"] != unit:
            raise ValueError(f"Unexpected units for {name}")
        return Curve(tuple(tuple(point) for point in curves[name]["points"]))

    return ReferenceRpmEngine(curve("fuel", "g/min"), curve("thrust", "kgf"),
                              curve("tsfc_check", "kg/(kgf*h)"), thrust_factor, continuous_max_krpm)
