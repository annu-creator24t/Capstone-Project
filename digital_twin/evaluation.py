"""Integrated Diagnostic Evaluation Framework for Connected Vehicle Digital Twin.

Provides a deterministic, reproducible experimental runner that connects the full pipeline:
Vehicle Simulator -> Fault Injection -> Network Impairment & AoI -> State Estimator ->
Nominal Model -> Residual Generator -> Telemetry Freshness -> Baseline Anomaly Detector.

Supports experimental scenarios A through G, comprehensive performance metrics, ground truth
comparison, detection delay quantification, and structured research export.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from digital_twin.anomaly_detector import BaselineAnomalyDetector
from digital_twin.models import (
    AnomalyLevel,
    AnomalyEvaluationResult,
    FreshnessStatus,
    SensorResidual,
)
from digital_twin.nominal_model import NominalVehicleModel
from digital_twin.residual_generator import ResidualGenerator
from digital_twin.state_estimator import DigitalTwinStateEstimator
from digital_twin.telemetry_freshness import TelemetryFreshnessEvaluator
from digital_twin.twin_config import DigitalTwinConfig
from network.bandwidth_model import BandwidthConfig
from network.delay_model import DelayConfig, DelayMode
from network.models import DeliveryStatus, NetworkPacket
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossConfig
from network.packet_ordering import OrderingConfig, OrderingPolicy
from network.network_emulator import NetworkEmulator
from simulator.fault_injector import FaultConfig, FaultInjector, FaultType
from simulator.sensor_generator import SensorGenerator, TelemetryPacket
from simulator.vehicle_model import VehicleModel, VehicleState


class ScenarioType(str, Enum):
    """Predefined diagnostic evaluation scenario modes."""
    CLEAN = "clean"
    AGING_STALE = "aging_stale"
    PACKET_LOSS = "packet_loss"
    DELAY_JITTER = "delay_jitter"
    DUPLICATES_OUT_OF_ORDER = "duplicates_out_of_order"
    INJECTED_FAULT = "injected_fault"
    FAULT_PLUS_IMPAIRMENT = "fault_plus_impairment"
    CUSTOM = "custom"


@dataclass
class EvaluationScenario:
    """Specification of an experimental evaluation run."""
    name: str = "Scenario_A_Clean"
    scenario_type: ScenarioType = ScenarioType.CLEAN
    duration_s: float = 20.0
    dt_s: float = 0.1
    vehicle_id: str = "EV_001"
    random_seed: int = 42
    
    # Subsystem Configurations
    fault_config: FaultConfig = field(default_factory=FaultConfig)
    network_config: NetworkConfig = field(default_factory=NetworkConfig)
    dt_config: DigitalTwinConfig = field(default_factory=DigitalTwinConfig)
    
    # Policy Overrides
    allow_aging: bool = False
    
    # Artificial transport impairment injection
    duplicate_injection_rate: float = 0.0
    stale_hold_duration_s: float = 0.0

    def validate(self) -> None:
        """Validate evaluation scenario parameters."""
        if self.duration_s < 0.0:
            raise ValueError(f"duration_s must be non-negative (>=0), got {self.duration_s}")
        if self.dt_s <= 0.0:
            raise ValueError(f"dt_s must be strictly positive (>0), got {self.dt_s}")
        if not (0.0 <= self.duplicate_injection_rate <= 1.0):
            raise ValueError(
                f"duplicate_injection_rate must be in [0.0, 1.0], got {self.duplicate_injection_rate}"
            )
        if self.stale_hold_duration_s < 0.0:
            raise ValueError(
                f"stale_hold_duration_s must be non-negative (>=0), got {self.stale_hold_duration_s}"
            )
        self.network_config.validate()
        self.dt_config.validate()


@dataclass
class EvaluationRecord:
    """Per-step snapshot capturing ground truth, telemetry, network state, residuals, and anomaly outcomes."""
    time_s: float
    ground_truth_fault_active: bool
    ground_truth_fault_type: str
    physical_state: Dict[str, Any]
    telemetry_generated: Dict[str, Any]
    packets_delivered_count: int
    delivered_packet_ids: List[str]
    expected_measurements: Dict[str, Any]
    residuals: Dict[str, Any]
    freshness_statuses: Dict[str, str]
    diagnostic_eligibilities: Dict[str, bool]
    aois: Dict[str, Optional[float]]
    anomaly_results: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary format."""
        return asdict(self)


