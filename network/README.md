# Network Impairment & Telemetry Pipeline (`network/`)

This package provides a high-fidelity, configurable communication layer that simulates real-world wireless and cellular channel degradation between connected vehicle ECUs and the cloud Digital Twin backend.

---

## 📡 1. End-to-End Packet Lifecycle & Pipeline Flow

```
[ Vehicle Telemetry Observation (generation_timestamp) ]
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

## ⚙️ 4. Configuration Reference

```python
from network import (
    NetworkConfig,
    DelayConfig,
    DelayMode,
    PacketLossConfig,
    OrderingConfig,
    OrderingPolicy,
    BandwidthConfig,
    QuotaAction,
    PacketQueue,
)

# Example: Configure cellular link with 64 kbps uplink, 10% packet loss, 50-200ms uniform jitter, and byte quota
config = NetworkConfig(
    seed=42,
    delay=DelayConfig(
        mode=DelayMode.UNIFORM,
        min_delay_ms=50.0,
        max_delay_ms=200.0,
    ),
    packet_loss=PacketLossConfig(
        enabled=True,
        probability=0.10,
    ),
    ordering=OrderingConfig(
        policy=OrderingPolicy.TIMESTAMP_AWARE,
        reject_stale=False,
    ),
    bandwidth=BandwidthConfig(
        enabled=True,
        bandwidth_bps=64000.0, # 64 kbps
        quota_bytes=5000,      # 5 KB per window
        quota_window_seconds=10.0,
        quota_action=QuotaAction.DELAY_TO_NEXT_WINDOW,
    ),
)

queue = PacketQueue(config=config)
```
