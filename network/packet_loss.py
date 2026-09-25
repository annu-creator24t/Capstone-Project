"""Configurable Packet Loss Model for Network Telemetry Emulation.

Simulates stochastic packet dropouts over cellular / wireless channels
with reproducible random seeds and probability validation.
"""

from dataclasses import dataclass
import random
from typing import Optional


@dataclass
class PacketLossConfig:
    """Configuration parameters for packet loss simulation.
    
    Attributes:
        enabled: Whether packet loss emulation is active.
        probability: Dropout probability p in range [0.0, 1.0].
        seed: Random seed for deterministic reproducibility.
    """
    enabled: bool = True
    probability: float = 0.10
    seed: Optional[int] = 42

    def validate(self) -> None:
        """Validate probability bounds [0.0, 1.0]."""
        if not (0.0 <= self.probability <= 1.0):
            raise ValueError(f"Packet loss probability must be between 0.0 and 1.0, got {self.probability}")


class PacketLossModel:
    """Evaluates whether individual packets are dropped during network transmission."""

    def __init__(self, config: Optional[PacketLossConfig] = None) -> None:
        self.config = config or PacketLossConfig()
        self.config.validate()
        self._rng = random.Random(self.config.seed)

    def should_drop(self) -> bool:
        """Evaluate if the next packet should be dropped based on configured probability."""
        if not self.config.enabled or self.config.probability <= 0.0:
            return False
        if self.config.probability >= 1.0:
            return True
        return self._rng.random() < self.config.probability

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Reset internal pseudo-random generator for reproducible simulation runs."""
        seed = new_seed if new_seed is not None else self.config.seed
        self._rng = random.Random(seed)
