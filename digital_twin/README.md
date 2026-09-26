# Cloud Digital Twin Engine (`digital_twin/`)

This package provides a cloud-side **Physics-Informed Digital Twin (DT)** that estimates the expected and current behavior of connected vehicles, tracks Age of Information (AoI) freshness, computes sensor residuals ($r = y - \hat{y}$), and provides baseline threshold anomaly detection under intermittent network connectivity.

---

## 🏛️ 1. Architecture & Pipeline

```
[ Received Telemetry Packets ] (via Network Emulator)
             |
             v
[ Network-Aware Synchronization Tracker ]
    ├── Evaluates Data Age (AoI)
    └── Determines Sync Status: SYNCHRONIZED | PARTIALLY_SYNCHRONIZED | STALE | DISCONNECTED
             |
             v
[ Digital Twin State Estimator (`digital_twin/state_estimator.py`) ]
    ├── Ingests Valid, Chronological Telemetry Updates
    ├── Rejects Stale / Out-of-Order / Duplicate Packets
    └── Fuses Nominal Physical Model Forward Predictions
             |
             v
[ Expected Measurement Synthesizer ]
    └── y^(k) = g(x^(k), u(k))
             |
             v
[ Residual Generator (`digital_twin/residual_generator.py`) ]
    ├── Raw Residual: r = y - y^
    ├── Absolute Residual: |r| = |y - y^|
    └── Defensive Relative Residual: r_rel = (y - y^) / max(|y^|, eps)
             |
             v
[ Baseline Anomaly Detector ]
    └── Compares Residuals against Sensor Thresholds
```

---

## 📐 2. Residual Formulation & Policies (`digital_twin/residual_generator.py`)

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
  - `Stale Telemetry`: Evaluated but classified as `STALE_DATA` (`is_accepted = False`).

---

## 📥 3. Telemetry Acceptance & Staleness Rejection Policies

1. **Duplicate Rejection:** Packets with already-observed `packet_id` or `(sensor_name, sequence_number)` are rejected.
2. **Stale / Out-of-Order Rejection:** If $t_{\text{generation}} < t_{\text{last\_accepted\_gen}}$, the packet is rejected from updating the state and recorded as stale/out-of-order.
3. **Synchronization Health:**
   - `INITIALIZING`: No valid telemetry ingested yet.
   - `SYNCHRONIZED`: Time since last observation $\le 3.0\text{s}$.
   - `STALE`: Time since last observation $> 3.0\text{s}$.
   - `DISCONNECTED`: Time since last observation $> 10.0\text{s}$.

---

## 🔬 4. Physics-Informed Nominal Model Equations (`digital_twin/nominal_model.py`)

$$\hat{x}_{k+1} = f(\hat{x}_k, u_k, \Delta t)$$

$$\hat{y}_k = g(\hat{x}_k, u_k)$$

$$\dot{Q}_{\text{in}} = (k_{\text{base}} + k_{\text{load}} \cdot \text{engine\_load}) \cdot \left(\frac{\text{rpm}}{1000}\right)$$

$$\dot{Q}_{\text{out}} = (k_{\text{nat}} + k_{\text{speed}} \cdot v + k_{\text{fan}} \cdot \text{fan\_status}) \cdot (T - T_{\text{ambient}})$$

$$\Delta T = \left(\frac{\dot{Q}_{\text{in}} - \dot{Q}_{\text{out}}}{C_{\text{thermal}}}\right) \cdot \Delta t$$

---

## ⚙️ 5. Usage Example

```python
from digital_twin import ResidualGenerator, ExpectedMeasurement

generator = ResidualGenerator(epsilon=1e-4)

# Generate residuals between received telemetry and expected measurement
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

residuals = generator.compute_residuals_for_frame(
    vehicle_id="EV_001",
    observed_telemetry=obs,
    expected_measurement=exp,
)

# Access residual
temp_res = residuals["engine_temperature_c"]
print(f"Raw Residual: {temp_res.residual}°C, Relative: {temp_res.relative_residual*100}%")
```
