"""Experiment Configuration System for Controlled Connected Vehicle Diagnostic Campaigns.

Defines structured configuration dataclasses for systematic research sweeps over
communication impairments, telemetry staleness/AoI, vehicle fault modes, and seeds.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from digital_twin.evaluation import EvaluationScenario, ScenarioType
from digital_twin.twin_config import DigitalTwinConfig
from network.bandwidth_model import BandwidthConfig
from network.delay_model import DelayConfig, DelayMode
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossConfig
from network.packet_ordering import OrderingConfig, OrderingPolicy
from simulator.fault_injector import FaultConfig, FaultType


class ExperimentGroup(str, Enum):
    """Categorical classification of experimental campaign groups."""
    BASELINE = "baseline"
    PACKET_LOSS_SWEEP = "packet_loss_sweep"
    DELAY_SWEEP = "delay_sweep"
    JITTER_SWEEP = "jitter_sweep"
    FAULT_SEVERITY_SWEEP = "fault_severity_sweep"
    FAULT_PACKET_LOSS = "fault_packet_loss"
    FAULT_DELAY = "fault_delay"
    COMBINED_IMPAIRMENT = "combined_impairment"
    CUSTOM = "custom"


@dataclass
class ExperimentConfig:
    """Specification of a single reproducible diagnostic experiment run."""
    experiment_id: str
    group: ExperimentGroup = ExperimentGroup.BASELINE
    description: str = ""
    seed: int = 42
    replicate_index: int = 0
    duration_s: float = 20.0
    dt_s: float = 0.1
    vehicle_id: str = "EV_001"

    # Network Transport Parameters
    packet_loss_rate: float = 0.0
    delay_mode: DelayMode = DelayMode.FIXED
    fixed_delay_ms: float = 10.0
    min_delay_ms: float = 10.0
    max_delay_ms: float = 10.0
    mean_delay_ms: float = 10.0
    std_delay_ms: float = 0.0
    duplicate_rate: float = 0.0
    stale_hold_duration_s: float = 0.0

    # Vehicle Fault Parameters
    fault_type: FaultType = FaultType.NORMAL
    fault_start_s: float = 5.0
    fault_end_s: Optional[float] = 15.0
    fault_magnitude: float = 0.0
    affected_sensor: str = "engine_temperature_c"

    # Evaluation Policy Override
    allow_aging: bool = False

    def validate(self) -> None:
        """Validate all experiment parameter bounds."""
        if not self.experiment_id or not isinstance(self.experiment_id, str):
            raise ValueError("experiment_id must be a non-empty string")
        if self.duration_s <= 0.0:
            raise ValueError(f"duration_s must be strictly positive (>0), got {self.duration_s}")
        if self.dt_s <= 0.0:
            raise ValueError(f"dt_s must be strictly positive (>0), got {self.dt_s}")
        if not (0.0 <= self.packet_loss_rate <= 1.0):
            raise ValueError(f"packet_loss_rate must be in [0.0, 1.0], got {self.packet_loss_rate}")
        if not (0.0 <= self.duplicate_rate <= 1.0):
            raise ValueError(f"duplicate_rate must be in [0.0, 1.0], got {self.duplicate_rate}")
        if self.fixed_delay_ms < 0.0:
            raise ValueError(f"fixed_delay_ms must be non-negative (>=0), got {self.fixed_delay_ms}")
        if self.min_delay_ms < 0.0 or self.max_delay_ms < self.min_delay_ms:
            raise ValueError(
                f"Invalid uniform delay bounds: min={self.min_delay_ms}, max={self.max_delay_ms}"
            )
        if self.mean_delay_ms < 0.0 or self.std_delay_ms < 0.0:
            raise ValueError(
                f"Invalid gaussian delay bounds: mean={self.mean_delay_ms}, std={self.std_delay_ms}"
            )
        if self.stale_hold_duration_s < 0.0:
            raise ValueError(
                f"stale_hold_duration_s must be non-negative (>=0), got {self.stale_hold_duration_s}"
            )
        if self.fault_start_s < 0.0:
            raise ValueError(f"fault_start_s must be non-negative (>=0), got {self.fault_start_s}")
        if self.fault_end_s is not None and self.fault_end_s < self.fault_start_s:
            raise ValueError(
                f"fault_end_s ({self.fault_end_s}) must be >= fault_start_s ({self.fault_start_s})"
            )

    def to_evaluation_scenario(self) -> EvaluationScenario:
        """Convert ExperimentConfig into an executable EvaluationScenario for Stage 4D."""
        self.validate()

        # Construct Network Configuration
        if self.delay_mode == DelayMode.FIXED:
            delay_cfg = DelayConfig(
                mode=DelayMode.FIXED,
                fixed_delay_ms=self.fixed_delay_ms,
                seed=self.seed,
            )
        elif self.delay_mode == DelayMode.UNIFORM:
            delay_cfg = DelayConfig(
                mode=DelayMode.UNIFORM,
                min_delay_ms=self.min_delay_ms,
                max_delay_ms=self.max_delay_ms,
                seed=self.seed,
            )
        elif self.delay_mode == DelayMode.GAUSSIAN:
            delay_cfg = DelayConfig(
                mode=DelayMode.GAUSSIAN,
                mean_delay_ms=self.mean_delay_ms,
                std_delay_ms=self.std_delay_ms,
                seed=self.seed,
            )
        else:
            delay_cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms, seed=self.seed)

        loss_cfg = PacketLossConfig(
            enabled=(self.packet_loss_rate > 0.0),
            probability=self.packet_loss_rate,
            seed=self.seed,
        )
        ordering_cfg = OrderingConfig(policy=OrderingPolicy.TIMESTAMP_AWARE)
        bw_cfg = BandwidthConfig(enabled=False, bandwidth_bps=1_000_000.0)

        net_cfg = NetworkConfig(
            seed=self.seed,
            delay=delay_cfg,
            packet_loss=loss_cfg,
            ordering=ordering_cfg,
            bandwidth=bw_cfg,
        )

        # Construct Fault Configuration
        fault_cfg = FaultConfig(
            fault_type=self.fault_type,
            start_time_s=self.fault_start_s,
            end_time_s=self.fault_end_s,
            bias_offset_c=self.fault_magnitude if self.fault_type == FaultType.TEMP_SENSOR_BIAS else 15.0,
            load_multiplier=self.fault_magnitude if self.fault_type == FaultType.HIGH_LOAD else 1.6,
            missing_sensor_name=self.affected_sensor,
        )

        dt_cfg = DigitalTwinConfig(vehicle_id=self.vehicle_id)

        return EvaluationScenario(
            name=self.experiment_id,
            scenario_type=ScenarioType.CUSTOM,
            duration_s=self.duration_s,
            dt_s=self.dt_s,
            vehicle_id=self.vehicle_id,
            random_seed=self.seed,
            fault_config=fault_cfg,
            network_config=net_cfg,
            dt_config=dt_cfg,
            allow_aging=self.allow_aging,
            duplicate_injection_rate=self.duplicate_rate,
            stale_hold_duration_s=self.stale_hold_duration_s,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        data = asdict(self)
        data["group"] = self.group.value
        data["delay_mode"] = self.delay_mode.value
        data["fault_type"] = self.fault_type.value
        return data
