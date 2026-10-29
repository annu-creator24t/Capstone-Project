"""Unit Tests for Dashboard Simulation Session Manager."""

import unittest
from dashboard.simulation_manager import DashboardSimulationSession
from simulator.fault_injector import FaultType
from network.delay_model import DelayMode


class TestDashboardSimulationSession(unittest.TestCase):
    """Test suite verifying simulation session manager functionality."""

    def setUp(self) -> None:
        self.session = DashboardSimulationSession(seed=42, dt_s=0.1, history_maxlen=100)

    def test_initialization(self) -> None:
        """Verify session initializes with valid baseline state."""
        self.assertEqual(self.session.time_s, 0.1)  # Advanced by 1 initial step
        latest = self.session.get_latest()
        self.assertIn("speed_kmh", latest)
        self.assertIn("rpm", latest)
        self.assertIn("true_engine_temp_c", latest)
        self.assertIn("nominal_engine_temp_c", latest)
        self.assertIn("residual_c", latest)
        self.assertIn("freshness_status", latest)
        self.assertIn("diagnostic_eligible", latest)
        self.assertIn("anomaly_level", latest)
        self.assertIn("pdr_percent", latest)

    def test_multi_step_execution(self) -> None:
        """Verify advancing simulation step by step."""
        initial_time = self.session.time_s
        self.session.step(n_steps=10)
        self.assertAlmostEqual(self.session.time_s, initial_time + 1.0, places=2)
        df = self.session.to_dataframe()
        self.assertEqual(len(df), 11)  # 1 initial + 10 steps

    def test_fault_reconfiguration_and_anomaly_detection(self) -> None:
        """Verify fault injection triggers residual escalation and confirmed anomaly."""
        # Baseline normal steps
        self.session.step(n_steps=10)
        self.assertFalse(self.session.get_latest()["is_confirmed"])

        # Inject +20°C bias
        self.session.reconfigure(fault_type=FaultType.TEMP_SENSOR_BIAS, bias_offset_c=20.0)
        self.session.step(n_steps=15)

        latest = self.session.get_latest()
        self.assertGreater(abs(latest["residual_c"]), 15.0)
        self.assertTrue(latest["is_confirmed"])
        self.assertGreater(self.session.confirmed_anomaly_count, 0)

    def test_network_impairment_update(self) -> None:
        """Verify dynamic network parameter updates."""
        self.session.reconfigure(
            packet_loss_rate=0.40,
            delay_mode=DelayMode.FIXED,
            fixed_delay_ms=250.0,
        )
        self.session.step(n_steps=20)
        df = self.session.to_dataframe()
        self.assertGreater(df["packets_transmitted"].iloc[-1], 0)
        self.assertGreater(df["aoi_ms"].iloc[-1], 0)

    def test_reset_behavior(self) -> None:
        """Verify session reset returns clock and metrics to initial baseline."""
        self.session.step(n_steps=30)
        self.assertGreater(self.session.time_s, 2.0)

        self.session.reset()
        self.assertAlmostEqual(self.session.time_s, 0.1, places=2)
        self.assertEqual(self.session.confirmed_anomaly_count, 0)
        self.assertEqual(len(self.session.history), 1)

    def test_cooling_fan_actuator_anomaly(self) -> None:
        """Verify cooling fan failure triggers categorical actuator anomaly when fan is expected ON."""
        # Initialize with engine at operating temperature (95°C)
        self.session.reset(initial_temp_c=95.0)
        self.session.reconfigure(fault_type=FaultType.FAN_FAILURE, fault_start_s=0.0)

        # Step 10 times (1.0s) with fan expected ON by thermostat
        for _ in range(10):
            rec = self.session.step(n_steps=1)

        latest = self.session.get_latest()
        self.assertEqual(latest["cooling_fan_status"], 0)
        self.assertTrue(latest["fan_relay_fault"])
        self.assertTrue(latest["is_confirmed"])
        self.assertEqual(latest["anomaly_level"], "anomaly")
        self.assertGreater(self.session.confirmed_anomaly_count, 0)

    def test_reset_with_custom_initial_temp(self) -> None:
        """Verify reset with custom initial temperature initializes models correctly."""
        self.session.reset(initial_temp_c=92.5)
        latest = self.session.get_latest()
        self.assertAlmostEqual(latest["true_engine_temp_c"], 92.5, delta=0.5)
        self.assertAlmostEqual(latest["nominal_engine_temp_c"], 92.5, delta=0.5)


if __name__ == "__main__":
    unittest.main()

