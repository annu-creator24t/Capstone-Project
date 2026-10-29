"""Interactive Web Analytics Dashboard Server for Connected Vehicle Digital Twin.

Provides real-time HTTP API endpoints and serves the modern glassmorphic web dashboard.
Directly interfaces with:
  - simulator.vehicle_model.VehicleModel
  - simulator.fault_injector.FaultInjector
  - network.network_emulator.NetworkEmulator
  - digital_twin.nominal_model.NominalVehicleModel
  - digital_twin.state_estimator.DigitalTwinStateEstimator
  - digital_twin.residual_generator.ResidualGenerator
  - digital_twin.anomaly_detector.BaselineAnomalyDetector
"""

import collections
import json
import math
import mimetypes
import os
import sys
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Deque, Dict, List, Optional
import urllib.parse
import webbrowser

# Ensure repository root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from simulator.fault_injector import FaultConfig, FaultInjector, FaultType
from simulator.sensor_generator import SensorGenerator
from simulator.vehicle_model import VehicleModel
from network.delay_model import DelayConfig, DelayMode, DelayModel
from network.packet_loss import PacketLossConfig, PacketLossModel
from network.network_config import NetworkConfig
from network.network_emulator import NetworkEmulator
from digital_twin.anomaly_detector import AnomalyLevel, BaselineAnomalyDetector
from digital_twin.nominal_model import NominalVehicleModel
from digital_twin.residual_generator import ResidualGenerator
from digital_twin.state_estimator import DigitalTwinStateEstimator
from digital_twin.telemetry_freshness import FreshnessStatus, TelemetryFreshnessEvaluator
from digital_twin.twin_config import DigitalTwinConfig


