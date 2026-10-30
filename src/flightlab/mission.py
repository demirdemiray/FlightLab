"""Flight inputs, tropospheric atmosphere and fuel-dependent mass evolution.

This supplies mission bookkeeping, not a complete trajectory/trim solver.
Fuel-flow callbacks must use validated aerodynamic/engine models for flight.
"""

from dataclasses import dataclass, replace
from math import cos, isfinite, radians, sqrt
from typing import Callable

from .performance import Aircraft, DragPolar, GRAVITY_M_S2, LevelFlight, level_flight


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class Atmosphere:
    pressure_pa: float
    temperature_k: float
    density_kg_m3: float
    speed_of_sound_m_s: float

    @property
    def dynamic_viscosity_pa_s(self) -> float:
        t = self.temperature_k
        return 1.716e-5 * (t / 273.15)**1.5 * (273.15 + 110.4)/(t + 110.4)

    @property
    def kinematic_viscosity_m2_s(self) -> float:
        return self.dynamic_viscosity_pa_s / self.density_kg_m3


@dataclass(frozen=True)
class FlightConditions:
    altitude_m: float = 0.0
    temperature_c: float | None = None  # None means ISA at the selected altitude
    temperature_offset_c: float | None = None
    # Wind is always zero. There is deliberately no selectable wind input.

    def __post_init__(self):
        _finite("altitude_m", self.altitude_m)
        if not -500 <= self.altitude_m <= 11000:
            raise ValueError("Atmosphere currently supports -500 to 11000 m pressure altitude")
        if self.temperature_c is not None:
            _finite("temperature_c", self.temperature_c)
            if self.temperature_c <= -273.15:
                raise ValueError("Temperature must be above absolute zero")
        if self.temperature_offset_c is not None:
            _finite("temperature_offset_c", self.temperature_offset_c)
            if self.temperature_c is not None:
                raise ValueError("Choose actual temperature or ISA offset, not both")
            if 288.15 - 0.0065 * self.altitude_m + self.temperature_offset_c <= 0:
                raise ValueError("Offset temperature must be above absolute zero")

    def atmosphere(self) -> Atmosphere:
        """ISA pressure at pressure altitude; optional local OAT override.

        Local temperature is not substituted into the ISA pressure profile.
        Dry air, geopotential pressure altitude and a tropospheric lapse rate
        are assumed. This is not a measured weather pressure profile.
        """
        isa_t = 288.15 - 0.0065 * self.altitude_m
        pressure = 101325 * (isa_t / 288.15) ** (GRAVITY_M_S2 / (287.05287 * 0.0065))
        temperature = isa_t + (self.temperature_offset_c or 0) if self.temperature_c is None else self.temperature_c + 273.15
        return Atmosphere(pressure, temperature, pressure / (287.05287 * temperature),
                          sqrt(1.4 * 287.05287 * temperature))


