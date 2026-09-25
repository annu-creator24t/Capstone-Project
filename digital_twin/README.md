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
[ Physics-Informed State Estimator ]
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

## 📊 2. Core Data Models (`digital_twin/models.py`)

- **`DigitalTwinState`:** Represents the estimated state ($\hat{x}$) of the vehicle, including estimated speed, RPM, load, thermal temperature, fan status, and synchronization health.
- **`ExpectedMeasurement`:** Represents the nominal output ($\hat{y}$) synthesized by the physical observer.
- **`SensorResidual`:** Stores the evaluated discrepancy $r = y - \hat{y}$, data age ($\text{AoI}$), staleness flags, and anomaly status.
- **`SynchronizationStatus`:** Tracks connectivity quality: `INITIALIZING`, `SYNCHRONIZED`, `PARTIALLY_SYNCHRONIZED`, `STALE`, and `DISCONNECTED`.
- **`AnomalyStatus`:** Diagnostic classification: `NORMAL`, `ANOMALY`, `STALE_DATA`, `INSUFFICIENT_DATA`, and `INVALID_DATA`.

---

## ⚙️ 3. Configuration Reference (`digital_twin/twin_config.py`)

```python
from digital_twin import DigitalTwinConfig, ResidualThresholds, SynchronizationThresholds

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
```