class LiveSimulationEngine:
    """Encapsulates the closed-loop real-time vehicle, network, and Digital Twin simulation."""

    def __init__(self, vehicle_id: str = "EV_001", seed: int = 42) -> None:
        self.vehicle_id = vehicle_id
        self.seed = seed
        self.dt_s = 0.1
        self.lock = threading.RLock()
        self.is_running = True
        self.speed_multiplier = 1.0

        # Control knobs
        self.current_fault_type = FaultType.NORMAL
        self.fault_bias_offset_c = 15.0
        self.packet_loss_rate = 0.05  # 5% default realistic loss
        self.fixed_delay_ms = 40.0   # 40ms default cellular delay

        # History buffer for real-time graphs (last 120 samples = 12 seconds)
        self.history: Deque[Dict[str, Any]] = collections.deque(maxlen=120)

        # Alert logs
        self.alert_log: Deque[Dict[str, Any]] = collections.deque(maxlen=50)

        self.reset()

    def reset(self) -> None:
        """Reset vehicle, network emulator, and digital twin state estimators."""
        with self.lock:
            self.time_s = 0.0
            self.step_count = 0
            self.total_transmitted = 0
            self.total_delivered = 0
            self.total_dropped = 0
            self.confirmed_anomalies_count = 0
            self.history.clear()
            self.alert_log.clear()

            # 1. Fault Configuration
            f_cfg = FaultConfig(
                fault_type=self.current_fault_type,
                start_time_s=0.0,
                bias_offset_c=self.fault_bias_offset_c,
            )
            self.fault_injector = FaultInjector(f_cfg)

            # 2. Vehicle Model & Sensor Generator
            self.dt_config = DigitalTwinConfig()
            self.vehicle = VehicleModel(
                initial_temp_c=self.dt_config.initial_temp_c,
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
            self.sensor_gen = SensorGenerator(
                vehicle_id=self.vehicle_id, random_seed=self.seed
            )

            # 3. Intermittent Network Emulator
            self.net_config = NetworkConfig(
                seed=self.seed,
                delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms),
                packet_loss=PacketLossConfig(enabled=True, probability=self.packet_loss_rate, seed=self.seed),
            )
            self.network = NetworkEmulator(config=self.net_config)
            self.network.reset(new_seed=self.seed)

            # 4. Cloud Digital Twin Models
            self.nominal_model = NominalVehicleModel(config=self.dt_config)
            self.estimator = DigitalTwinStateEstimator(config=self.dt_config)
            self.freshness_eval = TelemetryFreshnessEvaluator(config=self.dt_config)
            self.residual_gen = ResidualGenerator(
                epsilon=1e-4,
                freshness_evaluator=self.freshness_eval,
                config=self.dt_config,
            )
            self.anomaly_detector = BaselineAnomalyDetector(
                master_config=self.dt_config
            )

            self.latest_observed_telemetry: Dict[str, Any] = {
                "speed_kmh": 45.0,
                "rpm": 2200.0,
                "engine_load": 0.50,
                "engine_temperature_c": self.dt_config.initial_temp_c,
                "cooling_fan_status": 0,
            }
            self.latest_record: Optional[Dict[str, Any]] = None

    def set_fault(self, fault_type_str: str, bias_offset_c: float = 15.0) -> None:
        """Dynamically configure active physical/sensor fault mode."""
        with self.lock:
            try:
                fault_enum = FaultType(fault_type_str)
            except ValueError:
                fault_enum = FaultType.NORMAL
            self.current_fault_type = fault_enum
            self.fault_bias_offset_c = bias_offset_c

            f_cfg = FaultConfig(
                fault_type=fault_enum,
                start_time_s=self.time_s,
                bias_offset_c=bias_offset_c,
            )
            self.fault_injector = FaultInjector(f_cfg)
            self.log_alert(
                f"Fault Mode changed to '{fault_enum.value}' (Offset: {bias_offset_c}°C)",
                level="INFO",
            )

    def set_network_params(self, loss_rate: float, delay_ms: float) -> None:
        """Dynamically update wireless transport impairments."""
        with self.lock:
            self.packet_loss_rate = max(0.0, min(0.99, loss_rate))
            self.fixed_delay_ms = max(0.0, min(2000.0, delay_ms))
            self.network.queue.loss_model = PacketLossModel(
                PacketLossConfig(enabled=True, probability=self.packet_loss_rate, seed=self.seed)
            )
            self.network.queue.delay_model = DelayModel(
                DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=self.fixed_delay_ms)
            )

    def log_alert(self, message: str, level: str = "INFO") -> None:
        """Record timestamped event to the alert feed."""
        self.alert_log.appendleft(
            {
                "time_s": round(self.time_s, 2),
                "timestamp": time.strftime("%H:%M:%S"),
                "message": message,
                "level": level,
            }
        )

    def step(self) -> Dict[str, Any]:
        """Perform one discrete simulation step across Vehicle, Network, and Cloud DT."""
        with self.lock:
            t = round(self.time_s, 3)

            # Dynamic driving inputs with natural acceleration & deceleration cycles
            base_speed = 52.0 + 18.0 * math.sin(t / 8.0) + 6.0 * math.cos(t / 3.0)
            base_rpm = 1900.0 + (base_speed / 100.0) * 1600.0
            base_load = max(0.20, min(0.95, 0.45 + 0.25 * math.sin(t / 6.0)))

            if self.current_fault_type == FaultType.HIGH_LOAD:
                base_load = 0.95
                base_rpm += 800.0

            # 1. Physical Vehicle Powertrain Step
            phys_state = self.vehicle.step(
                dt_seconds=self.dt_s,
                speed_kmh=base_speed,
                rpm=base_rpm,
                engine_load=base_load,
                fault_type=self.current_fault_type,
            )

            # 2. Sensor Telemetry Generation
            noisy_telemetry = self.sensor_gen.generate(
                phys_state, self.fault_injector
            )

            # 3. Network Emulation Pipeline
            scheduled = self.network.ingest_telemetry_frame(
                noisy_telemetry, current_time=t
            )
            transmitted_in_step = len([p for p in scheduled if p is not None])
            self.total_transmitted += transmitted_in_step

            # Deliver queued packets whose delivery time <= current time
            delivered_packets = self.network.advance_time(current_time=t)
            self.total_delivered = self.network.queue.delivered_count()
            self.total_dropped = self.network.queue.dropped_count()

            # 4. Ingest into Cloud Digital Twin State Estimator
            for pkt in delivered_packets:
                self.estimator.update_from_packet(pkt, reception_time=t)
                if (
                    pkt.value is not None
                    and pkt.sensor_name in self.latest_observed_telemetry
                ):
                    self.latest_observed_telemetry[pkt.sensor_name] = pkt.value

            # 5. Physics-Informed Nominal Model Prediction
            self.nominal_model.step(
                dt_seconds=self.dt_s,
                input_speed_kmh=self.latest_observed_telemetry.get("speed_kmh"),
                input_rpm=self.latest_observed_telemetry.get("rpm"),
                input_engine_load=self.latest_observed_telemetry.get("engine_load"),
            )
            expected = self.nominal_model.generate_expected_measurements()

            # 6. Age of Information (AoI) Query
            aoi_val = self.network.get_current_aoi(
                self.vehicle_id, "engine_temperature_c", current_time=t
            )
            aoi_map = {"engine_temperature_c": aoi_val}

            # 7. Residual Generation & Freshness Gating
            residuals = self.residual_gen.compute_residuals_for_frame(
                vehicle_id=self.vehicle_id,
                observed_telemetry=self.latest_observed_telemetry,
                expected_measurement=expected,
                timestamp=t,
                data_ages=aoi_map,
            )

            res_temp = residuals.get("engine_temperature_c")
            temp_residual_val = (
                res_temp.residual if (res_temp and res_temp.residual is not None) else 0.0
            )
            freshness_status = (
                res_temp.freshness_status.value
                if res_temp
                else FreshnessStatus.STALE.value
            )
            is_eligible = res_temp.diagnostic_eligible if res_temp else False

            # 8. Anomaly Detection
            anomaly_res = self.anomaly_detector.detect_frame(
                residuals=residuals,
            )
            temp_anomaly = anomaly_res.get("engine_temperature_c")
            anomaly_level = (
                temp_anomaly.anomaly_level.value
                if temp_anomaly
                else AnomalyLevel.NORMAL.value
            )
            persistence = (
                temp_anomaly.persistence_count if temp_anomaly else 0
            )
            is_confirmed = (
                temp_anomaly.is_confirmed if temp_anomaly else False
            )

            if is_confirmed:
                self.confirmed_anomalies_count += 1
                if persistence == self.dt_config.anomaly_thresholds.anomaly_persistence_count:
                    self.log_alert(
                        f"CRITICAL: Confirmed thermal anomaly! Residual={temp_residual_val:.2f}°C (Obs={self.latest_observed_telemetry['engine_temperature_c']:.1f}°C, Exp={expected.expected_engine_temperature_c:.1f}°C)",
                        level="DANGER",
                    )
            elif anomaly_level == AnomalyLevel.WARNING.value and persistence == 1:
                self.log_alert(
                    f"WARNING: Thermal residual exceeded threshold ({temp_residual_val:.2f}°C). Gating persistence...",
                    level="WARNING",
                )

            # Record creation
            record = {
                "time_s": t,
                "speed_kmh": round(phys_state.speed_kmh, 1),
                "rpm": round(phys_state.rpm, 0),
                "engine_load": round(phys_state.engine_load * 100, 1),
                "physical_temp_c": round(phys_state.true_engine_temp_c, 2),
                "observed_temp_c": round(
                    self.latest_observed_telemetry["engine_temperature_c"], 2
                ),
                "nominal_temp_c": round(expected.expected_engine_temperature_c, 2),
                "residual_temp_c": round(temp_residual_val, 2),
                "cooling_fan_status": phys_state.cooling_fan_status,
                "cooling_fan_fault": self.current_fault_type == FaultType.FAN_FAILURE,
                "aoi_ms": round((aoi_val or 0.0) * 1000, 1),
                "freshness": freshness_status,
                "is_eligible": is_eligible,
                "anomaly_level": anomaly_level,
                "persistence": persistence,
                "is_confirmed": is_confirmed,
                "packets_transmitted": self.total_transmitted,
                "packets_delivered": self.total_delivered,
                "packets_dropped": self.total_dropped,
                "packet_delivery_rate": (
                    round((self.total_delivered / self.total_transmitted) * 100, 1)
                    if self.total_transmitted > 0
                    else 100.0
                ),
                "loss_rate_setting": round(self.packet_loss_rate * 100, 1),
                "delay_ms_setting": round(self.fixed_delay_ms, 1),
                "current_fault": self.current_fault_type.value,
                "confirmed_count": self.confirmed_anomalies_count,
            }

            self.latest_record = record
            self.history.append(record)

            self.time_s += self.dt_s
            self.step_count += 1

            return record

    def get_snapshot(self) -> Dict[str, Any]:
        """Retrieve full state for API response."""
        with self.lock:
            latest = self.latest_record or self.step()
            return {
                "latest": latest,
                "is_running": self.is_running,
                "speed_multiplier": self.speed_multiplier,
                "history": list(self.history),
                "alerts": list(self.alert_log),
                "config": {
                    "fault_type": self.current_fault_type.value,
                    "bias_offset_c": self.fault_bias_offset_c,
                    "packet_loss_rate": self.packet_loss_rate,
                    "fixed_delay_ms": self.fixed_delay_ms,
                },
            }