@dataclass(frozen=True)
class FlightLimits:
    cl_max: float
    max_true_airspeed_m_s: float
    trusted_aerodynamic_mach: float | None = None
    min_groundspeed_m_s: float = 0.0
    max_load_factor: float | None = None

    def __post_init__(self):
        for name in ("cl_max", "max_true_airspeed_m_s"):
            value = getattr(self, name)
            _finite(name, value)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.trusted_aerodynamic_mach is not None:
            _finite("trusted_aerodynamic_mach", self.trusted_aerodynamic_mach)
            if self.trusted_aerodynamic_mach <= 0:
                raise ValueError("Trusted Mach must be positive")
        _finite("min_groundspeed_m_s", self.min_groundspeed_m_s)
        if not 0 <= self.min_groundspeed_m_s < self.max_true_airspeed_m_s:
            raise ValueError("Minimum groundspeed must be nonnegative and below maximum TAS")
        if self.max_load_factor is not None:
            _finite("max_load_factor", self.max_load_factor)
            if self.max_load_factor < 1:
                raise ValueError("Maximum load factor must permit level flight")

    def aerodynamic_warnings(self, speed_m_s: float, atmosphere: Atmosphere) -> tuple[str, ...]:
        if (self.trusted_aerodynamic_mach is not None and
                speed_m_s > self.trusted_aerodynamic_mach * atmosphere.speed_of_sound_m_s):
            return (f"Flight Mach exceeds trusted Mach {self.trusted_aerodynamic_mach:g}; aerodynamic result is unreliable",)
        return ()

    def check_level_flight(self, mass_kg: float, area_m2: float, speed_m_s: float,
                           atmosphere: Atmosphere) -> float:
        return self.check_flight_state(mass_kg, area_m2, speed_m_s, atmosphere, load_factor=1)

    def check_flight_state(self, mass_kg: float, area_m2: float, speed_m_s: float,
                           atmosphere: Atmosphere, *, load_factor: float,
                           flight_path_angle_deg: float = 0.0) -> float:
        """Fixed-wing flight limits; positive normal load n=L/(m*g).

        Not a catapult longitudinal acceleration or parachute opening-load
        model. Minimum horizontal groundspeed applies to airborne fixed-wing
        flight only. Wind is zero; pitch is not the flight-path angle.
        """
        for name, value in (("mass_kg", mass_kg), ("area_m2", area_m2), ("speed_m_s", speed_m_s)):
            _finite(name, value)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if speed_m_s > self.max_true_airspeed_m_s:
            raise ValueError("True airspeed exceeds aircraft limit")
        _finite("flight_path_angle_deg", flight_path_angle_deg)
        if not -90 <= flight_path_angle_deg <= 90:
            raise ValueError("Flight-path angle must be within -90 to 90 degrees")
        groundspeed = speed_m_s * cos(radians(flight_path_angle_deg))
        if groundspeed < self.min_groundspeed_m_s:
            raise ValueError("Horizontal groundspeed is below the operational minimum")
        _finite("load_factor", load_factor)
        if load_factor < 0:
            raise ValueError("Negative-load envelope is not specified")
        if self.max_load_factor is not None and load_factor > self.max_load_factor:
            raise ValueError("Normal load factor exceeds aircraft limit")
        cl = 2 * load_factor * mass_kg * GRAVITY_M_S2 / (atmosphere.density_kg_m3 * speed_m_s**2 * area_m2)
        if cl > self.cl_max:
            raise ValueError("Required CL exceeds aircraft CLmax")
        return cl


@dataclass(frozen=True)
class MissionRequirements:
    launch_method: str
    recovery_method: str
    target_cruise_groundspeed_m_s: float
    altitude_capability_target_m: float
    catapult_exit_speed_m_s: float | None = None
    catapult_exit_flight_path_angle_deg: float | None = None
    catapult_exit_pitch_deg: float | None = None
    parachute_deployment_altitude_m: float | None = None
    parachute_deployment_speed_m_s: float | None = None
    model_parachute: bool = False

    def __post_init__(self):
        for name in ("target_cruise_groundspeed_m_s", "altitude_capability_target_m"):
            _finite(name, getattr(self, name))
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("catapult_exit_speed_m_s", "catapult_exit_flight_path_angle_deg", "catapult_exit_pitch_deg",
                     "parachute_deployment_altitude_m", "parachute_deployment_speed_m_s"):
            value = getattr(self, name)
            if value is not None:
                _finite(name, value)
        for speed in (self.catapult_exit_speed_m_s, self.parachute_deployment_speed_m_s):
            if speed is not None and speed <= 0:
                raise ValueError("Boundary airspeeds must be positive")
        if (self.catapult_exit_flight_path_angle_deg is not None and
                not -90 <= self.catapult_exit_flight_path_angle_deg <= 90):
            raise ValueError("Exit flight-path angle must be within -90 to 90 degrees")
        if self.catapult_exit_pitch_deg is not None and not -90 <= self.catapult_exit_pitch_deg <= 90:
            raise ValueError("Exit pitch must be within -90 to 90 degrees")


