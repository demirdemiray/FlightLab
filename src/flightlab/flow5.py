"""Read Flow5 CSV exports without guessing missing analysis settings.

Original column names and units are retained (notably CL versus Cl).
This imports observations only; it does not infer trim or level flight.
"""

import csv
from io import StringIO
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from .performance import TabulatedPolar


@dataclass
class Flow5Polar:
    metadata_lines: tuple[str, ...]
    columns: tuple[str, ...]
    points: list[dict[str, float]]

    def drag_polar(self, *, trusted_mach: float | None = None,
                   speed_of_sound_m_s: float | None = None) -> TabulatedPolar:
        """Use total CD as exported, with no extra trim correction.

        Multiple controls or branches must be separated before calling this.
        Single-point stability exports cannot form a tabulated polar.
        """
        if len({point["Ctrl"] for point in self.points}) > 1:
            raise ValueError("Select one control configuration before creating a polar")
        points = sorted(self.points, key=lambda p: p["CL"])
        source_mach: tuple[float, ...] = ()
        if trusted_mach is not None:
            if (not isfinite(trusted_mach) or trusted_mach <= 0 or speed_of_sound_m_s is None
                    or not isfinite(speed_of_sound_m_s) or speed_of_sound_m_s <= 0):
                raise ValueError("Mach assessment requires positive threshold and sound speed")
            source_mach = tuple(point["V (m/s)"] / speed_of_sound_m_s for point in points)
        return TabulatedPolar(tuple((point["CL"], point["CD"]) for point in points),
                               source_mach, trusted_mach)


def read_flow5_csv(path: str | Path) -> Flow5Polar:
    """Read UTF-8 Flow5 data, including a header joined to its first point.

    Blank lines and trailing commas are accepted. Missing/misaligned fields
    and nonfinite core physical values are rejected; undefined auxiliary
    ratios are retained as NaN/Inf for dataset-quality reporting.
    """
    return parse_flow5_csv(Path(path).read_text(encoding="utf-8-sig"))


def parse_flow5_csv(text: str) -> Flow5Polar:
    """Parse a CSV string, including ZIP members without extracting files.

    Core physical fields must be finite. Undefined derived ratios at negative
    CL may be NaN/Inf; they are retained and do not invalidate usable CL/CD.
    """
    metadata: list[str] = []
    columns: tuple[str, ...] | None = None
    points: list[dict[str, float]] = []
    with StringIO(text.lstrip("\ufeff"), newline="") as stream:
        for line_number, row in enumerate(csv.reader(stream), start=1):
            cells = [cell.strip() for cell in row]
            while cells and cells[-1] == "":
                cells.pop()
            if not cells:
                continue
            if columns is None:
                if cells[0] != "Ctrl":
                    metadata.append(",".join(cells))
                    continue
                # Numeric Ctrl is the boundary in the merged-header variant.
                boundary = len(cells)
                for index, cell in enumerate(cells):
                    try:
                        float(cell)
                    except ValueError:
                        continue
                    boundary = index
                    break
                columns = tuple(cells[:boundary])
                if len(set(columns)) != len(columns):
                    raise ValueError("Duplicate Flow5 column names")
                required = {"Ctrl", "α (°)", "CL", "CD", "Cm", "V (m/s)"}
                if not required.issubset(columns):
                    raise ValueError(f"Missing Flow5 columns: {sorted(required - set(columns))}")
                cells = cells[boundary:]
                if not cells:
                    continue
            if len(cells) != len(columns):
                raise ValueError(f"Line {line_number}: expected {len(columns)} values, got {len(cells)}")
            try:
                values = [float(cell) for cell in cells]
            except ValueError as error:
                raise ValueError(f"Line {line_number}: invalid numeric field") from error
            core = {"Ctrl", "α (°)", "CL", "CD", "Cm", "V (m/s)"}
            if any(not isfinite(v) for name, v in zip(columns, values) if name in core):
                raise ValueError(f"Line {line_number}: nonfinite core numeric field")
            points.append(dict(zip(columns, values)))
    if columns is None or not points:
        raise ValueError("Flow5 export must contain a header and at least one data point")
    return Flow5Polar(tuple(metadata), columns, points)
