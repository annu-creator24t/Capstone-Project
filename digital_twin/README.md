# Cloud Digital Twin Engine (`digital_twin/`)

This package provides a cloud-side **Physics-Informed Digital Twin (DT)** that estimates the expected and current behavior of connected vehicles, tracks Age of Information (AoI) freshness, computes sensor residuals ($r = y - \hat{y}$), evaluates telemetry freshness and diagnostic eligibility, and provides baseline anomaly detection under intermittent network connectivity.

---

## 🏛️ 1. Architecture & Diagnostic Pipeline

```
[ Received Telemetry Packets ] (via Network Emulator)
             │
             ▼
[ Network-Aware Synchronization Tracker ]
    ├── Evaluates Data Age (AoI = t_eval - t_gen)
    └── Determines Sync Status: SYNCHRONIZED | PARTIALLY_SYNCHRONIZED | STALE | DISCONNECTED
             │
             ▼
[ Digital Twin State Estimator (`digital_twin/state_estimator.py`) ]
    ├── Ingests Valid, Chronological Telemetry Updates
    ├── Rejects Stale / Out-of-Order / Duplicate Packets
    └── Fuses Nominal Physical Model Forward Predictions
             │
             ▼
[ Expected Measurement Synthesizer ]
    └── y^(k) = g(x^(k), u(k))
             │
             ▼
[ Residual Generator (`digital_twin/residual_generator.py`) ]
    ├── Raw Residual: r = y - y^
    ├── Absolute Residual: |r| = |y - y^|
    └── Defensive Relative Residual: r_rel = (y - y^) / max(|y^|, eps)
             │
             ▼
[ Telemetry Freshness & Validity Evaluator (`digital_twin/telemetry_freshness.py`) ]
    ├── Evaluates Data Age (AoI) Against Freshness Thresholds
    ├── Classifies Freshness: FRESH | AGING | STALE | INVALID | MISSING
    └── Evaluates Diagnostic Eligibility (is_diagnostic_eligible)
             │
             ▼
[ Baseline Anomaly Detector (`digital_twin/anomaly_detector.py`) ]
    ├── Signal-Specific Two-Level Thresholding (Warning vs Anomaly)
    ├── Relative Discrepancy & Categorical Actuator Mismatch Evaluation
    ├── Deterministic Persistence Tracking (consecutive sample confirmation)
    └── Produces Structured AnomalyEvaluationResult (NORMAL, WARNING, ANOMALY, NOT_EVALUATED)
```

---

## ⏱️ 2. Telemetry Freshness & Residual Validity (Stage 4B)

### Why Telemetry Freshness Matters

In connected vehicle cloud diagnostics, a large residual discrepancy $r = y - \hat{y}$ does **not** automatically indicate a physical fault. Network delays, buffering, and packet loss create temporal misalignment between vehicle observations and cloud state models.

> **Important Principle:**
> Residual magnitude and telemetry freshness are separate concepts. A residual of $+15^\circ\text{C}$ on fresh data ($\text{AoI} = 0.1\text{s}$) indicates a potential thermal anomaly; the same residual on stale data ($\text{AoI} = 5.0\text{s}$) may merely reflect transient delay.
>
> **Stage 4B does not determine whether a vehicle component is faulty.** It determines whether telemetry and residual information are sufficiently valid and fresh for later diagnostic evaluation.

### Freshness States (`FreshnessStatus`)

1. **`FRESH`:** $0 \le \text{AoI} \le \text{fresh\_aoi\_threshold\_s}$ ($1.0\text{s}$). Telemetry is recent enough to be fully trustworthy for baseline anomaly detection.
2. **`AGING`:** $\text{fresh\_aoi\_threshold\_s} < \text{AoI} \le \text{stale\_aoi\_threshold\_s}$ ($1.0\text{s} < \text{AoI} \le 3.0\text{s}$). Telemetry is older than the preferred fresh window but retained; distinguishable by downstream reasoners.
3. **`STALE`:** $\text{AoI} > \text{stale\_aoi\_threshold\_s}$ ($3.0\text{s}$). Telemetry exceeds acceptable age; not eligible for fresh anomaly evaluation.
4. **`INVALID`:** Telemetry contains $\text{NaN}$, $\pm\infty$, non-numeric types, or causality violations ($\text{AoI} < 0$).
5. **`MISSING`:** Observation or expected measurement is missing/dropped.

