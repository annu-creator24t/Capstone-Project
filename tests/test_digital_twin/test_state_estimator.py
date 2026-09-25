"""Unit Tests for Module 3 Stage 3 — Digital Twin State Estimator."""

import unittest
from digital_twin.models import SynchronizationStatus
from digital_twin.state_estimator import DigitalTwinStateEstimator
from digital_twin.twin_config import DigitalTwinConfig
from network.models import NetworkPacket


class TestDigitalTwinStateEstimator(unittest.TestCase):
    """Test suite for State Estimator initialization, packet acceptance, and staleness rejection."""

    def test_initialization_from_first_packet(self) -> None:
        """Verify estimator initializes upon receiving its first valid telemetry packet."""
        estimator = DigitalTwinStateEstimator()
        self.assertFalse(estimator.is_initialized)
        self.assertEqual(estimator.get_state().sync_status, SynchronizationStatus.INITIALIZING)

        pkt = NetworkPacket(
            packet_id="pkt_init",
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            value=89.5,
            generation_timestamp=2.0,
            sequence_number=1,
        )

        accepted = estimator.update_from_packet(pkt, reception_time=2.1)
        self.assertTrue(accepted)
        self.assertTrue(estimator.is_initialized)
        
        state = estimator.get_state()
        self.assertEqual(state.estimated_engine_temperature_c, 89.5)
        self.assertEqual(state.timestamp, 2.0)
        self.assertEqual(state.last_observation_timestamp, 2.0)
        self.assertEqual(state.sync_status, SynchronizationStatus.SYNCHRONIZED)

    def test_newer_telemetry_advances_state(self) -> None:
        """Verify newer chronological packets advance state estimation."""
        estimator = DigitalTwinStateEstimator()

        p1 = NetworkPacket("p1", "EV_001", "speed_kmh", 50.0, 1.0, 1)
        p2 = NetworkPacket("p2", "EV_001", "speed_kmh", 65.0, 2.0, 2)

        self.assertTrue(estimator.update_from_packet(p1, reception_time=1.1))
        self.assertEqual(estimator.get_state().estimated_speed_kmh, 50.0)

        self.assertTrue(estimator.update_from_packet(p2, reception_time=2.1))
        self.assertEqual(estimator.get_state().estimated_speed_kmh, 65.0)
        self.assertEqual(estimator.get_state().timestamp, 2.0)

    def test_stale_and_out_of_order_telemetry_rejection(self) -> None:
        """Verify older generation timestamps arriving late do NOT overwrite newer accepted state."""
        estimator = DigitalTwinStateEstimator()

        # Packet at t=5.0 arrives first
        p_newer = NetworkPacket("p_new", "EV_001", "rpm", 3000.0, 5.0, 5)
        self.assertTrue(estimator.update_from_packet(p_newer, reception_time=5.1))
        self.assertEqual(estimator.get_state().estimated_rpm, 3000.0)

        # Older packet at t=3.0 arrives late
        p_stale = NetworkPacket("p_old", "EV_001", "rpm", 1800.0, 3.0, 3)
        self.assertFalse(estimator.update_from_packet(p_stale, reception_time=5.3))

        # State must remain at 3000.0 (not overwritten by 1800.0)
        self.assertEqual(estimator.get_state().estimated_rpm, 3000.0)
        self.assertEqual(estimator.get_state().timestamp, 5.0)

        metrics = estimator.get_metrics()
        self.assertEqual(metrics["accepted_updates"], 1)
        self.assertEqual(metrics["stale_updates"], 1)
        self.assertEqual(metrics["out_of_order_updates"], 1)
        self.assertEqual(metrics["rejected_updates"], 1)

    def test_duplicate_telemetry_rejection(self) -> None:
        """Verify duplicate packets with identical packet_id or sequence are rejected."""
        estimator = DigitalTwinStateEstimator()

        p1 = NetworkPacket("dup_01", "EV_001", "engine_load", 0.60, 4.0, 4)
        self.assertTrue(estimator.update_from_packet(p1, reception_time=4.1))

        # Send exact duplicate
        p2 = NetworkPacket("dup_01", "EV_001", "engine_load", 0.60, 4.0, 4)
        self.assertFalse(estimator.update_from_packet(p2, reception_time=4.2))

        metrics = estimator.get_metrics()
        self.assertEqual(metrics["accepted_updates"], 1)
        self.assertEqual(metrics["duplicate_updates"], 1)
        self.assertEqual(metrics["rejected_updates"], 1)

    def test_state_prediction_forward(self) -> None:
        """Verify predict() advances nominal physical state forward in time."""
        estimator = DigitalTwinStateEstimator()

        # Initialize at t=0.0 with high load
        p0 = NetworkPacket("p0", "EV_001", "engine_load", 0.85, 0.0, 0)
        estimator.update_from_packet(p0, 0.0)

        initial_temp = estimator.get_state().estimated_engine_temperature_c

        # Predict forward by 10 seconds
        predicted_state = estimator.predict(target_time=10.0)
        self.assertEqual(predicted_state.timestamp, 10.0)
        self.assertGreater(predicted_state.estimated_engine_temperature_c, initial_temp)
        self.assertEqual(estimator.metrics.prediction_steps, 1)

        # Negative time prediction raises ValueError
        with self.assertRaises(ValueError):
            estimator.predict(target_time=5.0)

    def test_missing_sensor_value_preservation(self) -> None:
        """Verify null/missing telemetry value does not corrupt or zero out existing state."""
        estimator = DigitalTwinStateEstimator()

        # 1. Establish valid temperature
        p1 = NetworkPacket("p1", "EV_001", "engine_temperature_c", 92.0, 1.0, 1)
        estimator.update_from_packet(p1, 1.1)
        self.assertEqual(estimator.get_state().estimated_engine_temperature_c, 92.0)

        # 2. Ingest missing packet (value=None)
        p_missing = NetworkPacket("p2", "EV_001", "engine_temperature_c", None, 2.0, 2)
        estimator.update_from_packet(p_missing, 2.1)

        # State should retain temperature (or predicted value) and not become None
        self.assertIsNotNone(estimator.get_state().estimated_engine_temperature_c)

    def test_synchronization_status_transitions(self) -> None:
        """Verify transition between SYNCHRONIZED, STALE, and DISCONNECTED based on data age."""
        config = DigitalTwinConfig()
        # stale threshold = 3.0s, disconnect threshold = 10.0s
        estimator = DigitalTwinStateEstimator(config=config)

        # Initial state
        self.assertEqual(estimator.get_state().sync_status, SynchronizationStatus.INITIALIZING)

        # Update at t=1.0s (rx=1.1s) -> SYNCHRONIZED
        p = NetworkPacket("p", "EV_001", "speed_kmh", 50.0, 1.0, 1)
        estimator.update_from_packet(p, reception_time=1.1)
        self.assertEqual(estimator.get_state().sync_status, SynchronizationStatus.SYNCHRONIZED)

        # Advance to t=5.0s (4.0s elapsed > 3.0s threshold) -> STALE
        estimator.predict(target_time=5.0)
        self.assertEqual(estimator.get_state().sync_status, SynchronizationStatus.STALE)

        # Advance to t=15.0s (14.0s elapsed > 10.0s threshold) -> DISCONNECTED
        estimator.predict(target_time=15.0)
        self.assertEqual(estimator.get_state().sync_status, SynchronizationStatus.DISCONNECTED)


if __name__ == "__main__":
    unittest.main()
