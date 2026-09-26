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
[ Future Anomaly Detector & Diagnostic Reasoner ]
    └── Evaluates Residual Magnitudes on Trustworthy, Fresh Data
```

---

## ⏱️ 2. Telemetry Freshness & Residual Validity (Stage 4B)

### Why Telemetry Freshness Matters

In connected vehicle cloud diagnostics, a large residual discrepancy $r = y - \hat{y}$ does **not** automatically indicate a physical fault. Network delays, buffering, and packet loss create temporal misalignment between vehicle observations and cloud state models.

> **Important Principle:**
> Residual magnitude and telemetry freshness are separate concepts. A residual of $+15^\circ\text{C}$ on fresh data ($\text{AoI} = 0.1\text{s}$) indicates a potential thermal anomaly; the same residual on stale data ($\text{AoI} = 5.0\text{s}$) may merely reflect transient delay.
>
> **Stage 4B does not determine whether a vehicle component is faulty.** It determines whether telemetry and residual information are sufficiently valid and fresh for later diagnostic evaluation.

### Conceptual Flow

```text
Telemetry
    ↓
Acceptance
    ↓
Residual Generation
    ↓
Data Age / AoI
    ↓
Freshness Evaluation
    ↓
Diagnostic Eligibility
    ↓
Future Anomaly Detector
```

### Freshness States (`FreshnessStatus`)

1. **`FRESH`:** $0 \le \text{AoI} \le \text{fresh\_aoi\_threshold\_s}$ ($1.0\text{s}$). Telemetry is recent enough to be fully trustworthy for baseline anomaly detection.
2. **`AGING`:** $\text{fresh\_aoi\_threshold\_s} < \text{AoI} \le \text{stale\_aoi\_threshold\_s}$ ($1.0\text{s} < \text{AoI} \le 3.0\text{s}$). Telemetry is older than the preferred fresh window but retained; distinguishable by downstream reasoners.
3. **`STALE`:** $\text{AoI} > \text{stale\_aoi\_threshold\_s}$ ($3.0\text{s}$). Telemetry exceeds acceptable age; not eligible for fresh anomaly evaluation.
4. **`INVALID`:** Telemetry contains $\text{NaN}$, $\pm\infty$, non-numeric types, or causality violations ($\text{AoI} < 0$).
5. **`MISSING`:** Observation or expected measurement is missing/dropped.

### Freshness Thresholds (`FreshnessThresholds`)

Configured in [`DigitalTwinConfig`](file:///c:/Users/ANNU%20TIWARI/Desktop/Capstone%20project/digital_twin/twin_config.py):
* `fresh_aoi_threshold_s = 1.0s`: Maximum age for fully fresh evidence.
* `stale_aoi_threshold_s = 3.0s`: Age beyond which telemetry is considered stale.

### Diagnostic Eligibility Policy

A residual is marked `diagnostic_eligible = True` if and only if:
1. It is accepted by the state estimator (`is_accepted = True`).
2. It is not flagged stale (`is_stale = False`).
3. It has valid numerical observed and expected values (not `INVALID_DATA` or `INSUFFICIENT_DATA`).
4. It has a calculated residual (`residual is not None`).
5. Its freshness status is `FRESH` (or `AGING` when explicitly allowed via `allow_aging=True`).

### Retention of Stale Telemetry for Research

Stale and aging residuals are **never discarded**. They are enriched with `residual`, `data_age_s` (AoI), `is_stale = True`, and `diagnostic_eligible = False`. This enables experimental evaluation of:
* Detection latency under stochastic delays
* False alarm rates induced by Age of Information
* Diagnostic reliability across network bandwidth variations

---

## 📐 3. Residual Formulation & Policies (`digital_twin/residual_generator.py`)

### Mathematical Equations
1. **Raw Residual:**
   $$r_k = y_k - \hat{y}_k$$
2. **Absolute Residual:**
   $$|r_k| = |y_k - \hat{y}_k|$$
3. **Defensive Relative Residual:**
   $$r_{\text{rel}, k} = \frac{y_k - \hat{y}_k}{\max(|\hat{y}_k|, \epsilon)}$$
   where $\epsilon = 10^{-4}$ prevents division-by-zero when $\hat{y}_k = 0$ (e.g., speed standstill).

### Signal Specific Policies
- **Continuous Numerical Signals (`speed_kmh`, `rpm`, `engine_load`, `engine_temperature_c`):** Full computation of raw and relative residuals.
- **Categorical Actuator Signals (`cooling_fan_status`):** Evaluates discrete state matching (0 vs 1); relative residual is set to `None` because percentage error on binary discrete states is unphysical.
- **Missing / Invalid Values:**
  - `observed_value = None`: Handled gracefully as `INSUFFICIENT_DATA` (`residual = None`).
  - `NaN / Inf / Non-numeric`: Classified as `INVALID_DATA` (`is_accepted = False`).
  - `Stale Telemetry`: Evaluated but classified as `STALE_DATA` (`is_accepted = False`, `diagnostic_eligible = False`).

---

## 📥 4. Telemetry Acceptance & Staleness Rejection Policies

1. **Duplicate Rejection:** Packets with already-observed `packet_id` or `(sensor_name, sequence_number)` are rejected.
2. **Stale / Out-of-Order Rejection:** If $t_{\text{generation}} < t_{\text{last\_accepted\_gen}}$, the packet is rejected from updating the state and recorded as stale/out-of-order.
3. **Synchronization Health:**
   - `INITIALIZING`: No valid telemetry ingested yet.
   - `SYNCHRONIZED`: Time since last observation $\le 3.0\text{s}$.
   - `STALE`: Time since last observation $> 3.0\text{s}$.
   - `DISCONNECTED`: Time since last observation $> 10.0\text{s}$.

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
    ExpectedMeasurement,
    FreshnessStatus,
    ResidualGenerator,
    TelemetryFreshnessEvaluator,
)

evaluator = TelemetryFreshnessEvaluator()
generator = ResidualGenerator(epsilon=1e-4, freshness_evaluator=evaluator)

# Expected nominal state synthesized by Digital Twin
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
    "engine_temperature_c": 96.0,  # +8.0°C deviation
    "cooling_fan_status": 0,
}

# Evaluates residuals and qualifies freshness with AoI tracking
residuals = generator.compute_residuals_for_frame(
    vehicle_id="EV_001",
    observed_telemetry=obs,
    expected_measurement=exp,
    timestamp=10.0,
    data_ages={"engine_temperature_c": 0.15},  # 150ms AoI -> FRESH
)

temp_res = residuals["engine_temperature_c"]
print(f"Raw Residual: {temp_res.residual}°C")
print(f"Freshness Status: {temp_res.freshness_status.value}")  # 'fresh'
print(f"Diagnostic Eligible: {temp_res.diagnostic_eligible}")  # True
```
