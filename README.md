# Cloud-Based Digital Twin for Connected Vehicle Diagnostics & Performance Analytics

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

> **Proposed Research Direction:** *Uncertainty- and Cost-Aware Active Digital Twin for Connected Vehicle Diagnostics Under Intermittent Connectivity*

---

## 📌 1. Project Overview

Modern connected vehicles operate in dynamic environments characterized by intermittent cellular connectivity, variable network latency, packet loss, and constrained telemetry bandwidth. When anomalous conditions occur (such as rising engine temperatures), conventional diagnostics either rely on static threshold alerts (causing high false alarm rates) or passive telemetry ingestion (struggling to isolate root causes when multiple faults produce identical passive symptoms).

This project develops an **Uncertainty- and Cost-Aware Active Digital Twin (ADT)** system that:
1. **Tracks Multi-Hypothesis Fault Beliefs:** Maintains a probability distribution over potential root causes (e.g., cooling fan failure vs. coolant leak vs. sensor bias vs. transient engine overload).
2. **Estimates Diagnostic Uncertainty:** Quantifies belief entropy $\mathbb{H}(b_k)$ to determine when diagnostic ambiguity is unacceptably high.
3. **Actively Selects Diagnostic Actions:** Dynamically decides whether to request high-rate sensor bursts, command edge ECU actuation routines (e.g., cycling the cooling fan), declare a fault, or wait—balancing Expected Information Gain against Age of Information (AoI), network latency, packet loss, and communication costs.
4. **Evaluates against Baselines:** Benchmarks against static threshold-based diagnosis (OBD-II style) and passive Digital Twin anomaly observers across accuracy, false alarm rate, isolation delay, and bandwidth consumption.

---

## 🏛️ 2. System Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                 CONNECTED VEHICLE SIMULATOR (EDGE/VEHICLE)                       |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
|  | Multi-Physics Powertrain  |   | Fault Injection Engine     |   | Onboard Telemetry / ECU    |  |
|  | - Thermal (Engine/Coolant)|   | - Normal operation         |   | - Periodic Low-rate Sync   |  |
|  | - Speed & RPM Kinematics  |   | - Cooling fan failure      |   | - Sensor Noise Generation  |  |
|  | - Dynamic Engine Load     |   | - Temp sensor bias/freeze  |   | - Standard Telemetry JSON  |  |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
                      +-------------------------------------------------------+
                      |             INTERMITTENT NETWORK EMULATOR             |
                      | - Configurable Latency / Jitter (tau ~ N(mu, sigma))  |
                      | - Packet Loss Probability (p_loss)                    |
                      | - Bandwidth Quota (B_limit) & AoI Tracking            |
                      +---------------------------+---------------------------+
                                                  |
                                                  v
