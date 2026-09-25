# Network Impairment & Telemetry Pipeline (`network/`)

This package provides a high-fidelity, configurable communication layer that simulates real-world wireless and cellular channel degradation between connected vehicle ECUs and the cloud Digital Twin backend.

---

## 📡 1. End-to-End Packet Lifecycle & Pipeline Flow

```
[ Vehicle Telemetry Observation (generation_timestamp) ]
             |
             v
[ NetworkEmulator.ingest_telemetry_frame() ]
    ├── Split into discrete sensor packets (temperature, RPM, speed, load, fan)
    └── Assign monotonically increasing sequence numbers
             |
             v
[ Packet Loss Evaluation ] ──(Dropped)──> [ Dropped Packets Log (Status: DROPPED) ]
             |
          (Passed)
             |
             v
[ Transmission Scheduler (FIFO Uplink Queue) ]
    ├── Serialization Duration: T_ser = (size_bytes * 8) / bandwidth_bps
    ├── Byte Quota Verification: check_quota(size_bytes, window)
    └── Single-Channel Channel Locking: tx_start = max(t_now, link_busy_until)
             |
             v
[ Propagation Delay Model ] (tau ~ Fixed / Uniform / Gaussian)
             |
    scheduled_delivery = tx_complete + tau
             |
             v
[ In-Transit Priority Queue ] (Min-Heap keyed by scheduled delivery timestamp)
             |
   (advance_time(t))
             |
             v
[ Arrival Stream Extraction ] (Chronological reception sequence)
             |
             v
[ Packet Ordering Tracker ]
    ├── Out-of-Order Detection
    ├── Stale Telemetry Flagging (Generation Timestamp < Latest Processed)
    └── Duplicate Detection
             |
             v
[ Age of Information (AoI) Freshness Engine ]
    ├── Instantaneous AoI: AoI(t) = t - u(t)
    ├── Peak AoI Tracking
    └── Time-Integrated Average AoI: (1/T) ∫ AoI(t) dt
             |
             v
[ Delivered to Cloud Digital Twin ]
```

---

## 🕒 2. Timestamps & Delay Definitions

All timing in the network emulation layer uses a deterministic **Logical Simulation Clock (seconds)**:

| Timestamp Field | Definition |
| :--- | :--- |
| `generation_timestamp` | The simulation time ($t$) when the vehicle sensor measured or generated the reading. |
| `queue_entry_timestamp` | The simulation time when the packet entered the transmission buffer queue. |
| `transmission_timestamp` | The simulation time when serialization onto the physical uplink starts. |
| `transmission_completion_timestamp` | The simulation time when serialization finishes ($t_{\text{tx}} + T_{\text{serialization}}$). |
| `scheduled_delivery_timestamp` | The calculated arrival time after wireless channel propagation ($t_{\text{complete}} + \tau_{\text{prop}}$). |
| `reception_timestamp` | The actual time the cloud receiver popped and ingested the packet. |

---

## ⏱️ 3. Age of Information (AoI) Freshness Metrics

$$\text{AoI}_{v, s}(t) = t - u_{v, s}(t)$$

where $u_{v, s}(t) = \max \{ t_{\text{generation}} : \text{valid non-stale update received by time } t \}$.

### Freshness Properties
- **Linear Growth:** When no newer packet arrives, $\text{AoI}(t)$ grows with unit slope ($\frac{d\text{AoI}}{dt} = 1$).
- **Freshness Reset:** Upon arrival of a strictly newer packet ($t_{\text{gen}} > u(t)$), AoI drops to the instantaneous delivery latency ($t_{\text{rx}} - t_{\text{gen}}$).
- **Stale Protection:** Stale and duplicate packets ($t_{\text{gen}} \le u(t)$) do NOT reset the AoI downward.
- **Peak AoI:** The highest age reached right before an update resets the freshness sawtooth curve.
- **Continuous Time-Integrated Average AoI:**
  $$\overline{\text{AoI}} = \frac{1}{T} \int_0^T \text{AoI}(t) \, dt$$

---

## ⚙️ 4. Quickstart & Integration Example

```python
from network import NetworkEmulator, NetworkConfig, DelayConfig, DelayMode, PacketLossConfig, BandwidthConfig
from simulator.vehicle_model import VehicleModel
from simulator.sensor_generator import SensorGenerator
from simulator.fault_injector import FaultInjector, FaultConfig, FaultType

# Configure cellular network with 64 kbps uplink, 10% packet loss, 50-200ms jitter
config = NetworkConfig(
    seed=42,
    delay=DelayConfig(mode=DelayMode.UNIFORM, min_delay_ms=50.0, max_delay_ms=200.0),
    packet_loss=PacketLossConfig(enabled=True, probability=0.10),
    bandwidth=BandwidthConfig(enabled=True, bandwidth_bps=64000.0),
)

emulator = NetworkEmulator(config=config)
vehicle = VehicleModel()
injector = FaultInjector(FaultConfig(fault_type=FaultType.NORMAL))
sensor_gen = SensorGenerator(random_seed=42)

# Step simulation and stream through network emulator
for step in range(30):
    t = float(step)
    state = vehicle.step(dt_seconds=1.0)
    telemetry = sensor_gen.generate(state, injector)
    
    # 1. Ingest into cellular emulator
    emulator.ingest_telemetry_frame(telemetry, current_time=t)
    
    # 2. Extract delivered packets at cloud receiver
    delivered_packets = emulator.advance_time(current_time=t + 0.1)
    
    # 3. Query telemetry freshness
    aoi_temp = emulator.get_current_aoi("EV_001", "engine_temperature_c", current_time=t + 0.1)
```
