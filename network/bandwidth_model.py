"""Bandwidth Limitation, Serialization Delay, and Byte Quota Accounting.

Simulates physical link throughput, serialization duration, and transmission byte quotas.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional


def calculate_serialization_time(packet_size_bytes: int, bandwidth_bps: float) -> float:
    """Calculate the time in seconds required to serialize a packet onto a communication link.
    
    Formula:
        T_serialization = (packet_size_bytes * 8) / bandwidth_bps
        
    Args:
        packet_size_bytes: Non-negative packet payload size in bytes.
        bandwidth_bps: Strictly positive bandwidth in bits per second.
        
    Returns:
        Duration in seconds as a floating point number.
    """
    if bandwidth_bps <= 0:
        raise ValueError(f"bandwidth_bps must be strictly positive (>0), got {bandwidth_bps}")
    if packet_size_bytes < 0:
        raise ValueError(f"packet_size_bytes must be non-negative (>=0), got {packet_size_bytes}")
        
    if packet_size_bytes == 0:
        return 0.0
        
    return (packet_size_bytes * 8.0) / float(bandwidth_bps)


class QuotaAction(str, Enum):
    """Action to take when a packet exceeds the available byte quota in a window."""
    DELAY_TO_NEXT_WINDOW = "delay_to_next_window"
    REJECT_PACKET = "reject_packet"


@dataclass
class BandwidthConfig:
    """Configuration for transmission bandwidth and byte quotas.
    
    Attributes:
        enabled: Whether bandwidth serialization and scheduling constraints are active.
        bandwidth_bps: Uplink throughput in bits per second (e.g. 64000 for 64 kbps).
        quota_bytes: Optional limit on transmitted bytes per time window (None = unlimited).
        quota_window_seconds: Duration of each quota period in simulation seconds.
        quota_action: Action when quota is exceeded (DELAY_TO_NEXT_WINDOW or REJECT_PACKET).
        max_queue_size: Optional maximum number of packets allowed in transmission buffer.
    """
    enabled: bool = True
    bandwidth_bps: float = 64000.0  # 64 kbps default
    quota_bytes: Optional[int] = None
    quota_window_seconds: float = 1.0
    quota_action: QuotaAction = QuotaAction.DELAY_TO_NEXT_WINDOW
    max_queue_size: Optional[int] = None

    def validate(self) -> None:
        """Validate bandwidth parameters and bounds."""
        if self.bandwidth_bps <= 0:
            raise ValueError(f"bandwidth_bps must be strictly positive, got {self.bandwidth_bps}")
        if self.quota_bytes is not None and self.quota_bytes < 0:
            raise ValueError(f"quota_bytes must be non-negative, got {self.quota_bytes}")
        if self.quota_window_seconds <= 0:
            raise ValueError(f"quota_window_seconds must be strictly positive, got {self.quota_window_seconds}")
        if self.max_queue_size is not None and self.max_queue_size <= 0:
            raise ValueError(f"max_queue_size must be strictly positive if set, got {self.max_queue_size}")


class ByteQuotaTracker:
    """Tracks byte consumption over discrete, non-overlapping time windows."""

    def __init__(self, quota_bytes: Optional[int] = None, quota_window_seconds: float = 1.0) -> None:
        self.quota_bytes = quota_bytes
        self.quota_window_seconds = quota_window_seconds
        self.current_window_index: int = 0
        self.bytes_transmitted_in_window: int = 0
        self.total_quota_blocked_count: int = 0

    def _get_window_index(self, current_time: float) -> int:
        """Compute the discrete window index for a given simulation time."""
        return int(math.floor(current_time / self.quota_window_seconds))

    def _sync_window(self, current_time: float) -> None:
        """Reset quota counter if simulation time has advanced into a new window."""
        win_idx = self._get_window_index(current_time)
        if win_idx != self.current_window_index:
            self.current_window_index = win_idx
            self.bytes_transmitted_in_window = 0

    def can_transmit(self, packet_size_bytes: int, current_time: float) -> bool:
        """Check if transmitting packet_size_bytes at current_time fits within quota."""
        if self.quota_bytes is None:
            return True
        self._sync_window(current_time)
        return (self.bytes_transmitted_in_window + packet_size_bytes) <= self.quota_bytes

    def consume(self, packet_size_bytes: int, current_time: float) -> None:
        """Record transmission of bytes at current_time against quota."""
        if self.quota_bytes is None:
            return
        self._sync_window(current_time)
        self.bytes_transmitted_in_window += packet_size_bytes

    def get_next_window_start(self, current_time: float) -> float:
        """Calculate the simulation timestamp when the next quota window begins."""
        win_idx = self._get_window_index(current_time)
        return (win_idx + 1) * self.quota_window_seconds

    def reset(self) -> None:
        """Reset quota tracking state."""
        self.current_window_index = 0
        self.bytes_transmitted_in_window = 0
        self.total_quota_blocked_count = 0