@dataclass
class ScenarioResult:
    """Comprehensive aggregated summary and metrics for an evaluation scenario."""
    scenario_name: str
    scenario_type: str
    duration_s: float
    dt_s: float
    random_seed: int
    
    # Telemetry and Network Metrics
    total_generated_frames: int = 0
    total_packets_transmitted: int = 0
    total_packets_delivered: int = 0
    total_packets_dropped: int = 0
    packet_loss_rate_percent: float = 0.0
    
    # State Estimator Assimilation Metrics
    total_accepted_updates: int = 0
    total_rejected_updates: int = 0
    duplicate_updates: int = 0
    stale_updates: int = 0
    out_of_order_updates: int = 0
    
    # Freshness & Qualification Metrics
    freshness_counts: Dict[str, int] = field(default_factory=lambda: {s.value: 0 for s in FreshnessStatus})
    diagnostic_eligible_count: int = 0
    not_eligible_count: int = 0
    
    # Anomaly Detection Severity Metrics
    anomaly_level_counts: Dict[str, int] = field(default_factory=lambda: {s.value: 0 for s in AnomalyLevel})
    candidate_anomaly_count: int = 0
    confirmed_anomaly_count: int = 0
    
    # Ground Truth vs Diagnostic Alignment Metrics
    ground_truth_fault_frames: int = 0
    true_positive_alert_count: int = 0
    false_alert_count: int = 0
    detection_delay_s: Optional[float] = None
    
    # Freshness and Residual Statistics
    mean_aoi_s: Optional[float] = None
    max_aoi_s: Optional[float] = None
    mean_residual_by_sensor: Dict[str, float] = field(default_factory=dict)
    max_residual_by_sensor: Dict[str, float] = field(default_factory=dict)
    
    # Detailed Frame-by-Frame Trace
    records: List[EvaluationRecord] = field(default_factory=list)

    def to_summary_dict(self) -> Dict[str, Any]:
        """Export high-level summary metrics excluding voluminous per-frame traces."""
        data = asdict(self)
        data.pop("records", None)
        return data

    def to_dict(self) -> Dict[str, Any]:
        """Export complete scenario result dictionary including per-frame traces."""
        return asdict(self)


