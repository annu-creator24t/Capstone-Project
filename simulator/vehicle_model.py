"""Physical Powertrain and Thermal Dynamic Model.

Simulates the ground truth internal state of the vehicle, including
speed, engine RPM, load, thermal energy balance, and cooling fan actuation.
"""

from dataclasses import dataclass
from typing import Optional
from simulator.fault_injector import FaultType


@dataclass
class VehicleState:
    """Internal ground truth physical state of the vehicle at time t."""
    time_s: float
    speed_kmh: float
    rpm: float
    engine_load: float
    true_engine_temp_c: float
    cooling_fan_status: int


class VehicleModel:
    """Dynamic physics model of vehicle powertrain and cooling system.
    
    Equations:
        Heat Generation: Q_in = (k_base + k_load * load) * (rpm / 1000.0)
        Heat Dissipation: Q_out = (k_nat + k_speed * speed + k_fan * fan_status) * (T - T_ambient)
        dT/dt = (Q_in - Q_out) / thermal_capacity
    """

    def __init__(
        self,
        initial_temp_c: float = 85.0,
        ambient_temp_c: float = 25.0,
        fan_on_temp_c: float = 95.0,
        fan_off_temp_c: float = 90.0,
        thermal_capacity: float = 120.0,
        k_base: float = 4.0,
        k_load: float = 18.0,
        k_nat: float = 0.08,
        k_speed: float = 0.003,
        k_fan: float = 0.25,
    ) -> None:
        self.ambient_temp_c = ambient_temp_c
        self.fan_on_temp_c = fan_on_temp_c
        self.fan_off_temp_c = fan_off_temp_c
        self.thermal_capacity = thermal_capacity
        self.k_base = k_base
        self.k_load = k_load
        self.k_nat = k_nat
        self.k_speed = k_speed
        self.k_fan = k_fan

        # Initial state variables
        self.initial_temp_c = initial_temp_c
        self.current_time_s: float = 0.0
        self.speed_kmh: float = 45.0
        self.rpm: float = 2200.0
        self.engine_load: float = 0.50
        self.true_engine_temp_c: float = initial_temp_c
        self.cooling_fan_status: int = 0

    def step(
        self,
        dt_seconds: float,
        speed_kmh: Optional[float] = None,
        rpm: Optional[float] = None,
        engine_load: Optional[float] = None,
        fault_type: FaultType = FaultType.NORMAL,
        load_multiplier: float = 1.0,
    ) -> VehicleState:
        """Advance physical state by dt_seconds based on driving inputs and active faults."""
        # 1. Update driving kinematics and load
        if speed_kmh is not None:
            self.speed_kmh = max(0.0, speed_kmh)
        if rpm is not None:
            self.rpm = max(600.0, rpm)
        if engine_load is not None:
            self.engine_load = max(0.0, min(1.0, engine_load))

        # Apply high load fault if active
        effective_load = self.engine_load
        if fault_type == FaultType.HIGH_LOAD:
            effective_load = min(1.0, self.engine_load * load_multiplier)

        # 2. Thermostat & Cooling Fan Actuation Logic
        if fault_type == FaultType.FAN_FAILURE:
            # Physical actuator/relay failure: fan cannot turn on
            self.cooling_fan_status = 0
        else:
            # Standard ECU hysteresis thermostat control
            if self.true_engine_temp_c >= self.fan_on_temp_c:
                self.cooling_fan_status = 1
            elif self.true_engine_temp_c <= self.fan_off_temp_c:
                self.cooling_fan_status = 0

        # 3. Dynamic Thermal Energy Balance
        q_in = (self.k_base + self.k_load * effective_load) * (self.rpm / 1000.0)
        temp_diff = max(0.0, self.true_engine_temp_c - self.ambient_temp_c)
        cooling_factor = self.k_nat + (self.k_speed * self.speed_kmh) + (self.k_fan * self.cooling_fan_status)
        q_out = cooling_factor * temp_diff

        dt_temp = ((q_in - q_out) / self.thermal_capacity) * dt_seconds
        self.true_engine_temp_c += dt_temp
        self.current_time_s += dt_seconds

        return VehicleState(
            time_s=round(self.current_time_s, 3),
            speed_kmh=round(self.speed_kmh, 2),
            rpm=round(self.rpm, 1),
            engine_load=round(effective_load, 3),
            true_engine_temp_c=round(self.true_engine_temp_c, 3),
            cooling_fan_status=self.cooling_fan_status,
        )

    def reset(self) -> None:
        """Reset the physical vehicle model to initial conditions."""
        self.current_time_s = 0.0
        self.speed_kmh = 45.0
        self.rpm = 2200.0
        self.engine_load = 0.50
        self.true_engine_temp_c = self.initial_temp_c
        self.cooling_fan_status = 0
