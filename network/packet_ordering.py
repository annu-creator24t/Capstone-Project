"""Packet Ordering, Stale Telemetry Detection, and Stream Analytics.

Tracks per-sensor telemetry sequence numbers, timestamps, and classifies
out-of-order, stale, duplicate, and in-sequence packet arrivals.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set, Tuple
from network.models import NetworkPacket


class OrderingPolicy(str, Enum):
    """Supported packet processing and ordering policies."""
    ARRIVAL_ORDER = "arrival_order"       # Process immediately upon arrival regardless of timestamps
    TIMESTAMP_AWARE = "timestamp_aware"   # Detect out-of-order & stale packets, preserve latest timestamp
    BOUNDED_BUFFER = "bounded_buffer"     # Hold in bounded window to re-order jittered packets


@dataclass
class OrderingConfig:
    """Configuration for packet ordering analysis and handling."""
    policy: OrderingPolicy = OrderingPolicy.TIMESTAMP_AWARE
    reject_stale: bool = False
    buffer_window_s: float = 0.0

    def validate(self) -> None:
        """Validate ordering configuration parameters."""
        if self.buffer_window_s < 0.0:
            raise ValueError(f"buffer_window_s must be non-negative, got {self.buffer_window_s}")


@dataclass
class StreamState:
    """Maintains sequencing and staleness telemetry metrics for a single sensor stream."""
    vehicle_id: str
    sensor_name: str
    last_generation_timestamp: float = -1.0
    last_sequence_number: int = -1
    last_reception_timestamp: float = -1.0
    total_received: int = 0
    accepted_count: int = 0
    out_of_order_count: int = 0
    stale_count: int = 0
    duplicate_count: int = 0
    seen_packet_ids: Set[str] = field(default_factory=set)
    seen_sequence_numbers: Set[int] = field(default_factory=set)


@dataclass
class PacketAnalysisResult:
    """Result of analyzing an arrived packet against the stream history."""
    packet: NetworkPacket
    is_duplicate: bool
    is_out_of_order: bool
    is_stale: bool
    is_accepted: bool
    stream_state: StreamState


class PacketOrderingTracker:
    """Tracks sequence numbers and timestamps per sensor stream to detect out-of-order anomalies."""

    def __init__(self, config: Optional[OrderingConfig] = None) -> None:
        self.config = config or OrderingConfig()
        self.config.validate()
        self._streams: Dict[Tuple[str, str], StreamState] = {}

    def get_or_create_stream(self, vehicle_id: str, sensor_name: str) -> StreamState:
        """Retrieve or initialize stream tracking state."""
        key = (vehicle_id, sensor_name)
        if key not in self._streams:
            self._streams[key] = StreamState(vehicle_id=vehicle_id, sensor_name=sensor_name)
        return self._streams[key]

    def process_packet(self, packet: NetworkPacket) -> PacketAnalysisResult:
        """Analyze an arrived packet for ordering, duplicates, and staleness.
        
        Definitions:
            - Duplicate: Packet ID or sequence number has already been processed for this stream.
            - Out-of-Order: Sequence number < last received sequence number OR generation_timestamp < last received.
            - Stale: Generation timestamp < highest observed generation timestamp (older information arriving late).
            - Accepted: Packet is valid and represents new, non-stale information (or accepted by policy).
        """
        stream = self.get_or_create_stream(packet.vehicle_id, packet.sensor_name)
        stream.total_received += 1

        is_duplicate = (packet.packet_id in stream.seen_packet_ids or 
                        packet.sequence_number in stream.seen_sequence_numbers)
        
        is_out_of_order = False
        is_stale = False

        if not is_duplicate:
            stream.seen_packet_ids.add(packet.packet_id)
            stream.seen_sequence_numbers.add(packet.sequence_number)

            if stream.last_sequence_number != -1 and packet.sequence_number < stream.last_sequence_number:
                is_out_of_order = True

            if stream.last_generation_timestamp >= 0.0 and packet.generation_timestamp < stream.last_generation_timestamp:
                is_stale = True
                is_out_of_order = True

        # Update metrics
        if is_duplicate:
            stream.duplicate_count += 1
        if is_out_of_order:
            stream.out_of_order_count += 1
        if is_stale:
            stream.stale_count += 1

        # Determine acceptance based on policy
        if self.config.policy == OrderingPolicy.ARRIVAL_ORDER:
            is_accepted = True
        elif self.config.reject_stale and (is_stale or is_duplicate):
            is_accepted = False
        else:
            is_accepted = not is_duplicate

        if is_accepted and not is_stale and not is_duplicate:
            stream.last_generation_timestamp = max(stream.last_generation_timestamp, packet.generation_timestamp)
            stream.last_sequence_number = max(stream.last_sequence_number, packet.sequence_number)

        if packet.reception_timestamp is not None:
            stream.last_reception_timestamp = packet.reception_timestamp

        if is_accepted:
            stream.accepted_count += 1

        return PacketAnalysisResult(
            packet=packet,
            is_duplicate=is_duplicate,
            is_out_of_order=is_out_of_order,
            is_stale=is_stale,
            is_accepted=is_accepted,
            stream_state=stream,
        )

    def get_stream_state(self, vehicle_id: str, sensor_name: str) -> Optional[StreamState]:
        """Return the stream state for a specific vehicle and sensor stream."""
        return self._streams.get((vehicle_id, sensor_name))

    def reset(self) -> None:
        """Reset all stream tracking states."""
        self._streams.clear()
