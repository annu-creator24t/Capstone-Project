"""Master Configuration for the Network Impairment Layer."""

from dataclasses import dataclass, field
from typing import Optional
from network.delay_model import DelayConfig, DelayMode
from network.packet_loss import PacketLossConfig


@dataclass
class NetworkConfig:
    """Consolidated configuration for all network impairment modules."""
    seed: Optional[int] = 42
    delay: DelayConfig = field(default_factory=lambda: DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=100.0))
    packet_loss: PacketLossConfig = field(default_factory=lambda: PacketLossConfig(enabled=True, probability=0.10))

    def validate(self) -> None:
        """Validate all child configurations."""
        self.delay.validate()
        self.packet_loss.validate()
