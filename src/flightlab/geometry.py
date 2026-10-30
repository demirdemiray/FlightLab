"""Flow5 plane XML reader; lengths/masses are converted to SI.

Section geometry is retained; no airfoil coordinates or NURBS solver is implied.
AutoInertia records are not treated as validated aircraft inertia or CG.
"""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import xml.etree.ElementTree as ET


def _text(element: ET.Element, name: str) -> str:
    value = element.findtext(name)
    if value is None or not value.strip():
        raise ValueError(f"Missing XML field: {name}")
    return value.strip()


def _number(element: ET.Element, name: str) -> float:
    value = float(_text(element, name))
    if not isfinite(value):
        raise ValueError(f"Nonfinite XML field: {name}")
    return value


def _boolean(element: ET.Element, name: str) -> bool:
    value = _text(element, name).lower()
    if value not in ("true", "false"):
        raise ValueError(f"Invalid boolean: {name}")
    return value == "true"


@dataclass(frozen=True)
class Section:
    y_m: float
    chord_m: float
    x_offset_m: float
    dihedral_deg: float
    twist_deg: float
    left_foil: str
    right_foil: str


@dataclass(frozen=True)
class Planform:
    span_m: float
    area_m2: float
    mac_m: float
    aspect_ratio: float


@dataclass(frozen=True)
class Surface:
    name: str
    kind: str
    symmetric: bool
    two_sided: bool
    sections: tuple[Section, ...]

    def flat_symmetric_planform(self) -> Planform:
        """Integrate linear chord segments for a flat, symmetric two-sided wing.

        This is geometric planform area, not a confirmed polar reference area.
        Surface mounting incidence does not change these local planform metrics.
        """
        if not self.symmetric or not self.two_sided:
            raise ValueError("Planform calculation requires a symmetric two-sided surface")
        if len(self.sections) < 2 or self.sections[0].y_m != 0:
            raise ValueError("Planform must start at y=0 and have at least two sections")
        if any(s.dihedral_deg != 0 for s in self.sections):
            raise ValueError("Nonzero dihedral needs a separate projected-area convention")
        half_area = chord_squared_integral = 0.0
        for start, end in zip(self.sections, self.sections[1:]):
            dy = end.y_m - start.y_m
            if dy <= 0:
                raise ValueError("Section y positions must strictly increase")
            a, b = start.chord_m, end.chord_m
            half_area += dy * (a + b) / 2
            chord_squared_integral += dy * (a*a + a*b + b*b) / 3
        area = 2 * half_area
        span = 2 * self.sections[-1].y_m
        return Planform(span, area, chord_squared_integral / half_area, span**2 / area)


@dataclass(frozen=True)
class PointMass:
    tag: str
    mass_kg: float
    coordinates_m: tuple[float, ...]


@dataclass(frozen=True)
class PlaneGeometry:
    name: str
    surfaces: tuple[Surface, ...]
    point_masses: tuple[PointMass, ...]
    declared_component_mass_kg: float

    @property
    def declared_total_mass_kg(self) -> float:
        return self.declared_component_mass_kg + sum(p.mass_kg for p in self.point_masses)


def read_flow5_geometry(path: str | Path) -> PlaneGeometry:
    """Read explicit plane geometry fields; reject ambiguous missing units.

    Flow5's embedded comment defines these multipliers as file-to-SI despite
    their historical names. No conversion is guessed from the filename.
    """
    content = Path(path).read_text(encoding="utf-8-sig")
    if "<!ENTITY" in content.upper():
        raise ValueError("XML entity declarations are not supported")
    root = ET.fromstring(content)
    # Flow5 explicitly allows case-insensitive field names.
    for node in root.iter():
        node.tag = node.tag.lower()
    if root.tag != "xflplane":
        raise ValueError("Expected Flow5 xflplane XML")
    units, plane = root.find("units"), root.find("plane")
    if units is None or plane is None:
        raise ValueError("Expected Units and Plane elements")
    length = _number(units, "meter_to_length_unit")
    mass = _number(units, "kg_to_mass_unit")
    if length <= 0 or mass <= 0:
        raise ValueError("Unit multipliers must be positive")
    surfaces = []
    for wing in plane.findall("wing"):
        sections = []
        for section in wing.findall("sections/section"):
            chord = _number(section, "chord") * length
            if chord <= 0:
                raise ValueError("Section chord must be positive")
            sections.append(Section(
                _number(section, "y_position") * length, chord,
                _number(section, "xoffset") * length,
                _number(section, "dihedral"), _number(section, "twist"),
                _text(section, "left_side_foilname"), _text(section, "right_side_foilname"),
            ))
        surfaces.append(Surface(_text(wing, "name"), _text(wing, "type"),
                                _boolean(wing, "symmetric"), _boolean(wing, "two_sided"), tuple(sections)))
    points = []
    for point in plane.findall("inertia/point_mass"):
        coordinates = tuple(float(v.strip()) * length for v in _text(point, "coordinates").split(","))
        if len(coordinates) != 3 or not all(map(isfinite, coordinates)):
            raise ValueError("Point mass requires three finite coordinates")
        points.append(PointMass(_text(point, "tag"), _number(point, "mass") * mass, coordinates))
    component_mass = sum(_number(w, "inertia/mass") * mass for w in plane.findall("wing"))
    component_mass += sum(_number(b, "inertia/volume_mass") * mass for b in plane.findall("body"))
    if component_mass < 0 or any(p.mass_kg < 0 for p in points):
        raise ValueError("Mass cannot be negative")
    return PlaneGeometry(_text(plane, "name"), tuple(surfaces), tuple(points), component_mass)
