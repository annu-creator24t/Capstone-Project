"""Vehicle Simulator Package for Connected Vehicle Digital Twin Research.

Provides physical powertrain models, sensor noise generators,
and controlled fault injection scenarios.
"""

from simulator.fault_injector import FaultType, FaultConfig, FaultInjector
from simulator.vehicle_model import VehicleModel, VehicleState
from simulator.sensor_generator import SensorGenerator, TelemetryPacket

__all__ = [
    "FaultType",
    "FaultConfig",
    "FaultInjector",
    "VehicleModel",
    "VehicleState",
    "SensorGenerator",
    "TelemetryPacket",
]