+-------------------------------------------------+-------------------------------------------------+
|                                    CLOUD DIGITAL TWIN BACKEND                                     |
|  +----------------------------+   +-----------------------------+   +--------------------------+  |
|  | Ingestion & Buffer Engine  |   | Physics-Informed State Twin |   | Multi-Hypothesis Belief  |  |
|  | - Age of Information (AoI) |   | - Nominal expected behavior |   | - Bayesian Belief Vector |  |
|  | - Residual: r_k = y_k - y^_k|  | - Residual thresholding     |   | - Diagnostic Entropy H(b)|  |
|  +----------------------------+   +-----------------------------+   +--------------------------+  |
|                                                  |                                                |
|                                                  v                                                |
|                               +-------------------------------------+                             |
|                               |   ACTIVE DIAGNOSTIC DECISION ENGINE |                             |
|                               | - Value of Information (VoI)        |                             |
|                               | - Test Cost & Bandwidth Penalties   |                             |
|                               | - Active Probes vs Edge Commands    |                             |
|                               +-------------------------------------+                             |
+---------------------------------------------------------------------------------------------------+
```

---

## 🚀 3. Current Implementation Status (Module 1 — Vehicle Simulator)

### Implemented Features
- **Physical Powertrain & Thermal Dynamics (`simulator/vehicle_model.py`):**
  - Dynamic differential equation for engine heat generation ($\dot{Q}_{\text{in}}$) based on RPM and load.
  - Multi-factor heat dissipation ($\dot{Q}_{\text{out}}$) based on ambient temperature, vehicle speed airflow, and ECU thermostat cooling fan actuation with hysteresis ($95^\circ\text{C}$ ON / $90^\circ\text{C}$ OFF).
- **Fault Injection Engine (`simulator/fault_injector.py`):**
  - Supports controlled, time-scheduled fault modes:
    - `normal`: Standard vehicle operation.
    - `high_load`: Engine overload driving profile.
    - `fan_failure`: Actuator/relay failure (fan disabled).
    - `temp_sensor_bias`: Sensor calibration drift with configurable offset $\Delta T$ in °C.
    - `temp_sensor_freeze`: Sensor locked at constant reading.
    - `missing_sensor_data`: Missing or dropped telemetry packets.
- **Sensor Telemetry Generator (`simulator/sensor_generator.py`):**
  - Realistic Gaussian measurement noise.
  - Reproducible, seedable pseudo-random generator.
  - Standardized JSON telemetry format conforming to schema.

### Standard Telemetry Schema
```json
{
  "vehicle_id": "EV_001",
  "timestamp": "2026-09-25T10:00:00Z",
  "speed_kmh": 45.0,
  "rpm": 2200.0,
  "engine_load": 0.62,
  "engine_temperature_c": 92.4,
  "cooling_fan_status": 1,
  "fault_status": "normal"
}
```

---

## ⚙️ 4. Installation & Quick Start

### 1. Clone & Setup Environment
```bash
git clone https://github.com/annu-creator24t/Capstone-Project.git
cd Capstone-Project
python -m venv venv
# On Windows PowerShell:
venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Vehicle Simulator
```bash
# Run a 30-second normal driving scenario
python -m simulator.main --scenario normal --duration 30

# Run a fan failure scenario with fault injected at t=10s
python -m simulator.main --scenario fan_failure --start-time 10 --duration 45

# Run a temperature sensor bias scenario with +20°C offset
python -m simulator.main --scenario temp_sensor_bias --start-time 10 --bias-offset 20.0

# Save generated telemetry packets to a JSON file
python -m simulator.main --scenario high_load --duration 60 --output telemetry_sample.json
```

### 3. Run Automated Tests
```bash
python -m unittest tests.test_simulator -v
```

---

## 🔬 5. Research Methodology & Prior Art Framing

We position this project with scientific rigor and honest claim-level comparisons:
- **Prior Art Grounding:** Active test selection (POMDPs, Bayesian active diagnosis) and vehicle Digital Twins exist independently in literature.
- **Defensible Contribution:** Our focus is the **joint formulation of active diagnostic test selection under non-stationary network impairments (stochastic delay, packet loss, bandwidth budgets) and Age of Information (AoI) staleness constraints in connected vehicles.**

---

## 🗺️ 6. Phased Roadmap

- [x] **Phase 1:** Repository Initialization & Module 1 (Vehicle Simulator & Fault Injection Core)
- [x] **Phase 2:** Module 2 — Intermittent Network Emulator (Delay, Loss, Queues, Bandwidth, AoI tracking)
- [ ] **Phase 3:** Module 3 — Cloud Digital Twin State Estimator & Residual Generator
- [ ] **Phase 4:** Module 4 — Multi-Hypothesis Bayesian Fault Belief Tracker
- [ ] **Phase 5:** Module 5 — Uncertainty- and Cost-Aware Active Diagnostic Action Engine
- [ ] **Phase 6:** Module 6 — Comparative Benchmark Suite (Baselines vs. Proposed ADT)
- [ ] **Phase 7:** Module 7 — Interactive Web Analytics Dashboard
- [ ] **Phase 8:** Module 8 — Academic Manuscript & Patentability Comparison Dossier
