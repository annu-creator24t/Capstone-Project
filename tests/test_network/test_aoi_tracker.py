"""Unit Tests for Age of Information (AoI) Tracking Engine (Stage 5)."""

import unittest
from network.aoi_tracker import AoITracker
from network.delay_model import DelayConfig, DelayMode
from network.models import NetworkPacket
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossConfig
from network.packet_queue import PacketQueue


class TestAoITracker(unittest.TestCase):
    """Test suite for Age of Information calculation, statistics, and staleness handling."""

    def test_unregistered_and_initial_state(self) -> None:
        """Verify sensors with no updates report None for current AoI."""
        tracker = AoITracker()
        self.assertIsNone(tracker.get_current_aoi("EV_001", "engine_temp", current_time=5.0))

        stream = tracker.register_sensor("EV_001", "engine_temp")
        self.assertIsNone(stream.current_aoi(current_time=5.0))
        self.assertFalse(stream.to_dict()["has_received_update"])

    def test_basic_aoi_growth_and_update_reset(self) -> None:
        """Verify AoI grows linearly with time and resets upon receiving newer valid telemetry."""
        tracker = AoITracker()

        # Update 1: generated at t=2.0, received at t=2.2 (delay = 0.2s)
        p1 = NetworkPacket(
            packet_id="p1", vehicle_id="EV_001", sensor_name="temp",
            value=85.0, generation_timestamp=2.0, sequence_number=1
        )
        instant_aoi_1 = tracker.update(p1, current_time=2.2)
        self.assertAlmostEqual(instant_aoi_1, 0.2, places=3)
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "temp", current_time=2.2), 0.2, places=3)

        # At t=3.0 without new packet, AoI must grow to 3.0 - 2.0 = 1.0s
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "temp", current_time=3.0), 1.0, places=3)

        # Update 2: generated at t=3.0, received at t=3.1 (delay = 0.1s)
        p2 = NetworkPacket(
            packet_id="p2", vehicle_id="EV_001", sensor_name="temp",
            value=86.0, generation_timestamp=3.0, sequence_number=2
        )
        instant_aoi_2 = tracker.update(p2, current_time=3.1)
        self.assertAlmostEqual(instant_aoi_2, 0.1, places=3)
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "temp", current_time=3.1), 0.1, places=3)

    def test_stale_and_out_of_order_packets_do_not_corrupt_aoi(self) -> None:
        """Verify older packets arriving late do NOT reset the AoI curve downward."""
        tracker = AoITracker()

        # New packet arrives: gen=10.0, rx=10.2
        p_new = NetworkPacket(
            packet_id="p_new", vehicle_id="EV_001", sensor_name="rpm",
            value=2500, generation_timestamp=10.0, sequence_number=5
        )
        tracker.update(p_new, current_time=10.2)
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "rpm", current_time=10.2), 0.2, places=3)

        # Stale packet arrives: gen=8.0, rx=10.5
        p_stale = NetworkPacket(
            packet_id="p_stale", vehicle_id="EV_001", sensor_name="rpm",
            value=2000, generation_timestamp=8.0, sequence_number=3
        )
        res = tracker.update(p_stale, current_time=10.5)
        
        # Must return None (no freshness improvement)
        self.assertIsNone(res)
        
        # AoI at t=10.5 must be 10.5 - 10.0 = 0.5s (NOT 10.5 - 8.0 = 2.5s)
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "rpm", current_time=10.5), 0.5, places=3)

        stats = tracker.get_statistics("EV_001", "rpm")
        self.assertEqual(stats["valid_updates_count"], 1)
        self.assertEqual(stats["stale_updates_count"], 1)
        self.assertEqual(stats["out_of_order_count"], 1)

    def test_duplicate_packet_ignored(self) -> None:
        """Verify duplicate packet does not increment valid updates or corrupt state."""
        tracker = AoITracker()

        p1 = NetworkPacket(
            packet_id="dup_1", vehicle_id="EV_001", sensor_name="speed",
            value=60.0, generation_timestamp=1.0, sequence_number=1
        )
        self.assertIsNotNone(tracker.update(p1, current_time=1.1))

        # Re-send same packet
        self.assertIsNone(tracker.update(p1, current_time=1.2))
        stats = tracker.get_statistics("EV_001", "speed")
        self.assertEqual(stats["duplicate_count"], 1)
        self.assertEqual(stats["valid_updates_count"], 1)

    def test_multi_vehicle_multi_sensor_isolation(self) -> None:
        """Verify independent AoI tracking across distinct vehicles and sensors."""
        tracker = AoITracker()

        p_v1_temp = NetworkPacket("p1", "EV_001", "temp", 90.0, 1.0, 1)
        p_v1_rpm = NetworkPacket("p2", "EV_001", "rpm", 2200, 2.0, 1)
        p_v2_temp = NetworkPacket("p3", "EV_002", "temp", 88.0, 3.0, 1)

        tracker.update(p_v1_temp, 1.2)
        tracker.update(p_v1_rpm, 2.1)
        tracker.update(p_v2_temp, 3.4)

        # At t=4.0:
        # EV_001 temp: 4.0 - 1.0 = 3.0
        # EV_001 rpm:  4.0 - 2.0 = 2.0
        # EV_002 temp: 4.0 - 3.0 = 1.0
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "temp", 4.0), 3.0, places=3)
        self.assertAlmostEqual(tracker.get_current_aoi("EV_001", "rpm", 4.0), 2.0, places=3)
        self.assertAlmostEqual(tracker.get_current_aoi("EV_002", "temp", 4.0), 1.0, places=3)

    def test_peak_and_average_aoi_statistics(self) -> None:
        """Verify peak and time-integrated average AoI calculations."""
        tracker = AoITracker()

        # Update at t=0.0 (rx=0.0) -> AoI=0.0
        p0 = NetworkPacket("p0", "EV_001", "t", 80.0, 0.0, 0)
        tracker.update(p0, 0.0)

        # Next update arrives at t=2.0 (generated at t=1.8, rx=2.0)
        # Right before arrival (t=2.0-), AoI grew to 2.0 - 0.0 = 2.0s (Peak!)
        p1 = NetworkPacket("p1", "EV_001", "t", 82.0, 1.8, 1)
        tracker.update(p1, 2.0)

        # Query stats at t=3.0 (AoI at t=3.0 is 3.0 - 1.8 = 1.2s)
        stats = tracker.get_statistics("EV_001", "t", current_time=3.0)
        self.assertGreaterEqual(stats["peak_aoi_s"], 2.0)
        self.assertIsNotNone(stats["time_integrated_average_aoi_s"])
        self.assertGreater(stats["time_integrated_average_aoi_s"], 0.0)

    def test_pipeline_integration_with_packet_queue(self) -> None:
        """Verify PacketQueue automatically updates integrated AoITracker upon delivery."""
        cfg = NetworkConfig(
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=100.0), # 0.1s
            packet_loss=PacketLossConfig(enabled=False),
        )
        queue = PacketQueue(config=cfg)

        pkt = NetworkPacket("p1", "EV_001", "engine_temperature_c", 92.0, 5.0, 1)
        queue.enqueue(pkt, current_time=5.0) # delivers at t=5.1

        # Advance to t=5.15 -> packet delivered
        queue.advance_time(5.15)
        
        # Check AoI via PacketQueue accessor at t=5.15 -> 5.15 - 5.0 = 0.15s
        stats = queue.get_aoi_statistics("EV_001", "engine_temperature_c", current_time=5.15)
        self.assertIsNotNone(stats)
        self.assertTrue(stats["has_received_update"])
        self.assertAlmostEqual(stats["current_aoi_s"], 0.15, places=3)


if __name__ == "__main__":
    unittest.main()
