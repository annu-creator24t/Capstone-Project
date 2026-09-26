"""Experiment Runner and Research Campaign Orchestrator for Connected Vehicle Digital Twin.

Orchestrates multi-parameter research campaigns, executes deterministic experimental matrix groups,
aggregates comprehensive cross-layer metrics, and generates publication-ready CSV/JSON datasets.
"""

import csv
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Sequence

from digital_twin.evaluation import DiagnosticEvaluationRunner, ScenarioResult
from digital_twin.experiment_config import ExperimentConfig, ExperimentGroup
from digital_twin.models import AnomalyLevel, FreshnessStatus
from network.delay_model import DelayMode
from simulator.fault_injector import FaultType


@dataclass
class ExperimentResult:
    """Structured container capturing configuration, cross-layer metrics, and ground truth for an experiment."""
    # Identification and Group
    experiment_id: str
    group: str
    seed: int
    replicate_index: int
    description: str = ""

    # Parameter Metadata
    duration_s: float = 20.0
    dt_s: float = 0.1
    vehicle_id: str = "EV_001"
    fault_type: str = "normal"
    fault_magnitude: float = 0.0
    fault_start_s: float = 0.0
    fault_end_s: Optional[float] = None
    packet_loss_rate: float = 0.0
    delay_ms: float = 10.0
    jitter_ms: float = 0.0
    duplicate_rate: float = 0.0
    stale_hold_duration_s: float = 0.0
    allow_aging: bool = False

    # Transport / Network Metrics
    total_generated_frames: int = 0
    total_packets_transmitted: int = 0
    total_packets_delivered: int = 0
    total_packets_dropped: int = 0
    packet_loss_rate_percent: float = 0.0

    # Estimator Metrics
    total_accepted_updates: int = 0
    total_rejected_updates: int = 0
    duplicate_updates: int = 0
    stale_updates: int = 0
    out_of_order_updates: int = 0

    # Freshness & Eligibility Metrics
    fresh_count: int = 0
    aging_count: int = 0
    stale_count: int = 0
    invalid_count: int = 0
    missing_count: int = 0
    diagnostic_eligible_count: int = 0
    not_eligible_count: int = 0

    # Diagnostic & Anomaly Metrics
    normal_count: int = 0
    warning_count: int = 0
    candidate_anomaly_count: int = 0
    confirmed_anomaly_count: int = 0
    not_evaluated_count: int = 0
    false_alert_count: int = 0
    true_positive_alert_count: int = 0
    detection_delay_s: Optional[float] = None

    # Signal & AoI Statistics
    mean_aoi_s: Optional[float] = None
    max_aoi_s: Optional[float] = None
    mean_temp_residual: float = 0.0
    max_temp_residual: float = 0.0
    mean_residual_by_sensor: Dict[str, float] = field(default_factory=dict)
    max_residual_by_sensor: Dict[str, float] = field(default_factory=dict)

    # Ground Truth
    ground_truth_fault_frames: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert result into a structured dictionary."""
        return asdict(self)

    def to_csv_row(self) -> Dict[str, Any]:
        """Generate a flattened 1-D dictionary formatted for tabular CSV research exports."""
        row = asdict(self)
        # Exclude nested sub-dictionaries for clean CSV export
        row.pop("mean_residual_by_sensor", None)
        row.pop("max_residual_by_sensor", None)
        return row


class ExperimentCampaign:
    """Factory creating standardized, reproducible experimental parameter sweeps."""

    @staticmethod
    def create_baseline_group(
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group A — Baseline Healthy Vehicle on clean link."""
        configs: List[ExperimentConfig] = []
        for idx, seed in enumerate(seeds):
            configs.append(
                ExperimentConfig(
                    experiment_id=f"EXP_A_Baseline_rep{idx}_seed{seed}",
                    group=ExperimentGroup.BASELINE,
                    description="Baseline healthy vehicle under minimal network delay",
                    seed=seed,
                    replicate_index=idx,
                    duration_s=duration_s,
                    packet_loss_rate=0.0,
                    delay_mode=DelayMode.FIXED,
                    fixed_delay_ms=10.0,
                    fault_type=FaultType.NORMAL,
                )
            )
        return configs

    @staticmethod
    def create_packet_loss_sweep_group(
        loss_rates: Sequence[float] = (0.0, 0.10, 0.20, 0.35, 0.50),
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group B — Packet Loss Sweep on healthy vehicle."""
        configs: List[ExperimentConfig] = []
        for loss in loss_rates:
            loss_pct = int(round(loss * 100))
            for idx, seed in enumerate(seeds):
                configs.append(
                    ExperimentConfig(
                        experiment_id=f"EXP_B_Loss_{loss_pct}pct_rep{idx}_seed{seed}",
                        group=ExperimentGroup.PACKET_LOSS_SWEEP,
                        description=f"Packet loss sweep at {loss_pct}% loss",
                        seed=seed,
                        replicate_index=idx,
                        duration_s=duration_s,
                        packet_loss_rate=loss,
                        delay_mode=DelayMode.FIXED,
                        fixed_delay_ms=10.0,
                        fault_type=FaultType.NORMAL,
                    )
                )
        return configs

    @staticmethod
    def create_delay_sweep_group(
        delays_ms: Sequence[float] = (10.0, 50.0, 100.0, 300.0, 600.0),
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group C — Fixed Delay Sweep on healthy vehicle."""
        configs: List[ExperimentConfig] = []
        for delay in delays_ms:
            delay_int = int(round(delay))
            for idx, seed in enumerate(seeds):
                configs.append(
                    ExperimentConfig(
                        experiment_id=f"EXP_C_Delay_{delay_int}ms_rep{idx}_seed{seed}",
                        group=ExperimentGroup.DELAY_SWEEP,
                        description=f"Fixed delay sweep at {delay_int}ms",
                        seed=seed,
                        replicate_index=idx,
                        duration_s=duration_s,
                        packet_loss_rate=0.0,
                        delay_mode=DelayMode.FIXED,
                        fixed_delay_ms=delay,
                        fault_type=FaultType.NORMAL,
                    )
                )
        return configs

    @staticmethod
    def create_jitter_sweep_group(
        jitters_ms: Sequence[float] = (0.0, 25.0, 50.0, 100.0, 250.0),
        base_delay_ms: float = 100.0,
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group D — Delay Jitter Sweep on healthy vehicle."""
        configs: List[ExperimentConfig] = []
        for jitter in jitters_ms:
            jitter_int = int(round(jitter))
            min_d = max(0.0, base_delay_ms - jitter)
            max_d = base_delay_ms + jitter
            for idx, seed in enumerate(seeds):
                configs.append(
                    ExperimentConfig(
                        experiment_id=f"EXP_D_Jitter_{jitter_int}ms_rep{idx}_seed{seed}",
                        group=ExperimentGroup.JITTER_SWEEP,
                        description=f"Delay jitter sweep: {base_delay_ms:.0f}ms +/- {jitter_int}ms",
                        seed=seed,
                        replicate_index=idx,
                        duration_s=duration_s,
                        packet_loss_rate=0.0,
                        delay_mode=DelayMode.FIXED if jitter == 0.0 else DelayMode.UNIFORM,
                        fixed_delay_ms=base_delay_ms,
                        min_delay_ms=min_d,
                        max_delay_ms=max_d,
                        mean_delay_ms=base_delay_ms,
                        std_delay_ms=jitter,
                        fault_type=FaultType.NORMAL,
                    )
                )
        return configs

    @staticmethod
    def create_fault_severity_sweep_group(
        biases_c: Sequence[float] = (5.0, 10.0, 15.0, 20.0),
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group E — Injected Fault Severity Sweep on clean link."""
        configs: List[ExperimentConfig] = []
        f_start = round(min(2.0, max(0.5, duration_s * 0.2)), 2)
        f_end = round(max(f_start + 1.0, duration_s * 0.8), 2)
        for bias in biases_c:
            bias_int = int(round(bias))
            for idx, seed in enumerate(seeds):
                configs.append(
                    ExperimentConfig(
                        experiment_id=f"EXP_E_FaultBias_{bias_int}C_rep{idx}_seed{seed}",
                        group=ExperimentGroup.FAULT_SEVERITY_SWEEP,
                        description=f"Thermal sensor bias fault at +{bias_int}C on clean link",
                        seed=seed,
                        replicate_index=idx,
                        duration_s=duration_s,
                        packet_loss_rate=0.0,
                        delay_mode=DelayMode.FIXED,
                        fixed_delay_ms=10.0,
                        fault_type=FaultType.TEMP_SENSOR_BIAS,
                        fault_magnitude=bias,
                        fault_start_s=f_start,
                        fault_end_s=f_end,
                    )
                )
        return configs

    @staticmethod
    def create_fault_packet_loss_group(
        bias_c: float = 15.0,
        loss_rates: Sequence[float] = (0.0, 0.10, 0.20, 0.35, 0.50),
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group F — Injected Fault + Packet Loss Sweep."""
        configs: List[ExperimentConfig] = []
        bias_int = int(round(bias_c))
        f_start = round(min(2.0, max(0.5, duration_s * 0.2)), 2)
        f_end = round(max(f_start + 1.0, duration_s * 0.8), 2)
        for loss in loss_rates:
            loss_pct = int(round(loss * 100))
            for idx, seed in enumerate(seeds):
                configs.append(
                    ExperimentConfig(
                        experiment_id=f"EXP_F_FaultPlusLoss_{bias_int}C_{loss_pct}pct_rep{idx}_seed{seed}",
                        group=ExperimentGroup.FAULT_PACKET_LOSS,
                        description=f"Thermal fault (+{bias_int}C) combined with {loss_pct}% packet loss",
                        seed=seed,
                        replicate_index=idx,
                        duration_s=duration_s,
                        packet_loss_rate=loss,
                        delay_mode=DelayMode.FIXED,
                        fixed_delay_ms=10.0,
                        fault_type=FaultType.TEMP_SENSOR_BIAS,
                        fault_magnitude=bias_c,
                        fault_start_s=f_start,
                        fault_end_s=f_end,
                    )
                )
        return configs

    @staticmethod
    def create_fault_delay_group(
        bias_c: float = 15.0,
        delays_ms: Sequence[float] = (10.0, 50.0, 100.0, 300.0, 600.0),
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group G — Injected Fault + Network Delay Sweep."""
        configs: List[ExperimentConfig] = []
        bias_int = int(round(bias_c))
        f_start = round(min(2.0, max(0.5, duration_s * 0.2)), 2)
        f_end = round(max(f_start + 1.0, duration_s * 0.8), 2)
        for delay in delays_ms:
            delay_int = int(round(delay))
            for idx, seed in enumerate(seeds):
                configs.append(
                    ExperimentConfig(
                        experiment_id=f"EXP_G_FaultPlusDelay_{bias_int}C_{delay_int}ms_rep{idx}_seed{seed}",
                        group=ExperimentGroup.FAULT_DELAY,
                        description=f"Thermal fault (+{bias_int}C) combined with {delay_int}ms delay",
                        seed=seed,
                        replicate_index=idx,
                        duration_s=duration_s,
                        packet_loss_rate=0.0,
                        delay_mode=DelayMode.FIXED,
                        fixed_delay_ms=delay,
                        fault_type=FaultType.TEMP_SENSOR_BIAS,
                        fault_magnitude=bias_c,
                        fault_start_s=f_start,
                        fault_end_s=f_end,
                    )
                )
        return configs

    @staticmethod
    def create_combined_impairment_group(
        seeds: Sequence[int] = (101, 202, 303),
        duration_s: float = 20.0,
    ) -> List[ExperimentConfig]:
        """Group H — Combined Injected Fault + Packet Loss + Delay + Jitter."""
        configs: List[ExperimentConfig] = []
        f_start = round(min(2.0, max(0.5, duration_s * 0.2)), 2)
        f_end = round(max(f_start + 1.0, duration_s * 0.8), 2)
        for idx, seed in enumerate(seeds):
            configs.append(
                ExperimentConfig(
                    experiment_id=f"EXP_H_CombinedImpairment_rep{idx}_seed{seed}",
                    group=ExperimentGroup.COMBINED_IMPAIRMENT,
                    description="Thermal fault (+15C) + 25% loss + 80ms Gaussian delay (+/-25ms jitter)",
                    seed=seed,
                    replicate_index=idx,
                    duration_s=duration_s,
                    packet_loss_rate=0.25,
                    delay_mode=DelayMode.GAUSSIAN,
                    mean_delay_ms=80.0,
                    std_delay_ms=25.0,
                    fault_type=FaultType.TEMP_SENSOR_BIAS,
                    fault_magnitude=15.0,
                    fault_start_s=f_start,
                    fault_end_s=f_end,
                )
            )
        return configs

    @classmethod
    def create_full_campaign(
        cls,
        seeds: Sequence[int] = (42, 101, 202),
        duration_s: float = 20.0,
        group_h_seeds: Optional[Sequence[int]] = (101, 202, 303),
    ) -> List[ExperimentConfig]:
        """Build the consolidated master experimental matrix covering all groups A through H."""
        full_list: List[ExperimentConfig] = []
        full_list.extend(cls.create_baseline_group(seeds=seeds, duration_s=duration_s))
        full_list.extend(cls.create_packet_loss_sweep_group(seeds=seeds, duration_s=duration_s))
        full_list.extend(cls.create_delay_sweep_group(seeds=seeds, duration_s=duration_s))
        full_list.extend(cls.create_jitter_sweep_group(seeds=seeds, duration_s=duration_s))
        full_list.extend(cls.create_fault_severity_sweep_group(seeds=seeds, duration_s=duration_s))
        full_list.extend(cls.create_fault_packet_loss_group(seeds=seeds, duration_s=duration_s))
        full_list.extend(cls.create_fault_delay_group(seeds=seeds, duration_s=duration_s))
        h_seeds = group_h_seeds if group_h_seeds is not None else seeds
        full_list.extend(cls.create_combined_impairment_group(seeds=h_seeds, duration_s=duration_s))
        return full_list


class ExperimentRunner:
    """Executes experiment campaigns, translates results, and exports research datasets."""

    def __init__(self) -> None:
        self.eval_runner = DiagnosticEvaluationRunner()

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Execute a single deterministic experiment and return a structured ExperimentResult."""
        scenario = config.to_evaluation_scenario()
        scenario_res: ScenarioResult = self.eval_runner.run_scenario(scenario)

        # Extract thermal residual statistics
        temp_mean = scenario_res.mean_residual_by_sensor.get("engine_temperature_c", 0.0)
        temp_max = scenario_res.max_residual_by_sensor.get("engine_temperature_c", 0.0)

        # Extract delay in ms for summary
        if config.delay_mode == DelayMode.FIXED:
            delay_val_ms = config.fixed_delay_ms
            jitter_val_ms = 0.0
        elif config.delay_mode == DelayMode.UNIFORM:
            delay_val_ms = (config.min_delay_ms + config.max_delay_ms) / 2.0
            jitter_val_ms = (config.max_delay_ms - config.min_delay_ms) / 2.0
        elif config.delay_mode == DelayMode.GAUSSIAN:
            delay_val_ms = config.mean_delay_ms
            jitter_val_ms = config.std_delay_ms
        else:
            delay_val_ms = config.fixed_delay_ms
            jitter_val_ms = 0.0

        return ExperimentResult(
            experiment_id=config.experiment_id,
            group=config.group.value,
            seed=config.seed,
            replicate_index=config.replicate_index,
            description=config.description,
            duration_s=config.duration_s,
            dt_s=config.dt_s,
            vehicle_id=config.vehicle_id,
            fault_type=config.fault_type.value,
            fault_magnitude=config.fault_magnitude,
            fault_start_s=config.fault_start_s,
            fault_end_s=config.fault_end_s,
            packet_loss_rate=config.packet_loss_rate,
            delay_ms=delay_val_ms,
            jitter_ms=jitter_val_ms,
            duplicate_rate=config.duplicate_rate,
            stale_hold_duration_s=config.stale_hold_duration_s,
            allow_aging=config.allow_aging,
            total_generated_frames=scenario_res.total_generated_frames,
            total_packets_transmitted=scenario_res.total_packets_transmitted,
            total_packets_delivered=scenario_res.total_packets_delivered,
            total_packets_dropped=scenario_res.total_packets_dropped,
            packet_loss_rate_percent=scenario_res.packet_loss_rate_percent,
            total_accepted_updates=scenario_res.total_accepted_updates,
            total_rejected_updates=scenario_res.total_rejected_updates,
            duplicate_updates=scenario_res.duplicate_updates,
            stale_updates=scenario_res.stale_updates,
            out_of_order_updates=scenario_res.out_of_order_updates,
            fresh_count=scenario_res.freshness_counts.get(FreshnessStatus.FRESH.value, 0),
            aging_count=scenario_res.freshness_counts.get(FreshnessStatus.AGING.value, 0),
            stale_count=scenario_res.freshness_counts.get(FreshnessStatus.STALE.value, 0),
            invalid_count=scenario_res.freshness_counts.get(FreshnessStatus.INVALID.value, 0),
            missing_count=scenario_res.freshness_counts.get(FreshnessStatus.MISSING.value, 0),
            diagnostic_eligible_count=scenario_res.diagnostic_eligible_count,
            not_eligible_count=scenario_res.not_eligible_count,
            normal_count=scenario_res.anomaly_level_counts.get(AnomalyLevel.NORMAL.value, 0),
            warning_count=scenario_res.anomaly_level_counts.get(AnomalyLevel.WARNING.value, 0),
            candidate_anomaly_count=scenario_res.candidate_anomaly_count,
            confirmed_anomaly_count=scenario_res.confirmed_anomaly_count,
            not_evaluated_count=scenario_res.anomaly_level_counts.get(AnomalyLevel.NOT_EVALUATED.value, 0),
            false_alert_count=scenario_res.false_alert_count,
            true_positive_alert_count=scenario_res.true_positive_alert_count,
            detection_delay_s=scenario_res.detection_delay_s,
            mean_aoi_s=scenario_res.mean_aoi_s,
            max_aoi_s=scenario_res.max_aoi_s,
            mean_temp_residual=temp_mean,
            max_temp_residual=temp_max,
            mean_residual_by_sensor=scenario_res.mean_residual_by_sensor,
            max_residual_by_sensor=scenario_res.max_residual_by_sensor,
            ground_truth_fault_frames=scenario_res.ground_truth_fault_frames,
        )

    def run_campaign(self, configs: List[ExperimentConfig]) -> List[ExperimentResult]:
        """Execute a batch of experimental configurations sequentially."""
        return [self.run_experiment(cfg) for cfg in configs]

    @staticmethod
    def export_to_csv(results: List[ExperimentResult], file_path: str) -> None:
        """Export experiment results to a standard tabular CSV file."""
        if not results:
            return

        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        rows = [res.to_csv_row() for res in results]
        fieldnames = list(rows[0].keys())

        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def export_to_json(
        results: List[ExperimentResult],
        file_path: str,
        indent: int = 2,
    ) -> None:
        """Export experiment results to structured JSON."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        data = [res.to_dict() for res in results]
        with open(file_path, mode="w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)

    @staticmethod
    def generate_manifest(
        configs: List[ExperimentConfig],
        file_path: str,
        indent: int = 2,
    ) -> None:
        """Export experiment specifications manifest describing planned experiments."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        manifest_data = {
            "total_experiments": len(configs),
            "experiments": [cfg.to_dict() for cfg in configs],
        }
        with open(file_path, mode="w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=indent)
