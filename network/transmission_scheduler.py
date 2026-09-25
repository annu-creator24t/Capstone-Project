"""Simulation-Time Transmission Scheduler with Bandwidth and Quota Enforcement.

Implements FIFO transmission scheduling on a shared uplink channel, calculating
serialization duration, preventing overlapping transmissions, and managing byte quotas.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from network.bandwidth_model import (
    BandwidthConfig,
    ByteQuotaTracker,
    QuotaAction,
    calculate_serialization_time,
)
from network.models import DeliveryStatus, NetworkPacket


@dataclass
class SchedulerMetrics:
    """Metrics tracked during transmission scheduling."""
    total_enqueued: int = 0
    total_transmitted: int = 0
    total_bytes_transmitted: int = 0
    total_serialization_time_s: float = 0.0
    total_queue_wait_time_s: float = 0.0
    quota_blocked_count: int = 0
    rejected_count: int = 0

    @property
    def average_queue_wait_time_s(self) -> float:
        """Calculate average wait time spent in queue prior to transmission."""
        if self.total_transmitted == 0:
            return 0.0
        return self.total_queue_wait_time_s / float(self.total_transmitted)

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        return {
            "total_enqueued": self.total_enqueued,
            "total_transmitted": self.total_transmitted,
            "total_bytes_transmitted": self.total_bytes_transmitted,
            "total_serialization_time_s": round(self.total_serialization_time_s, 4),
            "total_queue_wait_time_s": round(self.total_queue_wait_time_s, 4),
            "average_queue_wait_time_s": round(self.average_queue_wait_time_s, 4),
            "quota_blocked_count": self.quota_blocked_count,
            "rejected_count": self.rejected_count,
        }


class TransmissionScheduler:
    """Schedules packets on a single-channel uplink enforcing serialization delay and byte quotas."""

    def __init__(self, config: Optional[BandwidthConfig] = None) -> None:
        self.config = config or BandwidthConfig()
        self.config.validate()

        self.quota_tracker = ByteQuotaTracker(
            quota_bytes=self.config.quota_bytes,
            quota_window_seconds=self.config.quota_window_seconds,
        )
        self.link_busy_until: float = 0.0
        self.metrics = SchedulerMetrics()

    def schedule(
        self,
        packet: NetworkPacket,
        current_time: float,
    ) -> Optional[Tuple[float, float]]:
        """Schedule a packet for transmission.
        
        Calculates serialization start and completion times without overlapping
        prior in-flight transmissions, applying byte quotas and queue rules.
        
        Returns:
            Tuple of (tx_start_time, tx_completion_time) in simulation seconds,
            or None if the packet is rejected.
        """
        self.metrics.total_enqueued += 1
        packet.queue_entry_timestamp = current_time

        # Calculate base serialization time (0.0 if bandwidth disabled)
        if not self.config.enabled:
            ser_time = 0.0
        else:
            ser_time = calculate_serialization_time(packet.size_bytes, self.config.bandwidth_bps)

        # 1. Determine earliest physical link availability
        earliest_start = max(current_time, self.link_busy_until)

        # 2. Check and enforce Byte Quota if configured
        if self.config.enabled and self.config.quota_bytes is not None:
            # Check if packet exceeds entire window quota capacity
            if packet.size_bytes > self.config.quota_bytes:
                packet.status = DeliveryStatus.QUOTA_BLOCKED
                self.metrics.rejected_count += 1
                return None

            while not self.quota_tracker.can_transmit(packet.size_bytes, earliest_start):
                self.metrics.quota_blocked_count += 1
                if self.config.quota_action == QuotaAction.REJECT_PACKET:
                    packet.status = DeliveryStatus.QUOTA_BLOCKED
                    self.metrics.rejected_count += 1
                    return None
                
                # Delay to start of next quota window
                next_window_time = self.quota_tracker.get_next_window_start(earliest_start)
                earliest_start = max(next_window_time, self.link_busy_until)

            self.quota_tracker.consume(packet.size_bytes, earliest_start)

        # 3. Commit Transmission Schedule
        tx_start = round(earliest_start, 4)
        tx_complete = round(tx_start + ser_time, 4)
        self.link_busy_until = tx_complete

        packet.transmission_timestamp = tx_start
        packet.transmission_completion_timestamp = tx_complete

        # 4. Update Metrics
        self.metrics.total_transmitted += 1
        self.metrics.total_bytes_transmitted += packet.size_bytes
        self.metrics.total_serialization_time_s += ser_time
        self.metrics.total_queue_wait_time_s += max(0.0, tx_start - current_time)

        return (tx_start, tx_complete)

    def get_metrics(self) -> Dict[str, Any]:
        """Return a copy of scheduler transmission metrics."""
        return self.metrics.to_dict()

    def reset(self) -> None:
        """Reset link state, quota tracker, and metrics."""
        self.link_busy_until = 0.0
        self.quota_tracker.reset()
        self.metrics = SchedulerMetrics()
