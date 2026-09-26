"""Configuration Parameters for Cloud Digital Twin State Estimation & Residual Thresholds."""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ResidualThresholds:
    """Threshold limits for baseline residual anomaly detection."""
    engine_temperature_c: float = 8.0  # Deviation > 8°C flags anomaly
    rpm: float = 350.0                # RPM deviation threshold
    speed_kmh: float = 12.0           # Speed deviation threshold
    engine_load: float = 0.20         # Engine load deviation threshold
    cooling_fan_status: float = 0.5   # Binary actuator discrepancy

    def get_threshold(self, sensor_name: str) -> Optional[float]:
        """Retrieve threshold value for a specific sensor."""
        return getattr(self, sensor_name, None)


@dataclass
class SynchronizationThresholds:
    """Freshness thresholds for determining Digital Twin sync health."""
    stale_aoi_threshold_s: float = 3.0       # AoI > 3.0s considered stale
    disconnect_aoi_threshold_s: float = 10.0 # AoI > 10.0s considered disconnected


@dataclass
class FreshnessThresholds:
    """Threshold limits for evaluating telemetry freshness and diagnostic eligibility."""
    fresh_aoi_threshold_s: float = 1.0       # 0 <= AoI <= 1.0s -> FRESH
    stale_aoi_threshold_s: float = 3.0       # 1.0s < AoI <= 3.0s -> AGING, AoI > 3.0s -> STALE

    def validate(self) -> None:
        """Validate freshness threshold ordering and positive bounds."""
        if self.fresh_aoi_threshold_s <= 0:
            raise ValueError(f"fresh_aoi_threshold_s must be positive (>0), got {self.fresh_aoi_threshold_s}")
        if self.stale_aoi_threshold_s <= self.fresh_aoi_threshold_s:
            raise ValueError(
                f"stale_aoi_threshold_s ({self.stale_aoi_threshold_s}) must be strictly greater than "
                f"fresh_aoi_threshold_s ({self.fresh_aoi_threshold_s})"
            )


@dataclass
class DigitalTwinConfig:
    """Master configuration for the Cloud Digital Twin."""
    vehicle_id: str = "EV_001"
    initial_temp_c: float = 85.0
    ambient_temp_c: float = 25.0
    fan_on_temp_c: float = 95.0
    fan_off_temp_c: float = 90.0
    thermal_capacity: float = 120.0
    k_base: float = 4.0
    k_load: float = 18.0
    k_nat: float = 0.08
    k_speed: float = 0.003
    k_fan: float = 0.25

    # Sub-configurations
    thresholds: ResidualThresholds = field(default_factory=ResidualThresholds)
    sync_thresholds: SynchronizationThresholds = field(default_factory=SynchronizationThresholds)
    freshness_thresholds: FreshnessThresholds = field(default_factory=FreshnessThresholds)

    def validate(self) -> None:
        """Validate physical and threshold parameters."""
        if self.thermal_capacity <= 0:
            raise ValueError(f"thermal_capacity must be positive, got {self.thermal_capacity}")
        if self.fan_off_temp_c >= self.fan_on_temp_c:
            raise ValueError(
                f"fan_off_temp_c ({self.fan_off_temp_c}) must be < fan_on_temp_c ({self.fan_on_temp_c})"
            )
        if self.sync_thresholds.stale_aoi_threshold_s <= 0:
            raise ValueError("stale_aoi_threshold_s must be positive")
        if self.sync_thresholds.disconnect_aoi_threshold_s <= self.sync_thresholds.stale_aoi_threshold_s:
            raise ValueError("disconnect_aoi_threshold_s must be greater than stale_aoi_threshold_s")
        self.freshness_thresholds.validate()
