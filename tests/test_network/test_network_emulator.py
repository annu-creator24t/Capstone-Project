"""Unit and Integration Tests for NetworkEmulator (Stage 6)."""

import unittest
from network.delay_model import DelayConfig, DelayMode
from network.network_config import NetworkConfig
from network.network_emulator import NetworkEmulator
from network.packet_loss import PacketLossConfig
from simulator.fault_injector import FaultConfig, FaultInjector, FaultType
from simulator.sensor_generator import SensorGenerator
from simulator.vehicle_model import VehicleModel


class TestNetworkEmulator(unittest.TestCase):
    """Integration test suite connecting Vehicle Simulator to Network Emulator."""

    def test_emulator_telemetry_ingest_and_delivery(self) -> None:
        """Verify telemetry frame ingestion creates discrete sensor packets delivered over time."""
        cfg = NetworkConfig(
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=100.0), # 100ms delay
            packet_loss=PacketLossConfig(enabled=False),
        )
        emulator = NetworkEmulator(config=cfg)

        vehicle = VehicleModel()
        injector = FaultInjector(FaultConfig(fault_type=FaultType.NORMAL))
        sensor_gen = SensorGenerator(random_seed=42)

        # Generate telemetry at t=1.0s
        state = vehicle.step(dt_seconds=1.0)
        telemetry = sensor_gen.generate(state, injector)

        # Ingest into network emulator at simulation time t=1.0
        scheduled = emulator.ingest_telemetry_frame(telemetry, current_time=1.0)
        self.assertEqual(len(scheduled), 5)  # 5 discrete sensor channels
        self.assertEqual(emulator.queue.pending_count(), 5)

        # Advance to t=1.05 (still in transit)
        delivered_early = emulator.advance_time(1.05)
        self.assertEqual(len(delivered_early), 0)

        # Advance to t=1.15 (all delivered)
        delivered = emulator.advance_time(1.15)
        self.assertEqual(len(delivered), 5)

        # Check AoI for engine temperature at t=1.15 -> 1.15 - 1.0 = 0.15s
        aoi = emulator.get_current_aoi("EV_001", "engine_temperature_c", current_time=1.15)
        self.assertIsNotNone(aoi)
        self.assertAlmostEqual(aoi, 0.15, places=3)

    def test_emulator_missing_sensor_data_handling(self) -> None:
        """Verify dropped sensor fields (missing telemetry) are skipped and AoI grows linearly."""
        cfg = NetworkConfig(
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=50.0),
            packet_loss=PacketLossConfig(enabled=False),
        )
        emulator = NetworkEmulator(config=cfg)

        vehicle = VehicleModel()
        injector = FaultInjector(FaultConfig(fault_type=FaultType.MISSING_SENSOR_DATA, start_time_s=0.0))
        sensor_gen = SensorGenerator(random_seed=42)

        # Step 1: Normal frame at t=0.0 (manually inject non-null temp)
        normal_injector = FaultInjector(FaultConfig(fault_type=FaultType.NORMAL))
        state0 = vehicle.step(dt_seconds=1.0)
        tel0 = sensor_gen.generate(state0, normal_injector)
        emulator.ingest_telemetry_frame(tel0, current_time=0.0)
        emulator.advance_time(0.1)

        # Verify initial AoI at t=0.1s -> 0.1s
        self.assertAlmostEqual(emulator.get_current_aoi("EV_001", "engine_temperature_c", 0.1), 0.1, places=2)

        # Step 2: Missing temperature data at t=1.0s
        state1 = vehicle.step(dt_seconds=1.0)
        tel1 = sensor_gen.generate(state1, injector)
        self.assertIsNone(tel1.engine_temperature_c)

        emulator.ingest_telemetry_frame(tel1, current_time=1.0)
        emulator.advance_time(1.1)

        # At t=2.0s, AoI for engine temperature should be 2.0 - 0.0 = 2.0s (since no update was received at t=1.0)
        aoi_missing = emulator.get_current_aoi("EV_001", "engine_temperature_c", current_time=2.0)
        self.assertAlmostEqual(aoi_missing, 2.0, places=2)

    def test_emulator_performance_summary(self) -> None:
        """Verify consolidated communication report generation."""
        cfg = NetworkConfig(
            packet_loss=PacketLossConfig(enabled=True, probability=0.20, seed=42),
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=50.0),
        )
        emulator = NetworkEmulator(config=cfg)

        vehicle = VehicleModel()
        injector = FaultInjector(FaultConfig(fault_type=FaultType.NORMAL))
        sensor_gen = SensorGenerator(random_seed=42)

        for step_idx in range(10):
            t = float(step_idx)
            state = vehicle.step(dt_seconds=1.0)
            tel = sensor_gen.generate(state, injector)
            emulator.ingest_telemetry_frame(tel, current_time=t)
            emulator.advance_time(current_time=t + 0.1)

        summary = emulator.get_performance_summary(current_time=10.0)
        self.assertEqual(summary["total_frames_ingested"], 10)
        self.assertGreater(summary["packets_delivered"], 0)
        self.assertGreater(summary["packets_dropped"], 0)
        self.assertIn("aoi_statistics", summary)
        self.assertIn("scheduler_metrics", summary)


if __name__ == "__main__":
    unittest.main()
