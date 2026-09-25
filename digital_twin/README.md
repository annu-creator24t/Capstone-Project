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
[ Residual Generator ]
    ├── Absolute Residual: |r| = |y - y^|
    └── Relative Residual: |r| / |y^|
             |
             v
[ Baseline Anomaly Detector ]
    └── Compares Residuals against Sensor Thresholds
```

---

## 📥 2. Telemetry Acceptance & Staleness Rejection Policies

1. **Duplicate Rejection:** Packets with already-observed `packet_id` or `(sensor_name, sequence_number)` are rejected and logged.
2. **Stale / Out-of-Order Rejection:** If $t_{\text{generation}} < t_{\text{last\_accepted\_gen}}$, the packet is rejected from updating the state and recorded as stale/out-of-order. The estimator never moves backward in simulation time.
3. **Valid Telemetry Assimilation:**
   - If $t_{\text{generation}} > t_{\text{current\_state}}$, the estimator predicts the nominal model forward to $t_{\text{generation}}$ and updates corresponding state fields.
4. **Synchronization State Machine:**
   - `INITIALIZING`: No valid telemetry ingested yet.
   - `SYNCHRONIZED`: Time since last observation $\le \text{stale\_aoi\_threshold\_s}$ ($3.0\text{s}$).
   - `STALE`: Time since last observation $> 3.0\text{s}$.
   - `DISCONNECTED`: Time since last observation $> \text{disconnect\_aoi\_threshold\_s}$ ($10.0\text{s}$).

---

## 🔬 3. Physics-Informed Nominal Model Equations (`digital_twin/nominal_model.py`)

$$\hat{x}_{k+1} = f(\hat{x}_k, u_k, \Delta t)$$

$$\hat{y}_k = g(\hat{x}_k, u_k)$$

### Dynamic Thermal Balance
$$\dot{Q}_{\text{in}} = (k_{\text{base}} + k_{\text{load}} \cdot \text{engine\_load}) \cdot \left(\frac{\text{rpm}}{1000}\right)$$

$$\dot{Q}_{\text{out}} = (k_{\text{nat}} + k_{\text{speed}} \cdot v + k_{\text{fan}} \cdot \text{fan\_status}) \cdot (T - T_{\text{ambient}})$$

$$\Delta T = \left(\frac{\dot{Q}_{\text{in}} - \dot{Q}_{\text{out}}}{C_{\text{thermal}}}\right) \cdot \Delta t$$

---

## 📊 4. Core Data Models (`digital_twin/models.py`)

- **`DigitalTwinState`:** Represents the estimated state ($\hat{x}$) of the vehicle.
- **`ExpectedMeasurement`:** Represents the nominal output ($\hat{y}$) synthesized by the physical observer.
- **`SensorResidual`:** Stores the evaluated discrepancy $r = y - \hat{y}$, data age ($\text{AoI}$), staleness flags, and anomaly status.
- **`SynchronizationStatus`:** Tracks connectivity quality: `INITIALIZING`, `SYNCHRONIZED`, `PARTIALLY_SYNCHRONIZED`, `STALE`, and `DISCONNECTED`.
- **`AnomalyStatus`:** Diagnostic classification: `NORMAL`, `ANOMALY`, `STALE_DATA`, `INSUFFICIENT_DATA`, and `INVALID_DATA`.

---

## ⚙️ 5. Usage Example

```python
from digital_twin import DigitalTwinConfig, DigitalTwinStateEstimator
from network import NetworkPacket

estimator = DigitalTwinStateEstimator()

# Process incoming telemetry packet arrived at reception time t=1.1s
packet = NetworkPacket(
    packet_id="pkt_001",
    vehicle_id="EV_001",
    sensor_name="engine_temperature_c",
    value=91.5,
    generation_timestamp=1.0,
    sequence_number=1,
)

accepted = estimator.update_from_packet(packet, reception_time=1.1)
state = estimator.get_state()
expected = estimator.get_expected_measurements()
```
