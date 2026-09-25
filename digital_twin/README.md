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
[ Physics-Informed Nominal Model / State Estimator ]
    ├── Predicts Nominal State: x^(k+1) = f(x^(k), u(k), dt)
    └── Updates with Valid Non-Stale Telemetry
             |
             v
[ Expected Measurement Synthesizer ]
    └── y^(k) = g(x^(k), u(k))
             |
             v
[ Residual Generator ]
    ├── Absolute Residual: |r| = |y - y^|
    └── Relative Residual: |r| / |y^|
             |
             v
[ Baseline Anomaly Detector ]
    └── Compares Residuals against Sensor Thresholds
```

---

## 🔬 2. Physics-Informed Nominal Model Equations (`digital_twin/nominal_model.py`)

The nominal model implements a deterministic discrete-time observer:

$$\hat{x}_{k+1} = f(\hat{x}_k, u_k, \Delta t)$$

$$\hat{y}_k = g(\hat{x}_k, u_k)$$

### Dynamic Thermal Balance
$$\dot{Q}_{\text{in}} = (k_{\text{base}} + k_{\text{load}} \cdot \text{engine\_load}) \cdot \left(\frac{\text{rpm}}{1000}\right)$$

$$\dot{Q}_{\text{out}} = (k_{\text{nat}} + k_{\text{speed}} \cdot v + k_{\text{fan}} \cdot \text{fan\_status}) \cdot (T - T_{\text{ambient}})$$

$$\Delta T = \left(\frac{\dot{Q}_{\text{in}} - \dot{Q}_{\text{out}}}{C_{\text{thermal}}}\right) \cdot \Delta t$$

### Thermostat Control Logic
- **Fan Engagement:** Turns ON ($1$) when $T \ge 95^\circ\text{C}$.
- **Fan Disengagement:** Turns OFF ($0$) when $T \le 90^\circ\text{C}$ (hysteresis).

---

## 📊 3. Core Data Models (`digital_twin/models.py`)

- **`DigitalTwinState`:** Represents the estimated state ($\hat{x}$) of the vehicle, including estimated speed, RPM, load, thermal temperature, fan status, and synchronization health.
- **`ExpectedMeasurement`:** Represents the nominal output ($\hat{y}$) synthesized by the physical observer.
- **`SensorResidual`:** Stores the evaluated discrepancy $r = y - \hat{y}$, data age ($\text{AoI}$), staleness flags, and anomaly status.
- **`SynchronizationStatus`:** Tracks connectivity quality: `INITIALIZING`, `SYNCHRONIZED`, `PARTIALLY_SYNCHRONIZED`, `STALE`, and `DISCONNECTED`.
- **`AnomalyStatus`:** Diagnostic classification: `NORMAL`, `ANOMALY`, `STALE_DATA`, `INSUFFICIENT_DATA`, and `INVALID_DATA`.

---

## ⚙️ 4. Configuration Reference (`digital_twin/twin_config.py`)

```python
from digital_twin import DigitalTwinConfig, ResidualThresholds, SynchronizationThresholds, NominalVehicleModel

config = DigitalTwinConfig(
    vehicle_id="EV_001",
    initial_temp_c=85.0,
    thresholds=ResidualThresholds(
        engine_temperature_c=8.0, # Flag anomaly if |r_temp| > 8.0°C
        rpm=350.0,
        speed_kmh=12.0,
        engine_load=0.20,
    ),
    sync_thresholds=SynchronizationThresholds(
        stale_aoi_threshold_s=3.0,
        disconnect_aoi_threshold_s=10.0,
    ),
)

nominal_model = NominalVehicleModel(config=config)
```
