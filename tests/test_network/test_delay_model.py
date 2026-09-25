"""Unit Tests for Network Delay Model and Packet Schema (Stage 1)."""

import unittest
from network.models import DeliveryStatus, NetworkPacket
from network.delay_model import DelayConfig, DelayMode, DelayModel
from network.network_config import NetworkConfig


class TestNetworkDelayModel(unittest.TestCase):
    """Test suite for NetworkPacket and DelayModel in Stage 1."""

    def test_packet_model_creation_and_serialization(self) -> None:
        """Verify packet metadata fields, default values, and serialization."""
        packet = NetworkPacket(
            packet_id="pkt_000001",
            vehicle_id="EV_001",
            sensor_name="engine_temperature_c",
            value=92.4,
            generation_timestamp=10.0,
            sequence_number=1,
            size_bytes=128,
        )

        data = packet.to_dict()
        self.assertEqual(data["packet_id"], "pkt_000001")
        self.assertEqual(data["vehicle_id"], "EV_001")
        self.assertEqual(data["sensor_name"], "engine_temperature_c")
        self.assertEqual(data["value"], 92.4)
        self.assertEqual(data["generation_timestamp"], 10.0)
        self.assertEqual(data["sequence_number"], 1)
        self.assertEqual(data["size_bytes"], 128)
        self.assertEqual(data["status"], "queued")
        self.assertIsNone(data["transmission_timestamp"])
        self.assertIsNone(data["reception_timestamp"])

    def test_fixed_delay_calculation(self) -> None:
        """Verify fixed delay returns exact conversion to seconds."""
        cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=150.0)
        model = DelayModel(cfg)

        delay_s = model.calculate_delay_seconds()
        self.assertAlmostEqual(delay_s, 0.150, places=4)

    def test_zero_fixed_delay(self) -> None:
        """Verify zero fixed delay produces 0.0 seconds (ideal link)."""
        cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=0.0)
        model = DelayModel(cfg)

        delay_s = model.calculate_delay_seconds()
        self.assertEqual(delay_s, 0.0)

    def test_invalid_fixed_delay_raises(self) -> None:
        """Verify negative fixed delay raises ValueError."""
        cfg = DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=-50.0)
        with self.assertRaises(ValueError):
            DelayModel(cfg)

    def test_network_config_validation(self) -> None:
        """Verify top-level NetworkConfig validates sub-configs."""
        invalid_cfg = NetworkConfig(
            delay=DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=-10.0)
        )
        with self.assertRaises(ValueError):
            invalid_cfg.validate()


if __name__ == "__main__":
    unittest.main()
