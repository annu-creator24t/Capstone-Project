"""Packet Queue and Delivery Pipeline for Connected Vehicle Telemetry.

Manages scheduling, packet loss evaluation, stochastic latency application,
and chronological delivery extraction for in-transit network packets.
"""

import heapq
from typing import List, Optional, Tuple
from network.delay_model import DelayModel
from network.models import DeliveryStatus, NetworkPacket
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossModel
from network.packet_ordering import PacketAnalysisResult, PacketOrderingTracker


class PacketQueue:
    """Simulates an asynchronous network pipeline with loss, latency, and out-of-order delivery."""

    def __init__(
        self,
        config: Optional[NetworkConfig] = None,
        delay_model: Optional[DelayModel] = None,
        loss_model: Optional[PacketLossModel] = None,
        ordering_tracker: Optional[PacketOrderingTracker] = None,
    ) -> None:
        self.config = config or NetworkConfig()
        self.config.validate()

        self.delay_model = delay_model or DelayModel(self.config.delay)
        self.loss_model = loss_model or PacketLossModel(self.config.packet_loss)
        self.ordering_tracker = ordering_tracker or PacketOrderingTracker()

        # Priority queue entries stored as: (scheduled_delivery_time, tie_breaker_seq, packet)
        self._in_transit_heap: List[Tuple[float, int, NetworkPacket]] = []
        self._counter: int = 0  # Tie-breaker for stable sorting in heap
        self._dropped_packets: List[NetworkPacket] = []
        self._delivered_packets: List[NetworkPacket] = []
        self._analysis_history: List[PacketAnalysisResult] = []

    def enqueue(
        self,
        packet: NetworkPacket,
        current_time: Optional[float] = None,
    ) -> Optional[NetworkPacket]:
        """Submit a packet into the network pipeline.
        
        Applies packet loss evaluation and transmission delay calculation.
        Returns the scheduled packet if accepted into transit, or None if dropped.
        """
        tx_time = current_time if current_time is not None else packet.generation_timestamp
        packet.transmission_timestamp = tx_time

        # 1. Evaluate Packet Loss
        if self.loss_model.should_drop():
            packet.status = DeliveryStatus.DROPPED
            self._dropped_packets.append(packet)
            return None

        # 2. Compute Stochastic Transmission & Propagation Delay
        delay_s = self.delay_model.calculate_delay_seconds()
        delivery_time = round(tx_time + delay_s, 4)
        
        packet.scheduled_delivery_timestamp = delivery_time
        packet.status = DeliveryStatus.IN_TRANSIT

        # 3. Push to Min-Heap ordered by scheduled delivery time
        self._counter += 1
        heapq.heappush(self._in_transit_heap, (delivery_time, self._counter, packet))
        return packet

    def advance_time(self, current_time: float) -> List[NetworkPacket]:
        """Extract all packets whose delivery time has arrived by current_time.
        
        Packets are delivered strictly in the order of their scheduled delivery timestamps.
        If multiple packets have different latencies, out-of-order delivery naturally emerges.
        """
        delivered: List[NetworkPacket] = []

        while self._in_transit_heap and self._in_transit_heap[0][0] <= current_time:
            delivery_time, _, packet = heapq.heappop(self._in_transit_heap)
            packet.reception_timestamp = delivery_time
            packet.status = DeliveryStatus.DELIVERED
            
            # Analyze ordering and stream state
            analysis = self.ordering_tracker.process_packet(packet)
            self._analysis_history.append(analysis)
            self._delivered_packets.append(packet)
            delivered.append(packet)

        return delivered

    def pending_count(self) -> int:
        """Return count of packets currently in transit."""
        return len(self._in_transit_heap)

    def dropped_count(self) -> int:
        """Return total count of dropped packets."""
        return len(self._dropped_packets)

    def delivered_count(self) -> int:
        """Return total count of delivered packets."""
        return len(self._delivered_packets)

    def is_empty(self) -> bool:
        """Check if any packets remain in transit."""
        return len(self._in_transit_heap) == 0

    def get_dropped_packets(self) -> List[NetworkPacket]:
        """Return read-only copy of dropped packets log."""
        return list(self._dropped_packets)

    def get_delivered_packets(self) -> List[NetworkPacket]:
        """Return read-only copy of delivered packets log."""
        return list(self._delivered_packets)

    def get_analysis_history(self) -> List[PacketAnalysisResult]:
        """Return stream analysis results for all delivered packets."""
        return list(self._analysis_history)

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Reset the queue, loss model, delay model, and ordering tracker."""
        self._in_transit_heap.clear()
        self._dropped_packets.clear()
        self._delivered_packets.clear()
        self._analysis_history.clear()
        self._counter = 0
        self.delay_model.reset(new_seed)
        self.loss_model.reset(new_seed)
        self.ordering_tracker.reset()
