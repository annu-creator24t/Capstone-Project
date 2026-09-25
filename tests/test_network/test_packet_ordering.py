"""Unit Tests for Packet Ordering Tracker and Staleness Detection (Stage 3)."""

import unittest
from network.models import DeliveryStatus, NetworkPacket
from network.packet_ordering import OrderingConfig, OrderingPolicy, PacketOrderingTracker


class TestPacketOrdering(unittest.TestCase):
    """Test suite for out-of-order, duplicate, and stale packet classification."""

    def test_in_sequence_stream_updates(self) -> None:
        """Verify sequentially increasing packets are accepted without out-of-order flags."""
        tracker = PacketOrderingTracker()

        p1 = NetworkPacket(
            packet_id="p1", vehicle_id="EV_001", sensor_name="engine_temperature_c",
            value=85.0, generation_timestamp=1.0, sequence_number=1, reception_timestamp=1.1
        )
        p2 = NetworkPacket(
            packet_id="p2", vehicle_id="EV_001", sensor_name="engine_temperature_c",
            value=86.0, generation_timestamp=2.0, sequence_number=2, reception_timestamp=2.1
        )

        res1 = tracker.process_packet(p1)
        self.assertTrue(res1.is_accepted)
        self.assertFalse(res1.is_out_of_order)
        self.assertFalse(res1.is_stale)
        self.assertFalse(res1.is_duplicate)

        res2 = tracker.process_packet(p2)
        self.assertTrue(res2.is_accepted)
        self.assertFalse(res2.is_out_of_order)
        self.assertFalse(res2.is_stale)

        state = tracker.get_stream_state("EV_001", "engine_temperature_c")
        self.assertIsNotNone(state)
        self.assertEqual(state.total_received, 2)
        self.assertEqual(state.accepted_count, 2)
        self.assertEqual(state.out_of_order_count, 0)
        self.assertEqual(state.stale_count, 0)

    def test_out_of_order_and_stale_detection(self) -> None:
        """Verify an older packet arriving after a newer packet is marked out-of-order and stale."""
        tracker = PacketOrderingTracker()

        # Newer packet arrives first (e.g. t_gen=5.0, seq=5)
        p_newer = NetworkPacket(
            packet_id="p_new", vehicle_id="EV_001", sensor_name="rpm",
            value=3000, generation_timestamp=5.0, sequence_number=5, reception_timestamp=5.1
        )
        res_new = tracker.process_packet(p_newer)
        self.assertTrue(res_new.is_accepted)

        # Older packet arrives late (e.g. t_gen=3.0, seq=3)
        p_older = NetworkPacket(
            packet_id="p_old", vehicle_id="EV_001", sensor_name="rpm",
            value=2200, generation_timestamp=3.0, sequence_number=3, reception_timestamp=5.4
        )
        res_old = tracker.process_packet(p_older)

        self.assertTrue(res_old.is_out_of_order)
        self.assertTrue(res_old.is_stale)
        self.assertFalse(res_old.is_duplicate)

        state = tracker.get_stream_state("EV_001", "rpm")
        self.assertEqual(state.total_received, 2)
        self.assertEqual(state.out_of_order_count, 1)
        self.assertEqual(state.stale_count, 1)
        # Verify that state's latest generation timestamp remained 5.0 (not overwritten by 3.0)
        self.assertEqual(state.last_generation_timestamp, 5.0)

    def test_duplicate_packet_detection(self) -> None:
        """Verify retransmitted identical packets are flagged as duplicates."""
        tracker = PacketOrderingTracker()

        p1 = NetworkPacket(
            packet_id="dup_01", vehicle_id="EV_001", sensor_name="speed_kmh",
            value=50.0, generation_timestamp=10.0, sequence_number=10
        )
        res1 = tracker.process_packet(p1)
        self.assertFalse(res1.is_duplicate)

        # Duplicate packet with same ID and seq
        p2 = NetworkPacket(
            packet_id="dup_01", vehicle_id="EV_001", sensor_name="speed_kmh",
            value=50.0, generation_timestamp=10.0, sequence_number=10
        )
        res2 = tracker.process_packet(p2)
        self.assertTrue(res2.is_duplicate)
        self.assertFalse(res2.is_accepted)

        state = tracker.get_stream_state("EV_001", "speed_kmh")
        self.assertEqual(state.duplicate_count, 1)

    def test_multi_sensor_independent_tracking(self) -> None:
        """Verify sequence and timestamp tracking are isolated per sensor channel."""
        tracker = PacketOrderingTracker()

        p_temp = NetworkPacket(
            packet_id="t1", vehicle_id="EV_001", sensor_name="engine_temperature_c",
            value=91.0, generation_timestamp=2.0, sequence_number=1
        )
        p_speed = NetworkPacket(
            packet_id="s1", vehicle_id="EV_001", sensor_name="speed_kmh",
            value=60.0, generation_timestamp=1.0, sequence_number=1
        )

        res_temp = tracker.process_packet(p_temp)
        res_speed = tracker.process_packet(p_speed)

        self.assertFalse(res_temp.is_out_of_order)
        self.assertFalse(res_speed.is_out_of_order)
        self.assertEqual(tracker.get_stream_state("EV_001", "engine_temperature_c").last_generation_timestamp, 2.0)
        self.assertEqual(tracker.get_stream_state("EV_001", "speed_kmh").last_generation_timestamp, 1.0)

    def test_reject_stale_policy(self) -> None:
        """Verify when reject_stale is enabled, stale packets are rejected (is_accepted = False)."""
        tracker = PacketOrderingTracker(OrderingConfig(policy=OrderingPolicy.TIMESTAMP_AWARE, reject_stale=True))

        p_new = NetworkPacket(
            packet_id="pn", vehicle_id="EV_001", sensor_name="rpm",
            value=3000, generation_timestamp=10.0, sequence_number=2
        )
        tracker.process_packet(p_new)

        p_stale = NetworkPacket(
            packet_id="ps", vehicle_id="EV_001", sensor_name="rpm",
            value=2000, generation_timestamp=8.0, sequence_number=1
        )
        res_stale = tracker.process_packet(p_stale)
        self.assertTrue(res_stale.is_stale)
        self.assertFalse(res_stale.is_accepted)


if __name__ == "__main__":
    unittest.main()
