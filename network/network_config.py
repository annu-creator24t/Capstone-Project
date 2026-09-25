"""Master Configuration for the Network Impairment Layer."""

from dataclasses import dataclass, field
from typing import Optional
from network.delay_model import DelayConfig, DelayMode


@dataclass
class NetworkConfig:
    """Consolidated configuration for all network impairment modules."""
    seed: Optional[int] = 42
    delay: DelayConfig = field(default_factory=lambda: DelayConfig(mode=DelayMode.FIXED, fixed_delay_ms=100.0))

    def validate(self) -> None:
        """Validate all child configurations."""
        self.delay.validate()
