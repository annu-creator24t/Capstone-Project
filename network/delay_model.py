"""Configurable Stochastic and Fixed Delay Models for Network Telemetry.

Simulates transmission and propagation latency between the connected vehicle
and the cloud Digital Twin receiver.
"""

from dataclasses import dataclass
from enum import Enum
import random
from typing import Optional


class DelayMode(str, Enum):
    """Supported delay modes for network transmission."""
    FIXED = "fixed"
    UNIFORM = "uniform"
    GAUSSIAN = "gaussian"


@dataclass
class DelayConfig:
    """Configuration parameters for network delay simulation.
    
    Attributes:
        mode: The delay generation mode (FIXED, UNIFORM, GAUSSIAN).
        fixed_delay_ms: Latency in milliseconds for FIXED mode.
        min_delay_ms: Minimum latency bound in milliseconds for UNIFORM mode.
        max_delay_ms: Maximum latency bound in milliseconds for UNIFORM mode.
        mean_delay_ms: Mean latency in milliseconds for GAUSSIAN mode.
        std_delay_ms: Standard deviation in milliseconds for GAUSSIAN mode.
        seed: Random seed for deterministic reproducibility.
    """
    mode: DelayMode = DelayMode.FIXED
    fixed_delay_ms: float = 100.0
    min_delay_ms: float = 50.0
    max_delay_ms: float = 200.0
    mean_delay_ms: float = 100.0
    std_delay_ms: float = 20.0
    seed: Optional[int] = 42

    def validate(self) -> None:
        """Validate configuration bounds and throw ValueError on invalid settings."""
        if self.mode == DelayMode.FIXED:
            if self.fixed_delay_ms < 0:
                raise ValueError(f"fixed_delay_ms must be non-negative, got {self.fixed_delay_ms}")
        elif self.mode == DelayMode.UNIFORM:
            if self.min_delay_ms < 0:
                raise ValueError(f"min_delay_ms must be non-negative, got {self.min_delay_ms}")
            if self.max_delay_ms < self.min_delay_ms:
                raise ValueError(f"max_delay_ms ({self.max_delay_ms}) must be >= min_delay_ms ({self.min_delay_ms})")
        elif self.mode == DelayMode.GAUSSIAN:
            if self.mean_delay_ms < 0:
                raise ValueError(f"mean_delay_ms must be non-negative, got {self.mean_delay_ms}")
            if self.std_delay_ms < 0:
                raise ValueError(f"std_delay_ms must be non-negative, got {self.std_delay_ms}")


class DelayModel:
    """Computes packet transmission delay based on configured mode and parameters."""

    def __init__(self, config: Optional[DelayConfig] = None) -> None:
        self.config = config or DelayConfig()
        self.config.validate()
        self._rng = random.Random(self.config.seed)

    def calculate_delay_seconds(self) -> float:
        """Calculate and return non-negative latency in seconds for a packet."""
        if self.config.mode == DelayMode.FIXED:
            delay_ms = self.config.fixed_delay_ms
        elif self.config.mode == DelayMode.UNIFORM:
            delay_ms = self._rng.uniform(self.config.min_delay_ms, self.config.max_delay_ms)
        elif self.config.mode == DelayMode.GAUSSIAN:
            # Gaussian delay truncated at 0 to guarantee causality (non-negative delay)
            delay_ms = max(0.0, self._rng.gauss(self.config.mean_delay_ms, self.config.std_delay_ms))
        else:
            raise ValueError(f"Unsupported delay mode: {self.config.mode}")

        return max(0.0, delay_ms / 1000.0)

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Reset internal random generator for deterministic test runs."""
        seed = new_seed if new_seed is not None else self.config.seed
        self._rng = random.Random(seed)
