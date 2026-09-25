"""Sensor Telemetry Generator for Connected Vehicles.

Transforms ground truth physical state into noisy, quantized telemetry packets
and applies sensor-level faults (bias, freeze, missing data).
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
import random
from typing import Any, Dict, Optional

from simulator.fault_injector import FaultInjector, FaultType
from simulator.vehicle_model import VehicleState


@dataclass
class TelemetryPacket:
    """Standardized connected vehicle telemetry schema."""
    vehicle_id: str
    timestamp: str
    speed_kmh: float
    rpm: float
    engine_load: float
    engine_temperature_c: Optional[float]
    cooling_fan_status: int
    fault_status: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert telemetry packet to dictionary format."""
        return asdict(self)


class SensorGenerator:
    """Generates sensor measurements with realistic Gaussian noise and sensor faults."""

    def __init__(
        self,
        vehicle_id: str = "EV_001",
        random_seed: Optional[int] = 42,
        base_timestamp: Optional[datetime] = None,
        temp_noise_std: float = 0.3,
        speed_noise_std: float = 0.4,
        rpm_noise_std: float = 15.0,
        load_noise_std: float = 0.01,
    ) -> None:
        self.vehicle_id = vehicle_id
        self.random_seed = random_seed
        self._rng = random.Random(random_seed)
        self.base_timestamp = base_timestamp or datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc)

        # Noise parameters (Standard Deviations)
        self.temp_noise_std = temp_noise_std
        self.speed_noise_std = speed_noise_std
        self.rpm_noise_std = rpm_noise_std
        self.load_noise_std = load_noise_std

    def generate(
        self,
        physical_state: VehicleState,
        fault_injector: FaultInjector,
    ) -> TelemetryPacket:
        """Produce a noisy, fault-injected telemetry packet from ground truth vehicle state."""
        fault_type = fault_injector.get_current_fault_type(physical_state.time_s)
        
        # Calculate ISO-8601 UTC timestamp
        packet_time = self.base_timestamp + timedelta(seconds=physical_state.time_s)
        timestamp_str = packet_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Add zero-mean Gaussian noise to continuous signals
        speed_meas = round(physical_state.speed_kmh + self._rng.gauss(0.0, self.speed_noise_std), 1)
        speed_meas = max(0.0, speed_meas)

        rpm_meas = round(physical_state.rpm + self._rng.gauss(0.0, self.rpm_noise_std), 0)
        rpm_meas = max(600.0, rpm_meas)

        load_meas = round(physical_state.engine_load + self._rng.gauss(0.0, self.load_noise_std), 2)
        load_meas = max(0.0, min(1.0, load_meas))

        # 2. Process temperature sensor signal based on fault mode
        raw_temp = physical_state.true_engine_temp_c + self._rng.gauss(0.0, self.temp_noise_std)
        sensed_temp: Optional[float] = round(raw_temp, 1)

        if fault_type == FaultType.TEMP_SENSOR_BIAS:
            # Add static sensor calibration drift/bias offset
            sensed_temp = round(raw_temp + fault_injector.config.bias_offset_c, 1)

        elif fault_type == FaultType.TEMP_SENSOR_FREEZE:
            # Capture initial freeze value and keep repeating it
            fault_injector.capture_freeze_value(round(raw_temp, 1))
            sensed_temp = fault_injector.get_frozen_value()

        elif fault_type == FaultType.MISSING_SENSOR_DATA:
            # Drop telemetry field to simulate intermittent sensor transmission failure
            if fault_injector.config.missing_sensor_name == "engine_temperature_c":
                sensed_temp = None

        return TelemetryPacket(
            vehicle_id=self.vehicle_id,
            timestamp=timestamp_str,
            speed_kmh=speed_meas,
            rpm=rpm_meas,
            engine_load=load_meas,
            engine_temperature_c=sensed_temp,
            cooling_fan_status=physical_state.cooling_fan_status,
            fault_status=fault_type.value,
        )

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Reset the random number generator for reproducible experiment runs."""
        seed = new_seed if new_seed is not None else self.random_seed
        self._rng = random.Random(seed)
