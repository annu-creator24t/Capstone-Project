"""Cloud Digital Twin State Estimator & Telemetry Updater.

Maintains the estimated vehicle state in the cloud by fusing physics-informed nominal
predictions with asynchronously received, delayed, or out-of-order telemetry packets.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set
from digital_twin.models import (
    DigitalTwinState,
    ExpectedMeasurement,
    SynchronizationStatus,
)
from digital_twin.nominal_model import NominalVehicleModel
from digital_twin.twin_config import DigitalTwinConfig
from network.models import NetworkPacket
from simulator.sensor_generator import TelemetryPacket


@dataclass
class EstimatorMetrics:
    """Performance and tracking metrics for the Digital Twin State Estimator."""
    total_telemetry_received: int = 0
    accepted_updates: int = 0
    rejected_updates: int = 0
    stale_updates: int = 0
    duplicate_updates: int = 0
    out_of_order_updates: int = 0
    prediction_steps: int = 0
    last_accepted_generation_timestamp: Optional[float] = None
    last_reception_timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return asdict(self)


class DigitalTwinStateEstimator:
    """State Estimator maintaining the Cloud Digital Twin's vehicle state."""

    def __init__(
        self,
        config: Optional[DigitalTwinConfig] = None,
        nominal_model: Optional[NominalVehicleModel] = None,
    ) -> None:
        self.config = config or DigitalTwinConfig()
        self.config.validate()

        self.nominal_model = nominal_model or NominalVehicleModel(self.config)
        self.is_initialized: bool = False
        self.metrics = EstimatorMetrics()

        # Tracking structures for duplicate and stale rejection
        self._seen_packet_ids: Set[str] = set()
        self._seen_sequence_numbers: Dict[str, Set[int]] = defaultdict(set)
        self._last_accepted_gen_per_sensor: Dict[str, float] = {}

        # Current estimated state snapshot
        self._current_state = DigitalTwinState(
            vehicle_id=self.config.vehicle_id,
            timestamp=0.0,
            estimated_speed_kmh=45.0,
            estimated_rpm=2200.0,
            estimated_engine_load=0.50,
            estimated_engine_temperature_c=self.config.initial_temp_c,
            estimated_cooling_fan_status=0,
            last_observation_timestamp=None,
            sync_status=SynchronizationStatus.INITIALIZING,
        )

    def _evaluate_sync_status(self, current_time: float) -> SynchronizationStatus:
        """Determine synchronization health based on elapsed time since latest observation."""
        if not self.is_initialized or self.metrics.last_accepted_generation_timestamp is None:
            return SynchronizationStatus.INITIALIZING

        data_age = current_time - self.metrics.last_accepted_generation_timestamp
        if data_age > self.config.sync_thresholds.disconnect_aoi_threshold_s:
            return SynchronizationStatus.DISCONNECTED
        elif data_age > self.config.sync_thresholds.stale_aoi_threshold_s:
            return SynchronizationStatus.STALE
        return SynchronizationStatus.SYNCHRONIZED

    def update_from_packet(
        self,
        packet: NetworkPacket,
        reception_time: float,
    ) -> bool:
        """Process an individual telemetry packet arrived from the network layer.
        
        Rules:
            1. Duplicate detection: Reject if packet_id or sequence_number seen.
            2. Stale/out-of-order detection: Reject if generation_timestamp < last_accepted_timestamp for this sensor.
            3. Valid acceptance: Advance nominal model to generation_timestamp, apply sensor value,
               and update synchronization status.
               
        Returns:
            True if packet was accepted and updated state; False if rejected/stale/duplicate.
        """
        self.metrics.total_telemetry_received += 1
        sensor = packet.sensor_name

        # 1. Duplicate check
        if packet.packet_id in self._seen_packet_ids or packet.sequence_number in self._seen_sequence_numbers[sensor]:
            self.metrics.duplicate_updates += 1
            self.metrics.rejected_updates += 1
            return False

        # 2. Stale / Out-of-Order check
        last_gen = self._last_accepted_gen_per_sensor.get(sensor, -1.0)
        if packet.generation_timestamp < last_gen:
            self.metrics.stale_updates += 1
            self.metrics.out_of_order_updates += 1
            self.metrics.rejected_updates += 1
            return False

        # Register packet identifiers
        self._seen_packet_ids.add(packet.packet_id)
        self._seen_sequence_numbers[sensor].add(packet.sequence_number)

        # 3. Apply Valid Update
        gen_time = packet.generation_timestamp
        self.metrics.accepted_updates += 1
        self.metrics.last_reception_timestamp = reception_time
        self.metrics.last_accepted_generation_timestamp = max(
            self.metrics.last_accepted_generation_timestamp or 0.0, gen_time
        )
        self._last_accepted_gen_per_sensor[sensor] = gen_time

        # If incoming packet is strictly newer than current DT state, predict forward
        if gen_time > self._current_state.timestamp:
            dt = gen_time - self._current_state.timestamp
            self.nominal_model.step(dt_seconds=dt)
            self._current_state.timestamp = round(gen_time, 4)

        # Update specific state field if value is non-null
        val = packet.value
        if val is not None:
            if sensor == "speed_kmh":
                self._current_state.estimated_speed_kmh = float(val)
                self.nominal_model.speed_kmh = float(val)
            elif sensor == "rpm":
                self._current_state.estimated_rpm = float(val)
                self.nominal_model.rpm = float(val)
            elif sensor == "engine_load":
                self._current_state.estimated_engine_load = float(val)
                self.nominal_model.engine_load = float(val)
            elif sensor == "engine_temperature_c":
                self._current_state.estimated_engine_temperature_c = float(val)
                self.nominal_model.engine_temperature_c = float(val)
            elif sensor == "cooling_fan_status":
                self._current_state.estimated_cooling_fan_status = int(val)
                self.nominal_model.cooling_fan_status = int(val)

        self._current_state.last_observation_timestamp = gen_time
        self.is_initialized = True
        self._current_state.sync_status = self._evaluate_sync_status(reception_time)

        return True

    def update_from_telemetry_frame(
        self,
        telemetry: TelemetryPacket,
        generation_time: float,
        reception_time: float,
    ) -> bool:
        """Convenience method to ingest a full TelemetryPacket frame."""
        self.metrics.total_telemetry_received += 1
        
        if self.metrics.last_accepted_generation_timestamp is not None:
            if generation_time < self.metrics.last_accepted_generation_timestamp:
                self.metrics.stale_updates += 1
                self.metrics.rejected_updates += 1
                return False

        # Advance model forward to generation time
        if generation_time > self._current_state.timestamp:
            dt = generation_time - self._current_state.timestamp
            self.nominal_model.step(dt_seconds=dt)
            self._current_state.timestamp = round(generation_time, 4)

        # Update fields
        self._current_state.estimated_speed_kmh = telemetry.speed_kmh
        self._current_state.estimated_rpm = telemetry.rpm
        self._current_state.estimated_engine_load = telemetry.engine_load
        if telemetry.engine_temperature_c is not None:
            self._current_state.estimated_engine_temperature_c = telemetry.engine_temperature_c
            self.nominal_model.engine_temperature_c = telemetry.engine_temperature_c
        self._current_state.estimated_cooling_fan_status = telemetry.cooling_fan_status

        # Synchronize nominal model internals
        self.nominal_model.speed_kmh = telemetry.speed_kmh
        self.nominal_model.rpm = telemetry.rpm
        self.nominal_model.engine_load = telemetry.engine_load
        self.nominal_model.cooling_fan_status = telemetry.cooling_fan_status

        self.is_initialized = True
        self.metrics.accepted_updates += 1
        self.metrics.last_accepted_generation_timestamp = generation_time
        self.metrics.last_reception_timestamp = reception_time
        self._current_state.last_observation_timestamp = generation_time
        self._current_state.sync_status = self._evaluate_sync_status(reception_time)

        return True

    def predict(self, target_time: float) -> DigitalTwinState:
        """Advance Digital Twin forward in time to target_time using nominal physical model."""
        if target_time < self._current_state.timestamp:
            raise ValueError(
                f"target_time ({target_time}) cannot be earlier than current state timestamp ({self._current_state.timestamp})"
            )

        dt = target_time - self._current_state.timestamp
        if dt > 0:
            self.metrics.prediction_steps += 1
            predicted_state = self.nominal_model.step(dt_seconds=dt)
            self._current_state.timestamp = round(target_time, 4)
            self._current_state.estimated_engine_temperature_c = predicted_state.estimated_engine_temperature_c
            self._current_state.estimated_cooling_fan_status = predicted_state.estimated_cooling_fan_status

        self._current_state.sync_status = self._evaluate_sync_status(target_time)
        return self.get_state()

    def get_state(self) -> DigitalTwinState:
        """Return the current estimated DigitalTwinState snapshot."""
        return DigitalTwinState(
            vehicle_id=self.config.vehicle_id,
            timestamp=self._current_state.timestamp,
            estimated_speed_kmh=self._current_state.estimated_speed_kmh,
            estimated_rpm=self._current_state.estimated_rpm,
            estimated_engine_load=self._current_state.estimated_engine_load,
            estimated_engine_temperature_c=self._current_state.estimated_engine_temperature_c,
            estimated_cooling_fan_status=self._current_state.estimated_cooling_fan_status,
            last_observation_timestamp=self._current_state.last_observation_timestamp,
            sync_status=self._current_state.sync_status,
        )

    def get_expected_measurements(self) -> ExpectedMeasurement:
        """Synthesize nominal expected sensor outputs from current estimated state."""
        return self.nominal_model.generate_expected_measurements(self._current_state)

    def get_metrics(self) -> Dict[str, Any]:
        """Return State Estimator performance metrics."""
        return self.metrics.to_dict()

    def reset(self) -> None:
        """Reset estimator state, metrics, and nominal model."""
        self.nominal_model.reset()
        self.is_initialized = False
        self.metrics = EstimatorMetrics()
        self._seen_packet_ids.clear()
        self._seen_sequence_numbers.clear()
        self._last_accepted_gen_per_sensor.clear()
        self._current_state = DigitalTwinState(
            vehicle_id=self.config.vehicle_id,
            timestamp=0.0,
            estimated_speed_kmh=45.0,
            estimated_rpm=2200.0,
            estimated_engine_load=0.50,
            estimated_engine_temperature_c=self.config.initial_temp_c,
            estimated_cooling_fan_status=0,
            last_observation_timestamp=None,
            sync_status=SynchronizationStatus.INITIALIZING,
        )
