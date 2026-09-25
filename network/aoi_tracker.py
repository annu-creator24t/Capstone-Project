"""Age of Information (AoI) Freshness Tracking Engine for Connected Vehicles.

Tracks data freshness per vehicle and per sensor stream according to the standard
AoI metric: AoI(t) = t - u(t), where u(t) is the generation timestamp of the
most recent valid update received by time t.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from network.models import NetworkPacket


@dataclass
class SensorAoIState:
    """Maintains Age-of-Information (AoI) freshness and statistics for a single sensor stream."""
    vehicle_id: str
    sensor_name: str
    latest_generation_timestamp: Optional[float] = None
    latest_reception_timestamp: Optional[float] = None
    
    # AoI Extremes and Peaks
    peak_aoi: float = 0.0
    min_aoi: Optional[float] = None
    max_aoi: Optional[float] = None
    
    # Counters
    valid_updates_count: int = 0
    stale_updates_count: int = 0
    out_of_order_count: int = 0
    duplicate_count: int = 0
    
    # Internal history & area under AoI curve for continuous time-average calculation
    last_eval_time: Optional[float] = None
    accumulated_aoi_area: float = 0.0
    total_observation_time: float = 0.0
    
    # Discrete Sample Accumulator
    sample_count: int = 0
    sample_sum_aoi: float = 0.0
    
    seen_packet_ids: Set[str] = field(default_factory=set)
    seen_sequence_numbers: Set[int] = field(default_factory=set)

    def current_aoi(self, current_time: float) -> Optional[float]:
        """Calculate freshness age AoI(t) = t - u(t) at simulation time t."""
        if self.latest_generation_timestamp is None:
            return None
        if current_time < self.latest_generation_timestamp:
            raise ValueError(
                f"Current simulation time ({current_time}) cannot be earlier than "
                f"latest generation timestamp ({self.latest_generation_timestamp})"
            )
        return round(current_time - self.latest_generation_timestamp, 4)

    def sample_time_average_aoi(self) -> Optional[float]:
        """Calculate discrete sample mean AoI across recorded observation timestamps."""
        if self.sample_count == 0:
            return None
        return round(self.sample_sum_aoi / float(self.sample_count), 4)

    def time_integrated_average_aoi(self) -> Optional[float]:
        """Calculate continuous time-weighted average AoI: (1/T) * integral(AoI(t) dt)."""
        if self.total_observation_time <= 0.0:
            return None
        return round(self.accumulated_aoi_area / self.total_observation_time, 4)

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """Export comprehensive freshness statistics for research analysis."""
        curr_aoi = self.current_aoi(current_time) if current_time is not None else None
        return {
            "vehicle_id": self.vehicle_id,
            "sensor_name": self.sensor_name,
            "has_received_update": self.latest_generation_timestamp is not None,
            "latest_generation_timestamp": self.latest_generation_timestamp,
            "latest_reception_timestamp": self.latest_reception_timestamp,
            "current_aoi_s": curr_aoi,
            "peak_aoi_s": round(self.peak_aoi, 4) if self.peak_aoi > 0 else None,
            "min_aoi_s": round(self.min_aoi, 4) if self.min_aoi is not None else None,
            "max_aoi_s": round(self.max_aoi, 4) if self.max_aoi is not None else None,
            "sample_average_aoi_s": self.sample_time_average_aoi(),
            "time_integrated_average_aoi_s": self.time_integrated_average_aoi(),
            "valid_updates_count": self.valid_updates_count,
            "stale_updates_count": self.stale_updates_count,
            "out_of_order_count": self.out_of_order_count,
            "duplicate_count": self.duplicate_count,
        }


class AoITracker:
    """Engine for tracking and evaluating telemetry data freshness across all vehicle sensor streams."""

    def __init__(self) -> None:
        self._streams: Dict[Tuple[str, str], SensorAoIState] = {}

    def register_sensor(self, vehicle_id: str, sensor_name: str) -> SensorAoIState:
        """Explicitly initialize tracking state for a vehicle sensor stream."""
        key = (vehicle_id, sensor_name)
        if key not in self._streams:
            self._streams[key] = SensorAoIState(vehicle_id=vehicle_id, sensor_name=sensor_name)
        return self._streams[key]

    def get_or_create_stream(self, vehicle_id: str, sensor_name: str) -> SensorAoIState:
        """Retrieve existing stream or initialize a new one."""
        return self.register_sensor(vehicle_id, sensor_name)

    def _advance_stream_integration(self, stream: SensorAoIState, current_time: float) -> None:
        """Integrate area under the AoI sawtooth curve from last_eval_time to current_time."""
        if stream.last_eval_time is None:
            stream.last_eval_time = current_time
            return

        dt = current_time - stream.last_eval_time
        if dt <= 0.0:
            return

        if stream.latest_generation_timestamp is not None:
            # AoI at start of interval: aoi_start = last_eval_time - latest_gen
            aoi_start = stream.last_eval_time - stream.latest_generation_timestamp
            # AoI right before current_time: aoi_end = current_time - latest_gen = aoi_start + dt
            aoi_end = aoi_start + dt
            # Trapezoidal integration for linear segment: Area = 0.5 * (aoi_start + aoi_end) * dt
            segment_area = 0.5 * (aoi_start + aoi_end) * dt
            stream.accumulated_aoi_area += segment_area
            stream.total_observation_time += dt

            # Update peak and max AoI
            if aoi_end > stream.peak_aoi:
                stream.peak_aoi = aoi_end
            if stream.max_aoi is None or aoi_end > stream.max_aoi:
                stream.max_aoi = aoi_end

        stream.last_eval_time = current_time

    def update(self, packet: NetworkPacket, current_time: float) -> Optional[float]:
        """Process an arrived telemetry packet and update data freshness.
        
        Rules:
            1. Integrates continuous AoI curve up to reception instant current_time.
            2. Checks for duplicates: duplicates do not update freshness.
            3. Checks for staleness: if packet.generation_timestamp <= latest_generation_timestamp,
               packet is recorded as stale and does NOT reset the AoI downwards.
            4. If packet is strictly newer: updates latest_generation_timestamp, resets AoI
               to instantaneous reception delay (current_time - packet.generation_timestamp),
               and updates min/max statistics.
               
        Returns:
            The new current AoI in seconds, or None if packet did not improve freshness.
        """
        if not packet.vehicle_id or not packet.sensor_name:
            raise ValueError("Packet vehicle_id and sensor_name must be non-empty strings")
            
        stream = self.get_or_create_stream(packet.vehicle_id, packet.sensor_name)
        
        # 1. Advance continuous integration to arrival time
        self._advance_stream_integration(stream, current_time)
        stream.latest_reception_timestamp = current_time

        # 2. Check for Duplicates
        is_duplicate = (packet.packet_id in stream.seen_packet_ids or 
                        packet.sequence_number in stream.seen_sequence_numbers)
        if is_duplicate:
            stream.duplicate_count += 1
            return None

        stream.seen_packet_ids.add(packet.packet_id)
        stream.seen_sequence_numbers.add(packet.sequence_number)

        # 3. Check for Out-of-Order and Staleness
        if stream.latest_generation_timestamp is not None:
            if packet.generation_timestamp < stream.latest_generation_timestamp:
                stream.stale_updates_count += 1
                stream.out_of_order_count += 1
                return None
            elif packet.generation_timestamp == stream.latest_generation_timestamp:
                # Equal generation timestamp (redundant update)
                stream.stale_updates_count += 1
                return None

        # 4. Valid Freshness Update
        stream.valid_updates_count += 1
        stream.latest_generation_timestamp = packet.generation_timestamp
        
        instant_aoi = round(current_time - packet.generation_timestamp, 4)
        
        # Track min/max/peak
        if stream.min_aoi is None or instant_aoi < stream.min_aoi:
            stream.min_aoi = instant_aoi
        if stream.max_aoi is None or instant_aoi > stream.max_aoi:
            stream.max_aoi = instant_aoi
        if instant_aoi > stream.peak_aoi:
            stream.peak_aoi = instant_aoi

        # Sample observation
        stream.sample_count += 1
        stream.sample_sum_aoi += instant_aoi

        return instant_aoi

    def sample_all(self, current_time: float) -> Dict[Tuple[str, str], Optional[float]]:
        """Sample and record the instantaneous AoI across all registered streams at simulation time t."""
        results: Dict[Tuple[str, str], Optional[float]] = {}
        for key, stream in self._streams.items():
            self._advance_stream_integration(stream, current_time)
            aoi_val = stream.current_aoi(current_time)
            if aoi_val is not None:
                stream.sample_count += 1
                stream.sample_sum_aoi += aoi_val
            results[key] = aoi_val
        return results

    def get_current_aoi(self, vehicle_id: str, sensor_name: str, current_time: float) -> Optional[float]:
        """Retrieve the instantaneous Age of Information for a stream at current_time."""
        stream = self._streams.get((vehicle_id, sensor_name))
        if stream is None:
            return None
        return stream.current_aoi(current_time)

    def get_statistics(self, vehicle_id: str, sensor_name: str, current_time: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Retrieve comprehensive AoI statistics dictionary for a specific sensor stream."""
        stream = self._streams.get((vehicle_id, sensor_name))
        if stream is None:
            return None
        if current_time is not None:
            self._advance_stream_integration(stream, current_time)
        return stream.to_dict(current_time)

    def get_all_statistics(self, current_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """Retrieve statistics across all active sensor streams."""
        return [self.get_statistics(v, s, current_time) for (v, s) in self._streams.keys()]

    def reset(self) -> None:
        """Clear all stream tracking states."""
        self._streams.clear()
