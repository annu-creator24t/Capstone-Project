"""Fault Injection Engine for Controlled Vehicle Diagnostics Research.

Defines supported fault modes, fault timing schedules, and transformations
applied to the physical state or sensor telemetry.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FaultType(str, Enum):
    """Enumeration of initial operating and fault modes."""
    NORMAL = "normal"
    HIGH_LOAD = "high_load"
    FAN_FAILURE = "fan_failure"
    TEMP_SENSOR_BIAS = "temp_sensor_bias"
    TEMP_SENSOR_FREEZE = "temp_sensor_freeze"
    MISSING_SENSOR_DATA = "missing_sensor_data"


@dataclass
class FaultConfig:
    """Configuration parameters for a specific fault injection."""
    fault_type: FaultType = FaultType.NORMAL
    start_time_s: float = 0.0
    end_time_s: Optional[float] = None
    
    # Fault parameter configurations
    bias_offset_c: float = 15.0          # Used for TEMP_SENSOR_BIAS
    freeze_value: Optional[float] = None # Used for TEMP_SENSOR_FREEZE (None = freeze at first fault step)
    load_multiplier: float = 1.6         # Used for HIGH_LOAD
    missing_sensor_name: str = "engine_temperature_c" # Used for MISSING_SENSOR_DATA


class FaultInjector:
    """Manages active and scheduled fault injections during a simulation run."""

    def __init__(self, config: Optional[FaultConfig] = None) -> None:
        self.config = config or FaultConfig()
        self._captured_freeze_value: Optional[float] = None

    def is_fault_active(self, current_time_s: float) -> bool:
        """Check if the configured fault is active at the current simulation timestamp."""
        if self.config.fault_type == FaultType.NORMAL:
            return False
        
        if current_time_s < self.config.start_time_s:
            return False
        
        if self.config.end_time_s is not None and current_time_s > self.config.end_time_s:
            return False
            
        return True

    def get_current_fault_type(self, current_time_s: float) -> FaultType:
        """Return the active fault type or NORMAL if inactive."""
        if self.is_fault_active(current_time_s):
            return self.config.fault_type
        return FaultType.NORMAL

    def capture_freeze_value(self, value: float) -> None:
        """Record the initial sensor value when freeze fault triggers."""
        if self._captured_freeze_value is None:
            self._captured_freeze_value = self.config.freeze_value if self.config.freeze_value is not None else value

    def get_frozen_value(self) -> Optional[float]:
        """Retrieve the captured freeze value."""
        return self._captured_freeze_value

    def reset(self) -> None:
        """Reset internal state for deterministic repeated simulation runs."""
        self._captured_freeze_value = None
