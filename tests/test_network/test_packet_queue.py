"""Unit Tests for PacketQueue Pipeline (Stage 3)."""

import unittest
from network.delay_model import DelayConfig, DelayMode, DelayModel
from network.models import DeliveryStatus, NetworkPacket
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossConfig, PacketLossModel
from network.packet_queue import PacketQueue


class TestPacketQueue(unittest.TestCase):
    """Test suite for PacketQueue scheduling, transit delays, and delivery extraction."""

    def test_enqueue_and_delayed_delivery(self) -> None:
        """Verify packet is held in transit until current_time reaches scheduled delivery."""
        cfg = NetworkConfig(
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=200.0),
            packet_loss=PacketLossConfig(enabled=False),
        )
        queue = PacketQueue(config=cfg)

        pkt = NetworkPacket(
            packet_id="pkt_001",
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            value=90.0,
            generation_timestamp=1.0,
            sequence_number=1,
        )

        scheduled = queue.enqueue(pkt, current_time=1.0)
        self.assertIsNotNone(scheduled)
        self.assertEqual(scheduled.status, DeliveryStatus.IN_TRANSIT)
        self.assertAlmostEqual(scheduled.scheduled_delivery_timestamp, 1.20, places=3)
        self.assertEqual(queue.pending_count(), 1)
        self.assertFalse(queue.is_empty())

        # Advance to t=1.1s (packet should still be in transit)
        delivered_1 = queue.advance_time(current_time=1.10)
        self.assertEqual(len(delivered_1), 0)
        self.assertEqual(queue.pending_count(), 1)

        # Advance to t=1.25s (packet should now be delivered)
        delivered_2 = queue.advance_time(current_time=1.25)
        self.assertEqual(len(delivered_2), 1)
        self.assertEqual(delivered_2[0].packet_id, "pkt_001")
        self.assertEqual(delivered_2[0].status, DeliveryStatus.DELIVERED)
        self.assertEqual(delivered_2[0].reception_timestamp, 1.20)
        self.assertEqual(queue.pending_count(), 0)
        self.assertTrue(queue.is_empty())

    def test_packet_loss_drop_behavior(self) -> None:
        """Verify dropped packets are excluded from delivery queue and logged."""
        cfg = NetworkConfig(
            packet_loss=PacketLossConfig(enabled=True, probability=1.0), # 100% loss
        )
        queue = PacketQueue(config=cfg)

        pkt = NetworkPacket(
            packet_id="pkt_drop_01",
            vehicle_id="EV_001",
            sensor_name="rpm",
            value=2500,
            generation_timestamp=2.0,
            sequence_number=1,
        )

        result = queue.enqueue(pkt, current_time=2.0)
        self.assertIsNone(result)
        self.assertEqual(pkt.status, DeliveryStatus.DROPPED)
        self.assertEqual(queue.pending_count(), 0)
        self.assertEqual(queue.dropped_count(), 1)

        delivered = queue.advance_time(current_time=10.0)
        self.assertEqual(len(delivered), 0)

    def test_out_of_order_arrival_order(self) -> None:
        """Verify two packets with different delays arrive in order of their arrival time, not generation time."""
        # Custom mock setup with fixed delay model
        queue = PacketQueue(
            config=NetworkConfig(packet_loss=PacketLossConfig(enabled=False))
        )

        # Packet 1 generated at t=1.0 with large delay (arrival t=1.50)
        pkt1 = NetworkPacket(
            packet_id="pkt_slow",
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            value=40.0,
            generation_timestamp=1.0,
            sequence_number=1,
        )
        # Override delay manually for deterministic out-of-order test
        queue.delay_model = DelayModel(DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=500.0))
        queue.enqueue(pkt1, current_time=1.0) # scheduled for t=1.50

        # Packet 2 generated at t=1.1 with short delay (arrival t=1.20)
        pkt2 = NetworkPacket(
            packet_id="pkt_fast",
            vehicle_id="EV_001",
            sensor_name="speed_kmh",
            value=45.0,
            generation_timestamp=1.1,
            sequence_number=2,
        )
        queue.delay_model = DelayModel(DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=100.0))
        queue.enqueue(pkt2, current_time=1.1) # scheduled for t=1.20

        # Advance to t=2.0 (both arrive, but pkt2 must arrive before pkt1)
        delivered = queue.advance_time(current_time=2.0)
        self.assertEqual(len(delivered), 2)
        self.assertEqual(delivered[0].packet_id, "pkt_fast")  # Arrived at t=1.20
        self.assertEqual(delivered[1].packet_id, "pkt_slow")  # Arrived at t=1.50

    def test_empty_queue_advance(self) -> None:
        """Verify advancing time on empty queue returns empty list safely."""
        queue = PacketQueue()
        delivered = queue.advance_time(current_time=5.0)
        self.assertEqual(delivered, [])


if __name__ == "__main__":
    unittest.main()
