"""Network Data Models for Connected Vehicle Telemetry Transmission.

Defines the structure of network packets, delivery status enums,
and serialization helpers for the network impairment layer.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class DeliveryStatus(str, Enum):
    """Status of a packet within the network emulation pipeline."""
    QUEUED = "queued"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    DROPPED = "dropped"


@dataclass
class NetworkPacket:
    """Represents a discrete telemetry packet traversing the network emulator.
    
    Attributes:
        packet_id: Unique string identifier (e.g., 'pkt_000001').
        vehicle_id: Originating vehicle ID.
        sensor_name: Name of the telemetry parameter (e.g., 'engine_temperature_c').
        value: Telemetry sensor value or payload.
        generation_timestamp: Logical simulation time (s) when the measurement was taken.
        sequence_number: Monotonically increasing sequence number per sensor/vehicle.
        size_bytes: Estimated size of the serialized network packet in bytes.
        transmission_timestamp: Simulation time (s) when packet leaves vehicle buffer.
        scheduled_delivery_timestamp: Simulation time (s) when packet is scheduled to arrive.
        reception_timestamp: Actual simulation time (s) when packet arrives at receiver.
        status: Current delivery status (QUEUED, IN_TRANSIT, DELIVERED, DROPPED).
    """
    packet_id: str
    vehicle_id: str
    sensor_name: str
    value: Any
    generation_timestamp: float
    sequence_number: int
    size_bytes: int = 128
    transmission_timestamp: Optional[float] = None
    scheduled_delivery_timestamp: Optional[float] = None
    reception_timestamp: Optional[float] = None
    status: DeliveryStatus = DeliveryStatus.QUEUED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize packet metadata and payload to a dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        return data
