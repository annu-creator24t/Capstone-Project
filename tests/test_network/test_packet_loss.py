"""Unit Tests for Network Packet Loss and Stochastic Delay Models (Stage 2)."""

import unittest
from network.delay_model import DelayConfig, DelayMode, DelayModel
from network.packet_loss import PacketLossConfig, PacketLossModel
from network.network_config import NetworkConfig


class TestPacketLossAndStochasticDelay(unittest.TestCase):
    """Test suite for PacketLossModel and stochastic delay distributions."""

    def test_zero_packet_loss(self) -> None:
        """Verify zero packet loss drops 0% of packets."""
        cfg = PacketLossConfig(enabled=True, probability=0.0)
        model = PacketLossModel(cfg)

        drops = sum(model.should_drop() for _ in range(100))
        self.assertEqual(drops, 0)

    def test_disabled_packet_loss(self) -> None:
        """Verify disabled packet loss never drops packets even with positive probability."""
        cfg = PacketLossConfig(enabled=False, probability=0.5)
        model = PacketLossModel(cfg)

        drops = sum(model.should_drop() for _ in range(100))
        self.assertEqual(drops, 0)

    def test_full_packet_loss(self) -> None:
        """Verify 100% packet loss drops all packets."""
        cfg = PacketLossConfig(enabled=True, probability=1.0)
        model = PacketLossModel(cfg)

        drops = sum(model.should_drop() for _ in range(100))
        self.assertEqual(drops, 100)

    def test_stochastic_packet_loss_rate(self) -> None:
        """Verify probabilistic dropout rate closely matches target probability."""
        target_p = 0.25
        cfg = PacketLossConfig(enabled=True, probability=target_p, seed=42)
        model = PacketLossModel(cfg)

        n_trials = 2000
        drops = sum(model.should_drop() for _ in range(n_trials))
        observed_p = drops / n_trials

        # Check within tight confidence interval (+/- 3%)
        self.assertAlmostEqual(observed_p, target_p, delta=0.03)

    def test_packet_loss_reproducibility(self) -> None:
        """Verify identical seeds produce exact identical drop sequences."""
        cfg1 = PacketLossConfig(enabled=True, probability=0.30, seed=12345)
        m1 = PacketLossModel(cfg1)
        seq1 = [m1.should_drop() for _ in range(50)]

        cfg2 = PacketLossConfig(enabled=True, probability=0.30, seed=12345)
        m2 = PacketLossModel(cfg2)
        seq2 = [m2.should_drop() for _ in range(50)]

        self.assertEqual(seq1, seq2)

    def test_invalid_packet_loss_probability(self) -> None:
        """Verify invalid probabilities raise ValueError."""
        with self.assertRaises(ValueError):
            PacketLossConfig(probability=-0.1).validate()

        with self.assertRaises(ValueError):
            PacketLossConfig(probability=1.05).validate()

    def test_uniform_stochastic_delay(self) -> None:
        """Verify uniform delay returns values strictly bounded in [min, max]."""
        cfg = DelayConfig(
            mode=DelayMode.UNIFORM,
            min_delay_ms=50.0,
            max_delay_ms=150.0,
            seed=42,
        )
        model = DelayModel(cfg)

        for _ in range(100):
            d = model.calculate_delay_seconds()
            self.assertGreaterEqual(d, 0.050)
            self.assertLessEqual(d, 0.150)

    def test_invalid_uniform_delay_bounds(self) -> None:
        """Verify max_delay_ms < min_delay_ms raises ValueError."""
        cfg = DelayConfig(mode=DelayMode.UNIFORM, min_delay_ms=200.0, max_delay_ms=100.0)
        with self.assertRaises(ValueError):
            DelayModel(cfg)

    def test_gaussian_stochastic_delay_non_negative(self) -> None:
        """Verify Gaussian delay produces non-negative causal delays."""
        cfg = DelayConfig(
            mode=DelayMode.GAUSSIAN,
            mean_delay_ms=80.0,
            std_delay_ms=30.0,
            seed=42,
        )
        model = DelayModel(cfg)

        delays = [model.calculate_delay_seconds() for _ in range(200)]
        for d in delays:
            self.assertGreaterEqual(d, 0.0)

    def test_network_config_full_validation(self) -> None:
        """Verify consolidated NetworkConfig validates both delay and packet loss."""
        invalid_net_cfg = NetworkConfig(
            packet_loss=PacketLossConfig(probability=1.5)
        )
        with self.assertRaises(ValueError):
            invalid_net_cfg.validate()


if __name__ == "__main__":
    unittest.main()
