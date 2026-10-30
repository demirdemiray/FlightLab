"""Windless planar point-mass flight, fuel burn and event-limited integration.

Controls: RPM and normal aerodynamic load factor n=L/W. Thrust is parallel to
velocity, no moment/trim dynamics. Ray launch and parachute are outside scope.
"""

from dataclasses import dataclass
from math import cos, degrees, isfinite, radians, sin

import numpy as np

from .dataset import AeroReference
from .mission import FlightConditions, FlightLimits, FuelPlan
from .models import AerodynamicModel, FlightEngine
from .performance import GRAVITY_M_S2


@dataclass(frozen=True)
class FlightState:
    time_s: float
    distance_m: float
    altitude_m: float
    speed_m_s: float
    flight_path_angle_deg: float
    fuel_kg: float


@dataclass(frozen=True)
class ControlSegment:
    duration_s: float
    krpm: float
    load_factor: float

    def __post_init__(self):
        if not all(map(isfinite, (self.duration_s, self.krpm, self.load_factor))) or self.duration_s <= 0:
            raise ValueError("Control segment needs finite values and positive duration")


@dataclass(frozen=True)
class TrajectoryResult:
    states: tuple[FlightState, ...]
    termination: str
    warnings: tuple[str, ...]
    failure_reason: str | None = None


def simulate(initial: FlightState, controls: list[ControlSegment], *, fuel_plan: FuelPlan,
             limits: FlightLimits, reference: AeroReference, aero: AerodynamicModel,
             engine: FlightEngine, step_s: float = 0.5, temperature_offset_c: float = 0.0,
             target_distance_m: float | None = None) -> TrajectoryResult:
    """RK4 with current mass/atmosphere/models at every substage.

    A true global fuel-flow upper bound prevents stages from crossing reserve.
    Distance arrival is located by bisection within the final step. Invalid
    model/envelope queries terminate as failures, never as successful missions.
    Variable weather and absolute-temperature profiles are not inferred.
    """
    if not isfinite(step_s) or step_s <= 0:
        raise ValueError("Time step must be finite and positive")
    if not all(map(isfinite, (initial.time_s, initial.distance_m, initial.altitude_m,
                              initial.speed_m_s, initial.flight_path_angle_deg, initial.fuel_kg))):
        raise ValueError("Initial state must be finite")
    if not fuel_plan.reserve_fuel_kg <= initial.fuel_kg <= fuel_plan.initial_fuel_kg:
        raise ValueError("Initial state fuel must be within the loading/reserve plan")
    if target_distance_m is not None and (not isfinite(target_distance_m) or target_distance_m <= initial.distance_m):
        raise ValueError("Target must be a finite forward horizontal distance")
    if not controls:
        raise ValueError("At least one control segment is required")
    bound = engine.max_fuel_flow_kg_s
    if not isfinite(bound) or bound < 0:
        raise ValueError("Engine must provide a finite nonnegative global fuel-flow bound")
    warnings = {"Point-mass model: thrust parallel to velocity; no trim or attitude dynamics"}
    states = [initial]
    y = np.array([initial.distance_m, initial.altitude_m, initial.speed_m_s,
                  radians(initial.flight_path_angle_deg), initial.fuel_kg])
    time = initial.time_s

    def rhs(state, control):
        x, h, v, gamma, fuel = state
        conditions = FlightConditions(float(h), temperature_offset_c=temperature_offset_c)
        air = conditions.atmosphere()
        mass = fuel_plan.mass_at_fuel(float(fuel))
        cl = limits.check_flight_state(mass, reference.area_m2, float(v), air,
                                       load_factor=control.load_factor, flight_path_angle_deg=degrees(gamma))
        coefficients = aero.at_flight(cl, float(v), conditions)
        output = engine.at_flight(control.krpm, float(v), conditions)
        if (not all(map(isfinite, (coefficients.cd, coefficients.alpha_deg, output.thrust_n, output.fuel_flow_kg_s)))
                or coefficients.cd < 0 or output.fuel_flow_kg_s < 0):
            raise ValueError("Nonphysical aerodynamic/engine output")
        if output.fuel_flow_kg_s > bound * (1+1e-12) + 1e-15:
            raise ValueError("Engine output exceeds its declared fuel-flow bound")
        warnings.update(coefficients.warnings)
        warnings.update(output.warnings)
        warnings.update(limits.aerodynamic_warnings(float(v), air))
        drag = 0.5*air.density_kg_m3*v*v*reference.area_m2*coefficients.cd
        return np.array([v*cos(gamma), v*sin(gamma),
                         (output.thrust_n-drag)/mass-GRAVITY_M_S2*sin(gamma),
                         GRAVITY_M_S2*(control.load_factor-cos(gamma))/v,
                         -output.fuel_flow_kg_s])

    def rk4(state, duration, control):
        a = rhs(state, control)
        b = rhs(state+duration*a/2, control)
        c = rhs(state+duration*b/2, control)
        d = rhs(state+duration*c, control)
        result = state+duration*(a+2*b+2*c+d)/6
        rhs(result, control)  # also validate the accepted endpoint
        return result

    def export(state):
        return FlightState(time, float(state[0]), float(state[1]), float(state[2]),
                           degrees(float(state[3])), float(state[4]))

    try:
        for control in controls:
            if not engine.rpm_bounds[0] <= control.krpm <= engine.rpm_bounds[1]:
                raise ValueError("Control RPM outside engine map/continuous limit")
            end_time = time+control.duration_s
            rhs(y, control)
            while time < end_time - 1e-10:
                burnable = y[4]-fuel_plan.reserve_fuel_kg
                if burnable <= 1e-8:
                    return TrajectoryResult(tuple(states), "fuel_reserve", tuple(sorted(warnings)))
                dt = min(step_s, end_time-time)
                if bound > 0:
                    dt = min(dt, burnable/bound)
                while True:
                    try:
                        candidate = rk4(y, dt, control)
                        break
                    except ValueError:
                        # A trial can cross an envelope/model boundary beyond
                        # an otherwise reachable arrival. Shorten before failing.
                        if dt <= 1e-6:
                            raise
                        dt /= 2
                if target_distance_m is not None and candidate[0] >= target_distance_m:
                    lo, hi = 0.0, dt
                    for _ in range(36):
                        middle = (lo+hi)/2
                        if rk4(y, middle, control)[0] >= target_distance_m:
                            hi = middle
                        else:
                            lo = middle
                    dt = hi
                    candidate = rk4(y, dt, control)
                    time += dt
                    states.append(export(candidate))
                    return TrajectoryResult(tuple(states), "distance_target", tuple(sorted(warnings)))
                time += dt
                y = candidate
                states.append(export(y))
        if y[4]-fuel_plan.reserve_fuel_kg <= 1e-8:
            return TrajectoryResult(tuple(states), "fuel_reserve", tuple(sorted(warnings)))
        return TrajectoryResult(tuple(states), "controls_completed", tuple(sorted(warnings)))
    except ValueError as error:
        return TrajectoryResult(tuple(states), "model_or_envelope_failure", tuple(sorted(warnings)), str(error))
