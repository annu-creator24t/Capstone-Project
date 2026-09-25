# Architecture & Research Specification: Uncertainty- and Cost-Aware Active Digital Twin (ADT) for Connected Vehicle Diagnostics

**Project Title:** Uncertainty- and Cost-Aware Active Digital Twin for Connected Vehicle Diagnostics Under Intermittent Connectivity  
**Target Output:** Working Python Simulator + Cloud DT Engine + Active Diagnostic Planner + Analytics Dashboard + Empirical Benchmark Suite + Research Paper & Patentability Dossier.

---

## 1. System Architecture Overview

```
+---------------------------------------------------------------------------------------------------+
|                                 CONNECTED VEHICLE SIMULATOR (EDGE/VEHICLE)                       |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
|  | Multi-Physics Powertrain  |   | Fault Injection Engine     |   | Onboard Telemetry / ECU    |  |
|  | - Thermal (Engine/Coolant)|   | - Coolant leak             |   | - Periodic Low-rate Sync   |  |
|  | - Electrical (Alt/Batt)   |   | - Fan electrical failure   |   | - On-Demand Active Probes  |  |
|  | - Mechanical (RPM/Torque) |   | - Sensor bias / freeze     |   | - Triggered Edge Test Exec |  |
|  +---------------------------+   +----------------------------+   +----------------------------+  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
                      +-------------------------------------------------------+
                      |             INTERMITTENT NETWORK EMULATOR             |
                      | - Configurable Latency / Jitter (tau ~ N(mu, sigma))  |
                      | - Packet Loss Probability (p_loss)                    |
                      | - Bandwidth Quota (B_limit)                           |
                      | - Out-of-order Delivery & Disconnections              |
                      +---------------------------+---------------------------+
                                                  |
                                                  v
+-------------------------------------------------+-------------------------------------------------+
|                                    CLOUD DIGITAL TWIN BACKEND                                     |
|  +----------------------------+   +-----------------------------+   +--------------------------+  |
|  | Ingestion & Buffer Engine  |   | Physics-Informed Digital    |   | Diagnostic Belief State  |  |
|  | - MQTT / REST API          |   | Twin Estimator              |   | - Bayesian / Particle /  |  |
|  | - AoI (Age of Information) |   | - Nominal expected state    |   |   POMDP Belief Vector    |  |
|  |   tracking per sensor      |   | - Residual calculation      |   | - Uncertainty (H(X))     |  |
|  +----------------------------+   +-----------------------------+   +--------------------------+  |
|                                                  |                                                |
|                                                  v                                                |
|                               +-------------------------------------+                             |
|                               |   ACTIVE DIAGNOSTIC DECISION ENGINE |                             |
|                               | - Information Gain / Entropy Red.   |                             |
|                               | - Test Cost & Bandwidth Penalty     |                             |
|                               | - Network Quality Penalty (tau, p)  |                             |
|                               | - Action: Probe / Test / Alert / Wait|                            |
|                               +------------------+------------------+                             |
+--------------------------------------------------|------------------------------------------------+
                                                   |
                         +-------------------------+-------------------------+
                         |                                                   |
                         v                                                   v
+--------------------------------------------------+  +---------------------------------------------+
|          INTERACTIVE ANALYTICS DASHBOARD         |  |         BENCHMARK & EXPERIMENTAL SUITE      |
| - Real-time Digital Twin Telemetry & Residuals   |  | Baseline 1: Fixed Threshold (Static OBD-II) |
| - Belief State & Fault Probability Distributions |  | Baseline 2: Passive Digital Twin            |
| - Action Selection Timeline & Cost Accumulator   |  | Proposed: Active Cost/Uncertainty DT        |
| - Network Condition & AoI Heatmaps               |  | Metrics: Accuracy, Delay, Bandwidth, Tests  |
+--------------------------------------------------+  +---------------------------------------------+
```

---

## 2. Rigorous Mathematical Formulation

### 2.1 State, Faults, and Residuals
Let the vehicle physical state at time step $k$ be $x_k \in \mathbb{R}^n$, control inputs $u_k \in \mathbb{R}^m$, and true sensor measurements $y_k \in \mathbb{R}^p$.
The Digital Twin maintains a nominal physics-informed state estimate $\hat{x}_k$ and nominal expected output $\hat{y}_k$:

$$\hat{x}_{k+1} = f(\hat{x}_k, u_k), \quad \hat{y}_k = g(\hat{x}_k, u_k)$$

The residual vector $r_k$ is defined as:
$$r_k = y_k - \hat{y}_k$$

Let $\mathcal{F} = \{f_0, f_1, f_2, \dots, f_M\}$ be the discrete set of health hypotheses, where $f_0$ represents nominal health, and $f_i$ ($i \ge 1$) represents specific faults (e.g., $f_1 = \text{Cooling Fan Failure}$, $f_2 = \text{Coolant Leakage}$, $f_3 = \text{Sensor Bias/Degradation}$, $f_4 = \text{Intermittent Telemetry Dropout}$).

### 2.2 Belief State and Uncertainty
Let $b_k \in \Delta^M$ be the belief distribution over fault hypotheses at time $k$:
$$b_k(i) = P(F = f_i \mid \mathcal{H}_k)$$
where $\mathcal{H}_k = \{y_{0:k}, u_{0:k}, a_{0:k-1}\}$ is the history of received observations, inputs, and executed diagnostic actions.

