"""Piecewise-linear CL/log(Re)/Mach model with explicit domain/provenance.

No high-order overshoot; no silent nearest-neighbour extrapolation. All valid
high-Mach source samples participate and their warnings propagate to queries.
"""

from dataclasses import dataclass
from math import exp, isfinite, log

import numpy as np
from scipy.spatial import Delaunay, QhullError, cKDTree

from .dataset import AeroReference, PolarDataset
from .mission import FlightConditions
from .performance import validate_drag_factor


class ModelDomainError(ValueError):
    pass


@dataclass(frozen=True)
class Contributor:
    polar_name: str
    row_index: int
    weight: float


@dataclass(frozen=True)
class AeroCoefficients:
    cl: float
    cd: float
    cm: float
    alpha_deg: float
    warnings: tuple[str, ...] = ()
    contributors: tuple[Contributor, ...] = ()


class PolarFamily:
    def __init__(self, dataset: PolarDataset, reference: AeroReference, *, drag_factor: float = 1.0):
        validate_drag_factor(drag_factor)
        runs = sorted((r for r in dataset.runs if r.usable), key=lambda r: r.condition.name)
        if len({r.condition.altitude_m for r in runs}) < 2 or len({r.condition.speed_m_s for r in runs}) < 2:
            raise ValueError("A 3D family needs at least two altitudes and two speeds; use a reference polar otherwise")
        if len({p["Ctrl"] for r in runs for p in r.polar.points}) != 1:
            raise ValueError("Select a single fixed control configuration for the family")
        if len({r.polar.metadata_lines[0] if r.polar.metadata_lines else None for r in runs}) != 1:
            raise ValueError("Cannot combine different aircraft in one polar family")
        self.reference, self.drag_factor = reference, drag_factor
        self.altitude_range_m = (min(r.condition.altitude_m for r in runs), max(r.condition.altitude_m for r in runs))
        incomplete = len(dataset.manifest) - len(runs)
        self.dataset_warnings = (f"Incomplete polar family: {incomplete} expected analyses missing or unusable",) if incomplete else ()
        if any(run.missing_alpha_deg for run in runs):
            self.dataset_warnings += ("Some source alpha sweeps are incomplete; inspect the dataset report",)
        coords, values, provenance, source_mach = [], [], [], []
        unique = {}
        for run in runs:
            c = run.condition
            reynolds = c.speed_m_s * reference.chord_m / c.nu_m2_s
            for index, point in enumerate(run.polar.points):
                q_area = 0.5*c.density_kg_m3*c.speed_m_s**2*reference.area_m2
                for force, coefficient in (("Lift (N)", "CL"), ("Drag (N)", "CD")):
                    if force in point and isfinite(point[force]):
                        expected = q_area*point[coefficient]
                        if abs(point[force]-expected) > max(0.05, abs(expected)*0.005):
                            raise ValueError(f"{c.name}: {force} is inconsistent with supplied reference area/manifest")
                coord = (point["CL"], log(reynolds), c.mach)
                value = (point["CD"], point["Cm"], point["α (°)"])
                key = tuple(round(x, 12) for x in coord)
                if key in unique:
                    if not np.allclose(values[unique[key]], value, rtol=1e-8, atol=1e-10):
                        raise ValueError("Conflicting CL/Re/Mach samples; possible stall branches or mixed settings")
                    continue  # identical repeated observation; original row remains in dataset
                unique[key] = len(coords)
                coords.append(coord)
                values.append(value)
                provenance.append((c.name, index))
                source_mach.append(c.mach)
        raw = np.asarray(coords, dtype=float)
        self.origin = raw.min(axis=0)
        self.scale = np.ptp(raw, axis=0)
        if np.any(self.scale <= 0):
            raise ValueError("Samples do not span CL, Reynolds and Mach")
        self.coordinates = (raw - self.origin)/self.scale
        try:
            self.mesh = Delaunay(self.coordinates)
        except QhullError as error:
            raise ValueError("Polar family does not span an independent 3D interpolation volume") from error
        self.tree = cKDTree(self.coordinates)
        self.values = np.asarray(values)
        self.provenance = provenance
        self.source_mach = np.asarray(source_mach)
        self.sample_count = len(raw)

    def evaluate(self, cl: float, reynolds: float, mach: float, *, extrapolation: str = "error") -> AeroCoefficients:
        if not all(map(isfinite, (cl, reynolds, mach))) or reynolds <= 0 or mach < 0:
            raise ModelDomainError("Query requires finite CL, positive Reynolds and nonnegative Mach")
        if extrapolation not in {"error", "nearest"}:
            raise ValueError("Extrapolation must be error or explicitly requested nearest")
        query = (np.array([cl, log(reynolds), mach]) - self.origin)/self.scale
        distance, closest = self.tree.query(query)
        warnings = list(self.dataset_warnings)
        if distance <= 1e-10:
            indices, weights = np.array([closest]), np.array([1.0])
        else:
            simplex = int(self.mesh.find_simplex(query))
            if simplex < 0:
                if extrapolation == "error":
                    raise ModelDomainError("Query is outside the sampled CL/Re/Mach convex hull")
                indices, weights = np.array([closest]), np.array([1.0])
                warnings.append("Outside sampled domain: explicit nearest-sample extrapolation; unreliable")
            else:
                transform = self.mesh.transform[simplex]
                first = transform[:3].dot(query - transform[3])
                weights = np.clip(np.r_[first, 1 - first.sum()], 0, 1)
                weights /= weights.sum()
                indices = self.mesh.simplices[simplex]
        active = weights > 1e-12
        indices, weights = indices[active], weights[active]
        cd, cm, alpha = weights @ self.values[indices]
        if mach > 0.65:
            warnings.append("Flight Mach exceeds trusted 0.65; aerodynamic result is unreliable")
        if np.any(self.source_mach[indices] > 0.65):
            warnings.append("Interpolation uses source points above trusted Mach 0.65; unreliable")
        contributors = tuple(Contributor(*self.provenance[i], float(w)) for i, w in zip(indices, weights))
        return AeroCoefficients(cl, float(cd) * self.drag_factor, float(cm), float(alpha),
                                 tuple(warnings), contributors)

    def at_flight(self, cl: float, speed_m_s: float, conditions: FlightConditions) -> AeroCoefficients:
        if not isfinite(speed_m_s) or speed_m_s <= 0:
            raise ModelDomainError("True airspeed must be finite and positive")
        air = conditions.atmosphere()
        result = self.evaluate(cl, speed_m_s*self.reference.chord_m/air.kinematic_viscosity_m2_s,
                                speed_m_s/air.speed_of_sound_m_s)
        if not self.altitude_range_m[0] <= conditions.altitude_m <= self.altitude_range_m[1]:
            from dataclasses import replace
            return replace(result, warnings=result.warnings +
                           ("Query altitude outside source altitude range; dimensionless interpolation only",))
        return result

    def summary(self) -> dict:
        upper = self.origin+self.scale
        return {"samples": self.sample_count, "source_altitude_range_m": self.altitude_range_m,
                "cl_range": (float(self.origin[0]), float(upper[0])),
                "reynolds_range": (exp(self.origin[1]), exp(upper[1])),
                "mach_range": (float(self.origin[2]), float(upper[2])),
                "warnings": self.dataset_warnings,
                "domain": "3D convex hull; independent min/max bounds do not imply every combination is covered"}
