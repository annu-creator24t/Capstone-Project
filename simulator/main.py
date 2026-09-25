"""Command-Line Interface and Runner for the Vehicle Simulator.

Usage:
    python -m simulator.main --scenario normal --duration 30
    python -m simulator.main --scenario fan_failure --start-time 10 --duration 60
    python -m simulator.main --scenario temp_sensor_bias --bias-offset 20.0
"""

import argparse
import json
import math
import sys
from typing import List

from simulator.fault_injector import FaultConfig, FaultInjector, FaultType
from simulator.sensor_generator import SensorGenerator, TelemetryPacket
from simulator.vehicle_model import VehicleModel


def run_simulation(
    scenario: str = "normal",
    duration_s: int = 30,
    dt_s: float = 1.0,
    seed: int = 42,
    fault_start_s: float = 10.0,
    fault_end_s: float = None,
    bias_offset_c: float = 15.0,
    vehicle_id: str = "EV_001",
) -> List[TelemetryPacket]:
    """Execute a simulated driving cycle and generate telemetry packets."""
    try:
        fault_type = FaultType(scenario)
    except ValueError:
        print(f"Error: Unknown scenario '{scenario}'. Supported: {[f.value for f in FaultType]}")
        sys.exit(1)

    fault_cfg = FaultConfig(
        fault_type=fault_type,
        start_time_s=fault_start_s,
        end_time_s=fault_end_s,
        bias_offset_c=bias_offset_c,
    )
    fault_injector = FaultInjector(fault_cfg)
    vehicle = VehicleModel()
    sensor_gen = SensorGenerator(vehicle_id=vehicle_id, random_seed=seed)

    packets: List[TelemetryPacket] = []
    total_steps = int(duration_s / dt_s)

    for step_idx in range(total_steps):
        current_time = step_idx * dt_s

        # Realistic dynamic driving profile (urban speed variations)
        base_speed = 45.0 + 15.0 * math.sin(current_time / 10.0)
        base_rpm = 1800.0 + (base_speed / 100.0) * 1500.0
        base_load = 0.40 + 0.20 * math.sin(current_time / 8.0)

        # Step vehicle physical model
        state = vehicle.step(
            dt_seconds=dt_s,
            speed_kmh=base_speed,
            rpm=base_rpm,
            engine_load=base_load,
            fault_type=fault_injector.get_current_fault_type(current_time),
        )

        # Generate noisy telemetry packet
        packet = sensor_gen.generate(physical_state=state, fault_injector=fault_injector)
        packets.append(packet)

    return packets


def main() -> None:
    """CLI entry point for running vehicle simulation scenarios."""
    parser = argparse.ArgumentParser(description="Connected Vehicle Telemetry Simulator")
    parser.add_argument(
        "--scenario",
        type=str,
        default="normal",
        choices=[f.value for f in FaultType],
        help="Operating mode or fault injection scenario",
    )
    parser.add_argument("--duration", type=int, default=30, help="Simulation duration in seconds")
    parser.add_argument("--dt", type=float, default=1.0, help="Simulation time step in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible noise")
    parser.add_argument("--start-time", type=float, default=10.0, help="Fault injection start time (s)")
    parser.add_argument("--bias-offset", type=float, default=15.0, help="Bias offset in °C for temp sensor bias")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON file path")
    parser.add_argument("--pretty", action="store_true", help="Print formatted telemetry stream to console")

    args = parser.parse_args()

    packets = run_simulation(
        scenario=args.scenario,
        duration_s=args.duration,
        dt_s=args.dt,
        seed=args.seed,
        fault_start_s=args.start_time,
        bias_offset_c=args.bias_offset,
    )

    print(f"=== Simulation Completed: Scenario='{args.scenario}' ({len(packets)} frames) ===")
    
    # Print summary table or first few frames
    if args.pretty:
        for p in packets:
            print(json.dumps(p.to_dict(), indent=2))
    else:
        # Sample display
        print(f"Time (s) | Speed(km/h) | RPM    | Load  | Temp(C) | Fan | Fault Mode")
        print("-" * 65)
        for i, p in enumerate(packets):
            if i % max(1, len(packets) // 10) == 0 or i == len(packets) - 1:
                temp_str = f"{p.engine_temperature_c:6.1f}" if p.engine_temperature_c is not None else "  None"
                print(
                    f"{i*args.dt:7.1f} | {p.speed_kmh:10.1f} | {p.rpm:6.0f} | {p.engine_load:5.2f} | "
                    f"{temp_str} | {p.cooling_fan_status:3d} | {p.fault_status}"
                )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in packets], f, indent=2)
        print(f"\n[Saved telemetry output to '{args.output}']")


if __name__ == "__main__":
    main()