The **Diagnostic Uncertainty** is quantified using Shannon Entropy:
$$\mathbb{H}(b_k) = -\sum_{i=0}^{M} b_k(i) \log_2 b_k(i)$$

### 2.3 Active Diagnostic Action Space
At time $k$, the Digital Twin can select an action $a \in \mathcal{A}$:
1. **$a_0$ (Passive Wait / Default Telemetry):** Maintain default low-frequency sync.
2. **$a_{\text{poll}, j}$ (High-Rate Sensor Probe):** Request high-frequency burst telemetry for sensor subset $j$ (e.g., fine-grained thermal gradient or RPM-load correlation).
3. **$a_{\text{test}, m}$ (Active ECU Virtual/Physical Actuation Test):** Command an edge diagnostic routine (e.g., momentarily cycle cooling fan relay at high duty cycle, or run injector balance test).
4. **$a_{\text{confirm}, i}$ (Declare Fault $f_i$):** Terminate search and trigger maintenance alert.

### 2.4 Value-of-Information (VoI) with Cost & Age of Information (AoI)
Each action $a$ has an associated multi-factor cost:
$$C(a, \Delta_k, \Omega_k) = C_{\text{monetary}}(a) + \lambda_{\text{bw}} \cdot \text{Bytes}(a) + \lambda_{\text{time}} \cdot \mathbb{E}[\tau_{\text{exec}}(a)] + \lambda_{\text{risk}} \cdot \text{Risk}(a)$$

Where:
- $\Delta_k = [\delta_1(k), \dots, \delta_p(k)]$ is the **Age of Information (AoI)** for telemetry channels.
- $\Omega_k = (p_{\text{loss}}, \tau_{\text{rtt}}, \text{BW}_{\text{avail}})$ represents current network link quality estimates.
- $\mathbb{E}[I(F; Y^a \mid b_k)]$ is the expected **Mutual Information / Entropy Reduction**:
  $$\mathbb{E}[\Delta \mathbb{H}(a)] = \mathbb{H}(b_k) - \mathbb{E}_{y^a \sim P(y^a \mid b_k, a)} \left[ \mathbb{H}(b_{k+1}^{y^a}) \right]$$

The Optimal Active Action Selection policy solves:
$$a^* = \arg\max_{a \in \mathcal{A}} \left\{ \frac{\mathbb{E}[\Delta \mathbb{H}(a)]}{\beta + C(a, \Delta_k, \Omega_k)} \cdot \gamma(\Omega_k) - \text{Penalty}_{\text{AoI}}(\Delta_k) \right\}$$

---

## 3. Prior-Art & Patentability Landscape Analysis

| Research Dimension | Existing Prior Art (Patents & Papers) | Why Existing Solutions Fall Short in Real Fleet Settings | Our Grounded, Defensible Technical Gap |
| :--- | :--- | :--- | :--- |
| **Active Testing in Diagnostics** | Classical active fault isolation (Heckerman et al., Sampath et al., Bayesian active learning in industrial machines). | Assumes low-latency, deterministic, wired test execution (OBD-II / CAN bus connected directly to physical shop tool). | Formulates active probing under **stochastic network delay, packet dropouts, and Age-of-Information (AoI) staleness penalties** for connected vehicles. |
| **Digital Twin Vehicle Telematics** | Digital twins estimating vehicle health (Bosch, Siemens, Tesla patents on fleet telemetry twins). | Primarily **passive**: waits for periodic telemetry and triggers alert thresholds or anomaly scores when residual exceeds limit. | Integrates **bidirectional active querying**: DT determines when passive data has ambiguous residuals and selectively triggers cost-bounded edge test sequences. |
| **Network-Aware Telemetry** | Adaptive rate telematics based on cellular link status (Qualcomm, GM OnStar). | Optimizes bandwidth purely for throughput or streaming quality; agnostic to diagnostic fault discrimination value. | Couples **telemetry bandwidth throttling directly to Fisher Information / Value of Information (VoI)** of fault hypotheses. |

---

## 4. Benchmark & Experimental Evaluation Protocol

### 4.1 Comparison Baselines
1. **Baseline 1: Static Threshold / OBD-II Rules:**
   - Static threshold flags (e.g., $T_{\text{eng}} > 105^\circ\text{C} \implies \text{Overheat Alert}$).
   - High false positive rate under sensor noise or transient peak loads.
2. **Baseline 2: Passive Digital Twin Anomaly Detection:**
   - Physics-informed residual generation without active test requests.
   - Suffers from ambiguity when multiple faults generate identical passive symptoms.
3. **Proposed System: Uncertainty- & Cost-Aware Active Digital Twin (ADT):**
   - Actively selects probes and edge tests only when entropy exceeds ambiguity threshold, factoring in link latency and bandwidth limits.

### 4.2 Evaluation Metrics
- **Diagnostic Accuracy & Macro F1-Score (%)** across all fault types.
- **Time-to-Isolate (seconds)** from fault onset to definitive diagnosis.
- **Diagnostic Cost & Bandwidth Consumption (KB per fault episode)**.
- **Robustness under Packet Loss (0% to 50%) and Variable Latency (50ms to 3000ms)**.
- **Diagnostic Ambiguity Reduction Rate ($\Delta \mathbb{H} / \text{sec}$)**.
