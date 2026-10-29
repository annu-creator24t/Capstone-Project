"""Simulation Session Manager for the Connected Vehicle Digital Twin Dashboard.

Integrates:
  - simulator.vehicle_model.VehicleModel
  - simulator.fault_injector.FaultInjector
  - simulator.sensor_generator.SensorGenerator
  - network.network_emulator.NetworkEmulator
  - digital_twin.nominal_model.NominalVehicleModel
  - digital_twin.state_estimator.DigitalTwinStateEstimator
  - digital_twin.residual_generator.ResidualGenerator
  - digital_twin.anomaly_detector.BaselineAnomalyDetector
"""

import collections
import math
import os
import sys
from typing import Any, Deque, Dict, List, Optional, Tuple

import pandas as pd

# Add repository root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulator.fault_injector import FaultConfig, FaultInjector, FaultType
from simulator.sensor_generator import SensorGenerator
from simulator.vehicle_model import VehicleModel, VehicleState
from network.delay_model import DelayConfig, DelayMode, DelayModel
from network.packet_loss import PacketLossConfig, PacketLossModel
from network.network_config import NetworkConfig
from network.network_emulator import NetworkEmulator
from digital_twin.anomaly_detector import AnomalyLevel, BaselineAnomalyDetector
from digital_twin.models import FreshnessStatus, SensorResidual
from digital_twin.nominal_model import NominalVehicleModel
from digital_twin.residual_generator import ResidualGenerator
from digital_twin.state_estimator import DigitalTwinStateEstimator
from digital_twin.telemetry_freshness import TelemetryFreshnessEvaluator
from digital_twin.twin_config import DigitalTwinConfig