---

## 🚨 3. Baseline Anomaly Detector (Stage 4C)

The [`BaselineAnomalyDetector`](file:///c:/Users/ANNU%20TIWARI/Desktop/Capstone%20project/digital_twin/anomaly_detector.py#L26) implements deterministic two-level thresholding, relative discrepancy evaluation, categorical mismatch detection, and persistence tracking for qualified residuals.

> **Notice:**
> **This is a deterministic baseline detector and is not a machine-learning diagnostic system.** The selected threshold values are engineering parameters designed for controlled benchmarking; experimental threshold calibration will be evaluated under varying network scenarios.

### Two-Level Threshold Model

For continuous numerical sensors, the detector compares absolute residual magnitude $|r_k| = |y_k - \hat{y}_k|$ and optional relative residual $|r_{\text{rel}, k}|$:

```text
NORMAL
    │
    │  |r| > warning_threshold  OR  |r_rel| > relative_warning_threshold
    ▼
WARNING
    │
    │  |r| > anomaly_threshold  OR  |r_rel| > relative_anomaly_threshold (consecutive >= N)
    ▼
ANOMALY
```

### Signal-Specific Physical Thresholds (`AnomalyThresholds`)

| Signal | Physical Unit | Warning Threshold | Anomaly Threshold | Relative Warning | Relative Anomaly |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `speed_kmh` | $\text{km/h}$ | $8.0\text{ km/h}$ | $12.0\text{ km/h}$ | $15\%$ ($0.15$) | $25\%$ ($0.25$) |
| `rpm` | $\text{RPM}$ | $200.0\text{ RPM}$ | $350.0\text{ RPM}$ | $10\%$ ($0.10$) | $18\%$ ($0.18$) |
| `engine_load` | $\text{ratio}$ | $0.12$ ($12\%$) | $0.20$ ($20\%$) | N/A | N/A |
| `engine_temperature_c` | $^\circ\text{C}$ | $5.0^\circ\text{C}$ | $8.0^\circ\text{C}$ | $6\%$ ($0.06$) | $10\%$ ($0.10$) |
| `cooling_fan_status` | $\text{discrete}$ | $|r| > 0$ | $|r| > 0.5$ (Mismatch) | N/A | N/A |

### Categorical Fan Policy

For `cooling_fan_status`:
* Matching states ($\text{observed} == \text{expected}$) $\rightarrow$ `NORMAL`.
* Mismatching states ($\text{observed} \ne \text{expected}$) $\rightarrow$ Candidate `ANOMALY`.
* Relative percentage residual is explicitly bypassed because percentage deviation on binary actuator flags is physically meaningless.

### Alert Persistence & Hysteresis

To eliminate false alerts from single-sample noise or instantaneous telemetry jitter:
* **Warning Persistence:** Default `warning_persistence_count = 1`.
* **Anomaly Persistence:** Default `anomaly_persistence_count = 3` consecutive anomalous frames before confirming `ANOMALY`.
* **Sample Interleaving:** A single nominal sample immediately resets the consecutive anomaly counter to zero.
* **Stream Isolation:** State counters are strictly isolated by `(vehicle_id, sensor_name)`.
* **Ineligible Telemetry:** Stale, invalid, or missing observations do **not** increment or corrupt persistence counters.

### Evaluation Severity Levels (`AnomalyLevel`)

* `NORMAL`: Residual is within nominal warning limits.
* `WARNING`: Residual exceeds warning threshold or is an unconfirmed candidate anomaly.
* `ANOMALY`: Residual exceeds anomaly threshold and satisfies configured consecutive persistence count.
* `NOT_EVALUATED`: Telemetry is ineligible (e.g. stale, invalid, missing, rejected).

---

## 📐 4. Residual Formulation & Policies (`digital_twin/residual_generator.py`)

### Mathematical Equations
1. **Raw Residual:**
   $$r_k = y_k - \hat{y}_k$$
2. **Absolute Residual:**
   $$|r_k| = |y_k - \hat{y}_k|$$
3. **Defensive Relative Residual:**
   $$r_{\text{rel}, k} = \frac{y_k - \hat{y}_k}{\max(|\hat{y}_k|, \epsilon)}$$
   where $\epsilon = 10^{-4}$ prevents division-by-zero when $\hat{y}_k = 0$ (e.g., speed standstill).

---

## 🔬 5. Physics-Informed Nominal Model Equations (`digital_twin/nominal_model.py`)

$$\hat{x}_{k+1} = f(\hat{x}_k, u_k, \Delta t)$$

$$\hat{y}_k = g(\hat{x}_k, u_k)$$

$$\dot{Q}_{\text{in}} = (k_{\text{base}} + k_{\text{load}} \cdot \text{engine\_load}) \cdot \left(\frac{\text{rpm}}{1000}\right)$$

$$\dot{Q}_{\text{out}} = (k_{\text{nat}} + k_{\text{speed}} \cdot v + k_{\text{fan}} \cdot \text{fan\_status}) \cdot (T - T_{\text{ambient}})$$

$$\Delta T = \left(\frac{\dot{Q}_{\text{in}} - \dot{Q}_{\text{out}}}{C_{\text{thermal}}}\right) \cdot \Delta t$$

---

## ⚙️ 6. Usage Example

```python
from digital_twin import (
    BaselineAnomalyDetector,
    ExpectedMeasurement,
    ResidualGenerator,
    TelemetryFreshnessEvaluator,
)

evaluator = TelemetryFreshnessEvaluator()
generator = ResidualGenerator(epsilon=1e-4, freshness_evaluator=evaluator)
detector = BaselineAnomalyDetector()

exp = ExpectedMeasurement(
    vehicle_id="EV_001",
    timestamp=10.0,
    expected_speed_kmh=50.0,
    expected_rpm=2200.0,
    expected_engine_load=0.50,
    expected_engine_temperature_c=88.0,
    expected_cooling_fan_status=0,
)

obs = {
    "speed_kmh": 50.0,
    "rpm": 2200.0,
    "engine_load": 0.50,
    "engine_temperature_c": 98.0,  # +10.0°C deviation (> 8.0°C anomaly threshold)
    "cooling_fan_status": 0,
}

residuals = generator.compute_residuals_for_frame(
    vehicle_id="EV_001",
    observed_telemetry=obs,
    expected_measurement=exp,
    timestamp=10.0,
    data_ages={"engine_temperature_c": 0.15},
)

# Evaluate frame through baseline anomaly detector
results = detector.detect_frame(residuals)

temp_eval = results["engine_temperature_c"]
print(f"Anomaly Level: {temp_eval.anomaly_level.value}")      # 'warning' (1st sample of 3)
print(f"Is Confirmed: {temp_eval.is_confirmed}")            # False
print(f"Reason: {temp_eval.reason}")
```

---

## 🔬 7. Integrated Diagnostic Evaluation Framework (Stage 4D)

Stage 4D provides a deterministic, reproducible experimental evaluation framework that integrates the entire connected vehicle Digital Twin diagnostic pipeline:

$$\text{Vehicle Simulator} \longrightarrow \text{Network Impairment \& AoI} \longrightarrow \text{State Estimator} \longrightarrow \text{Nominal Vehicle Model} \longrightarrow \text{Residual Generator} \longrightarrow \text{Freshness Evaluation} \longrightarrow \text{Baseline Anomaly Detector}$$

### Purpose & Scope

The purpose of Stage 4D is **NOT** to introduce machine learning models or novel anomaly detection algorithms. Instead, it provides an empirical testing harness to evaluate how transport-layer impairments (Age of Information, packet loss, transmission delay, jitter, duplicate packets, out-of-order delivery) and physical vehicle faults affect Digital Twin diagnostic accuracy and timeliness.

### Predefined Scenarios (A through G)

The [`DiagnosticEvaluationRunner`](file:///c:/Users/ANNU%20TIWARI/Desktop/Capstone%20project/digital_twin/evaluation.py#L159) provides factory constructors for standard experimental evaluation scenarios:

| Scenario | Name | Condition | Key Metric / Verification |
| :--- | :--- | :--- | :--- |
| **A** | `Scenario_A_Clean` | Healthy vehicle, minimal network impairment (10ms fixed delay). | Telemetry accepted; residuals remain normal; 0 false alerts. |
| **B** | `Scenario_B_Aging_Stale` | Healthy vehicle with communication blackout / staleness hold. | AoI increases; freshness transitions `FRESH` $\to$ `AGING` $\to$ `STALE`; stale frames marked `NOT_EVALUATED`; **0 false vehicle alerts**. |
| **C** | `Scenario_C_Packet_Loss` | Controlled stochastic packet loss ($p = 0.35$). | Quantifies dropped packets, missing updates, and AoI degradation windows. |
| **D** | `Scenario_D_Delay_Jitter` | Stochastic uniform network delay ($50\text{ms} - 600\text{ms}$). | Captures variable arrival jitter, dynamic AoI peaks, and state estimator alignment. |
| **E** | `Scenario_E_Duplicates_OutOfOrder` | Retransmission duplicates ($30\%$) and jittered arrival order. | Verifies duplicate rejection, out-of-order handling, and state integrity in State Estimator. |
| **F** | `Scenario_F_InjectedFault` | Deterministic vehicle fault ($+15^\circ\text{C}$ sensor bias, fan failure, etc.) on clean link. | Evaluates residual magnitude, time-to-confirmation, and detection delay ($\Delta t_{\text{detect}}$). |
| **G** | `Scenario_G_FaultPlusImpairment` | Combined vehicle fault with packet loss ($25\%$) and Gaussian delay ($80\text{ms} \pm 25\text{ms}$). | Evaluates diagnostic resilience under lossy, delayed transport channels. |

### Performance & Diagnostic Metrics

Each evaluation run compiles a structured [`ScenarioResult`](file:///c:/Users/ANNU%20TIWARI/Desktop/Capstone%20project/digital_twin/evaluation.py#L100) containing:

- **Transport & Network Metrics:** `total_generated_frames`, `total_packets_transmitted`, `total_packets_delivered`, `total_packets_dropped`, `packet_loss_rate_percent`.
- **State Estimator Metrics:** `total_accepted_updates`, `total_rejected_updates`, `duplicate_updates`, `stale_updates`, `out_of_order_updates`.
- **Freshness & Eligibility:** `freshness_counts` (`FRESH`, `AGING`, `STALE`, `INVALID`, `MISSING`), `diagnostic_eligible_count`, `not_eligible_count`.
- **Anomaly Severity Counts:** `anomaly_level_counts` (`NORMAL`, `WARNING`, `ANOMALY`, `NOT_EVALUATED`), `candidate_anomaly_count`, `confirmed_anomaly_count`.
- **Ground Truth & Timing Alignment:** `ground_truth_fault_frames`, `true_positive_alert_count`, `false_alert_count`, `detection_delay_s` ($\Delta t = t_{\text{confirmed}} - t_{\text{fault\_start}}$).
- **Residual & AoI Statistics:** `mean_aoi_s`, `max_aoi_s`, `mean_residual_by_sensor`, `max_residual_by_sensor`.

### Evaluation Framework Example

```python
from digital_twin.evaluation import DiagnosticEvaluationRunner
from simulator.fault_injector import FaultType

runner = DiagnosticEvaluationRunner()

# Run Scenario F: Thermal sensor bias (+15°C)
scenario_f = runner.create_scenario_f_injected_fault(
    duration_s=20.0,
    fault_type=FaultType.TEMP_SENSOR_BIAS,
    fault_start_s=5.0,
    fault_end_s=15.0,
    bias_offset_c=15.0,
    seed=42,
)
result = runner.run_scenario(scenario_f)

print(f"Scenario: {result.scenario_name}")
print(f"Delivered Packets: {result.total_packets_delivered}")
print(f"Confirmed Anomalies: {result.confirmed_anomaly_count}")
print(f"Detection Delay: {result.detection_delay_s}s")
print(f"Max Thermal Residual: {result.max_residual_by_sensor['engine_temperature_c']}°C")

# Export structured summary for research analysis
summary = result.to_summary_dict()
```

### Limitations

- **Baseline Thresholds:** Anomaly classifications rely on fixed engineering thresholds rather than adaptive, probabilistic, or machine-learning models.
- **Single Vehicle Scope:** Evaluates one connected vehicle at a time per scenario instance.
- **Physical Dynamics:** Nominal thermal physics uses 1D lumped-parameter differential equations.

---

## 🚀 8. Experimental Campaign & Research Data Generation (Stage 5)

Stage 5 provides an experiment orchestration and research data generation framework built directly on top of the Stage 4D diagnostic evaluation runner.

### Purpose & Research Principle

The objective is to systematically sweep communication parameters (loss, delay, jitter), vehicle fault modes (sensor bias, component failures), and replicate seeds to produce structured research datasets (CSV/JSON/Manifest) for statistical analysis, conference papers, and benchmark comparisons.

The framework preserves the core research distinction:
- **Case 1 (Communication Impairment):** Healthy vehicle with stale or delayed telemetry produces high AoI and $\text{NOT\_EVALUATED}$ freshness classification, avoiding false vehicle anomaly alerts.
- **Case 2 (Genuine Vehicle Fault):** Physical fault on fresh telemetry generates persistent residuals confirmed as an anomaly with measured detection delay ($\Delta t_{\text{detect}}$).

### Standard Experiment Groups (A through H)

- **Group A (`baseline`):** Reference baseline under nominal health and clean $10\text{ms}$ fixed delay.
- **Group B (`packet_loss_sweep`):** Packet loss rates swept over $0\%, 10\%, 20\%, 35\%, 50\%$.
- **Group C (`delay_sweep`):** Transmission latencies swept over $10, 50, 100, 300, 600\text{ms}$.
- **Group D (`jitter_sweep`):** Latency jitter swept over $0, 25, 50, 100, 250\text{ms}$.
- **Group E (`fault_severity_sweep`):** Thermal sensor biases swept over $+5^\circ\text{C}, +10^\circ\text{C}, +15^\circ\text{C}, +20^\circ\text{C}$.
- **Group F (`fault_packet_loss`):** Fault condition ($+15^\circ\text{C}$ bias) evaluated under packet loss ($0\%$ to $50\%$).
- **Group G (`fault_delay`):** Fault condition ($+15^\circ\text{C}$ bias) evaluated across network delays ($10\text{ms}$ to $600\text{ms}$).
- **Group H (`combined_impairment`):** Multi-variable real-world impairment ($+15^\circ\text{C}$ bias, $25\%$ loss, $80\text{ms} \pm 25\text{ms}$ delay) across replicate seeds.

### Campaign Execution via Python API

```python
from digital_twin.experiment_runner import ExperimentCampaign, ExperimentRunner

runner = ExperimentRunner()

# 1. Build a packet loss sweep campaign
configs = ExperimentCampaign.create_packet_loss_sweep_group(
    loss_rates=[0.0, 0.10, 0.20, 0.35, 0.50],
    seeds=[42, 101, 202],
    duration_s=20.0,
)

# 2. Run the campaign batch
results = runner.run_campaign(configs)

# 3. Export datasets
runner.export_to_csv(results, "experiments/results/campaign_packet_loss_results.csv")
runner.export_to_json(results, "experiments/results/campaign_packet_loss_results.json")
runner.generate_manifest(configs, "experiments/experiment_manifest.json")
```

### Campaign Execution via CLI

```bash
# Run full master campaign
python -m digital_twin.run_experiments --all

# Run specific experiment group
python -m digital_twin.run_experiments --group fault_packet_loss --seeds 42 101 202
```
