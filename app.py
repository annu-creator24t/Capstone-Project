"""Connected Vehicle Digital Twin — Interactive Research & Diagnostic Analytics Dashboard.

Streamlit-based engineering and research interface integrating:
  - simulator.vehicle_model.VehicleModel
  - simulator.fault_injector.FaultInjector
  - simulator.sensor_generator.SensorGenerator
  - network.network_emulator.NetworkEmulator
  - digital_twin.nominal_model.NominalVehicleModel
  - digital_twin.state_estimator.DigitalTwinStateEstimator
  - digital_twin.residual_generator.ResidualGenerator
  - digital_twin.anomaly_detector.BaselineAnomalyDetector
  - digital_twin.evaluation.DiagnosticEvaluationRunner
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Ensure repository root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dashboard.simulation_manager import DashboardSimulationSession
from digital_twin.anomaly_detector import AnomalyLevel
from digital_twin.evaluation import DiagnosticEvaluationRunner, EvaluationScenario
from digital_twin.models import FreshnessStatus
from network.delay_model import DelayMode
from simulator.fault_injector import FaultConfig, FaultType

# ---------------------------------------------------------------------------
# Streamlit Page Configuration & Theming
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Connected Vehicle Digital Twin Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-End Engineering CSS
st.markdown(
    """
    <style>
    /* Dark Theme & Typography */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Top Header Styling */
    .app-title-container {
        padding: 1.2rem 1.6rem;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85), rgba(30, 41, 59, 0.70));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .app-main-title {
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .app-sub-title {
        font-size: 0.88rem;
        color: #94a3b8;
        margin-top: 0.3rem;
        margin-bottom: 0;
    }

    /* KPI Summary Cards */
    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.8rem 1rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    div[data-testid="stMetric"]:hover {
        border-color: rgba(56, 189, 248, 0.35);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        color: #94a3b8 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Status Pills */
    .status-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .status-normal {
        background-color: rgba(16, 185, 129, 0.18);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .status-warning {
        background-color: rgba(245, 158, 11, 0.18);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .status-danger {
        background-color: rgba(244, 63, 94, 0.22);
        color: #f43f5e;
        border: 1px solid rgba(244, 63, 94, 0.5);
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.75; }
    }

    /* Callout & Explanation Boxes */
    .info-callout {
        background: rgba(30, 41, 59, 0.5);
        border-left: 4px solid #38bdf8;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.84rem;
        color: #cbd5e1;
        margin: 0.8rem 0;
    }
    .warning-callout {
        background: rgba(45, 26, 14, 0.5);
        border-left: 4px solid #f59e0b;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.84rem;
        color: #fde68a;
        margin: 0.8rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
if "simulation_session" not in st.session_state:
    st.session_state.simulation_session = DashboardSimulationSession(
        vehicle_id="EV_001", dt_s=0.1, seed=42, history_maxlen=300
    )

if "is_running" not in st.session_state:
    st.session_state.is_running = False

if "step_delay" not in st.session_state:
    st.session_state.step_delay = 0.08

session: DashboardSimulationSession = st.session_state.simulation_session


# ---------------------------------------------------------------------------
# Sidebar: Scenario & Interactive Controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🎛️ Simulation Controls")

    # A. Playback & Clock Controls
    start_temp_mode = st.radio(
        "Thermal State on Reset",
        options=["Cold Start (85.0°C)", "Warm Operating Temp (95.0°C)"],
        index=0,
        help="Cold start warms gradually. Warm operating temp engages ECU fan thermostat immediately for testing fan actuator relay faults.",
    )
    init_temp_val = 95.0 if "95.0" in start_temp_mode else 85.0

    ctrl_col1, ctrl_col2 = st.columns(2)
    with ctrl_col1:
        if st.session_state.is_running:
            if st.button("⏸ Pause", use_container_width=True):
                st.session_state.is_running = False
                st.rerun()
        else:
            if st.button("▶ Run Live", use_container_width=True, type="primary"):
                st.session_state.is_running = True
                st.rerun()

    with ctrl_col2:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.is_running = False
            session.reset(seed=42, initial_temp_c=init_temp_val)
            st.rerun()

    step_col1, step_col2 = st.columns(2)
    with step_col1:
        if st.button("⏭ Step (+0.1s)", use_container_width=True):
            session.step(n_steps=1)
            st.rerun()
    with step_col2:
        if st.button("⏩ Step (+1.0s)", use_container_width=True):
            session.step(n_steps=10)
            st.rerun()

    # Refresh Delay Slider
    st.session_state.step_delay = st.slider(
        "Animation Step Delay (s)",
        min_value=0.02,
        max_value=0.40,
        value=st.session_state.step_delay,
        step=0.02,
        help="Adjust execution pacing when running in continuous mode.",
    )

    st.divider()

    # B. Fault Injection Controls
    st.subheader("2. Fault Injection Engine")

    fault_options = {
        "Normal Operation": FaultType.NORMAL,
        "Cooling Fan Failure": FaultType.FAN_FAILURE,
        "Temp Sensor Bias (+ΔT)": FaultType.TEMP_SENSOR_BIAS,
        "Temp Sensor Freeze": FaultType.TEMP_SENSOR_FREEZE,
        "Missing Sensor Data": FaultType.MISSING_SENSOR_DATA,
        "High Engine Overload": FaultType.HIGH_LOAD,
    }

    selected_fault_label = st.selectbox(
        "Operating Scenario / Fault Mode",
        options=list(fault_options.keys()),
        index=0,
        help="Select physical or sensor fault injection scenario implemented in simulator/fault_injector.py.",
    )
    chosen_fault_type = fault_options[selected_fault_label]

    # Conditional parameters based on fault mode
    bias_offset = 15.0
    if chosen_fault_type == FaultType.TEMP_SENSOR_BIAS:
        bias_offset = st.slider(
            "Sensor Bias Offset ΔT (°C)",
            min_value=1.0,
            max_value=30.0,
            value=15.0,
            step=1.0,
            help="Positive calibration offset added to engine temperature telemetry.",
        )

    fault_start_time = st.number_input(
        "Fault Start Time (s)",
        min_value=0.0,
        max_value=200.0,
        value=0.0,
        step=1.0,
        help="Simulation second when the fault becomes active.",
    )

    # Explanation Callout
    if chosen_fault_type == FaultType.NORMAL:
        st.markdown(
            "<div class='info-callout'><b>Nominal Operation:</b> Vehicle operates under standard urban kinematics. Residuals are bounded within noise levels (<5°C).</div>",
            unsafe_allow_html=True,
        )
    elif chosen_fault_type == FaultType.FAN_FAILURE:
        st.markdown(
            "<div class='warning-callout'><b>Cooling Fan Failure:</b> ECU thermostat signals relay, but cooling fan remains disabled. "
            "Under cold start (85°C), the thermostat engages the fan once coolant reaches 95°C (~65s of dynamic driving). "
            "To test immediate fan actuator failure detection, select <b>Warm Operating Temp (95.0°C)</b> above and click <b>↺ Reset</b>!</div>",
            unsafe_allow_html=True,
        )
    elif chosen_fault_type == FaultType.TEMP_SENSOR_BIAS:
        st.markdown(
            f"<div class='warning-callout'><b>Sensor Bias Drift (+{bias_offset}°C):</b> Physical engine remains healthy, but telemetry reports artificially elevated temperature, causing persistent residual $r_k > 8^\\circ\\text{{C}}$.</div>",
            unsafe_allow_html=True,
        )
    elif chosen_fault_type == FaultType.TEMP_SENSOR_FREEZE:
        st.markdown(
            "<div class='warning-callout'><b>Sensor Freeze:</b> Telemetry reading locks at fixed temperature while vehicle continues dynamic operation. Discrepancy emerges during speed/load shifts.</div>",
            unsafe_allow_html=True,
        )
    elif chosen_fault_type == FaultType.MISSING_SENSOR_DATA:
        st.markdown(
            "<div class='warning-callout'><b>Missing Sensor Data:</b> Telemetry packets are dropped at edge sensor generator, forcing Digital Twin to evaluate staleness & freshness degradation.</div>",
            unsafe_allow_html=True,
        )
    elif chosen_fault_type == FaultType.HIGH_LOAD:
        st.markdown(
            "<div class='info-callout'><b>High Load Operation:</b> Vehicle experiences sustained 95% engine load, testing nominal model tracking during heavy uphill driving.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # C. Network Emulation Controls
    st.subheader("3. Wireless Network Channel")

    packet_loss_pct = st.slider(
        "Wireless Packet Loss (%)",
        min_value=0,
        max_value=50,
        value=int(session.packet_loss_rate * 100),
        step=5,
        help="Simulates stochastic cellular dropouts over unreliable wireless links.",
    )

    latency_mode_label = st.radio(
        "Latency Mode",
        options=["Fixed Latency", "Gaussian Jitter"],
        horizontal=True,
    )
    selected_delay_mode = (
        DelayMode.FIXED if latency_mode_label == "Fixed Latency" else DelayMode.GAUSSIAN
    )

    mean_delay_val = 40.0
    jitter_val = 10.0
    if selected_delay_mode == DelayMode.FIXED:
        mean_delay_val = st.slider(
            "Transmission Latency (ms)",
            min_value=10,
            max_value=600,
            value=int(session.fixed_delay_ms),
            step=10,
            help="Fixed transport delay representing propagation and cellular queuing.",
        )
    else:
        mean_delay_val = st.slider(
            "Mean Delay μ (ms)", min_value=20, max_value=400, value=80, step=10
        )
        jitter_val = st.slider(
            "Jitter σ (ms)", min_value=5, max_value=150, value=25, step=5
        )

    # Apply configuration updates to live simulation session
    session.reconfigure(
        fault_type=chosen_fault_type,
        bias_offset_c=bias_offset,
        fault_start_s=fault_start_time,
        packet_loss_rate=float(packet_loss_pct) / 100.0,
        delay_mode=selected_delay_mode,
        fixed_delay_ms=float(mean_delay_val),
        mean_delay_ms=float(mean_delay_val),
        std_delay_ms=float(jitter_val),
    )


# ---------------------------------------------------------------------------
# Continuous Simulation Step Execution Hook
# ---------------------------------------------------------------------------
if st.session_state.is_running:
    session.step(n_steps=1)


# ---------------------------------------------------------------------------
# Top Header Banner & Research Framing
# ---------------------------------------------------------------------------
latest = session.get_latest()
df_history = session.to_dataframe()

st.markdown(
    """
    <div class="app-title-container">
        <h1 class="app-main-title">Cloud-Based Digital Twin for Connected Vehicle Diagnostics</h1>
        <p class="app-sub-title">
            Uncertainty- and Cost-Aware Active Digital Twin Research &bull; Real-Time Telemetry &bull; Intermittent Network Emulator &bull; Physics-Informed Residual Observer
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Top KPI Metric Cards (Real Simulation Signals)
# ---------------------------------------------------------------------------
kpi_cols = st.columns(6)

with kpi_cols[0]:
    st.metric(
        label="Sim Time",
        value=f"{latest['time_s']:.1f} s",
        delta=f"+{session.dt_s:.1f}s step",
    )

with kpi_cols[1]:
    st.metric(
        label="Vehicle Speed",
        value=f"{latest['speed_kmh']:.1f} km/h",
        delta=f"{latest['rpm']:.0f} RPM",
    )

with kpi_cols[2]:
    st.metric(
        label="Engine Load",
        value=f"{latest['engine_load']:.1f} %",
        delta=f"Q_in: {latest['q_in_w']:.0f} W",
    )

with kpi_cols[3]:
    st.metric(
        label="Coolant Temp (True)",
        value=f"{latest['true_engine_temp_c']:.1f} °C",
        delta=f"Obs: {latest['observed_engine_temp_c']:.1f} °C",
    )

with kpi_cols[4]:
    # Residual with warning / alert color indication
    res_val = latest["residual_c"]
    delta_str = f"Nom: {latest['nominal_engine_temp_c']:.1f} °C"
    st.metric(
        label="Thermal Residual (r)",
        value=f"{res_val:+.2f} °C",
        delta=delta_str,
        delta_color="inverse" if abs(res_val) > 5.0 else "normal",
    )

with kpi_cols[5]:
    st.metric(
        label="Data Freshness (AoI)",
        value=f"{latest['aoi_ms']:.0f} ms",
        delta=f"PDR: {latest['pdr_percent']:.1f}%",
    )


# ---------------------------------------------------------------------------
# Status Banner: Physical State, Network Health, and Anomaly Classification
# ---------------------------------------------------------------------------
banner_cols = st.columns([1.2, 1.2, 1.6, 2.0])

with banner_cols[0]:
    fan_text = "FAN ACTIVE (ON)" if latest["cooling_fan_status"] == 1 else "FAN STANDBY (OFF)"
    fan_cls = "status-normal" if latest["cooling_fan_status"] == 1 else "status-normal"
    if latest["fan_relay_fault"]:
        fan_text = "FAN RELAY FAILURE"
        fan_cls = "status-danger"
    st.markdown(
        f"**Actuator Health:** <span class='status-pill {fan_cls}'>{fan_text}</span>",
        unsafe_allow_html=True,
    )

with banner_cols[1]:
    fresh_cls = (
        "status-normal"
        if latest["freshness_status"] == FreshnessStatus.FRESH.value
        else ("status-warning" if latest["freshness_status"] == FreshnessStatus.AGING.value else "status-danger")
    )
    st.markdown(
        f"**Freshness:** <span class='status-pill {fresh_cls}'>{latest['freshness_status']}</span>",
        unsafe_allow_html=True,
    )

with banner_cols[2]:
    anom_level = latest["anomaly_level"]
    is_conf = latest["is_confirmed"]
    if is_conf:
        anom_txt = "CONFIRMED ANOMALY"
        anom_cls = "status-danger"
    elif anom_level == AnomalyLevel.WARNING.value:
        anom_txt = f"WARNING ({latest['persistence_count']}/3)"
        anom_cls = "status-warning"
    else:
        anom_txt = "NORMAL NOMINAL"
        anom_cls = "status-normal"
    st.markdown(
        f"**Diagnostic Detection:** <span class='status-pill {anom_cls}'>{anom_txt}</span>",
        unsafe_allow_html=True,
    )

with banner_cols[3]:
    st.markdown(
        f"**Active Fault Scenario:** `{latest['fault_type'].upper()}` &bull; Confirmed Events: `{session.confirmed_anomaly_count}`"
    )

st.write("")


# ---------------------------------------------------------------------------
# Main Tabs: Telemetry, Digital Twin, Network Emulator, Campaign Analytics, Theory
# ---------------------------------------------------------------------------
tab_telemetry, tab_digital_twin, tab_network, tab_campaign, tab_architecture = st.tabs(
    [
        "🚗 Vehicle Telemetry",
        "🧠 Digital Twin Diagnostics",
        "📡 Wireless Network Emulator",
        "📊 Research Campaign Explorer",
        "📚 Architecture & Theory",
    ]
)


# ---------------------------------------------------------------------------
# TAB 1: VEHICLE TELEMETRY & POWERTRAIN DYNAMICS
# ---------------------------------------------------------------------------
with tab_telemetry:
    st.subheader("Vehicle Powertrain & Thermal Dynamics")
    st.caption(
        "Ground truth physical vehicle state produced by `simulator.vehicle_model.VehicleModel` dynamic ODEs."
    )

    if not df_history.empty:
        # Chart 1: Kinematics (Speed & RPM)
        fig_kin = go.Figure()
        fig_kin.add_trace(
            go.Scatter(
                x=df_history["time_s"],
                y=df_history["speed_kmh"],
                name="Vehicle Speed (km/h)",
                line=dict(color="#38bdf8", width=2.5),
            )
        )
        fig_kin.add_trace(
            go.Scatter(
                x=df_history["time_s"],
                y=df_history["rpm"] / 50.0,
                name="Engine RPM (scaled / 50)",
                line=dict(color="#818cf8", width=1.5, dash="dot"),
            )
        )
        fig_kin.update_layout(
            title="Vehicle Kinematics (Speed & Engine RPM)",
            xaxis_title="Simulation Time (s)",
            yaxis_title="Kinematic Values",
            template="plotly_dark",
            height=300,
            margin=dict(l=40, r=40, t=40, b=40),
            hovermode="x unified",
        )
        st.plotly_chart(fig_kin, use_container_width=True)

        # Chart 2: Thermal Energy Balance (Q_in vs Q_out)
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            fig_thermal = go.Figure()
            fig_thermal.add_trace(
                go.Scatter(
                    x=df_history["time_s"],
                    y=df_history["true_engine_temp_c"],
                    name="Ground Truth Temp (°C)",
                    line=dict(color="#34d399", width=2.5),
                )
            )
            fig_thermal.add_trace(
                go.Scatter(
                    x=df_history["time_s"],
                    y=df_history["observed_engine_temp_c"],
                    name="Observed Sensor Telemetry (°C)",
                    line=dict(color="#38bdf8", width=1.8, dash="dash"),
                )
            )
            # Thermostat switch lines
            fig_thermal.add_hline(
                y=95.0,
                line_dash="dot",
                line_color="#f59e0b",
                annotation_text="Fan Trigger (95°C)",
            )
            fig_thermal.add_hline(
                y=90.0,
                line_dash="dot",
                line_color="#10b981",
                annotation_text="Fan Off (90°C)",
            )
            fig_thermal.update_layout(
                title="Engine Coolant Temperature vs Observed Sensor",
                xaxis_title="Time (s)",
                yaxis_title="Temperature (°C)",
                template="plotly_dark",
                height=320,
                margin=dict(l=40, r=40, t=40, b=40),
            )
            st.plotly_chart(fig_thermal, use_container_width=True)

        with t_col2:
            fig_heat = go.Figure()
            fig_heat.add_trace(
                go.Scatter(
                    x=df_history["time_s"],
                    y=df_history["q_in_w"],
                    name="Heat Generation Q_in (W)",
                    line=dict(color="#f43f5e", width=2),
                )
            )
            fig_heat.add_trace(
                go.Scatter(
                    x=df_history["time_s"],
                    y=df_history["q_out_w"],
                    name="Heat Dissipation Q_out (W)",
                    line=dict(color="#38bdf8", width=2),
                )
            )
            fig_heat.update_layout(
                title="Dynamic Thermal Energy Balance (Q_in vs Q_out)",
                xaxis_title="Time (s)",
                yaxis_title="Power (Watts)",
                template="plotly_dark",
                height=320,
                margin=dict(l=40, r=40, t=40, b=40),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

    else:
        st.info("Simulation session initialized. Click 'Run Live' or 'Step' to stream telemetry.")


# ---------------------------------------------------------------------------
# TAB 2: DIGITAL TWIN & DIAGNOSTICS
# ---------------------------------------------------------------------------
with tab_digital_twin:
    st.subheader("Physics-Informed Digital Twin State Estimation & Residual Generator")
    st.caption(
        "Compares received vehicle telemetry with nominal physics expectations to compute residual discrepancies $r_k = y_k - \\hat{y}_k$."
    )

    dt_info_col1, dt_info_col2 = st.columns(2)
    with dt_info_col1:
        st.markdown(
            """
            **Baseline Anomaly Detection Logic:**
            - **Signal Thresholds:** Warning threshold = $5.0^\\circ\\text{C}$ &bull; Anomaly threshold = $8.0^\\circ\\text{C}$
            - **Persistence Counter:** Requires **$N=3$ consecutive** breach cycles before declaring a confirmed anomaly.
            - **Gating Mechanism:** Telemetry with $\\text{AoI} > 3.0\\text{s}$ (`STALE`) is marked **`NOT_EVALUATED`** to prevent false alarms from outdated data.
            """
        )
    with dt_info_col2:
        st.markdown(
            f"""
            **Current Diagnostic Snapshot ($t={latest['time_s']:.1f}\\text{{s}}$):**
            - **Observed Telemetry ($y_k$):** `{latest['observed_engine_temp_c']:.2f} °C`
            - **Nominal Model Expectation ($\\hat{{y}}_k$):** `{latest['nominal_engine_temp_c']:.2f} °C`
            - **Raw Residual ($r_k$):** `{latest['residual_c']:+.2f} °C`
            - **Diagnostic Eligibility:** `{'ELIGIBLE' if latest['diagnostic_eligible'] else 'NOT EVALUATED (STALE)'}`
            - **Current Persistence:** `{latest['persistence_count']} / 3 consecutive breach frames`
            """
        )

    if not df_history.empty:
        # Chart: Observed vs Nominal Model Tracking
        fig_dt_tracking = go.Figure()
        fig_dt_tracking.add_trace(
            go.Scatter(
                x=df_history["time_s"],
                y=df_history["observed_engine_temp_c"],
                name="Observed Telemetry (y_k)",
                line=dict(color="#38bdf8", width=2.5),
            )
        )
        fig_dt_tracking.add_trace(
            go.Scatter(
                x=df_history["time_s"],
                y=df_history["nominal_engine_temp_c"],
                name="Nominal Twin Model (y^_k)",
                line=dict(color="#818cf8", width=2.0, dash="dash"),
            )
        )
        fig_dt_tracking.update_layout(
            title="Digital Twin State Tracking: Ingested Telemetry vs Physics-Informed Nominal Model",
            xaxis_title="Time (s)",
            yaxis_title="Engine Temperature (°C)",
            template="plotly_dark",
            height=320,
            margin=dict(l=40, r=40, t=40, b=40),
            hovermode="x unified",
        )
        st.plotly_chart(fig_dt_tracking, use_container_width=True)

        # Chart: Residual Error Stream & Threshold Breach Detection
        fig_res = go.Figure()
        fig_res.add_trace(
            go.Scatter(
                x=df_history["time_s"],
                y=df_history["residual_c"].abs(),
                name="|Residual| (|r_k|)",
                line=dict(color="#fbbf24", width=2.5),
            )
        )
        fig_res.add_hline(
            y=5.0,
            line_dash="dot",
            line_color="#f59e0b",
            annotation_text="Warning Threshold (5.0°C)",
        )
        fig_res.add_hline(
            y=8.0,
            line_dash="dash",
            line_color="#f43f5e",
            annotation_text="Anomaly Threshold (8.0°C)",
        )
        fig_res.update_layout(
            title="Diagnostic Thermal Residual Magnitude |r_k| & Threshold Gating",
            xaxis_title="Time (s)",
            yaxis_title="|Residual| (°C)",
            template="plotly_dark",
            height=300,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig_res, use_container_width=True)

        # Recent Alert Log
        st.write("##### 📜 Recent Diagnostic Events & Alert Log")
        alerts = session.get_alerts()
        if alerts:
            alert_df = pd.DataFrame(alerts)
            st.dataframe(alert_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No warning or critical anomaly events recorded yet.")


# ---------------------------------------------------------------------------
# TAB 3: WIRELESS NETWORK EMULATOR
# ---------------------------------------------------------------------------
with tab_network:
    st.subheader("Intermittent Wireless Network Emulator")
    st.caption(
        "Simulates transmission latency, stochastic packet dropouts, and computes instantaneous Age of Information (AoI)."
    )

    net_cols = st.columns(4)
    with net_cols[0]:
        st.metric("Packets Transmitted", f"{latest['packets_transmitted']:,}")
    with net_cols[1]:
        st.metric("Packets Delivered", f"{latest['packets_delivered']:,}")
    with net_cols[2]:
        st.metric("Packets Dropped", f"{latest['packets_dropped']:,}")
    with net_cols[3]:
        st.metric("Packet Delivery Ratio", f"{latest['pdr_percent']:.1f} %")

    if not df_history.empty:
        # Chart: Age of Information (AoI) over Time
        fig_aoi = go.Figure()
        fig_aoi.add_trace(
            go.Scatter(
                x=df_history["time_s"],
                y=df_history["aoi_ms"],
                name="Age of Information (ms)",
                line=dict(color="#38bdf8", width=2),
                fill="tozeroy",
                fillcolor="rgba(56, 189, 248, 0.15)",
            )
        )
        fig_aoi.add_hline(
            y=1000.0,
            line_dash="dot",
            line_color="#10b981",
            annotation_text="Fresh Limit (1.0s)",
        )
        fig_aoi.add_hline(
            y=3000.0,
            line_dash="dash",
            line_color="#f43f5e",
            annotation_text="Stale Gating (3.0s)",
        )
        fig_aoi.update_layout(
            title="Instantaneous Age of Information (AoI) Stream Dynamics",
            xaxis_title="Time (s)",
            yaxis_title="AoI (ms)",
            template="plotly_dark",
            height=320,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig_aoi, use_container_width=True)

        # Freshness Breakdown Pie Chart
        st.write("##### Telemetry Freshness Distribution")
        freshness_counts = df_history["freshness_status"].value_counts()
        fig_fresh = px.pie(
            values=freshness_counts.values,
            names=freshness_counts.index,
            title="Telemetry Sample Freshness Classification",
            color_discrete_map={
                FreshnessStatus.FRESH.value: "#10b981",
                FreshnessStatus.AGING.value: "#f59e0b",
                FreshnessStatus.STALE.value: "#f43f5e",
                FreshnessStatus.INVALID.value: "#a855f7",
                FreshnessStatus.MISSING.value: "#64748b",
            },
            template="plotly_dark",
            height=280,
        )
        st.plotly_chart(fig_fresh, use_container_width=True)


# ---------------------------------------------------------------------------
# TAB 4: RESEARCH CAMPAIGN EXPLORER
# ---------------------------------------------------------------------------
with tab_campaign:
    st.subheader("Experimental Research Campaigns & Benchmark Results")
    st.caption(
        "Analyzes precomputed research sweep datasets generated via `python -m digital_twin.run_experiments --all`."
    )

    campaign_csv_path = os.path.join(
        PROJECT_ROOT, "experiments", "results", "campaign_all_results.csv"
    )

    if os.path.exists(campaign_csv_path):
        df_campaign = pd.read_csv(campaign_csv_path)

        # Summary KPIs for Campaign
        c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
        with c_kpi1:
            st.metric("Total Campaign Runs", len(df_campaign))
        with c_kpi2:
            st.metric(
                "Max Loss Swept",
                f"{df_campaign['packet_loss_rate'].max() * 100:.0f}%",
            )
        with c_kpi3:
            st.metric("Max Latency Swept", f"{df_campaign['delay_ms'].max():.0f} ms")
        with c_kpi4:
            conf_col = "confirmed_anomaly_count" if "confirmed_anomaly_count" in df_campaign.columns else "anomaly_confirmed_count"
            confirmed_runs = (df_campaign[conf_col] > 0).sum() if conf_col in df_campaign.columns else 0
            st.metric(
                "Runs with Confirmed Anomaly",
                f"{confirmed_runs} / {len(df_campaign)}",
            )

        # Research Group Filter
        st.write("##### Filter by Research Group")
        available_groups = ["ALL"] + sorted(df_campaign["group"].unique().tolist())
        selected_grp = st.selectbox(
            "Select Benchmark Group", options=available_groups, index=0
        )

        filtered_df = (
            df_campaign
            if selected_grp == "ALL"
            else df_campaign[df_campaign["group"] == selected_grp]
        )

        st.caption(f"Showing **{len(filtered_df)}** of {len(df_campaign)} experiment runs.")

        # Campaign Benchmark Charts
        bc_col1, bc_col2 = st.columns(2)
        with bc_col1:
            # Packet Loss vs Delivered Packets
            fig_cmp1 = px.scatter(
                filtered_df,
                x="packet_loss_rate",
                y="total_packets_delivered",
                color="group",
                title="Packet Loss Rate vs Packets Delivered",
                labels={"packet_loss_rate": "Packet Loss Rate", "total_packets_delivered": "Delivered Packets"},
                template="plotly_dark",
                height=320,
            )
            st.plotly_chart(fig_cmp1, use_container_width=True)

        with bc_col2:
            # Fault Bias Magnitude vs Residual Peak
            res_col = "mean_temp_residual" if "mean_temp_residual" in filtered_df.columns else "residual_mean_engine_temp_c"
            fig_cmp2 = px.scatter(
                filtered_df,
                x="fault_magnitude",
                y=res_col,
                color="group",
                title="Fault Bias Offset (°C) vs Mean Thermal Residual",
                labels={"fault_magnitude": "Fault Bias Offset (°C)", res_col: "Mean Residual (°C)"},
                template="plotly_dark",
                height=320,
            )
            st.plotly_chart(fig_cmp2, use_container_width=True)

        # Full Data Table
        st.write("##### Experimental Run Dataset Table")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        # Download CSV button
        csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Filtered Results (CSV)",
            data=csv_bytes,
            file_name=f"campaign_{selected_grp.lower()}_results.csv",
            mime="text/csv",
        )

    else:
        st.warning(
            f"Campaign dataset not found at `{campaign_csv_path}`. "
            "Run `python -m digital_twin.run_experiments --all` to execute the full 93-experiment research campaign."
        )

    st.divider()

    # On-Demand Scenario Evaluation Runner
    st.write("#### ⚡ Run Custom Scenario Evaluation")
    st.caption(
        "Execute an end-to-end evaluation scenario using `digital_twin.evaluation.DiagnosticEvaluationRunner`."
    )

    eval_c1, eval_c2, eval_c3, eval_c4 = st.columns(4)
    with eval_c1:
        eval_duration = st.slider("Evaluation Duration (s)", 5.0, 30.0, 15.0, 5.0)
    with eval_c2:
        eval_fault = st.selectbox(
            "Evaluation Fault",
            options=[FaultType.NORMAL.value, FaultType.FAN_FAILURE.value, FaultType.TEMP_SENSOR_BIAS.value],
        )
    with eval_c3:
        eval_loss = st.slider("Evaluation Loss Rate", 0.0, 0.50, 0.10, 0.05)
    with eval_c4:
        eval_delay = st.slider("Evaluation Delay (ms)", 10.0, 300.0, 50.0, 10.0)

    if st.button("🚀 Execute Scenario Evaluation Now", type="primary"):
        with st.spinner("Executing evaluation scenario across vehicle, network, and twin..."):
            f_cfg = FaultConfig(
                fault_type=FaultType(eval_fault),
                start_time_s=3.0,
                bias_offset_c=15.0,
            )
            scenario = EvaluationScenario(
                scenario_name="OnDemand_Dashboard_Scenario",
                scenario_type="interactive_custom",
                duration_s=eval_duration,
                dt_s=0.1,
                random_seed=42,
                fault_config=f_cfg,
            )
            scenario.network_config.packet_loss.probability = eval_loss
            scenario.network_config.packet_loss.enabled = eval_loss > 0
            scenario.network_config.delay.fixed_delay_ms = eval_delay

            eval_runner = DiagnosticEvaluationRunner()
            scenario_res = eval_runner.run_scenario(scenario)

            st.success("Scenario evaluation completed successfully!")
            res_c1, res_c2, res_c3, res_c4 = st.columns(4)
            with res_c1:
                st.metric("Generated Frames", scenario_res.total_generated_frames)
            with res_c2:
                st.metric("Delivered Packets", scenario_res.total_packets_delivered)
            with res_c3:
                st.metric("Confirmed Anomalies", scenario_res.confirmed_anomaly_count)
            with res_c4:
                delay_str = (
                    f"{scenario_res.detection_delay_s:.2f} s"
                    if scenario_res.detection_delay_s is not None
                    else "N/A"
                )
                st.metric("Detection Delay", delay_str)


# ---------------------------------------------------------------------------
# TAB 5: ARCHITECTURE, MATHEMATICAL FORMULATIONS & ROADMAP
# ---------------------------------------------------------------------------
with tab_architecture:
    st.subheader("System Architecture & Mathematical Modeling")

    st.markdown(
        r"""
        ### 1. Multi-Physics Powertrain & Thermal Dynamics
        The vehicle physical thermal state evolves according to a lumped-parameter thermal energy balance ODE:

        $$\frac{dT_{\text{eng}}}{dt} = \frac{\dot{Q}_{\text{in}} - \dot{Q}_{\text{out}}}{C_{\text{th}}}$$

        Where:
        - **Heat Generation:** $\dot{Q}_{\text{in}} = (k_{\text{base}} + k_{\text{load}} \cdot L) \cdot \left(\frac{\text{RPM}}{1000}\right)$
        - **Heat Dissipation:** $\dot{Q}_{\text{out}} = \left(k_{\text{nat}} + k_{\text{speed}} \cdot v + k_{\text{fan}} \cdot u_{\text{fan}}\right) \cdot (T_{\text{eng}} - T_{\text{ambient}})$
        - **Thermostat Actuation:** $u_{\text{fan}} = 1$ when $T_{\text{eng}} \ge 95^\circ\text{C}$, switching off when $T_{\text{eng}} \le 90^\circ\text{C}$ (hysteresis).

        ---

        ### 2. Transport Layer Impairments & Age of Information (AoI)
        Connected vehicles transmit telemetry frames over stochastic, intermittent wireless channels:
        - **Transmission Latency:** $\tau_k \sim \mathcal{N}(\mu, \sigma^2)$ or fixed cellular propagation delay.
        - **Packet Loss:** Packets are dropped with Bernoulli probability $p_{\text{loss}}$.
        - **Age of Information:** Measures data staleness at Cloud DT arrival time $t$:
          
          $$\Delta_i(t) = t - U_i(t)$$
          
          Where $U_i(t)$ is the generation timestamp of the freshest delivered update for sensor stream $i$.

        ---

        ### 3. Physics-Informed Digital Twin Residual Generator
        The nominal Digital Twin model maintains an expected physical state trajectory:

        $$r_k = y_k - \hat{y}_k$$

        - **Freshness Gating:** Evaluated only when $\Delta_i(t) \le \tau_{\text{stale}}$ ($3.0\text{s}$). Stale packets are classified as `NOT_EVALUATED`.
        - **Two-Level Thresholding:** Warning threshold at $|r| > 5.0^\circ\text{C}$, anomaly threshold at $|r| > 8.0^\circ\text{C}$.
        - **Persistence Requirement:** An anomaly alert is confirmed only after **$N=3$ consecutive** breach cycles, suppressing single-packet transient spikes.

        ---

        ### 4. Roadmap & Scientific Positioning
        - ✅ **Module 1 (Implemented):** High-Fidelity Vehicle Simulator & Fault Injection Core
        - ✅ **Module 2 (Implemented):** Intermittent Network Emulator (Loss, Delay, Jitter, AoI)
        - ✅ **Module 3 (Implemented):** Cloud Digital Twin State Estimator & Residual Generator
        - ✅ **Module 7 (Implemented):** Interactive Real-Time Web Analytics Dashboard
        - ⏳ **Future Phase 4 & 5 (Roadmap):** Multi-Hypothesis Bayesian Fault Belief Tracker & Active Diagnostic Decision Engine (POMDP action selection).
        """
    )


# ---------------------------------------------------------------------------
# Continuous Animation Loop Trigger
# ---------------------------------------------------------------------------
if st.session_state.is_running:
    time.sleep(st.session_state.step_delay)
    st.rerun()