@dataclass(frozen=True)
class FuelPlan:
    nonfuel_mass_kg: float
    initial_fuel_kg: float
    reserve_fuel_kg: float

    def __post_init__(self):
        for name in ("nonfuel_mass_kg", "initial_fuel_kg", "reserve_fuel_kg"):
            _finite(name, getattr(self, name))
        if self.nonfuel_mass_kg <= 0 or self.initial_fuel_kg < 0:
            raise ValueError("Nonfuel mass must be positive and initial fuel nonnegative")
        if not 0 <= self.reserve_fuel_kg <= self.initial_fuel_kg:
            raise ValueError("Reserve must be between zero and the total loaded fuel")

    @property
    def initial_mass_kg(self) -> float:
        return self.nonfuel_mass_kg + self.initial_fuel_kg

    def mass_at_fuel(self, remaining_fuel_kg: float) -> float:
        _finite("remaining_fuel_kg", remaining_fuel_kg)
        if not 0 <= remaining_fuel_kg <= self.initial_fuel_kg:
            raise ValueError("Remaining fuel is outside the loading plan")
        return self.nonfuel_mass_kg + remaining_fuel_kg


@dataclass(frozen=True)
class FuelState:
    time_s: float
    fuel_kg: float
    mass_kg: float


def level_flight_at_fuel(plan: FuelPlan, remaining_fuel_kg: float, *, area_m2: float,
                         speed_m_s: float, conditions: FlightConditions,
                         limits: FlightLimits, polar: DragPolar) -> LevelFlight:
    """Recompute required lift, drag and power using the current fuel mass.

    Area must be supplied explicitly: geometric area is not silently assigned
    as a Flow5 coefficient reference. Aircraft and polar CL bounds both apply.
    CG/trim and inertia changes are outside this initial quasi-steady model.
    """
    mass = plan.mass_at_fuel(remaining_fuel_kg)
    atmosphere = conditions.atmosphere()
    limits.check_level_flight(mass, area_m2, speed_m_s, atmosphere)
    result = level_flight(Aircraft(mass, area_m2), polar, speed_m_s, atmosphere.density_kg_m3)
    return replace(result, mach=speed_m_s / atmosphere.speed_of_sound_m_s,
                   warnings=result.warnings + limits.aerodynamic_warnings(speed_m_s, atmosphere))


def integrate_fuel_until_reserve(
    plan: FuelPlan,
    fuel_flow_kg_s: Callable[[FuelState], float],
    *,
    step_s: float = 1.0,
    max_duration_s: float = 86400,
) -> tuple[FuelState, ...]:
    """Explicit time stepping, sampling flow with the current mass at every step.

    The last step is shortened to stop exactly at reserve. Time-varying flows
    require step convergence checks. No thrust or trajectory is inferred here.
    Failure to reach reserve by max_duration raises rather than reporting an
    incomplete run as endurance. Reserve stays aboard and contributes weight.
    """
    for name, value in (("step_s", step_s), ("max_duration_s", max_duration_s)):
        _finite(name, value)
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    states = [FuelState(0, plan.initial_fuel_kg, plan.initial_mass_kg)]
    while states[-1].fuel_kg > plan.reserve_fuel_kg:
        previous = states[-1]
        flow = fuel_flow_kg_s(previous)
        _finite("fuel_flow_kg_s", flow)
        if flow <= 0:
            raise ValueError("Fuel burn integration requires positive fuel flow")
        burnable = previous.fuel_kg - plan.reserve_fuel_kg
        to_reserve = burnable / flow
        time_left = max_duration_s - previous.time_s
        if time_left <= 0:
            raise ValueError("Reserve not reached within max_duration_s")
        dt = min(step_s, to_reserve, time_left)
        remaining = plan.reserve_fuel_kg if dt == to_reserve else previous.fuel_kg - flow * dt
        states.append(FuelState(previous.time_s + dt, remaining, plan.mass_at_fuel(remaining)))
    return tuple(states)
