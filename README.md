# Cloud-Based Digital Twin for Connected Vehicle Diagnostics & Performance Analytics

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-171%20Passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Code%20Style](https://img.shields.io/badge/Code%20Style-PEP8-black.svg)]()

> **Proposed Research Direction:** *Uncertainty- and Cost-Aware Active Digital Twin for Connected Vehicle Diagnostics Under Intermittent Connectivity*

---

## 📑 Table of Contents

1. [Project Overview & Research Motivation](#-1-project-overview--research-motivation)
2. [End-to-End System Architecture](#-2-end-to-end-system-architecture)
3. [Physical Powertrain & Thermal Vehicle Simulator (`simulator/`)](#-3-physical-powertrain--thermal-vehicle-simulator-simulator)
4. [Wireless Network Impairment & AoI Freshness Layer (`network/`)](#-4-wireless-network-impairment--aoi-freshness-layer-network)
5. [Cloud Digital Twin Backend & Diagnostic Engine (`digital_twin/`)](#-5-cloud-digital-twin-backend--diagnostic-engine-digital_twin)
6. [Experimental Benchmark Campaigns & Empirical Results (`experiments/`)](#-6-experimental-benchmark-campaigns--empirical-results-experiments)
7. [Interactive Engineering Cockpits & Dashboards (`dashboard/`, `app.py`)](#-7-interactive-engineering-cockpits--dashboards-dashboard-apppy)
8. [Installation & Execution Guide](#-8-installation--execution-guide)
9. [Automated Test Suite & Verification](#-9-automated-test-suite--verification)
10. [Repository Directory Structure](#-10-repository-directory-structure)
11. [Research Roadmap](#-11-research-roadmap)

---

## 📌 1. Project Overview & Research Motivation

Modern connected vehicles operate in dynamic, non-stationary wireless environments characterized by intermittent cellular connectivity, variable latency ($\tau \in [10, 600]\text{ ms}$), stochastic packet dropouts ($p_{\text{loss}} \in [0\%, 50\%]$), and constrained uplink telemetry bandwidth. When anomalous conditions arise (such as rising engine temperatures), conventional diagnostic frameworks face critical limitations:

1. **Static Threshold Diagnostic Alerts (OBD-II style):** Trigger frequent false alarms during transient vehicle load spikes and cannot adapt to delayed or missing telemetry frames.
2. **Passive Telemetry Ingestion (Traditional Digital Twins):** Struggle to isolate root causes when distinct physical faults produce identical passive symptoms (for example, cooling fan actuator relay failure vs. coolant fluid leak vs. temperature sensor calibration bias vs. transient engine overload).
3. **Transport Channel Ambiguity:** When observations are delayed or missing, conventional systems cannot discern whether silence is caused by cellular signal fade or an onboard hardware bus failure.

### The Proposed Solution

This project develops an **Uncertainty- and Cost-Aware Active Digital Twin (ADT)** system that:
- **Separates Communication Impairments from Vehicle Faults:** Uses continuous Age-of-Information (AoI) freshness tracking to qualify whether telemetry is fresh enough for diagnostic inference. Stale observations are marked `NOT_EVALUATED`, preventing false alarms during wireless dropouts.
- **Physics-Informed Nominal State Mirroring:** Solves coupled continuous-time powertrain and thermal differential equations in the cloud to predict expected vehicle states in real time.
- **Persistence-Gated Residual Generation:** Evaluates raw, relative, and categorical discrepancy metrics $r(t) = y_{\text{obs}}(t) - \hat{y}(t)$, applying consecutive sample persistence ($N = 3$) to eliminate transient noise and jitter.
- **Empirical Benchmarking & Validation:** Validated across a 93-experiment research campaign sweeping packet loss, latency, jitter, and fault severity, achieving a **91.80% empirical packet delivery ratio**, **0.1672s mean AoI**, **93.3% fault detection rate**, and **0.0% false alarm rate** across healthy baseline driving.

---

## 🏛️ 2. End-to-End System Architecture

The architecture decouples the physical vehicle from the communication channel and cloud diagnostic reasoning engine:

```
+---------------------------------------------------------------------------------------------------+
|                                 CONNECTED VEHICLE SIMULATOR (EDGE / VEHICLE)                      |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
|  | Multi-Physics Powertrain  |   | Fault Injection Engine     |   | Onboard Telemetry / ECU    |  |
|  | - Thermal (Engine/Coolant)|   | - Normal operation         |   | - Periodic Low-Rate Sync   |  |
|  | - Speed & RPM Kinematics  |   | - Cooling fan failure      |   | - Gaussian Sensor Noise    |  |
|  | - Dynamic Engine Load     |   | - Temp sensor bias/freeze  |   | - Standard Telemetry JSON  |  |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
                      +-------------------------------------------------------+
                      |             INTERMITTENT NETWORK EMULATOR             |
                      | - Stochastic Latency / Jitter (tau ~ Fixed/Gauss/Uni) |
                      | - Bernoulli Packet Loss Probability (p_loss)          |
                      | - Priority Queue & Bandwidth Quotas (B_limit)         |
                      | - Continuous Age-of-Information (AoI) Freshness       |
                      +---------------------------+---------------------------+
                                                  |
                                                  v
+-------------------------------------------------+-------------------------------------------------+
|                                    CLOUD DIGITAL TWIN BACKEND                                     |
|  +----------------------------+   +-----------------------------+   +--------------------------+  |
|  | Ingestion & Buffer Engine  |   | Physics-Informed State Twin |   | Residual & Freshness     |  |
|  | - Out-of-Order Rejection   |   | - Nominal expected behavior |   | - Residual: r = y - y^   |  |
|  | - Duplicate Detection      |   | - Energy balance equations  |   | - Defensive relative r   |  |
|  | - Chronological Sorting    |   | - Thermostat hysteresis     |   | - Freshness: FRESH/STALE |  |
|  +----------------------------+   +-----------------------------+   +--------------------------+  |
|                                                  |                                                |
|                                                  v                                                |
|                               +-------------------------------------+                             |
|                               |      BASELINE ANOMALY DETECTOR      |                             |
|                               | - Two-Level Physical Thresholds     |                             |
|                               | - Categorical Fan Actuator Mismatch |                             |
|                               | - Alert Persistence Gating (N = 3)  |                             |
|                               +-------------------------------------+                             |
+--------------------------------------------------+------------------------------------------------+
                                                   |
                                                   v
+--------------------------------------------------+------------------------------------------------+
|                         INTERACTIVE VISUALIZATION & ANALYTICS COCKPITS                            |
|  +-------------------------------------------------+   +---------------------------------------+  |
|  | Streamlit Research Cockpit (app.py :8501)       |   | HTML5 Telemetry Cockpit (server.py)   |  |
|  | - Live Gauges, Thermal Residual Curves, Sliders |   | - Fast SVG Instruments, WebSockets    |  |
|  | - Scenario Injections, Campaign Data Explorer   |   | - Port 8050, Glassmorphic UI          |  |
|  +-------------------------------------------------+   +---------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

---

## 🚗 3. Physical Powertrain & Thermal Vehicle Simulator (`simulator/`)

The vehicle simulation layer advances physical state variables over discrete intervals ($\Delta t = 0.1\text{ s}$, $10\text{ Hz}$ sampling rate).

### 3.1 Kinematics & Driving Profiles
Velocity follows dynamic urban and highway cycles with natural acceleration/deceleration:
$$v(t) = 52.0 + 18.0 \sin\left(\frac{t}{8.0}\right) + 6.0 \cos\left(\frac{t}{3.0}\right) \quad [\text{km/h}]$$
$$\text{RPM}(t) = 1900.0 + \left(\frac{v(t)}{100.0}\right) \cdot 1600.0$$
$$\text{Load}(t) = \max\left(0.20, \, \min\left(0.95, \, 0.45 + 0.25 \sin\left(\frac{t}{6.0}\right)\right)\right)$$

### 3.2 Dynamic Thermal Differential Equations
Engine temperature is governed by continuous-time thermal energy conservation:
$$\frac{dT_{\text{eng}}}{dt} = \frac{\dot{Q}_{\text{in}} - \dot{Q}_{\text{out}}}{C_{\text{thermal}}}$$

Where:
- $C_{\text{thermal}} = 4500.0\text{ J/}^\circ\text{C}$ is the lumped heat capacity of the engine block and coolant.
- **Heat Generation Rate ($\dot{Q}_{\text{in}}$):**
  $$\dot{Q}_{\text{in}} = (k_{\text{base}} + k_{\text{load}} \cdot \text{Load}) \cdot \left(\frac{\text{RPM}}{1000.0}\right)$$
  with baseline generation $k_{\text{base}} = 180.0\text{ W}$ and load coefficient $k_{\text{load}} = 650.0\text{ W}$.
- **Heat Dissipation Rate ($\dot{Q}_{\text{out}}$):**
  $$\dot{Q}_{\text{out}} = (k_{\text{nat}} + k_{\text{speed}} \cdot v + k_{\text{fan}} \cdot F) \cdot (T_{\text{eng}} - T_{\text{ambient}})$$
  with natural convection $k_{\text{nat}} = 12.0\text{ W/}^\circ\text{C}$, airspeed convection $k_{\text{speed}} = 0.8\text{ W/(km/h}\cdot^\circ\text{C})$, fan cooling $k_{\text{fan}} = 45.0\text{ W/}^\circ\text{C}$, and ambient temperature $T_{\text{ambient}} = 25.0^\circ\text{C}$.
- **ECU Thermostat Cooling Fan Relay Hysteresis:**
  $$F(t) = \begin{cases} 1, & \text{if } T_{\text{eng}} \ge 95.0^\circ\text{C} \quad (\text{Fan ON}) \\ 0, & \text{if } T_{\text{eng}} \le 90.0^\circ\text{C} \quad (\text{Fan OFF}) \\ F(t-\Delta t), & \text{if } 90.0^\circ\text{C} < T_{\text{eng}} < 95.0^\circ\text{C} \quad (\text{Hold State}) \end{cases}$$

### 3.3 Fault Injection Engine (`simulator/fault_injector.py`)
Supports parameterized, time-scheduled fault modes:
- `NORMAL`: Healthy vehicle operation.
- `HIGH_LOAD`: Engine overload profile locking engine load to $0.95$ and increasing RPM ($+800$).
- `FAN_FAILURE`: Actuator relay failure forcing $F(t) = 0$ regardless of thermostat command, disabling forced convection.
- `TEMP_SENSOR_BIAS`: Calibration drift adding offset $\Delta T_{\text{bias}}$ (default $+15.0^\circ\text{C}$) to sensed telemetry.
- `TEMP_SENSOR_FREEZE`: Sensor locks output to the initial observed temperature reading.
- `MISSING_SENSOR_DATA`: Emulates sensor bus disconnections by dropping telemetry fields (`None`).

### 3.4 Standard Telemetry Schema
```json
{
  "vehicle_id": "EV_001",
  "timestamp": "2026-10-29T10:00:00Z",
  "speed_kmh": 45.0,
  "rpm": 2200.0,
  "engine_load": 0.62,
  "engine_temperature_c": 92.4,
  "cooling_fan_status": 1,
  "fault_status": "normal"
}
```

---

## 📡 4. Wireless Network Impairment & AoI Freshness Layer (`network/`)

The communication layer emulates cellular link degradation between vehicle onboard ECUs and the cloud Digital Twin.

### 4.1 Packet Lifecycle & Queue Processing
```
[ Telemetry Frame Generated (t_gen) ]
                 │
                 ▼
[ NetworkEmulator.ingest_telemetry_frame() ]
  ├── Split into individual sensor packets (speed, RPM, load, temp, fan)
  └── Assign monotonic sequence numbers
                 │
                 ▼
[ Packet Loss Evaluation ] ────(Dropped)────> [ Dropped Packets Log ]
                 │
              (Passed)
                 │
                 ▼
[ Priority Uplink Transmission Scheduler ]
  ├── Serialization Delay: T_ser = (size_bytes * 8) / bandwidth_bps
  ├── Channel Locking: tx_start = max(t_now, link_busy_until)
  └── Quota Verification: check_quota(size_bytes, window)
                 │
                 ▼
[ Propagation Delay Engine ] (tau ~ Fixed / Uniform / Gaussian)
  └── scheduled_delivery = tx_start + T_ser + tau
                 │
                 ▼
[ In-Transit Min-Heap Priority Queue ] (Keyed by scheduled delivery timestamp)
                 │
                 ▼ (advance_time(current_time))
[ Cloud Arrival Stream Extraction ]
  ├── Out-of-Order Detection & Sorting
  ├── Duplicate Rejection
  └── Age-of-Information Freshness Evaluation
                 │
                 ▼
[ Ingested into Cloud Digital Twin ]
```

### 4.2 Timestamps & Latency Definitions
All timing operates on a deterministic **Logical Simulation Clock (seconds)**:
- `generation_timestamp`: Simulation time $t_{\text{gen}}$ when the vehicle measured the reading.
- `queue_entry_timestamp`: Time packet entered the edge transmission queue.
- `transmission_timestamp`: Time serialization started on the wireless uplink.
- `transmission_completion_timestamp`: Time serialization finished ($t_{\text{tx}} + T_{\text{ser}}$).
- `scheduled_delivery_timestamp`: Calculated cloud arrival instant ($t_{\text{complete}} + \tau$).
- `reception_timestamp`: Actual time cloud receiver popped and ingested the packet.

### 4.3 Age of Information (AoI) Sawtooth Formulation
Age of Information quantifies receiver-side data staleness:
$$\text{AoI}_s(t) = t - u_s(t)$$
where $u_s(t) = \max \{ t_{\text{gen}} : \text{valid non-stale update received for sensor } s \text{ by time } t \}$.

- **Linear Aging:** In the absence of new arrivals, $\text{AoI}(t)$ increases with unit slope: $\frac{d\text{AoI}}{dt} = 1$.
- **Freshness Reset:** Arrival of a strictly newer packet ($t_{\text{gen}} > u_s(t)$) resets AoI down to the instantaneous delivery delay ($t_{\text{recv}} - t_{\text{gen}}$).
- **Stale Protection:** Stale and duplicate packets ($t_{\text{gen}} \le u_s(t)$) do **not** reset the AoI downward.
- **Continuous Time-Integrated Average AoI:**
  $$\overline{\text{AoI}}_s = \frac{1}{T} \int_0^T \text{AoI}_s(t) \, dt = \frac{1}{T} \sum_{i=1}^M \frac{1}{2} \left[ \text{AoI}_s(t_{i-1}^+) + \text{AoI}_s(t_i^-) \right] \Delta t_i$$

---

## ☁️ 5. Cloud Digital Twin Backend & Diagnostic Engine (`digital_twin/`)

The cloud backend mirrors physical vehicle dynamics, evaluates residuals, qualifies data freshness, and detects anomalies without ML-induced opacity.

### 5.1 Physics-Informed Nominal State Model (`nominal_model.py`)
Predicts expected vehicle state transitions forward in time:
$$\hat{x}_{k+1} = f(\hat{x}_k, u_k, \Delta t)$$
$$\hat{y}_k = g(\hat{x}_k, u_k)$$
Solving the identical baseline energy balance in the cloud to reconstruct nominal temperatures $\hat{T}(t)$ and fan actuation states $\hat{F}(t)$.

### 5.2 Residual Generation Policies (`residual_generator.py`)
Discrepancies are evaluated across all active channels:
1. **Raw Residual:** $r_k = y_k - \hat{y}_k$
2. **Absolute Residual:** $|r_k| = |y_k - \hat{y}_k|$
3. **Defensive Relative Residual:**
   $$r_{\text{rel}, k} = \frac{y_k - \hat{y}_k}{\max(|\hat{y}_k|, \epsilon)}$$
   where $\epsilon = 10^{-4}$ prevents division-by-zero during vehicle standstill ($\hat{y}_k = 0$).

### 5.3 Telemetry Freshness States (`telemetry_freshness.py`)
- **`FRESH` ($0 \le \text{AoI} \le 1.0\text{ s}$):** Trustworthy for immediate diagnostic evaluation.
- **`AGING` ($1.0\text{ s} < \text{AoI} \le 3.0\text{ s}$):** Conditionally accepted with warning qualification.
- **`STALE` ($\text{AoI} > 3.0\text{ s}$):** Ineligible for fresh diagnostic evaluation; holds last known valid state.
- **`INVALID`:** Contains $\text{NaN}$, $\pm\infty$, or causality violations ($\text{AoI} < 0$).
- **`MISSING`:** Telemetry packet dropped or lost in transmission.

### 5.4 Baseline Anomaly Detector & Persistence Tracking (`anomaly_detector.py`)
- **Two-Level Engineering Thresholds:**
  | Signal | Physical Unit | Warning Threshold | Anomaly Threshold | Relative Warning | Relative Anomaly |
  | :--- | :--- | :--- | :--- | :--- | :--- |
  | `speed_kmh` | $\text{km/h}$ | $8.0\text{ km/h}$ | $12.0\text{ km/h}$ | $15\%$ | $25\%$ |
  | `rpm` | $\text{RPM}$ | $200.0\text{ RPM}$ | $350.0\text{ RPM}$ | $10\%$ | $18\%$ |
  | `engine_load` | $\text{ratio}$ | $0.12$ ($12\%$) | $0.20$ ($20\%$) | N/A | N/A |
  | `engine_temperature_c` | $^\circ\text{C}$ | $5.0^\circ\text{C}$ | $8.0^\circ\text{C}$ | $6\%$ | $10\%$ |
  | `cooling_fan_status` | $\text{discrete}$ | $|r| > 0$ | $|r| > 0.5$ (Mismatch) | N/A | N/A |
- **Categorical Actuator Mismatch:** If the nominal model expects the fan to be running ($\hat{F} = 1$) but telemetry reports $F_{\text{obs}} = 0$, an immediate actuator relay fault is flagged.
- **Deterministic Persistence Gating:** To prevent transient jitter spikes from causing false alarms, an anomaly is only confirmed when:
  $$C_{\text{consecutive}} \ge N_{\text{persist}} = 3\text{ evaluation cycles}$$
  A single nominal sample immediately resets the persistence counter to zero.

---

## 📊 6. Experimental Benchmark Campaigns & Empirical Results (`experiments/`)

The repository contains extensive benchmark evaluations with pre-computed results stored in `experiments/results/`.

### 6.1 Research Variables
- **Independent Variables:** Packet loss rate ($0\%$ to $50\%$), network delay ($10\text{ ms}$ to $600\text{ ms}$), latency jitter ($0\text{ ms}$ to $250\text{ ms}$), sensor bias offset ($+5^\circ\text{C}$ to $+20^\circ\text{C}$), random seeds (`42`, `101`, `202`).
- **Controlled Variables:** Engine thermal capacitance ($4500\text{ J/}^\circ\text{C}$), baseline threshold bounds, simulation step size ($\Delta t = 0.1\text{ s}$).
- **Dependent Variables:** Empirical packet delivery ratio (PDR), mean/peak AoI, false alarm count, detection delay ($\Delta t_{\text{detect}}$).

### 6.2 Standard Experiment Groups (93 Campaign Runs)
The 93-experiment research campaign (`experiments/results/campaign_all_results.csv`) sweeps 8 distinct groups:
1. `baseline` (3 runs): Healthy operation, minimal 10ms latency.
2. `packet_loss_sweep` (15 runs): Loss swept from 0% to 50%.
3. `delay_sweep` (15 runs): Cellular latency swept from 10ms to 600ms.
4. `jitter_sweep` (15 runs): Latency jitter with mean 100-175ms.
5. `fault_severity_sweep` (12 runs): Sensor bias offsets from 0°C to +30°C.
6. `fault_packet_loss` (15 runs): Sensor bias evaluated under 0% to 50% packet loss.
7. `fault_delay` (15 runs): Sensor bias evaluated across 10ms to 600ms latency.
8. `combined_impairment` (3 runs): Stress test ($+15^\circ\text{C}$ bias, 25% loss, $80\text{ ms}$ delay).

### 6.3 Quantitative Benchmark Findings
- **Total Telemetry Packets Evaluated:** 92,315 packets (84,749 delivered, 7,566 dropped).
- **Empirical Packet Delivery Ratio (PDR):** **$91.80\%$**.
- **Mean Age of Information (AoI):** **$0.1672\text{ seconds}$** (ranging from $0.1000\text{ s}$ to $0.6000\text{ s}$).
- **Fault Detection Success Rate:** **$93.3\%$** ($42 / 45$ faulted runs confirmed; 3 sub-threshold runs remained within nominal noise bounds).
- **False Alarm Rate:** **$0.0\%$** ($0 / 48$ healthy runs triggered false alerts).

### 6.4 40.0-Second Controlled Fault Experiment Evidence
A dedicated 40.0-second controlled comparison ($\Delta t = 0.1\text{ s}$, 400 steps) was executed starting at warm operating temperature ($T_0 = 95.0^\circ\text{C}$) via `digital_twin/run_controlled_experiment.py`:

| Evaluated Metric | Normal Operation (Healthy) | Cooling Fan Failure (Faulted) | Physical & Diagnostic Outcome |
| :--- | :--- | :--- | :--- |
| **Initial Temp ($T_0$)** | $95.00^\circ\text{C}$ | $95.00^\circ\text{C}$ | Identical initial state |
| **Final Temp ($T_{40\text{s}}$)** | $94.75^\circ\text{C}$ | $100.40^\circ\text{C}$ | **$+5.65^\circ\text{C}$ excess temperature rise** |
| **Mean Operating Temp** | $95.33^\circ\text{C}$ | $98.20^\circ\text{C}$ | Steady dissipation vs heat accumulation |
| **Final Thermal Residual** | $-0.005^\circ\text{C}$ | **$+5.660^\circ\text{C}$** | Escalates past anomaly threshold |
| **Cooling Fan ON Ratio** | $100.0\%$ (ECU ON) | $0.0\%$ (Relay stuck OFF) | Thermostat hysteresis engaged vs disabled |
| **First Confirmed Detection** | None (Clean) | **$t = 0.50\text{ s}$** | Immediate confirmation ($N \ge 3$ cycles) |
| **Confirmed Anomaly Steps** | **0 / 400 steps** | **396 / 400 steps** | Zero false alarms in normal driving |

---

## 🎛️ 7. Interactive Engineering Cockpits & Dashboards (`dashboard/`, `app.py`)

The project provides dual visualization interfaces:

### 7.1 Primary Streamlit Research Cockpit (`app.py`)
- **Port:** `http://localhost:8501`
- **Features:**
  - Real-time Plotly charts for vehicle kinematics, thermal dynamics, and residual escalation.
  - Interactive scenario selection (Normal, High Load, Fan Failure, Sensor Bias, Sensor Freeze).
  - Thermal State on Reset controls: Cold Start ($85.0^\circ\text{C}$) vs Warm Operating Temp ($95.0^\circ\text{C}$).
  - Live network impairment sliders (packet loss rate, delay mode, fixed/Gaussian latency).
  - Research Campaign Explorer tab: Filters, plots, and exports the 93-experiment benchmark dataset.
  - Windows 1-click launcher: `run_dashboard.bat`.

### 7.2 Standalone HTML5 Telemetry Cockpit (`dashboard/server.py`)
- **Port:** `http://localhost:8050`
- **Features:**
  - Lightweight, high-refresh SVG circular physics gauges (Speed, RPM, Temp).
  - Glassmorphic CSS styling with real-time step controls and live alert log feed.
  - Zero external web framework dependencies (built with Python `ThreadingHTTPServer`).
  - Windows 1-click launcher: `run_cockpit.bat`.

---

## ⚙️ 8. Installation & Execution Guide

### 8.1 Setup Environment
```bash
# Clone the repository
git clone https://github.com/annu-creator24t/Capstone-Project.git
cd Capstone-Project

# Create and activate virtual environment
python -m venv venv

# Windows PowerShell:
venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 8.2 Launch Dashboards
```bash
# Option A: Primary Streamlit Dashboard (Port 8501)
python -m streamlit run app.py
# Or double-click: run_dashboard.bat

# Option B: High-Speed Telemetry Cockpit (Port 8050)
python dashboard/server.py --port 8050
# Or double-click: run_cockpit.bat
```

### 8.3 Run Headless Simulator Scenarios
```bash
# 30-second normal driving scenario
python -m simulator.main --scenario normal --duration 30

# Fan failure scenario injected at t=10s
python -m simulator.main --scenario fan_failure --start-time 10 --duration 45

# Temperature sensor bias scenario (+20°C offset)
python -m simulator.main --scenario temp_sensor_bias --start-time 10 --bias-offset 20.0
```

### 8.4 Execute Benchmark Campaigns via CLI
```bash
# Run full 93-experiment research campaign
python -m digital_twin.run_experiments --all

# Run specific sweep (e.g. packet loss sweep)
python -m digital_twin.run_experiments --group packet_loss --seeds 42 101 202

# Run 40-second controlled comparison experiment
python -m digital_twin.run_controlled_experiment
```

---

## 🧪 9. Automated Test Suite & Verification

The repository maintains an automated test harness with **171 unit and integration tests** covering vehicle dynamics, network emulation, Age of Information, digital twin estimation, and dashboard managers:

```bash
python -m pytest
```

### Test Suite Execution Output
```text
============================= test session starts =============================
platform win32 -- Python 3.10.0, pytest-8.4.1, pluggy-1.6.0
rootdir: C:\Users\ANNU TIWARI\Desktop\Capstone project
plugins: anyio-4.12.1, asyncio-1.2.0, cov-6.3.0
collected 171 items

tests\test_dashboard_manager.py .......                                  [  4%]
tests\test_digital_twin\test_anomaly_detector.py ....................... [ 17%]
........                                                                 [ 22%]
tests\test_digital_twin\test_evaluation.py ...............               [ 30%]
tests\test_digital_twin\test_experiments.py .................            [ 40%]
tests\test_digital_twin\test_models.py .......                           [ 45%]
tests\test_digital_twin\test_nominal_model.py ........                   [ 49%]
tests\test_digital_twin\test_residual_generator.py ........              [ 54%]
tests\test_digital_twin\test_state_estimator.py .......                  [ 58%]
tests\test_digital_twin\test_telemetry_freshness.py .................... [ 70%]
..                                                                       [ 71%]
tests\test_network\test_aoi_tracker.py .......                           [ 75%]
tests\test_network\test_bandwidth_model.py ....                          [ 77%]
tests\test_network\test_delay_model.py .....                             [ 80%]
tests\test_network\test_network_emulator.py ...                          [ 82%]
tests\test_network\test_packet_loss.py ..........                        [ 88%]
tests\test_network\test_packet_ordering.py .....                         [ 91%]
tests\test_network\test_packet_queue.py ....                             [ 93%]
tests\test_network\test_transmission_scheduler.py .....                  [ 96%]
tests\test_simulator.py ......                                           [100%]

============================= 171 passed in 1.47s =============================
```

---

## 📁 10. Repository Directory Structure

```text
Capstone-Project/
├── .env.example                            # Template configuration environment variables
├── .gitignore                              # Comprehensive secret & build ignore rules
├── app.py                                  # Primary Streamlit Research Analytics Dashboard (Port 8501)
├── README.md                               # Authoritative master project documentation
├── requirements.txt                        # Pinned dependencies (Pydantic, NumPy, Pandas, Streamlit, etc.)
├── run_cockpit.bat                         # 1-Click launcher for HTML5 Telemetry Cockpit
├── run_dashboard.bat                       # 1-Click launcher for Streamlit Analytics Cockpit
│
├── dashboard/                              # High-speed telemetry web cockpit
│   ├── app.js                              # Responsive UI controls & telemetry gauge rendering
│   ├── index.html                          # Glassmorphic cockpit layout
│   ├── server.py                           # Python HTTP server providing REST API (Port 8050)
│   ├── simulation_manager.py               # Closed-loop session manager driving live dashboards
│   └── style.css                           # Modern engineering styling & responsive instruments
│
├── digital_twin/                           # Cloud Digital Twin diagnostic engine
│   ├── __init__.py                         # Module exports
│   ├── anomaly_detector.py                 # Baseline two-level anomaly detector & persistence counter
│   ├── evaluation.py                       # Stage 4D diagnostic evaluation runner (Scenarios A-G)
│   ├── experiment_config.py                # Typed experiment matrix configuration schemas
│   ├── experiment_runner.py                # Batch campaign runner & CSV/JSON exporter
│   ├── models.py                           # Dataclasses (DigitalTwinState, SensorResidual, etc.)
│   ├── nominal_model.py                    # Physics-informed nominal powertrain & thermal model
│   ├── residual_generator.py               # Raw, absolute, and defensive relative residual calculator
│   ├── run_controlled_experiment.py        # Reproducible 40s controlled comparison runner
│   ├── run_experiments.py                  # CLI runner for parameter sweep campaigns
│   ├── state_estimator.py                  # Telemetry ingestion, chronologic ordering & buffering
│   ├── telemetry_freshness.py              # Freshness evaluator (FRESH, AGING, STALE, MISSING)
│   └── twin_config.py                      # Master Digital Twin configuration & signal thresholds
│
├── experiments/                            # Experimental campaign data & manifests
│   ├── experiment_manifest.json            # Declarative execution manifest
│   └── results/                            # Pre-computed empirical campaign datasets
│       ├── campaign_all_results.csv        # Complete 93-experiment tabular benchmark dataset
│       ├── campaign_all_results.json       # Full structured JSON results with residual maps
│       ├── controlled_fault_experiment.csv # 40s controlled cooling fan comparison dataset
│       └── controlled_fault_experiment.json# Summary metrics for controlled comparison
│
├── network/                                # Wireless network impairment emulation layer
│   ├── __init__.py                         # Module exports
│   ├── aoi_tracker.py                      # Continuous sawtooth Age-of-Information (AoI) engine
│   ├── bandwidth_model.py                  # Telemetry serialization delay & bandwidth throttling
│   ├── delay_model.py                      # Stochastic propagation latency (Fixed, Uniform, Gaussian)
│   ├── models.py                           # Dataclasses (NetworkPacket, QueueState, StreamStatistics)
│   ├── network_config.py                   # Master network configuration schema
│   ├── network_emulator.py                 # Top-level network emulator orchestrator
│   ├── packet_loss.py                      # Bernoulli packet loss engine
│   ├── packet_ordering.py                  # Duplicate detection & out-of-order arrival tracker
│   ├── packet_queue.py                     # Priority queue with min-heap scheduling
│   └── transmission_scheduler.py           # Single-channel FIFO uplink serialization scheduler
│
├── simulator/                              # Physical vehicle powertrain & fault simulation
│   ├── __init__.py                         # Module exports
│   ├── fault_injector.py                   # Fault scheduling & parameter injection engine
│   ├── main.py                             # CLI entrypoint for running standalone simulations
│   ├── sensor_generator.py                 # Gaussian noise generator producing JSON telemetry
│   └── vehicle_model.py                    # Dynamic thermal ODE & speed kinematics model
│
└── tests/                                  # Comprehensive automated test suite (171 tests)
    ├── test_dashboard_manager.py           # Dashboard simulation session manager unit tests
    ├── test_simulator.py                   # Vehicle model & fault injector unit tests
    ├── test_digital_twin/                  # Digital twin diagnostic engine tests
    │   ├── test_anomaly_detector.py        # Anomaly threshold & persistence tests
    │   ├── test_evaluation.py              # Scenario A-G evaluation pipeline tests
    │   ├── test_experiments.py             # Campaign execution & controlled experiment tests
    │   ├── test_models.py                  # Dataclass serialization & state tests
    │   ├── test_nominal_model.py           # Physics ODE forward prediction tests
    │   ├── test_residual_generator.py      # Residual calculation & zero-guard tests
    │   ├── test_state_estimator.py         # Packet ingestion & sync state tests
    │   └── test_telemetry_freshness.py     # AoI freshness classification tests
    └── test_network/                       # Network emulator subsystem tests
        ├── test_aoi_tracker.py             # AoI trapezoidal integration & reset tests
        ├── test_bandwidth_model.py         # Bandwidth throttling & quota tests
        ├── test_delay_model.py             # Propagation delay profile tests
        ├── test_network_emulator.py        # End-to-end network transmission tests
        ├── test_packet_loss.py             # Bernoulli packet drop tests
        ├── test_packet_ordering.py         # Out-of-order & duplicate packet tests
        ├── test_packet_queue.py            # Min-heap priority scheduling tests
        └── test_transmission_scheduler.py  # Uplink FIFO serialization tests
```

---

## 🗺️ 11. Research Roadmap

- [x] **Phase 1:** Repository Initialization & Module 1 (Vehicle Simulator & Fault Injection Core)
- [x] **Phase 2:** Module 2 — Intermittent Network Emulator (Delay, Loss, Priority Queues, Bandwidth, AoI tracking)
- [x] **Phase 3:** Module 3 — Cloud Digital Twin State Estimator & Residual Generator
- [x] **Phase 4:** Module 7 — Interactive Web Analytics Dashboard (Streamlit & HTML5 Cockpits)
- [x] **Phase 5:** Empirical Benchmark Campaign Suite (8 Groups, 93 Replicates, Controlled 40s Fault Experiment)
- [ ] **Phase 6:** Module 4 — Multi-Hypothesis Bayesian Fault Belief Tracker ($b_k(H_i)$)
- [ ] **Phase 7:** Module 5 — Uncertainty- and Cost-Aware Active Diagnostic Decision Engine (Value of Information)
- [ ] **Phase 8:** Module 6 — Comparative Benchmark Suite (Static Threshold vs Passive Twin vs Active Digital Twin)
- [ ] **Phase 9:** Academic Manuscript & Patentability Comparison Dossier

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
