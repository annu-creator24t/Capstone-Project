"""Reproducible Controlled Experiment Runner: Normal Operation vs Cooling Fan Failure.

Executes a 40-second comparative run between healthy vehicle operation and
cooling fan actuator failure, logging all physical and diagnostic metrics.

Usage:
    python -m digital_twin.run_controlled_experiment
"""

import json
import os
import sys
from typing import Optional
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard.simulation_manager import DashboardSimulationSession
from simulator.fault_injector import FaultType


def run_controlled_experiment(
    duration_s: float = 40.0,
    dt_s: float = 0.1,
    initial_temp_c: float = 95.0,
    output_dir: Optional[str] = None,
) -> pd.DataFrame:
    """Run controlled comparison and persist results to CSV and JSON."""
    n_steps = int(duration_s / dt_s)
    out_dir = output_dir or os.path.join(PROJECT_ROOT, "experiments", "results")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Executing Controlled Experiment: {duration_s}s, initial temp={initial_temp_c}°C")

    # A: Normal Operation
    session_a = DashboardSimulationSession(vehicle_id="EV_001", dt_s=dt_s, seed=42, history_maxlen=1000)
    session_a.reset(initial_temp_c=initial_temp_c)
    session_a.reconfigure(fault_type=FaultType.NORMAL)

    history_a = []
    for _ in range(n_steps):
        rec = session_a.step(n_steps=1)
        rec["experiment"] = "Normal_Operation"
        history_a.append(rec)
    df_a = pd.DataFrame(history_a)

    # B: Cooling Fan Failure
    session_b = DashboardSimulationSession(vehicle_id="EV_001", dt_s=dt_s, seed=42, history_maxlen=1000)
    session_b.reset(initial_temp_c=initial_temp_c)
    session_b.reconfigure(fault_type=FaultType.FAN_FAILURE, fault_start_s=0.0)

    history_b = []
    for _ in range(n_steps):
        rec = session_b.step(n_steps=1)
        rec["experiment"] = "Cooling_Fan_Failure"
        history_b.append(rec)
    df_b = pd.DataFrame(history_b)

    df_combined = pd.concat([df_a, df_b], ignore_index=True)
    csv_path = os.path.join(out_dir, "controlled_fault_experiment.csv")
    json_path = os.path.join(out_dir, "controlled_fault_experiment.json")

    df_combined.to_csv(csv_path, index=False)

    summary_data = {
        "duration_s": duration_s,
        "dt_s": dt_s,
        "initial_temp_c": initial_temp_c,
        "normal_operation": {
            "final_temp_c": float(df_a["true_engine_temp_c"].iloc[-1]),
            "mean_temp_c": float(df_a["true_engine_temp_c"].mean()),
            "max_residual_c": float(df_a["residual_c"].abs().max()),
            "confirmed_anomalies": int(session_a.confirmed_anomaly_count),
        },
        "fan_failure": {
            "final_temp_c": float(df_b["true_engine_temp_c"].iloc[-1]),
            "mean_temp_c": float(df_b["true_engine_temp_c"].mean()),
            "final_residual_c": float(df_b["residual_c"].iloc[-1]),
            "first_anomaly_time_s": float(session_b.first_anomaly_time or 0.0),
            "confirmed_anomalies": int(session_b.confirmed_anomaly_count),
        },
        "temperature_difference_at_end_c": float(
            df_b["true_engine_temp_c"].iloc[-1] - df_a["true_engine_temp_c"].iloc[-1]
        ),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print(f"Results saved to:\n  {csv_path}\n  {json_path}")
    return df_combined


if __name__ == "__main__":
    from typing import Optional
    run_controlled_experiment()
