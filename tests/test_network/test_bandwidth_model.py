"""Unit Tests for Bandwidth Serialization Model and Byte Quota Tracker (Stage 4)."""

import unittest
from network.bandwidth_model import (
    BandwidthConfig,
    ByteQuotaTracker,
    QuotaAction,
    calculate_serialization_time,
)


class TestBandwidthModel(unittest.TestCase):
    """Test suite for serialization delay calculation and byte quota accounting."""

    def test_serialization_known_values(self) -> None:
        """Verify mathematical formula T_ser = (size_bytes * 8) / bandwidth_bps."""
        # 1000 bytes at 64000 bps = (8000 bits) / (64000 bits/s) = 0.125 seconds
        t1 = calculate_serialization_time(1000, 64000.0)
        self.assertAlmostEqual(t1, 0.125, places=5)

        # 128 bytes at 1024 bps = 1024 bits / 1024 bps = 1.0 seconds
        t2 = calculate_serialization_time(128, 1024.0)
        self.assertAlmostEqual(t2, 1.0, places=5)

        # 0 bytes = 0.0 seconds
        t3 = calculate_serialization_time(0, 50000.0)
        self.assertEqual(t3, 0.0)

    def test_invalid_serialization_arguments(self) -> None:
        """Verify invalid bandwidth or size raises ValueError."""
        with self.assertRaises(ValueError):
            calculate_serialization_time(-10, 64000.0)

        with self.assertRaises(ValueError):
            calculate_serialization_time(100, 0.0)

        with self.assertRaises(ValueError):
            calculate_serialization_time(100, -5000.0)

    def test_byte_quota_consumption_and_window_reset(self) -> None:
        """Verify ByteQuotaTracker enforces limits within window and resets in next window."""
        tracker = ByteQuotaTracker(quota_bytes=500, quota_window_seconds=1.0)

        # Window 0 (0.0s to 1.0s)
        self.assertTrue(tracker.can_transmit(packet_size_bytes=200, current_time=0.1))
        tracker.consume(200, current_time=0.1)

        self.assertTrue(tracker.can_transmit(packet_size_bytes=250, current_time=0.5))
        tracker.consume(250, current_time=0.5)

        # Total in window is 450 bytes. Next 100-byte packet should exceed 500-byte quota
        self.assertFalse(tracker.can_transmit(packet_size_bytes=100, current_time=0.8))

        # Window 1 (1.0s to 2.0s) - Quota resets
        self.assertTrue(tracker.can_transmit(packet_size_bytes=100, current_time=1.05))
        tracker.consume(100, current_time=1.05)

        # Verify next window start calculation
        self.assertAlmostEqual(tracker.get_next_window_start(0.8), 1.0, places=3)
        self.assertAlmostEqual(tracker.get_next_window_start(1.2), 2.0, places=3)

    def test_bandwidth_config_validation(self) -> None:
        """Verify validation rules in BandwidthConfig."""
        valid_cfg = BandwidthConfig(bandwidth_bps=128000.0, quota_bytes=1000)
        valid_cfg.validate()

        with self.assertRaises(ValueError):
            BandwidthConfig(bandwidth_bps=-1000).validate()

        with self.assertRaises(ValueError):
            BandwidthConfig(quota_bytes=-5).validate()

        with self.assertRaises(ValueError):
            BandwidthConfig(quota_window_seconds=0.0).validate()


if __name__ == "__main__":
    unittest.main()
