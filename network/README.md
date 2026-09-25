# Network Impairment & Telemetry Pipeline (`network/`)

This package provides a high-fidelity, configurable communication layer that simulates real-world wireless and cellular channel degradation between connected vehicle ECUs and the cloud Digital Twin backend.

---

## 📡 1. Packet Lifecycle & Pipeline Flow

```
[ Vehicle Telemetry Packet ]
             |
             v
[ Packet Loss Evaluation ] ──(Dropped)──> [ Dropped Packets Log (Status: DROPPED) ]
             |
          (Passed)
             |
             v
[ Stochastic Latency Model ] (tau ~ Fixed / Uniform / Gaussian)
             |
             v
[ In-Transit Priority Queue ] (Min-Heap keyed by scheduled delivery timestamp)
             |
   (advance_time(t))
             |
             v
[ Arrival Stream Extraction ] (Arrival-order delivery sequence)
             |
             v
[ Packet Ordering Tracker ]
    ├── Out-of-Order Detection
    ├── Stale Telemetry Flagging (Generation Timestamp < Latest Processed)
    └── Duplicate Detection
             |
             v
[ Delivered to Cloud Digital Twin ]
```

---

## 🕒 2. Timestamps & Clock Definitions

All timing in the network emulation layer is tracked using a deterministic **Logical Simulation Clock (seconds)**:

| Timestamp Field | Definition |
| :--- | :--- |
| `generation_timestamp` | The simulation time ($t$) when the vehicle sensor measured or generated the reading. |
| `transmission_timestamp` | The simulation time when the packet left the vehicle's onboard transmission buffer. |
| `scheduled_delivery_timestamp` | The calculated arrival time ($t_{\text{tx}} + \tau_{\text{delay}}$) when the packet will reach the cloud receiver. |
| `reception_timestamp` | The actual time the cloud receiver popped and ingested the packet. |

---

## 🔀 3. Out-of-Order & Stale Telemetry Definitions

When packets experience variable latency (jitter), later generated packets may arrive at the receiver before earlier generated packets:

- **In-Sequence Packet:** $t_{\text{gen}} \ge t_{\text{last\_gen}}$ and $\text{seq} > \text{seq}_{\text{last}}$.
- **Out-of-Order Packet:** Arrives with a sequence number lower than the most recently received packet ($\text{seq} < \text{seq}_{\text{last}}$).
- **Stale Packet:** Arrives with an older generation timestamp than the latest accepted update for that specific sensor stream ($t_{\text{gen}} < t_{\text{last\_gen}}$).
- **Duplicate Packet:** Arrives with an already-observed packet ID or sequence number.

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
    PacketQueue,
)

# Example: Configure cellular link with 10% packet loss and 50-200ms uniform jitter
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
)

queue = PacketQueue(config=config)
```
