"""Unit Tests for Transmission Scheduler and Integrated Pipeline (Stage 4)."""

import unittest
from network.bandwidth_model import BandwidthConfig, QuotaAction
from network.delay_model import DelayConfig, DelayMode
from network.models import DeliveryStatus, NetworkPacket
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossConfig
from network.packet_queue import PacketQueue
from network.transmission_scheduler import TransmissionScheduler


class TestTransmissionScheduler(unittest.TestCase):
    """Test suite for single-link FIFO transmission scheduling, serialization, and quotas."""

    def test_single_packet_scheduling(self) -> None:
        """Verify transmission start and completion times for a single packet."""
        # 128 bytes at 1024 bps = 1.0s serialization time
        cfg = BandwidthConfig(enabled=True, bandwidth_bps=1024.0)
        scheduler = TransmissionScheduler(config=cfg)

        pkt = NetworkPacket(
            packet_id="p1", vehicle_id="EV_001", sensor_name="speed_kmh",
            value=50.0, generation_timestamp=2.0, sequence_number=1, size_bytes=128
        )

        res = scheduler.schedule(pkt, current_time=2.0)
        self.assertIsNotNone(res)
        tx_start, tx_complete = res

        self.assertAlmostEqual(tx_start, 2.0, places=3)
        self.assertAlmostEqual(tx_complete, 3.0, places=3)
        self.assertEqual(pkt.queue_entry_timestamp, 2.0)
        self.assertEqual(pkt.transmission_timestamp, 2.0)
        self.assertEqual(pkt.transmission_completion_timestamp, 3.0)

    def test_fifo_no_overlapping_transmissions(self) -> None:
        """Verify back-to-back packets queue up so transmissions do not overlap."""
        # 128 bytes at 1024 bps = 1.0s serialization
        cfg = BandwidthConfig(enabled=True, bandwidth_bps=1024.0)
        scheduler = TransmissionScheduler(config=cfg)

        p1 = NetworkPacket(
            packet_id="p1", vehicle_id="EV_001", sensor_name="rpm",
            value=2000, generation_timestamp=1.0, sequence_number=1, size_bytes=128
        )
        p2 = NetworkPacket(
            packet_id="p2", vehicle_id="EV_001", sensor_name="rpm",
            value=2200, generation_timestamp=1.2, sequence_number=2, size_bytes=128
        )

        # Enqueue p1 at t=1.0 -> transmits from t=1.0 to 2.0
        res1 = scheduler.schedule(p1, current_time=1.0)
        self.assertEqual(res1, (1.0, 2.0))

        # Enqueue p2 at t=1.2 (channel is busy until t=2.0) -> transmits from t=2.0 to 3.0
        res2 = scheduler.schedule(p2, current_time=1.2)
        self.assertEqual(res2, (2.0, 3.0))

        metrics = scheduler.get_metrics()
        self.assertEqual(metrics["total_transmitted"], 2)
        self.assertEqual(metrics["total_bytes_transmitted"], 256)
        # p2 waited (2.0 - 1.2) = 0.8s in queue
        self.assertAlmostEqual(metrics["total_queue_wait_time_s"], 0.8, places=3)

    def test_quota_delay_to_next_window(self) -> None:
        """Verify packet exceeding quota is scheduled into the next quota window."""
        # 200 bytes quota per 1.0s window. 64 kbps (serialization = 100*8/64000 = 0.0125s)
        cfg = BandwidthConfig(
            enabled=True,
            bandwidth_bps=64000.0,
            quota_bytes=200,
            quota_window_seconds=1.0,
            quota_action=QuotaAction.DELAY_TO_NEXT_WINDOW,
        )
        scheduler = TransmissionScheduler(config=cfg)

        p1 = NetworkPacket(
            packet_id="p1", vehicle_id="EV_001", sensor_name="t",
            value=80.0, generation_timestamp=0.1, sequence_number=1, size_bytes=150
        )
        p2 = NetworkPacket(
            packet_id="p2", vehicle_id="EV_001", sensor_name="t",
            value=82.0, generation_timestamp=0.2, sequence_number=2, size_bytes=100
        )

        # p1 (150 bytes) fits in Window 0 [0.0 - 1.0)
        res1 = scheduler.schedule(p1, current_time=0.1)
        self.assertIsNotNone(res1)
        self.assertAlmostEqual(res1[0], 0.1, places=3)

        # p2 (100 bytes) + 150 = 250 > 200 quota -> delayed to Window 1 start (t=1.0)
        res2 = scheduler.schedule(p2, current_time=0.2)
        self.assertIsNotNone(res2)
        self.assertAlmostEqual(res2[0], 1.0, places=3)
        self.assertEqual(scheduler.metrics.quota_blocked_count, 1)

    def test_quota_reject_action(self) -> None:
        """Verify packet exceeding quota is rejected when quota_action is REJECT_PACKET."""
        cfg = BandwidthConfig(
            enabled=True,
            bandwidth_bps=64000.0,
            quota_bytes=100,
            quota_action=QuotaAction.REJECT_PACKET,
        )
        scheduler = TransmissionScheduler(config=cfg)

        p1 = NetworkPacket(
            packet_id="p1", vehicle_id="EV_001", sensor_name="t",
            value=80.0, generation_timestamp=0.1, sequence_number=1, size_bytes=80
        )
        p2 = NetworkPacket(
            packet_id="p2", vehicle_id="EV_001", sensor_name="t",
            value=82.0, generation_timestamp=0.2, sequence_number=2, size_bytes=80
        )

        self.assertIsNotNone(scheduler.schedule(p1, current_time=0.1))
        # p2 exceeds 100 bytes limit -> rejected
        res2 = scheduler.schedule(p2, current_time=0.2)
        self.assertIsNone(res2)
        self.assertEqual(p2.status, DeliveryStatus.QUOTA_BLOCKED)
        self.assertEqual(scheduler.metrics.rejected_count, 1)

    def test_integrated_packet_queue_with_bandwidth(self) -> None:
        """Verify PacketQueue end-to-end integration with bandwidth scheduling and propagation delay."""
        # 128 bytes at 1024 bps = 1.0s serialization + 200ms fixed propagation delay
        cfg = NetworkConfig(
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=200.0),
            packet_loss=PacketLossConfig(enabled=False),
            bandwidth=BandwidthConfig(enabled=True, bandwidth_bps=1024.0),
        )
        queue = PacketQueue(config=cfg)

        pkt = NetworkPacket(
            packet_id="pkt_integrated", vehicle_id="EV_001", sensor_name="temp",
            value=95.0, generation_timestamp=10.0, sequence_number=1, size_bytes=128
        )

        scheduled = queue.enqueue(pkt, current_time=10.0)
        self.assertIsNotNone(scheduled)
        # tx_start=10.0, tx_complete=11.0, prop_delay=0.20 -> delivery=11.20
        self.assertAlmostEqual(scheduled.transmission_timestamp, 10.0, places=3)
        self.assertAlmostEqual(scheduled.transmission_completion_timestamp, 11.0, places=3)
        self.assertAlmostEqual(scheduled.scheduled_delivery_timestamp, 11.20, places=3)

        # Before delivery time
        self.assertEqual(len(queue.advance_time(11.10)), 0)
        # At delivery time
        delivered = queue.advance_time(11.25)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0].packet_id, "pkt_integrated")


if __name__ == "__main__":
    unittest.main()
