"""Physics-Informed Nominal Vehicle Model for Cloud Digital Twin State Estimation.

Estimates the nominal physical state transitions and generates expected sensor
measurements under nominal operating conditions.
"""

from typing import Optional
from digital_twin.models import DigitalTwinState, ExpectedMeasurement, SynchronizationStatus
from digital_twin.twin_config import DigitalTwinConfig


class NominalVehicleModel:
    """Deterministic physics-informed model predicting nominal powertrain and thermal behavior.
    
    State transition equations:
        x_hat(k+1) = f(x_hat(k), u(k), dt)
        
    Heat balance equation:
        Q_in = (k_base + k_load * load) * (rpm / 1000.0)
        Q_out = (k_nat + k_speed * speed + k_fan * fan) * (T_hat - T_ambient)
        dT/dt = (Q_in - Q_out) / thermal_capacity
    """

    def __init__(self, config: Optional[DigitalTwinConfig] = None) -> None:
        self.config = config or DigitalTwinConfig()
        self.config.validate()

        # Internal nominal state variables
        self.current_time_s: float = 0.0
        self.speed_kmh: float = 45.0
        self.rpm: float = 2200.0
        self.engine_load: float = 0.50
        self.engine_temperature_c: float = self.config.initial_temp_c
        self.cooling_fan_status: int = 0
        self.last_observation_timestamp: Optional[float] = None
        self.sync_status: SynchronizationStatus = SynchronizationStatus.INITIALIZING

    def step(
        self,
        dt_seconds: float,
        input_speed_kmh: Optional[float] = None,
        input_rpm: Optional[float] = None,
        input_engine_load: Optional[float] = None,
        override_fan_status: Optional[int] = None,
    ) -> DigitalTwinState:
        """Advance the nominal model forward in time by dt_seconds.
        
        Args:
            dt_seconds: Time step in seconds (must be >= 0).
            input_speed_kmh: Observed or control speed in km/h.
            input_rpm: Observed or control engine RPM.
            input_engine_load: Observed or control load ratio in [0.0, 1.0].
            override_fan_status: Optional explicit override for cooling fan.
            
        Returns:
            The predicted nominal DigitalTwinState.
        """
        if dt_seconds < 0.0:
            raise ValueError(f"dt_seconds must be non-negative (>= 0), got {dt_seconds}")
            
        # 1. Update driving kinematics and input constraints
        if input_speed_kmh is not None:
            self.speed_kmh = max(0.0, float(input_speed_kmh))
        if input_rpm is not None:
            self.rpm = max(600.0, float(input_rpm))
        if input_engine_load is not None:
            self.engine_load = max(0.0, min(1.0, float(input_engine_load)))

        if dt_seconds == 0.0:
            return self.get_current_state()

        # 2. Thermostat & Cooling Fan Control Logic
        if override_fan_status is not None:
            self.cooling_fan_status = 1 if override_fan_status > 0 else 0
        else:
            if self.engine_temperature_c >= self.config.fan_on_temp_c:
                self.cooling_fan_status = 1
            elif self.engine_temperature_c <= self.config.fan_off_temp_c:
                self.cooling_fan_status = 0

        # 3. Dynamic Thermal Energy Balance (Euler Integration)
        q_in = (self.config.k_base + self.config.k_load * self.engine_load) * (self.rpm / 1000.0)
        temp_diff = max(0.0, self.engine_temperature_c - self.config.ambient_temp_c)
        cooling_factor = (
            self.config.k_nat + 
            (self.config.k_speed * self.speed_kmh) + 
            (self.config.k_fan * self.cooling_fan_status)
        )
        q_out = cooling_factor * temp_diff

        dt_temp = ((q_in - q_out) / self.config.thermal_capacity) * dt_seconds
        self.engine_temperature_c += dt_temp
        self.current_time_s += dt_seconds

        return self.get_current_state()

    def generate_expected_measurements(
        self,
        state: Optional[DigitalTwinState] = None,
    ) -> ExpectedMeasurement:
        """Synthesize nominal expected sensor outputs from the Digital Twin state."""
        st = state or self.get_current_state()
        return ExpectedMeasurement(
            vehicle_id=st.vehicle_id,
            timestamp=st.timestamp,
            expected_speed_kmh=round(st.estimated_speed_kmh, 2),
            expected_rpm=round(st.estimated_rpm, 1),
            expected_engine_load=round(st.estimated_engine_load, 3),
            expected_engine_temperature_c=round(st.estimated_engine_temperature_c, 3),
            expected_cooling_fan_status=st.estimated_cooling_fan_status,
        )

    def get_current_state(self) -> DigitalTwinState:
        """Return the current estimated DigitalTwinState snapshot."""
        return DigitalTwinState(
            vehicle_id=self.config.vehicle_id,
            timestamp=round(self.current_time_s, 4),
            estimated_speed_kmh=round(self.speed_kmh, 2),
            estimated_rpm=round(self.rpm, 1),
            estimated_engine_load=round(self.engine_load, 3),
            estimated_engine_temperature_c=round(self.engine_temperature_c, 3),
            estimated_cooling_fan_status=self.cooling_fan_status,
            last_observation_timestamp=self.last_observation_timestamp,
            sync_status=self.sync_status,
        )

    def reset(self, initial_temp_c: Optional[float] = None) -> None:
        """Reset internal nominal state to default initial conditions."""
        self.current_time_s = 0.0
        self.speed_kmh = 45.0
        self.rpm = 2200.0
        self.engine_load = 0.50
        self.engine_temperature_c = initial_temp_c if initial_temp_c is not None else self.config.initial_temp_c
        self.cooling_fan_status = 0
        self.last_observation_timestamp = None
        self.sync_status = SynchronizationStatus.INITIALIZING
