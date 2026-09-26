# Experimental Campaign & Research Data Generation (`experiments/`)

This directory contains experimental manifests, research benchmark configurations, and data generation tools for evaluating the **Cloud-Based Digital Twin for Connected Vehicle Diagnostics**.

---

## 🎯 1. Research Objectives

The goal of this experimental campaign is to evaluate how transport-layer communication impairments (Age of Information, stochastic latency, jitter, packet loss, duplicates, and out-of-order deliveries) interact with vehicle subsystem health and fault diagnosis in a cloud-hosted Digital Twin.

### Core Scientific Distinction

The framework strictly separates:
- **Physical Vehicle Health:** Ground-truth condition of the vehicle (nominal vs. active fault).
- **Transport Channel Quality:** Latency, jitter, packet loss, and Age of Information ($\text{AoI}$).
- **Residual Discrepancy:** Mathematical difference $r = y - \hat{y}$ between observed and predicted state.
- **Diagnostic Qualification:** Telemetry validity and freshness gating ($\text{FRESH} \to \text{eligible}$, $\text{STALE} \to \text{NOT\_EVALUATED}$).
- **Fault Confirmation:** Persistent evidence over consecutive evaluation cycles.

---

## 🔬 2. Experimental Variables

| Category | Variables | Description |
| :--- | :--- | :--- |
| **Independent Variables** | Packet Loss Rate ($p_{\text{loss}}$) | $0\% \le p_{\text{loss}} \le 50\%$ |
| | Network Delay ($\mu_{\text{delay}}$) | $10\text{ms} \le \text{delay} \le 600\text{ms}$ |
| | Delay Jitter ($\sigma_{\text{delay}}$) | $0\text{ms} \le \text{jitter} \le 250\text{ms}$ |
| | Fault Type & Magnitude | Thermal sensor bias ($+5^\circ\text{C}$ to $+20^\circ\text{C}$), fan failure, high load |
| | Replicate Seed | Integer seeds (e.g. $42, 101, 202, 303, 404, 505$) |
| **Controlled Variables** | Vehicle Powertrain Parameters | Engine displacement, inertia, thermal capacitance, heat transfer coefficients |
| | Nominal Operating Profile | Speed ($45\text{km/h}$), Engine Load ($0.50$), RPM ($2200\text{ RPM}$) |
| | Sampling & Simulation Timestep | $\Delta t = 0.1\text{s}$ ($10\text{ Hz}$ telemetry rate) |
| | Baseline Thresholds | Engineering thresholds ($5^\circ\text{C}$ warning, $8^\circ\text{C}$ anomaly, $N=3$ persistence) |
| **Dependent Variables** | Data Age ($\text{AoI}$) | Mean and peak Age of Information across streams |
| | Freshness Distribution | Frame counts in $\text{FRESH}$, $\text{AGING}$, $\text{STALE}$, $\text{INVALID}$, $\text{MISSING}$ |
| | Diagnostic Eligibility | Count of frames qualifying for diagnostic inference |
| | Residual Magnitudes | Mean and peak residual $|r| = |y - \hat{y}|$ per sensor |
| | Alert Classifications | Counts of $\text{NORMAL}$, $\text{WARNING}$, and confirmed $\text{ANOMALY}$ |
| | Detection Timeliness | Detection delay $\Delta t_{\text{detect}} = t_{\text{confirmed}} - t_{\text{fault\_start}}$ |
| | False Alert Count | Confirmed anomalies during ground-truth healthy periods |

---

## 📊 3. Standard Experiment Groups

| Group | Identifier | Objective | Primary Swept Parameter |
| :--- | :--- | :--- | :--- |
| **A** | `baseline` | Establish reference Digital Twin performance under nominal health and clean connectivity. | Clean link ($10\text{ms}$ fixed delay, $0\%$ loss) |
| **B** | `packet_loss_sweep` | Quantify diagnostic blackout windows and AoI growth under lossy wireless channels. | $p_{\text{loss}} \in \{0\%, 10\%, 20\%, 35\%, 50\%\}$ |
| **C** | `delay_sweep` | Measure steady-state AoI elevation across cellular latency tiers. | $\text{Delay} \in \{10\text{ms}, 50\text{ms}, 100\text{ms}, 300\text{ms}, 600\text{ms}\}$ |
| **D** | `jitter_sweep` | Evaluate packet arrival stochasticity and state estimator alignment under delay variance. | $\text{Jitter} \in \{0\text{ms}, 25\text{ms}, 50\text{ms}, 100\text{ms}, 250\text{ms}\}$ |
| **E** | `fault_severity_sweep` | Benchmark sensitivity and time-to-confirmation across progressive sensor bias magnitudes. | $\Delta T_{\text{bias}} \in \{+5^\circ\text{C}, +10^\circ\text{C}, +15^\circ\text{C}, +20^\circ\text{C}\}$ |
| **F** | `fault_packet_loss` | Evaluate fault confirmation resilience when physical fault occurs during network dropouts. | $+15^\circ\text{C}$ bias with $p_{\text{loss}} \in \{0\%, 10\%, 20\%, 35\%, 50\%\}$ |
| **G** | `fault_delay` | Measure detection delay escalation when physical fault telemetry is delayed in transit. | $+15^\circ\text{C}$ bias with $\text{Delay} \in \{10, 50, 100, 300, 600\}\text{ms}$ |
| **H** | `combined_impairment` | Replicate real-world multi-impairment conditions across multiple deterministic seeds. | $+15^\circ\text{C}$ bias, $25\%$ loss, $80\text{ms} \pm 25\text{ms}$ Gaussian delay |

---

## 🛠️ 4. Running Experimental Campaigns via CLI

Execute predefined experiment sweeps using the command-line interface:

```bash
# Run the entire experimental matrix across all groups
python -m digital_twin.run_experiments --all

# Run a specific sweep (e.g. packet loss sweep) with custom seeds
python -m digital_twin.run_experiments --group packet_loss --seeds 42 101 202 303

# Run fault severity sweep with custom duration and output directory
python -m digital_twin.run_experiments --group fault --duration 30.0 --output-dir experiments/results

# Run combined impairment benchmark in quiet mode
python -m digital_twin.run_experiments --group combined --quiet
```

---

## 📁 5. Output Datasets & Structure

All generated campaign datasets are saved in structured, machine-readable formats suitable for Pandas, statistical review, and plotting scripts:

1. **Tabular CSV (`experiments/results/campaign_<group>_results.csv`):**
   - Flattened 1-D tabular format (1 row per experiment run).
   - Contains all configuration parameters, network statistics, freshness counts, anomaly levels, detection delays, and false alert counts.
2. **Structured JSON (`experiments/results/campaign_<group>_results.json`):**
   - Full hierarchy including sensor-specific residual maps and detailed metadata.
3. **Experiment Manifest (`experiments/experiment_manifest.json`):**
   - Declarative specification of planned experiment configurations, seeds, and parameter assignments.

---

## ⚠️ 6. Research Limitations

- **Engineering Baseline:** Diagnostic detection is based on deterministic two-level physical thresholds and persistence counters (no machine learning or probabilistic classification claims).
- **Simulation Scope:** Single-vehicle simulation scope per scenario instance.
- **Physical Dynamics:** 1D lumped-parameter thermal energy balance model.
