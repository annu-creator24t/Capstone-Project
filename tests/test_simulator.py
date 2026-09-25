"""Unit Tests for Module 1 — Vehicle Simulator and Fault Injection.

Validates physics dynamics, sensor noise determinism, and all fault injection modes.
"""

import unittest
from simulator.fault_injector import FaultConfig, FaultInjector, FaultType
from simulator.sensor_generator import SensorGenerator, TelemetryPacket
from simulator.vehicle_model import VehicleModel, VehicleState
from simulator.main import run_simulation


class TestVehicleSimulator(unittest.TestCase):
    """Test suite for physical model, sensor generator, and fault injector."""

    def test_telemetry_schema(self) -> None:
        """Verify telemetry packet schema keys and types."""
        vehicle = VehicleModel()
        injector = FaultInjector(FaultConfig(fault_type=FaultType.NORMAL))
        sensor_gen = SensorGenerator(vehicle_id="EV_001", random_seed=42)

        state = vehicle.step(dt_seconds=1.0)
        packet = sensor_gen.generate(state, injector)
        data = packet.to_dict()

        required_keys = {
            "vehicle_id",
            "timestamp",
            "speed_kmh",
            "rpm",
            "engine_load",
            "engine_temperature_c",
            "cooling_fan_status",
            "fault_status",
        }
        self.assertTrue(required_keys.issubset(data.keys()))
        self.assertEqual(data["vehicle_id"], "EV_001")
        self.assertEqual(data["fault_status"], "normal")
        self.assertIsInstance(data["speed_kmh"], float)
        self.assertIsInstance(data["rpm"], float)
        self.assertIsInstance(data["engine_load"], float)
        self.assertIsInstance(data["engine_temperature_c"], float)
        self.assertIsInstance(data["cooling_fan_status"], int)

    def test_deterministic_reproducibility(self) -> None:
        """Ensure identical seeds produce exact identical telemetry streams."""
        run1 = run_simulation(scenario="normal", duration_s=15, seed=12345)
        run2 = run_simulation(scenario="normal", duration_s=15, seed=12345)

        self.assertEqual(len(run1), len(run2))
        for p1, p2 in zip(run1, run2):
            self.assertEqual(p1.to_dict(), p2.to_dict())

    def test_fan_failure_scenario(self) -> None:
        """Verify fan failure disables cooling fan actuation even when engine runs hot."""
        vehicle = VehicleModel(initial_temp_c=98.0) # Above fan_on_temp (95.0)
        
        # 1. In normal mode, fan should turn ON
        normal_state = vehicle.step(dt_seconds=1.0, fault_type=FaultType.NORMAL)
        self.assertEqual(normal_state.cooling_fan_status, 1)

        # 2. In fan failure mode, fan must remain OFF (0)
        vehicle.reset()
        vehicle.true_engine_temp_c = 98.0
        failed_state = vehicle.step(dt_seconds=1.0, fault_type=FaultType.FAN_FAILURE)
        self.assertEqual(failed_state.cooling_fan_status, 0)

    def test_temp_sensor_bias_scenario(self) -> None:
        """Verify sensor bias adds an offset to sensed reading while physical state remains unaffected."""
        bias_offset = 20.0
        packets = run_simulation(
            scenario="temp_sensor_bias",
            duration_s=20,
            dt_s=1.0,
            seed=42,
            fault_start_s=10.0,
            bias_offset_c=bias_offset,
        )

        pre_fault_temp = packets[8].engine_temperature_c  # Before fault injection (t = 9.0s)
        post_fault_temp = packets[10].engine_temperature_c  # After fault injection (t = 11.0s)
        
        self.assertIsNotNone(pre_fault_temp)
        self.assertIsNotNone(post_fault_temp)
        self.assertEqual(packets[8].fault_status, "normal")
        self.assertEqual(packets[10].fault_status, "temp_sensor_bias")
        # Sensed temperature should jump by approximately the bias offset
        self.assertGreater(post_fault_temp - pre_fault_temp, bias_offset - 2.0)

    def test_temp_sensor_freeze_scenario(self) -> None:
        """Verify sensor freeze holds constant reading over time."""
        packets = run_simulation(
            scenario="temp_sensor_freeze",
            duration_s=25,
            dt_s=1.0,
            seed=42,
            fault_start_s=10.0,
        )

        frozen_reading_1 = packets[12].engine_temperature_c
        frozen_reading_2 = packets[18].engine_temperature_c
        frozen_reading_3 = packets[24].engine_temperature_c

        self.assertIsNotNone(frozen_reading_1)
        self.assertEqual(frozen_reading_1, frozen_reading_2)
        self.assertEqual(frozen_reading_2, frozen_reading_3)

    def test_missing_sensor_data_scenario(self) -> None:
        """Verify missing sensor fault outputs None for the sensor field."""
        packets = run_simulation(
            scenario="missing_sensor_data",
            duration_s=20,
            dt_s=1.0,
            seed=42,
            fault_start_s=10.0,
        )

        self.assertIsNotNone(packets[5].engine_temperature_c)
        self.assertIsNone(packets[15].engine_temperature_c)
        self.assertEqual(packets[15].fault_status, "missing_sensor_data")


if __name__ == "__main__":
    unittest.main()