class DashboardSimulationSession:
    """Manages an interactive discrete simulation session for connected vehicle digital twin."""

    def __init__(
        self,
        vehicle_id: str = "EV_001",
        dt_s: float = 0.1,
        seed: int = 42,
        history_maxlen: int = 300,
    ) -> None:
        self.vehicle_id = vehicle_id
        self.dt_s = dt_s
        self.seed = seed
        self.history_maxlen = history_maxlen

        # Configurable fault parameters
        self.fault_type = FaultType.NORMAL
        self.fault_bias_offset_c: float = 15.0
        self.fault_start_s: float = 0.0
        self.fault_end_s: Optional[float] = None
        self.load_multiplier: float = 1.0

        # Configurable network parameters
        self.packet_loss_rate: float = 0.05
        self.delay_mode: DelayMode = DelayMode.FIXED
        self.fixed_delay_ms: float = 40.0
        self.mean_delay_ms: float = 40.0
        self.std_delay_ms: float = 10.0

        # State tracking & alert feed
        self.history: Deque[Dict[str, Any]] = collections.deque(maxlen=history_maxlen)
        self.alerts: Deque[Dict[str, Any]] = collections.deque(maxlen=100)

        self.reset(seed=self.seed)

    def reset(self, seed: Optional[int] = None, initial_temp_c: Optional[float] = None) -> None:
        """Reset simulation state, vehicle physics, network, and digital twin models."""
        if seed is not None:
            self.seed = seed

        self.time_s: float = 0.0
        self.step_index: int = 0
        self.total_packets_transmitted: int = 0
        self.total_packets_delivered: int = 0
        self.total_packets_dropped: int = 0
        self.confirmed_anomaly_count: int = 0
        self.first_anomaly_time: Optional[float] = None

        self.history.clear()
        self.alerts.clear()

        # 1. Fault Injector
        self._init_fault_injector()

        # 2. Vehicle Model & Sensor Generator
        self.dt_config = DigitalTwinConfig()
        init_temp = initial_temp_c if initial_temp_c is not None else self.dt_config.initial_temp_c
        self.vehicle = VehicleModel(
            initial_temp_c=init_temp,
            ambient_temp_c=self.dt_config.ambient_temp_c,
            fan_on_temp_c=self.dt_config.fan_on_temp_c,
            fan_off_temp_c=self.dt_config.fan_off_temp_c,
            thermal_capacity=self.dt_config.thermal_capacity,
            k_base=self.dt_config.k_base,
            k_load=self.dt_config.k_load,
            k_nat=self.dt_config.k_nat,
            k_speed=self.dt_config.k_speed,
            k_fan=self.dt_config.k_fan,
        )
        self.sensor_generator = SensorGenerator(
            vehicle_id=self.vehicle_id, random_seed=self.seed
        )

        # 3. Network Emulator Pipeline
        self._init_network_emulator()

        # 4. Cloud Digital Twin Models
        self.nominal_model = NominalVehicleModel(config=self.dt_config)
        if initial_temp_c is not None:
            self.nominal_model.reset(initial_temp_c=initial_temp_c)
        self.state_estimator = DigitalTwinStateEstimator(config=self.dt_config)
        self.freshness_evaluator = TelemetryFreshnessEvaluator(config=self.dt_config)
        self.residual_generator = ResidualGenerator(
            epsilon=1e-4,
            freshness_evaluator=self.freshness_evaluator,
            config=self.dt_config,
        )
        self.anomaly_detector = BaselineAnomalyDetector(
            master_config=self.dt_config
        )

        # Observation buffer maintained by Cloud DT
        self.latest_observed_telemetry: Dict[str, Any] = {
            "speed_kmh": 45.0,
            "rpm": 2200.0,
            "engine_load": 0.50,
            "engine_temperature_c": init_temp,
            "cooling_fan_status": 0,
        }

        # Step once at t=0 to populate initial valid record
        self.step(n_steps=1)

    def _init_fault_injector(self) -> None:
        """Instantiate fault injector with current parameters."""
        cfg = FaultConfig(
            fault_type=self.fault_type,
            start_time_s=self.fault_start_s,
            end_time_s=self.fault_end_s,
            bias_offset_c=self.fault_bias_offset_c,
            load_multiplier=self.load_multiplier,
        )
        self.fault_injector = FaultInjector(cfg)

    def _init_network_emulator(self) -> None:
        """Instantiate network emulator with current impairment settings."""
        if self.delay_mode == DelayMode.FIXED:
            delay_cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms)
        elif self.delay_mode == DelayMode.GAUSSIAN:
            delay_cfg = DelayConfig(
                mode=DelayMode.GAUSSIAN,
                mean_delay_ms=self.mean_delay_ms,
                std_delay_ms=self.std_delay_ms,
            )
        else:
            delay_cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms)

        loss_cfg = PacketLossConfig(
            enabled=self.packet_loss_rate > 0,
            probability=self.packet_loss_rate,
            seed=self.seed,
        )

        self.network_config = NetworkConfig(
            seed=self.seed,
            delay=delay_cfg,
            packet_loss=loss_cfg,
        )
        self.network = NetworkEmulator(config=self.network_config)
        self.network.reset(new_seed=self.seed)

    def reconfigure(
        self,
        fault_type: Optional[FaultType] = None,
        bias_offset_c: Optional[float] = None,
        fault_start_s: Optional[float] = None,
        fault_end_s: Optional[float] = None,
        load_multiplier: Optional[float] = None,
        packet_loss_rate: Optional[float] = None,
        delay_mode: Optional[DelayMode] = None,
        fixed_delay_ms: Optional[float] = None,
        mean_delay_ms: Optional[float] = None,
        std_delay_ms: Optional[float] = None,
    ) -> None:
        """Dynamically update scenario parameters during runtime."""
        fault_changed = False
        if fault_type is not None and fault_type != self.fault_type:
            self.fault_type = fault_type
            fault_changed = True
        if bias_offset_c is not None and bias_offset_c != self.fault_bias_offset_c:
            self.fault_bias_offset_c = bias_offset_c
            fault_changed = True
        if fault_start_s is not None:
            self.fault_start_s = fault_start_s
            fault_changed = True
        if fault_end_s is not None:
            self.fault_end_s = fault_end_s
            fault_changed = True
        if load_multiplier is not None:
            self.load_multiplier = load_multiplier
            fault_changed = True

        if fault_changed:
            self._init_fault_injector()
            self._log_alert(
                f"Fault scenario set to: {self.fault_type.value} (Bias={self.fault_bias_offset_c}°C, Start={self.fault_start_s}s)",
                severity="INFO",
            )

        # Network parameter updates
        network_changed = False
        if packet_loss_rate is not None and packet_loss_rate != self.packet_loss_rate:
            self.packet_loss_rate = max(0.0, min(1.0, packet_loss_rate))
            network_changed = True
        if delay_mode is not None:
            self.delay_mode = delay_mode
            network_changed = True
        if fixed_delay_ms is not None:
            self.fixed_delay_ms = max(0.0, fixed_delay_ms)
            network_changed = True
        if mean_delay_ms is not None:
            self.mean_delay_ms = max(0.0, mean_delay_ms)
            network_changed = True
        if std_delay_ms is not None:
            self.std_delay_ms = max(0.0, std_delay_ms)
            network_changed = True

        if network_changed:
            self._update_network_params()

    def _update_network_params(self) -> None:
        """Update live network queue models without discarding queue history."""
        self.network.queue.loss_model = PacketLossModel(
            PacketLossConfig(
                enabled=self.packet_loss_rate > 0,
                probability=self.packet_loss_rate,
                seed=self.seed,
            )
        )
        if self.delay_mode == DelayMode.FIXED:
            delay_cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms)
        elif self.delay_mode == DelayMode.GAUSSIAN:
            delay_cfg = DelayConfig(
                mode=DelayMode.GAUSSIAN,
                mean_delay_ms=self.mean_delay_ms,
                std_delay_ms=self.std_delay_ms,
            )
        else:
            delay_cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms)
        self.network.queue.delay_model = DelayModel(delay_cfg)

    def _log_alert(self, message: str, severity: str = "INFO") -> None:
        """Append an event to the alert buffer."""
        self.alerts.appendleft(
            {
                "time_s": round(self.time_s, 2),
                "severity": severity,
                "message": message,
            }
        )

    def step(self, n_steps: int = 1) -> Dict[str, Any]:
        """Perform n discrete simulation steps across Vehicle, Network, and Digital Twin."""
        latest_record: Dict[str, Any] = {}
        for _ in range(max(1, n_steps)):
            t = round(self.time_s, 3)

            # 1. Realistic Dynamic Driving Inputs (Urban speed cycles)
            base_speed = 50.0 + 16.0 * math.sin(t / 8.0) + 5.0 * math.cos(t / 3.0)
            base_rpm = 1950.0 + (base_speed / 100.0) * 1500.0
            base_load = max(0.20, min(0.95, 0.45 + 0.22 * math.sin(t / 6.0)))

            if self.fault_type == FaultType.HIGH_LOAD and self.fault_injector.is_fault_active(t):
                base_load = 0.95
                base_rpm += 750.0

            active_fault_type = self.fault_injector.get_current_fault_type(t)
            is_fault_active = self.fault_injector.is_fault_active(t)

            # 2. Advance Vehicle Physical Dynamics
            phys_state: VehicleState = self.vehicle.step(
                dt_seconds=self.dt_s,
                speed_kmh=base_speed,
                rpm=base_rpm,
                engine_load=base_load,
                fault_type=active_fault_type,
                load_multiplier=self.load_multiplier,
            )

            # Calculate heat balance breakdown for physical observability
            effective_load = phys_state.engine_load
            q_in = (self.vehicle.k_base + self.vehicle.k_load * effective_load) * (phys_state.rpm / 1000.0)
            temp_diff = max(0.0, phys_state.true_engine_temp_c - self.vehicle.ambient_temp_c)
            cooling_factor = (
                self.vehicle.k_nat
                + (self.vehicle.k_speed * phys_state.speed_kmh)
                + (self.vehicle.k_fan * phys_state.cooling_fan_status)
            )
            q_out = cooling_factor * temp_diff

            # 3. Sensor Measurement & Telemetry Packet Synthesis
            telemetry = self.sensor_generator.generate(
                phys_state, self.fault_injector
            )

            # 4. Ingest Telemetry into Network Impairment Queue
            scheduled = self.network.ingest_telemetry_frame(telemetry, current_time=t)
            transmitted_count = len([p for p in scheduled if p is not None])
            self.total_packets_transmitted += transmitted_count

            # Advance network time and pop arrived packets
            delivered_packets = self.network.advance_time(current_time=t)
            self.total_packets_delivered = self.network.queue.delivered_count()
            self.total_packets_dropped = self.network.queue.dropped_count()

            # 5. Ingest Delivered Packets into Cloud State Estimator
            for pkt in delivered_packets:
                self.state_estimator.update_from_packet(pkt, reception_time=t)
                if pkt.value is not None and pkt.sensor_name in self.latest_observed_telemetry:
                    self.latest_observed_telemetry[pkt.sensor_name] = pkt.value

            # 6. Step Physics-Informed Nominal Model
            self.nominal_model.step(
                dt_seconds=self.dt_s,
                input_speed_kmh=self.latest_observed_telemetry.get("speed_kmh"),
                input_rpm=self.latest_observed_telemetry.get("rpm"),
                input_engine_load=self.latest_observed_telemetry.get("engine_load"),
            )
            expected = self.nominal_model.generate_expected_measurements()

            # 7. Query Instantaneous Age of Information (AoI)
            aoi_val = self.network.get_current_aoi(
                self.vehicle_id, "engine_temperature_c", current_time=t
            )
            supported_sensor_list = (
                "speed_kmh",
                "rpm",
                "engine_load",
                "engine_temperature_c",
                "cooling_fan_status",
            )
            aoi_map = {
                sensor: self.network.get_current_aoi(self.vehicle_id, sensor, current_time=t)
                for sensor in supported_sensor_list
            }

            # 8. Compute Residuals & Apply Freshness Gating
            residuals = self.residual_generator.compute_residuals_for_frame(
                vehicle_id=self.vehicle_id,
                observed_telemetry=self.latest_observed_telemetry,
                expected_measurement=expected,
                timestamp=t,
                data_ages=aoi_map,
            )

            res_temp: Optional[SensorResidual] = residuals.get("engine_temperature_c")
            temp_res_val = res_temp.residual if (res_temp and res_temp.residual is not None) else 0.0
            freshness_status = (
                res_temp.freshness_status.value
                if res_temp
                else FreshnessStatus.STALE.value
            )
            is_eligible = res_temp.diagnostic_eligible if res_temp else False

            # 9. Baseline Anomaly Detection & Persistence Gating across all signals
            anomaly_evaluations = self.anomaly_detector.detect_frame(
                residuals=residuals,
            )
            temp_anomaly = anomaly_evaluations.get("engine_temperature_c")
            fan_anomaly = anomaly_evaluations.get("cooling_fan_status")

            # Check if ANY eligible sensor has a confirmed anomaly
            is_anomaly_confirmed = any(
                e.anomaly_level == AnomalyLevel.ANOMALY and e.is_confirmed
                for e in anomaly_evaluations.values()
            )

            if is_anomaly_confirmed:
                overall_anomaly_level = AnomalyLevel.ANOMALY.value
            elif any(e.anomaly_level == AnomalyLevel.WARNING for e in anomaly_evaluations.values()):
                overall_anomaly_level = AnomalyLevel.WARNING.value
            else:
                overall_anomaly_level = AnomalyLevel.NORMAL.value

            # Primary persistence count
            persistence = (
                temp_anomaly.persistence_count if temp_anomaly else 0
            )
            if fan_anomaly and fan_anomaly.is_confirmed:
                persistence = fan_anomaly.persistence_count

            if is_anomaly_confirmed:
                self.confirmed_anomaly_count += 1
                if self.first_anomaly_time is None:
                    self.first_anomaly_time = t
                if fan_anomaly and fan_anomaly.is_confirmed and fan_anomaly.persistence_count == self.dt_config.anomaly_thresholds.anomaly_persistence_count:
                    self._log_alert(
                        f"CRITICAL: Cooling fan actuator failure! ECU thermostat commanded fan ON (Nom=1), but actuator relay disabled (Obs=0).",
                        severity="DANGER",
                    )
                elif temp_anomaly and temp_anomaly.is_confirmed and temp_anomaly.persistence_count == self.dt_config.anomaly_thresholds.anomaly_persistence_count:
                    self._log_alert(
                        f"CRITICAL: Confirmed thermal anomaly! Residual={temp_res_val:.2f}°C "
                        f"(Obs={self.latest_observed_telemetry['engine_temperature_c']:.1f}°C, "
                        f"Nom={expected.expected_engine_temperature_c:.1f}°C)",
                        severity="DANGER",
                    )
            elif overall_anomaly_level == AnomalyLevel.WARNING.value and persistence == 1:
                self._log_alert(
                    f"WARNING: Residual exceeded warning threshold ({temp_res_val:.2f}°C). Tracking persistence...",
                    severity="WARNING",
                )

            # Calculate Packet Delivery Rate
            total_eval = self.total_packets_delivered + self.total_packets_dropped
            pdr_percent = (
                round((self.total_packets_delivered / total_eval) * 100.0, 1)
                if total_eval > 0
                else 100.0
            )

            # 10. Record Complete Step Snapshot
            latest_record = {
                "time_s": t,
                "step_index": self.step_index,
                "speed_kmh": round(phys_state.speed_kmh, 1),
                "rpm": round(phys_state.rpm, 0),
                "engine_load": round(phys_state.engine_load * 100.0, 1),
                "true_engine_temp_c": round(phys_state.true_engine_temp_c, 2),
                "observed_engine_temp_c": round(
                    self.latest_observed_telemetry["engine_temperature_c"], 2
                ),
                "nominal_engine_temp_c": round(
                    expected.expected_engine_temperature_c, 2
                ),
                "residual_c": round(temp_res_val, 2),
                "cooling_fan_status": phys_state.cooling_fan_status,
                "fan_relay_fault": active_fault_type == FaultType.FAN_FAILURE,
                "fault_type": active_fault_type.value,
                "fault_active": is_fault_active,
                "q_in_w": round(q_in, 2),
                "q_out_w": round(q_out, 2),
                "aoi_ms": round((aoi_val or 0.0) * 1000.0, 1),
                "freshness_status": freshness_status,
                "diagnostic_eligible": is_eligible,
                "anomaly_level": overall_anomaly_level,
                "persistence_count": persistence,
                "is_confirmed": is_anomaly_confirmed,
                "packets_transmitted": self.total_packets_transmitted,
                "packets_delivered": self.total_packets_delivered,
                "packets_dropped": self.total_packets_dropped,
                "pdr_percent": pdr_percent,
                "packet_loss_setting": round(self.packet_loss_rate * 100.0, 1),
                "delay_ms_setting": round(self.fixed_delay_ms, 1),
            }

            self.history.append(latest_record)
            self.time_s += self.dt_s
            self.step_index += 1

        return latest_record

    def to_dataframe(self) -> pd.DataFrame:
        """Convert recorded simulation history to a pandas DataFrame for plotting."""
        if not self.history:
            return pd.DataFrame()
        return pd.DataFrame(list(self.history))

    def get_latest(self) -> Dict[str, Any]:
        """Retrieve the most recent simulation record."""
        if self.history:
            return self.history[-1]
        return self.step(n_steps=1)

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Retrieve recent diagnostic alerts."""
        return list(self.alerts)
