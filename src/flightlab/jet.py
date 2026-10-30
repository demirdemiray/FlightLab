"""Turbojet column-output data and thrust-only derating.

No throttle law is inferred. Interpolation is only within the supplied
altitude/Mach grid and the supplied operating regime.
"""

from bisect import bisect_left
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import re


def validate_thrust_factor(value: float) -> None:
    if isinstance(value, bool) or not isfinite(value) or not 0.6 <= value <= 1.0:
        raise ValueError("Thrust factor must be between 0.6 and 1.0")


@dataclass(frozen=True)
class JetOutput:
    thrust_n: float
    fuel_flow_kg_s: float

    @property
    def fuel_flow_kg_h(self) -> float:
        return self.fuel_flow_kg_s * 3600


@dataclass(frozen=True)
class JetPoint:
    case_id: int
    altitude_m: float
    mach: float
    output: JetOutput


@dataclass(frozen=True)
class JetMap:
    points: tuple[JetPoint, ...]


def read_jet_column_output(path: str | Path, *, altitude_unit: str) -> JetMap:
    """Read whitespace-delimited Case columns, despite the .csv extension.

    Altitude's source label is dimensionless, so the caller must supply its
    interpretation explicitly. Net thrust is kN; fuel is directly Wf in kg/s,
    not reconstructed from the separately rounded SFC column.
    """
    if altitude_unit not in {"m", "ft"}:
        raise ValueError("Altitude unit must explicitly be m or ft")
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError("Empty engine data")
    ids = tuple(map(int, re.findall(r"Case\s+(\d+)", lines[0])))
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Missing or duplicate Case IDs")
    rows: dict[str, tuple[float, ...]] = {}
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        fields = re.split(r"\s{2,}", line, maxsplit=1)
        if len(fields) != 2:
            raise ValueError(f"Unrecognized engine data row: {line[:60]}")
        label, raw = fields
        label = label.strip()
        values = tuple(map(float, raw.split()))
        if len(values) != len(ids) or not all(map(isfinite, values)):
            raise ValueError(f"Invalid values/count in {label}")
        if label in rows and rows[label] != values:
            raise ValueError(f"Conflicting duplicate engine row: {label}")
        rows[label] = values
    required = ("Altitude (-)", "Mach_Number (-)", "F_Net (kN)", "Wf_3_4 (kg/sec)", "converged (-)")
    if any(name not in rows for name in required):
        raise ValueError("Missing required engine performance rows")
    points = []
    altitude_scale = 1 if altitude_unit == "m" else 0.3048
    for index, case_id in enumerate(ids):
        if rows["converged (-)"][index] != 1:
            raise ValueError(f"Engine Case {case_id} did not converge")
        mach = rows["Mach_Number (-)"][index]
        thrust = rows["F_Net (kN)"][index] * 1000
        fuel = rows["Wf_3_4 (kg/sec)"][index]
        if mach < 0 or fuel < 0:
            raise ValueError("Negative Mach or fuel flow")
        points.append(JetPoint(case_id, rows["Altitude (-)"][index] * altitude_scale,
                               mach, JetOutput(thrust, fuel)))
    return JetMap(tuple(points))


def _bracket(axis: list[float], value: float) -> tuple[float, float, float]:
    if not isfinite(value) or not axis[0] <= value <= axis[-1]:
        raise ValueError("Requested conditions are outside the engine map")
    i = bisect_left(axis, value)
    if axis[i] == value:
        return value, value, 0.0
    low, high = axis[i - 1], axis[i]
    return low, high, (value - low) / (high - low)


@dataclass(frozen=True)
class JetEngine:
    performance_map: JetMap
    thrust_factor: float = 1.0

    def __post_init__(self):
        validate_thrust_factor(self.thrust_factor)

    def _derate(self, output: JetOutput) -> JetOutput:
        return JetOutput(output.thrust_n * self.thrust_factor, output.fuel_flow_kg_s)

    def at_case(self, case_id: int) -> JetOutput:
        for point in self.performance_map.points:
            if point.case_id == case_id:
                return self._derate(point.output)
        raise KeyError(case_id)

    def at_conditions(self, altitude_m: float, mach: float) -> JetOutput:
        """Bilinear interpolation of a complete rectangular operating grid.

        A standalone reference row (such as Case 0 at h=0, M=0) is retained
        for at_case(), but excluded from interpolation if its altitude has no
        complete Mach sweep. No extrapolation or throttle scaling is performed.
        """
        grouped: dict[float, dict[float, JetOutput]] = {}
        for point in self.performance_map.points:
            group = grouped.setdefault(point.altitude_m, {})
            if point.mach in group:
                raise ValueError("Duplicate altitude/Mach point")
            group[point.mach] = point.output
        if not grouped:
            raise ValueError("Empty engine map")
        mach_axis = sorted({p.mach for p in self.performance_map.points})
        grid = {h: row for h, row in grouped.items() if set(row) == set(mach_axis)}
        if len(grid) < 2 or len(mach_axis) < 2:
            raise ValueError("A complete altitude/Mach grid is required")
        h0, h1, wh = _bracket(sorted(grid), altitude_m)
        m0, m1, wm = _bracket(mach_axis, mach)

        def blend(field: str) -> float:
            low = (1 - wm) * getattr(grid[h0][m0], field) + wm * getattr(grid[h0][m1], field)
            high = (1 - wm) * getattr(grid[h1][m0], field) + wm * getattr(grid[h1][m1], field)
            return (1 - wh) * low + wh * high

        return self._derate(JetOutput(blend("thrust_n"), blend("fuel_flow_kg_s")))
