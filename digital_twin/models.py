"""Digital Twin Data Models, State Representations, and Residual Schemas.

Defines the estimated vehicle state, expected sensor measurements,
residual evaluations, anomaly statuses, and synchronization states for Cloud DT.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Dict, Optional


class SynchronizationStatus(str, Enum):
    """Synchronization health between the physical vehicle and the Cloud Digital Twin."""
    INITIALIZING = "initializing"
    SYNCHRONIZED = "synchronized"
    PARTIALLY_SYNCHRONIZED = "partially_synchronized"
    STALE = "stale"
    DISCONNECTED = "disconnected"


class AnomalyStatus(str, Enum):
    """Diagnostic classification of sensor residual evaluation."""
    NORMAL = "normal"
    ANOMALY = "anomaly"
    STALE_DATA = "stale_data"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_DATA = "invalid_data"


class FreshnessStatus(str, Enum):
    """Telemetry data freshness and temporal reliability qualification."""
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    INVALID = "invalid"
    MISSING = "missing"


@dataclass
class DigitalTwinState:
    """Estimated physical and operating state maintained by the Cloud Digital Twin."""
    vehicle_id: str
    timestamp: float
    estimated_speed_kmh: float
    estimated_rpm: float
    estimated_engine_load: float
    estimated_engine_temperature_c: float
    estimated_cooling_fan_status: int
    last_observation_timestamp: Optional[float] = None
    sync_status: SynchronizationStatus = SynchronizationStatus.INITIALIZING

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary with formatted string enums."""
        data = asdict(self)
        data["sync_status"] = self.sync_status.value
        return data


@dataclass
class ExpectedMeasurement:
    """Expected sensor measurements synthesized by the nominal Digital Twin model."""
    vehicle_id: str
    timestamp: float
    expected_speed_kmh: float
    expected_rpm: float
    expected_engine_load: float
    expected_engine_temperature_c: float
    expected_cooling_fan_status: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert expected measurements to dictionary."""
        return asdict(self)


@dataclass
class SensorResidual:
    """Evaluation of discrepancy between observed telemetry and nominal Digital Twin expectation."""
    vehicle_id: str
    sensor_name: str
    timestamp: float
    observed_value: Optional[float]
    expected_value: Optional[float] = None
    residual: Optional[float] = None
    absolute_residual: Optional[float] = None
    relative_residual: Optional[float] = None
    data_age_s: Optional[float] = None
    is_stale: bool = False
    is_accepted: bool = True
    anomaly_status: AnomalyStatus = AnomalyStatus.NORMAL
    threshold: Optional[float] = None
    details: str = ""
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH
    diagnostic_eligible: bool = True
    freshness_reason: str = ""

    def __post_init__(self) -> None:
        """Compute residual differences automatically if not explicitly provided and data is valid."""
        if (
            self.residual is None 
            and self.observed_value is not None 
            and self.expected_value is not None 
            and self.anomaly_status not in (AnomalyStatus.INSUFFICIENT_DATA, AnomalyStatus.INVALID_DATA)
        ):
            raw_r = self.observed_value - self.expected_value
            self.residual = round(raw_r, 4)
            self.absolute_residual = round(abs(raw_r), 4)

            # Safe relative residual computation avoiding division by zero
            denom = max(abs(self.expected_value), 1e-4)
            self.relative_residual = round(self.absolute_residual / denom, 4)

    def to_dict(self) -> Dict[str, Any]:
        """Convert residual to dictionary format."""
        data = asdict(self)
        data["anomaly_status"] = self.anomaly_status.value
        data["freshness_status"] = self.freshness_status.value
        return data
