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
class SignalThreshold:
    """Two-level threshold bounds and optional relative discrepancy limits for a single sensor."""
    warning_threshold: float
    anomaly_threshold: float
    relative_warning_threshold: Optional[float] = None
    relative_anomaly_threshold: Optional[float] = None
    unit: str = ""

    def validate(self) -> None:
        """Validate non-negativity and strictly increasing threshold ordering."""
        if self.warning_threshold < 0:
            raise ValueError(f"warning_threshold must be non-negative (>=0), got {self.warning_threshold}")
        if self.anomaly_threshold <= self.warning_threshold:
            raise ValueError(
                f"anomaly_threshold ({self.anomaly_threshold}) must be strictly greater than "
                f"warning_threshold ({self.warning_threshold})"
            )
        if self.relative_warning_threshold is not None:
            if self.relative_warning_threshold <= 0:
                raise ValueError(
                    f"relative_warning_threshold must be positive (>0), got {self.relative_warning_threshold}"
                )
        if self.relative_anomaly_threshold is not None:
            if self.relative_warning_threshold is not None:
                if self.relative_anomaly_threshold <= self.relative_warning_threshold:
                    raise ValueError(
                        f"relative_anomaly_threshold ({self.relative_anomaly_threshold}) must be strictly greater than "
                        f"relative_warning_threshold ({self.relative_warning_threshold})"
                    )
            elif self.relative_anomaly_threshold <= 0:
                raise ValueError("relative_anomaly_threshold must be positive (>0)")


@dataclass
class AnomalyThresholds:
    """Configurable two-level signal thresholds and persistence policies for baseline anomaly detection."""
    speed_kmh: SignalThreshold = field(
        default_factory=lambda: SignalThreshold(
            warning_threshold=8.0,
            anomaly_threshold=12.0,
            relative_warning_threshold=0.15,
            relative_anomaly_threshold=0.25,
            unit="km/h",
        )
    )
    rpm: SignalThreshold = field(
        default_factory=lambda: SignalThreshold(
            warning_threshold=200.0,
            anomaly_threshold=350.0,
            relative_warning_threshold=0.10,
            relative_anomaly_threshold=0.18,
            unit="RPM",
        )
    )
    engine_load: SignalThreshold = field(
        default_factory=lambda: SignalThreshold(
            warning_threshold=0.12,
            anomaly_threshold=0.20,
            relative_warning_threshold=None,
            relative_anomaly_threshold=None,
            unit="ratio",
        )
    )
    engine_temperature_c: SignalThreshold = field(
        default_factory=lambda: SignalThreshold(
            warning_threshold=5.0,
            anomaly_threshold=8.0,
            relative_warning_threshold=0.06,
            relative_anomaly_threshold=0.10,
            unit="°C",
        )
    )
    cooling_fan_status: SignalThreshold = field(
        default_factory=lambda: SignalThreshold(
            warning_threshold=0.0,
            anomaly_threshold=0.5,
            unit="state",
        )
    )

    # Persistence counters (number of consecutive samples to confirm alerts)
    warning_persistence_count: int = 1
    anomaly_persistence_count: int = 3
    allow_aging: bool = False

    def get_signal_threshold(self, sensor_name: str) -> Optional[SignalThreshold]:
        """Retrieve threshold specification for a specific sensor."""
        return getattr(self, sensor_name, None)

    def validate(self) -> None:
        """Validate all signal threshold specifications and persistence counts."""
        if self.warning_persistence_count < 1:
            raise ValueError(
                f"warning_persistence_count must be >= 1, got {self.warning_persistence_count}"
            )
        if self.anomaly_persistence_count < 1:
            raise ValueError(
                f"anomaly_persistence_count must be >= 1, got {self.anomaly_persistence_count}"
            )

        for sensor in ("speed_kmh", "rpm", "engine_load", "engine_temperature_c", "cooling_fan_status"):
            th = getattr(self, sensor, None)
            if th is not None:
                th.validate()


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
    anomaly_thresholds: AnomalyThresholds = field(default_factory=AnomalyThresholds)

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
        self.anomaly_thresholds.validate()