# Singleton engine instance
ENGINE = LiveSimulationEngine()


def background_simulation_loop() -> None:
    """Continuously advances simulation when ENGINE.is_running is True."""
    while True:
        if ENGINE.is_running:
            try:
                ENGINE.step()
            except Exception as ex:
                print(f"[Simulation Worker Error] {ex}")
            # Target 10Hz step rate adjusted by speed multiplier
            sleep_duration = max(0.01, (ENGINE.dt_s / max(0.1, ENGINE.speed_multiplier)))
            time.sleep(sleep_duration)
        else:
            time.sleep(0.08)


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving the static dashboard and REST API."""

    def __init__(self, *args, **kwargs):
        # Set directory to dashboard folder
        dashboard_dir = os.path.join(PROJECT_ROOT, "dashboard")
        super().__init__(*args, directory=dashboard_dir, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress noisy request logs."""
        pass

    def _send_json(self, data: Any, status_code: int = 200) -> None:
        """Helper to send properly formatted JSON responses with explicit Content-Length."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/state":
            data = ENGINE.get_snapshot()
            self._send_json(data)
            return

        elif path == "/api/campaign":
            campaign_path = os.path.join(
                PROJECT_ROOT, "experiments", "results", "campaign_all_results.json"
            )
            if os.path.exists(campaign_path):
                with open(campaign_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "not_found"}, 404)
            return

        # Serve static files
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            body = json.loads(post_body)
        except json.JSONDecodeError:
            body = {}

        if path == "/api/step":
            record = ENGINE.step()
            self._send_json(record)
            return

        elif path == "/api/control":
            if "is_running" in body:
                ENGINE.is_running = bool(body["is_running"])
            if "speed" in body:
                ENGINE.speed_multiplier = float(body["speed"])
            if "fault_type" in body:
                bias = float(body.get("bias_offset_c", 15.0))
                ENGINE.set_fault(str(body["fault_type"]), bias)
            if "loss_rate" in body or "delay_ms" in body:
                loss = float(body.get("loss_rate", ENGINE.packet_loss_rate))
                delay = float(body.get("delay_ms", ENGINE.fixed_delay_ms))
                ENGINE.set_network_params(loss, delay)

            self._send_json({"status": "ok"})
            return

        elif path == "/api/reset":
            ENGINE.reset()
            self._send_json({"status": "reset_complete"})
            return

        self._send_json({"error": "not_found"}, 404)


def run_server(port: int = 8050, auto_open: bool = True) -> None:
    """Start the dashboard web server and launch browser."""
    # Start simulation worker thread
    worker = threading.Thread(target=background_simulation_loop, daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardRequestHandler)
    url = f"http://localhost:{port}"
    print(f"================================================================")
    print(f"  CONNECTED VEHICLE DIGITAL TWIN — INTERACTIVE WEB DASHBOARD   ")
    print(f"================================================================")
    print(f"  Web Dashboard running at: {url}")
    print(f"  Press Ctrl+C to terminate.")
    print(f"----------------------------------------------------------------")

    if auto_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Connected Vehicle Digital Twin Web Dashboard")
    parser.add_argument("--port", type=int, default=8050, help="HTTP server port")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    run_server(port=args.port, auto_open=not args.no_open)