class DiagnosticEvaluationRunner:
    """Executes deterministic end-to-end connected vehicle digital twin evaluation experiments."""

    SUPPORTED_SENSORS = {
        "speed_kmh",
        "rpm",
        "engine_load",
        "engine_temperature_c",
        "cooling_fan_status",
    }

    def __init__(self) -> None:
        pass

    def run_scenario(self, scenario: EvaluationScenario) -> ScenarioResult:
        """Execute a complete deterministic simulation scenario and return structured metrics.
        
        Args:
            scenario: EvaluationScenario defining parameters, models, and network conditions.
            
        Returns:
            Structured ScenarioResult instance.
        """
        scenario.validate()

        # 1. Initialize Deterministic Subsystem Pipelines
        fault_injector = FaultInjector(config=scenario.fault_config)
        vehicle_model = VehicleModel(
            initial_temp_c=scenario.dt_config.initial_temp_c,
            ambient_temp_c=scenario.dt_config.ambient_temp_c,
            fan_on_temp_c=scenario.dt_config.fan_on_temp_c,
            fan_off_temp_c=scenario.dt_config.fan_off_temp_c,
            thermal_capacity=scenario.dt_config.thermal_capacity,
            k_base=scenario.dt_config.k_base,
            k_load=scenario.dt_config.k_load,
            k_nat=scenario.dt_config.k_nat,
            k_speed=scenario.dt_config.k_speed,
            k_fan=scenario.dt_config.k_fan,
        )
        sensor_generator = SensorGenerator(
            vehicle_id=scenario.vehicle_id,
            random_seed=scenario.random_seed,
        )
        network_emulator = NetworkEmulator(config=scenario.network_config)
        network_emulator.reset(new_seed=scenario.random_seed)

        # Digital Twin Cloud Stack
        nominal_model = NominalVehicleModel(config=scenario.dt_config)
        estimator = DigitalTwinStateEstimator(config=scenario.dt_config)
        freshness_evaluator = TelemetryFreshnessEvaluator(config=scenario.dt_config)
        residual_generator = ResidualGenerator(
            epsilon=1e-4,
            freshness_evaluator=freshness_evaluator,
            config=scenario.dt_config,
        )
        anomaly_detector = BaselineAnomalyDetector(master_config=scenario.dt_config)

        # 2. Simulation State Tracking Structures
        records: List[EvaluationRecord] = []
        steps = int(math.floor(scenario.duration_s / scenario.dt_s)) if scenario.dt_s > 0 else 0
        
        freshness_counts: Dict[str, int] = {s.value: 0 for s in FreshnessStatus}
        anomaly_level_counts: Dict[str, int] = {s.value: 0 for s in AnomalyLevel}
        
        all_aois: List[float] = []
        residuals_by_sensor: Dict[str, List[float]] = {s: [] for s in self.SUPPORTED_SENSORS}
        
        total_packets_transmitted = 0
        candidate_anomaly_count = 0
        confirmed_anomaly_count = 0
        ground_truth_fault_frames = 0
        true_positive_alert_count = 0
        false_alert_count = 0
        first_confirmed_anomaly_time: Optional[float] = None

        rng_dup = random.Random(scenario.random_seed)
        
        # Latest observed sensor telemetry dictionary maintained by Cloud DT
        latest_observed_telemetry: Dict[str, Any] = {
            "speed_kmh": 45.0,
            "rpm": 2200.0,
            "engine_load": 0.50,
            "engine_temperature_c": scenario.dt_config.initial_temp_c,
            "cooling_fan_status": 0,
        }

        # 3. Step-by-Step Simulation Execution
        for step in range(steps):
            t = round(step * scenario.dt_s, 4)
            is_fault_active = fault_injector.is_fault_active(t)
            active_fault_type = fault_injector.get_current_fault_type(t)
            if is_fault_active:
                ground_truth_fault_frames += 1

            # A. Vehicle Physical Dynamics Step
            physical_state = vehicle_model.step(
                dt_seconds=scenario.dt_s,
                fault_type=active_fault_type,
                load_multiplier=scenario.fault_config.load_multiplier,
            )

            # B. Sensor Telemetry Generation
            telemetry = sensor_generator.generate(physical_state, fault_injector)

            # C. Ingest into Network Pipeline
            scheduled = network_emulator.ingest_telemetry_frame(telemetry, current_time=t)
            total_packets_transmitted += len([p for p in scheduled if p is not None])

            # Optional artificial duplicate packet injection
            if scenario.duplicate_injection_rate > 0:
                for pkt in scheduled:
                    if pkt is not None and rng_dup.random() < scenario.duplicate_injection_rate:
                        dup_pkt = NetworkPacket(
                            packet_id=pkt.packet_id,
                            vehicle_id=pkt.vehicle_id,
                            sensor_name=pkt.sensor_name,
                            value=pkt.value,
                            generation_timestamp=pkt.generation_timestamp,
                            sequence_number=pkt.sequence_number,
                            size_bytes=pkt.size_bytes,
                        )
                        network_emulator.queue.enqueue(dup_pkt, current_time=t)
                        total_packets_transmitted += 1

            # D. Advance Network Time and Pop Delivered Packets
            # If scenario specifies artificial hold/freeze to test staleness:
            # Allow initial packets (t < 1.0s) to establish AoI tracking, then hold during stale window
            eval_network_time = t
            if scenario.stale_hold_duration_s > 0 and 1.0 <= t < (1.0 + scenario.stale_hold_duration_s):
                delivered_packets: List[NetworkPacket] = []
            else:
                delivered_packets = network_emulator.advance_time(current_time=eval_network_time)

            delivered_ids: List[str] = []

            # E. Ingest Delivered Packets into Digital Twin State Estimator
            for pkt in delivered_packets:
                delivered_ids.append(pkt.packet_id)
                estimator.update_from_packet(pkt, reception_time=t)
                if pkt.value is not None and pkt.sensor_name in latest_observed_telemetry:
                    latest_observed_telemetry[pkt.sensor_name] = pkt.value

            # F. Extract Expected Measurements from Nominal Vehicle Model
            nominal_model.step(
                dt_seconds=scenario.dt_s,
                input_speed_kmh=latest_observed_telemetry.get("speed_kmh"),
                input_rpm=latest_observed_telemetry.get("rpm"),
                input_engine_load=latest_observed_telemetry.get("engine_load"),
            )
            expected = nominal_model.generate_expected_measurements()

            # G. Query Instantaneous AoI Freshness
            aoi_map: Dict[str, Optional[float]] = {}
            for sensor in self.SUPPORTED_SENSORS:
                aoi_val = network_emulator.get_current_aoi(scenario.vehicle_id, sensor, current_time=t)
                aoi_map[sensor] = aoi_val
                if aoi_val is not None:
                    all_aois.append(aoi_val)

            # H. Generate Residuals and Qualify Freshness
            residuals = residual_generator.compute_residuals_for_frame(
                vehicle_id=scenario.vehicle_id,
                observed_telemetry=latest_observed_telemetry,
                expected_measurement=expected,
                timestamp=t,
                data_ages=aoi_map,
            )

            # I. Baseline Anomaly Detection
            anomaly_evaluations = anomaly_detector.detect_frame(
                residuals=residuals,
                allow_aging=scenario.allow_aging,
            )

            # J. Aggregate Per-Sensor Records and Trace Statistics
            rec_residuals: Dict[str, Any] = {}
            rec_freshness: Dict[str, str] = {}
            rec_eligibility: Dict[str, bool] = {}
            rec_anomalies: Dict[str, Any] = {}
            
            frame_has_confirmed_anomaly = False

            for sensor_name, res in residuals.items():
                eval_res = anomaly_evaluations[sensor_name]
                
                # Freshness counts
                freshness_counts[res.freshness_status.value] += 1
                
                # Severity counts
                anomaly_level_counts[eval_res.anomaly_level.value] += 1
                
                if eval_res.anomaly_level == AnomalyLevel.WARNING and not eval_res.is_confirmed:
                    candidate_anomaly_count += 1
                elif eval_res.anomaly_level == AnomalyLevel.ANOMALY and eval_res.is_confirmed:
                    confirmed_anomaly_count += 1
                    frame_has_confirmed_anomaly = True

                # Residual magnitude tracking
                if res.absolute_residual is not None:
                    residuals_by_sensor[sensor_name].append(res.absolute_residual)

                # Dictionaries for record
                rec_residuals[sensor_name] = res.to_dict()
                rec_freshness[sensor_name] = res.freshness_status.value
                rec_eligibility[sensor_name] = res.diagnostic_eligible
                rec_anomalies[sensor_name] = eval_res.to_dict()

            # Detection delay and false alert analysis
            if frame_has_confirmed_anomaly:
                if is_fault_active:
                    true_positive_alert_count += 1
                    if first_confirmed_anomaly_time is None:
                        first_confirmed_anomaly_time = t
                else:
                    false_alert_count += 1

            record = EvaluationRecord(
                time_s=t,
                ground_truth_fault_active=is_fault_active,
                ground_truth_fault_type=active_fault_type.value,
                physical_state={
                    "time_s": physical_state.time_s,
                    "speed_kmh": physical_state.speed_kmh,
                    "rpm": physical_state.rpm,
                    "engine_load": physical_state.engine_load,
                    "true_engine_temp_c": physical_state.true_engine_temp_c,
                    "cooling_fan_status": physical_state.cooling_fan_status,
                },
                telemetry_generated=telemetry.to_dict(),
                packets_delivered_count=len(delivered_packets),
                delivered_packet_ids=delivered_ids,
                expected_measurements=expected.to_dict(),
                residuals=rec_residuals,
                freshness_statuses=rec_freshness,
                diagnostic_eligibilities=rec_eligibility,
                aois=aoi_map,
                anomaly_results=rec_anomalies,
            )
            records.append(record)

        # 4. Compile Scenario Performance Metrics
        net_summary = network_emulator.get_performance_summary(current_time=scenario.duration_s)
        est_metrics = estimator.get_metrics()
        
        delivered_pkts = net_summary["packets_delivered"]
        dropped_pkts = net_summary["packets_dropped"]
        loss_rate = net_summary["packet_loss_rate_percent"]

        eligible_count = sum(
            1 for rec in records for elig in rec.diagnostic_eligibilities.values() if elig
        )
        total_eval_points = max(1, len(records) * len(self.SUPPORTED_SENSORS))
        not_eligible_count = total_eval_points - eligible_count

        mean_res_map: Dict[str, float] = {}
        max_res_map: Dict[str, float] = {}
        for s_name, res_list in residuals_by_sensor.items():
            if res_list:
                mean_res_map[s_name] = round(sum(res_list) / len(res_list), 4)
                max_res_map[s_name] = round(max(res_list), 4)
            else:
                mean_res_map[s_name] = 0.0
                max_res_map[s_name] = 0.0

        # Calculate detection delay if fault was injected and confirmed
        detection_delay_s: Optional[float] = None
        if scenario.fault_config.fault_type != FaultType.NORMAL and first_confirmed_anomaly_time is not None:
            detection_delay_s = round(
                max(0.0, first_confirmed_anomaly_time - scenario.fault_config.start_time_s), 4
            )

        mean_aoi = round(sum(all_aois) / len(all_aois), 4) if all_aois else None
        max_aoi = round(max(all_aois), 4) if all_aois else None

        return ScenarioResult(
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type.value,
            duration_s=scenario.duration_s,
            dt_s=scenario.dt_s,
            random_seed=scenario.random_seed,
            total_generated_frames=len(records),
            total_packets_transmitted=total_packets_transmitted,
            total_packets_delivered=delivered_pkts,
            total_packets_dropped=dropped_pkts,
            packet_loss_rate_percent=loss_rate,
            total_accepted_updates=est_metrics["accepted_updates"],
            total_rejected_updates=est_metrics["rejected_updates"],
            duplicate_updates=est_metrics["duplicate_updates"],
            stale_updates=est_metrics["stale_updates"],
            out_of_order_updates=est_metrics["out_of_order_updates"],
            freshness_counts=freshness_counts,
            diagnostic_eligible_count=eligible_count,
            not_eligible_count=not_eligible_count,
            anomaly_level_counts=anomaly_level_counts,
            candidate_anomaly_count=candidate_anomaly_count,
            confirmed_anomaly_count=confirmed_anomaly_count,
            ground_truth_fault_frames=ground_truth_fault_frames,
            true_positive_alert_count=true_positive_alert_count,
            false_alert_count=false_alert_count,
            detection_delay_s=detection_delay_s,
            mean_aoi_s=mean_aoi,
            max_aoi_s=max_aoi,
            mean_residual_by_sensor=mean_res_map,
            max_residual_by_sensor=max_res_map,
            records=records,
        )

    def run_suite(self, scenarios: List[EvaluationScenario]) -> Dict[str, ScenarioResult]:
        """Execute a batch of evaluation scenarios."""
        return {sc.name: self.run_scenario(sc) for sc in scenarios}

    # -------------------------------------------------------------------------
    # Predefined Factory Scenarios A through G
    # -------------------------------------------------------------------------
    @staticmethod
    def create_scenario_a_clean(duration_s: float = 20.0, seed: int = 42) -> EvaluationScenario:
        """Scenario A — Healthy Vehicle / Clean Link: No fault, negligible network impairment."""
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=10.0, seed=seed),
            packet_loss=PacketLossConfig(enabled=False, probability=0.0, seed=seed),
            bandwidth=BandwidthConfig(enabled=False, bandwidth_bps=1_000_000.0),
        )
        return EvaluationScenario(
            name="Scenario_A_Clean",
            scenario_type=ScenarioType.CLEAN,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            network_config=net_cfg,
        )

    @staticmethod
    def create_scenario_b_aging_stale(duration_s: float = 20.0, seed: int = 42) -> EvaluationScenario:
        """Scenario B — Telemetry Age / Staleness: Demonstrates stale telemetry is NOT treated as physical anomaly."""
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=10.0, seed=seed),
            packet_loss=PacketLossConfig(enabled=False, probability=0.0, seed=seed),
        )
        return EvaluationScenario(
            name="Scenario_B_Aging_Stale",
            scenario_type=ScenarioType.AGING_STALE,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            network_config=net_cfg,
            stale_hold_duration_s=5.0,  # Hold delivery for first 5 seconds
        )

    @staticmethod
    def create_scenario_c_packet_loss(
        duration_s: float = 20.0,
        loss_rate: float = 0.35,
        seed: int = 42,
    ) -> EvaluationScenario:
        """Scenario C — Controlled Packet Loss: Evaluates AoI evolution and diagnostic blackout windows."""
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=20.0, seed=seed),
            packet_loss=PacketLossConfig(enabled=True, probability=loss_rate, seed=seed),
        )
        return EvaluationScenario(
            name="Scenario_C_Packet_Loss",
            scenario_type=ScenarioType.PACKET_LOSS,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            network_config=net_cfg,
        )

    @staticmethod
    def create_scenario_d_delay_jitter(
        duration_s: float = 20.0,
        min_delay_ms: float = 50.0,
        max_delay_ms: float = 600.0,
        seed: int = 42,
    ) -> EvaluationScenario:
        """Scenario D — Network Delay and Jitter: Stochastic arrival times and dynamic AoI fluctuation."""
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(
                mode=DelayMode.UNIFORM,
                min_delay_ms=min_delay_ms,
                max_delay_ms=max_delay_ms,
                seed=seed,
            ),
            packet_loss=PacketLossConfig(enabled=False, probability=0.0, seed=seed),
        )
        return EvaluationScenario(
            name="Scenario_D_Delay_Jitter",
            scenario_type=ScenarioType.DELAY_JITTER,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            network_config=net_cfg,
        )

    @staticmethod
    def create_scenario_e_duplicates_out_of_order(
        duration_s: float = 20.0,
        dup_rate: float = 0.30,
        seed: int = 42,
    ) -> EvaluationScenario:
        """Scenario E — Duplicate & Out-of-Order Telemetry: Verifies robust estimator rejection and AoI stability."""
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(
                mode=DelayMode.UNIFORM,
                min_delay_ms=10.0,
                max_delay_ms=150.0,
                seed=seed,
            ),
            packet_loss=PacketLossConfig(enabled=False, probability=0.0, seed=seed),
        )
        return EvaluationScenario(
            name="Scenario_E_Duplicates_OutOfOrder",
            scenario_type=ScenarioType.DUPLICATES_OUT_OF_ORDER,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            network_config=net_cfg,
            duplicate_injection_rate=dup_rate,
        )

    @staticmethod
    def create_scenario_f_injected_fault(
        duration_s: float = 20.0,
        fault_type: FaultType = FaultType.TEMP_SENSOR_BIAS,
        fault_start_s: float = 5.0,
        fault_end_s: Optional[float] = 15.0,
        bias_offset_c: float = 15.0,
        seed: int = 42,
    ) -> EvaluationScenario:
        """Scenario F — Injected Vehicle Fault on Clean Link: Quantifies detection delay and confirmed alerts."""
        fault_cfg = FaultConfig(
            fault_type=fault_type,
            start_time_s=fault_start_s,
            end_time_s=fault_end_s,
            bias_offset_c=bias_offset_c,
        )
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=10.0, seed=seed),
            packet_loss=PacketLossConfig(enabled=False, probability=0.0, seed=seed),
        )
        return EvaluationScenario(
            name=f"Scenario_F_InjectedFault_{fault_type.value}",
            scenario_type=ScenarioType.INJECTED_FAULT,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            fault_config=fault_cfg,
            network_config=net_cfg,
        )

    @staticmethod
    def create_scenario_g_fault_plus_impairment(
        duration_s: float = 20.0,
        fault_type: FaultType = FaultType.TEMP_SENSOR_BIAS,
        fault_start_s: float = 5.0,
        fault_end_s: Optional[float] = 15.0,
        loss_probability: float = 0.25,
        seed: int = 42,
    ) -> EvaluationScenario:
        """Scenario G — Combined Injected Fault + Network Impairment: Evaluates resilience under loss and delay."""
        fault_cfg = FaultConfig(
            fault_type=fault_type,
            start_time_s=fault_start_s,
            end_time_s=fault_end_s,
            bias_offset_c=15.0,
        )
        net_cfg = NetworkConfig(
            seed=seed,
            delay=DelayConfig(
                mode=DelayMode.GAUSSIAN,
                mean_delay_ms=80.0,
                std_delay_ms=25.0,
                seed=seed,
            ),
            packet_loss=PacketLossConfig(enabled=True, probability=loss_probability, seed=seed),
        )
        return EvaluationScenario(
            name=f"Scenario_G_FaultPlusImpairment_{fault_type.value}",
            scenario_type=ScenarioType.FAULT_PLUS_IMPAIRMENT,
            duration_s=duration_s,
            dt_s=0.1,
            random_seed=seed,
            fault_config=fault_cfg,
            network_config=net_cfg,
        )
