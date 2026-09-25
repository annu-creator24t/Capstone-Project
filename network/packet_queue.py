"""Packet Queue and Delivery Pipeline for Connected Vehicle Telemetry.

Manages scheduling, bandwidth serialization, byte quotas, packet loss evaluation,
stochastic latency application, chronological delivery extraction, and AoI freshness tracking.
"""

import heapq
from typing import Any, Dict, List, Optional, Tuple
from network.aoi_tracker import AoITracker
from network.bandwidth_model import BandwidthConfig
from network.delay_model import DelayModel
from network.models import DeliveryStatus, NetworkPacket
from network.network_config import NetworkConfig
from network.packet_loss import PacketLossModel
from network.packet_ordering import PacketAnalysisResult, PacketOrderingTracker
from network.transmission_scheduler import TransmissionScheduler


class PacketQueue:
    """Simulates an asynchronous network pipeline with bandwidth, loss, latency, and AoI tracking."""

    def __init__(
        self,
        config: Optional[NetworkConfig] = None,
        delay_model: Optional[DelayModel] = None,
        loss_model: Optional[PacketLossModel] = None,
        scheduler: Optional[TransmissionScheduler] = None,
        ordering_tracker: Optional[PacketOrderingTracker] = None,
        aoi_tracker: Optional[AoITracker] = None,
    ) -> None:
        self.config = config or NetworkConfig()
        self.config.validate()

        self.delay_model = delay_model or DelayModel(self.config.delay)
        self.loss_model = loss_model or PacketLossModel(self.config.packet_loss)
        self.scheduler = scheduler or TransmissionScheduler(self.config.bandwidth)
        self.ordering_tracker = ordering_tracker or PacketOrderingTracker(self.config.ordering)
        self.aoi_tracker = aoi_tracker or AoITracker()

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
        
        Applies:
            1. Packet loss evaluation
            2. Bandwidth serialization and byte quota scheduling
            3. Propagation delay calculation
            4. In-transit priority queue placement
            
        Returns:
            The scheduled packet if accepted into transit, or None if dropped/blocked.
        """
        t_now = current_time if current_time is not None else packet.generation_timestamp

        # 1. Evaluate Packet Loss
        if self.loss_model.should_drop():
            packet.status = DeliveryStatus.DROPPED
            self._dropped_packets.append(packet)
            return None

        # 2. Bandwidth & Quota Transmission Scheduling
        schedule_result = self.scheduler.schedule(packet, t_now)
        if schedule_result is None:
            # Packet blocked by quota (and rejected)
            self._dropped_packets.append(packet)
            return None

        tx_start, tx_complete = schedule_result

        # 3. Compute Stochastic Propagation Latency
        propagation_delay_s = self.delay_model.calculate_delay_seconds()
        delivery_time = round(tx_complete + propagation_delay_s, 4)
        
        packet.scheduled_delivery_timestamp = delivery_time
        packet.status = DeliveryStatus.IN_TRANSIT

        # 4. Push to Min-Heap ordered by scheduled delivery time
        self._counter += 1
        heapq.heappush(self._in_transit_heap, (delivery_time, self._counter, packet))
        return packet

    def advance_time(self, current_time: float) -> List[NetworkPacket]:
        """Extract all packets whose delivery time has arrived by current_time.
        
        Packets are delivered strictly in the order of their scheduled delivery timestamps.
        Updates ordering tracker and AoI freshness engine.
        """
        delivered: List[NetworkPacket] = []

        while self._in_transit_heap and self._in_transit_heap[0][0] <= current_time:
            delivery_time, _, packet = heapq.heappop(self._in_transit_heap)
            packet.reception_timestamp = delivery_time
            packet.status = DeliveryStatus.DELIVERED
            
            # 1. Analyze ordering and stream state
            analysis = self.ordering_tracker.process_packet(packet)
            self._analysis_history.append(analysis)
            
            # 2. Update Age-of-Information (AoI) Freshness
            self.aoi_tracker.update(packet, current_time=delivery_time)

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

    def get_scheduler_metrics(self) -> Dict[str, Any]:
        """Return transmission scheduler performance metrics."""
        return self.scheduler.get_metrics()

    def get_aoi_statistics(self, vehicle_id: str, sensor_name: str, current_time: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Retrieve Age of Information metrics for a specific stream."""
        return self.aoi_tracker.get_statistics(vehicle_id, sensor_name, current_time)

    def reset(self, new_seed: Optional[int] = None) -> None:
        """Reset the queue, loss model, delay model, scheduler, ordering tracker, and AoI engine."""
        self._in_transit_heap.clear()
        self._dropped_packets.clear()
        self._delivered_packets.clear()
        self._analysis_history.clear()
        self._counter = 0
        self.delay_model.reset(new_seed)
        self.loss_model.reset(new_seed)
        self.scheduler.reset()
        self.ordering_tracker.reset()
        self.aoi_tracker.reset()
