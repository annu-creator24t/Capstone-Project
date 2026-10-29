"""Script to generate a comprehensive, publication-quality PDF guide for the Capstone Project.
Covers the entire codebase, architecture, folder structure, file-by-file breakdown,
mathematical formulations, experimental results, and test suite verification.
"""

import os
import sys

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas that performs a two-pass calculation of total page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Suppress running headers/footers on first page
        if self._pageNumber > 1:
            # Header
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#1A365D"))
            self.drawString(54, 750, "CLOUD-BASED DIGITAL TWIN FOR CONNECTED VEHICLE DIAGNOSTICS")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#718096"))
            self.drawRightString(612 - 54, 750, "Architecture & Codebase Reference Guide")
            
            self.setStrokeColor(colors.HexColor("#CBD5E0"))
            self.setLineWidth(0.75)
            self.line(54, 744, 612 - 54, 744)

            # Footer
            self.line(54, 45, 612 - 54, 45)
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#718096"))
            self.drawString(54, 32, "Author: Annu Tiwari | Capstone Project Repository")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(612 - 54, 32, page_text)
            
        self.restoreState()


def build_pdf(filename="Capstone_Project_Comprehensive_Guide.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    c_primary = colors.HexColor("#1A365D")    # Deep Navy
    c_secondary = colors.HexColor("#2B6CB0")  # Cobalt Blue
    c_accent = colors.HexColor("#D69E2E")     # Gold/Amber Accent
    c_dark = colors.HexColor("#2D3748")       # Body Charcoal
    c_light = colors.HexColor("#F7FAFC")      # Panel Background
    c_border = colors.HexColor("#CBD5E0")     # Light Border
    c_code_bg = colors.HexColor("#EDF2F7")    # Code block background
    c_success = colors.HexColor("#276749")    # Forest Green

    # Typography Styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=21,
        leading=26,
        textColor=c_primary,
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=c_secondary,
        alignment=0,
    )

    meta_style = ParagraphStyle(
        'CoverMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.0,
        leading=12,
        textColor=c_dark,
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.0,
        leading=11.5,
        textColor=c_dark,
        spaceAfter=4,
    )

    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.0,
        leading=11.5,
        textColor=colors.HexColor("#1A202C"),
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=0,
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.0,
        leading=9.0,
        textColor=c_dark,
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.0,
        leading=9.0,
        textColor=c_primary,
    )

    table_cell_code = ParagraphStyle(
        'TableCellCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor("#2C5282"),
    )

    story = []

    # =========================================================================
    # COVER / HEADER BLOCK
    # =========================================================================
    story.append(Spacer(1, 8))
    story.append(Paragraph("PROJECT ARCHITECTURE & CODEBASE REFERENCE GUIDE", subtitle_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Cloud-Based Digital Twin for Connected Vehicle Diagnostics & Performance Analytics", title_style))
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width="100%", thickness=1.8, color=c_primary, spaceBefore=2, spaceAfter=6))

    meta_text = """
    <b>Lead Developer:</b> Annu Tiwari &nbsp;|&nbsp; 
    <b>Repository:</b> <code>github.com/annu-creator24t/Capstone-Project</code><br/>
    <b>Automated Testing Status:</b> 163 of 163 Unit & Integration Tests Passing (100% Pass Rate)<br/>
    <b>Core Technology Stack:</b> Python 3.10+, NumPy, SciPy, Pandas, Matplotlib, ReportLab, PyTest<br/>
    <b>Research Focus:</b> Powertrain Multi-Physics, Intermittent Cellular Emulation, Age of Information (AoI), State Estimation, Residual Generation, Baseline Anomaly Detection, & Systematic Campaign Orchestration.
    """
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 6))

    # Executive Box
    exec_summary_html = """
    <b>Executive Summary:</b> Modern connected vehicles transmit telemetry over stochastic, bandwidth-constrained wireless channels characterized by packet loss, communication latency, arrival jitter, and duplicate packets. Conventional cloud diagnostics often conflate communication staleness with mechanical vehicle faults, producing high false alarm rates. This project implements an end-to-end <b>Physics-Informed Cloud Digital Twin Diagnostic System</b> that strictly decouples communication-induced data aging (quantified via <i>Age of Information - AoI</i>) from physical vehicle anomalies. The codebase is organized into four core modular engines backed by 163 rigorous automated tests.
    """
    exec_table = Table([[Paragraph(exec_summary_html, callout_style)]], colWidths=[504])
    exec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), c_light),
        ('BOX', (0, 0), (-1, -1), 1, c_secondary),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(exec_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 1: SYSTEM ARCHITECTURE & INFORMATION PIPELINE
    # =========================================================================
    story.append(Paragraph("1. System Architecture & End-to-End Pipeline", h1_style))
    story.append(Paragraph(
        "The architecture implements a 7-stage closed-loop telemetry and diagnostic processing pipeline that models both physical powertrain behaviors and wireless communication channel degradation:",
        body_style
    ))

    pipeline_stages = [
        ("Stage 1: Multi-Physics Powertrain", "Vehicle Simulator (`simulator/vehicle_model.py`) integrates ODEs for thermal energy balance, engine RPM, vehicle speed kinematics, and dynamic engine load. Actuates cooling fan with hysteresis (95 deg C ON / 90 deg C OFF)."),
        ("Stage 2: Fault Injection Engine", "Controlled Fault Injector (`simulator/fault_injector.py`) injects deterministic, time-bounded physical faults: cooling fan actuator failure, sensor calibration bias (+Delta T), sensor freeze, engine overload, or missing data packets."),
        ("Stage 3: Sensor Noise & Formatting", "Sensor Generator (`simulator/sensor_generator.py`) superimposes Gaussian noise onto continuous states and formats standardized ISO-8601 UTC JSON telemetry frames (`EV_001`)."),
        ("Stage 4: Intermittent Network Channel", "Network Emulator (`network/`) splits frames into discrete packets, applies stochastic packet loss, models FIFO serialization delay (T_ser = bits/bps), enforces byte quotas, and introduces fixed, uniform, or Gaussian propagation latency."),
        ("Stage 5: Stream Ordering & AoI Engine", "Arrival Tracker (`network/packet_ordering.py`, `network/aoi_tracker.py`) detects sequence inversions, flags stale telemetry (t_gen < t_latest), eliminates duplicates, and tracks continuous Age of Information (AoI(t) = t - u(t))."),
        ("Stage 6: Cloud DT State Estimator", "Digital Twin (`digital_twin/state_estimator.py`, `digital_twin/nominal_model.py`) ingests valid, non-stale packets, forward-predicts nominal vehicle dynamics, synthesizes expected measurements y_hat(k), and evaluates sync health."),
        ("Stage 7: Residuals & Anomaly Detection", "Diagnostic Engine (`digital_twin/residual_generator.py`, `digital_twin/telemetry_freshness.py`, `digital_twin/anomaly_detector.py`) computes raw/relative residuals, evaluates freshness (FRESH, AGING, STALE, INVALID), and executes two-level thresholding with persistence counters (N=3)."),
    ]

    pipe_table_data = [[Paragraph("<b>Pipeline Stage</b>", table_header_style), Paragraph("<b>Architectural Responsibility & Implementation</b>", table_header_style)]]
    for stg, desc in pipeline_stages:
        pipe_table_data.append([Paragraph(f"<b>{stg}</b>", table_cell_bold), Paragraph(desc, table_cell_style)])

    pipe_table = Table(pipe_table_data, colWidths=[130, 374])
    pipe_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_light]),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(pipe_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 2: COMPLETE FOLDER STRUCTURE & FILE-BY-FILE DIRECTORY
    # =========================================================================
    story.append(Paragraph("2. Master Folder Structure & Detailed File Directory", h1_style))
    story.append(Paragraph(
        "The repository is organized into cleanly decoupled packages following professional software engineering standards. Every file serves a dedicated, mathematically defined purpose:",
        body_style
    ))

    file_records = [
        ("Root", ".env.example", "Configuration template", "Specifies optional cloud API keys, environment profiles, and port definitions."),
        ("Root", ".gitignore", "Git exclusions", "Prevents tracking of Python cache (__pycache__), virtualenvs, build artifacts, and test caches."),
        ("Root", "README.md", "Master Documentation", "High-level overview, architecture diagrams, mathematical formulas, quick-start guides, and roadmap."),
        ("Root", "requirements.txt", "Dependencies", "Pins core dependencies: numpy, scipy, pandas, matplotlib, reportlab, pytest, etc."),
        ("Root", "Cloud_Based_...pdf", "Archival Reference", "9-page journal reference report documenting architecture, stage evolution, and 93 experimental runs."),
        ("simulator/", "__init__.py", "Package Init", "Exposes vehicle simulation models, fault injectors, and telemetry generation interfaces."),
        ("simulator/", "vehicle_model.py", "Powertrain Multi-Physics", "Physical vehicle model: dynamic heat generation (Q_in), multi-factor dissipation (Q_out), Euler ODE solver, fan hysteresis."),
        ("simulator/", "fault_injector.py", "Fault Injection Engine", "Configures and injects physical and sensor faults (fan failure, temp bias, freeze, overload, dropped data) across time windows."),
        ("simulator/", "sensor_generator.py", "Telemetry Generator", "Converts ground-truth physical state into noisy, quantized telemetry packets with ISO-8601 UTC timestamps."),
        ("simulator/", "main.py", "Simulator CLI Runner", "Command-line entrypoint to run vehicle driving cycles, inject faults, output formatted JSON telemetry streams."),
        ("network/", "__init__.py", "Package Init", "Exposes network emulation components, delay/loss models, bandwidth models, and AoI trackers."),
        ("network/", "models.py", "Network Data Schemas", "Defines NetworkPacket dataclass (timestamps, IDs, payloads) and DeliveryStatus enum (QUEUED, IN_TRANSIT, DELIVERED, etc.)."),
        ("network/", "network_config.py", "Consolidated Config", "Master NetworkConfig combining delay, loss, ordering, and bandwidth configurations with comprehensive validation."),
        ("network/", "delay_model.py", "Latency Models", "Simulates transmission latency supporting Fixed, Uniform, and Gaussian modes with non-negative causality guarantees."),
        ("network/", "packet_loss.py", "Packet Loss Engine", "Stochastic packet loss simulator with seedable pseudo-random generator and probability boundary enforcement."),
        ("network/", "bandwidth_model.py", "Throughput & Quotas", "Computes serialization delay (T_ser = bits/bps), manages byte quotas per time window, handles quota rejections."),
        ("network/", "packet_queue.py", "Priority Pipeline Queue", "Min-heap priority queue tracking in-transit packets keyed by scheduled delivery timestamp; extracts arrived packets."),
        ("network/", "packet_ordering.py", "Stream Sequencing", "Tracks per-sensor sequence numbers and timestamps to detect duplicates, out-of-order deliveries, and stale arrivals."),
        ("network/", "aoi_tracker.py", "AoI Freshness Engine", "Calculates instantaneous AoI(t) = t - u(t), tracks peak AoI, sample average, and continuous time-integrated average AoI."),
        ("network/", "transmission_scheduler.py", "FIFO Uplink Scheduler", "Schedules packets on a single-channel link, prevents overlapping transmissions, and enforces byte quotas."),
        ("network/", "network_emulator.py", "High-Level Facade", "Orchestrates frame ingestion, channel splitting (speed, rpm, load, temp, fan), transmission, and communication metrics."),
        ("network/", "README.md", "Network Module Docs", "Comprehensive documentation of network pipelines, timestamps, delay equations, and usage patterns."),
        ("digital_twin/", "__init__.py", "Package Init", "Exposes Digital Twin models, nominal estimators, residual generators, freshness evaluators, and detectors."),
        ("digital_twin/", "models.py", "DT Data Representations", "Defines DigitalTwinState, ExpectedMeasurement, SensorResidual, AnomalyEvaluationResult, and status enums."),
        ("digital_twin/", "twin_config.py", "Digital Twin Configs", "Defines ResidualThresholds, FreshnessThresholds, SignalThreshold (two-level), and master DigitalTwinConfig."),
        ("digital_twin/", "nominal_model.py", "Physics-Informed Model", "Nominal vehicle model executing identical physics to predict expected states and synthesize expected measurements y_hat(k)."),
        ("digital_twin/", "state_estimator.py", "Cloud State Estimator", "Fuses nominal forward predictions with asynchronously delivered telemetry updates; rejects stale/out-of-order packets."),
        ("digital_twin/", "telemetry_freshness.py", "Freshness & Validity", "Evaluates AoI against freshness thresholds (FRESH, AGING, STALE, INVALID, MISSING) and gates diagnostic eligibility."),
        ("digital_twin/", "residual_generator.py", "Residual Engine", "Computes raw residuals (r = y - y_hat), absolute residuals (|r|), and defensive relative residuals (r_rel) with epsilon safety."),
        ("digital_twin/", "anomaly_detector.py", "Baseline Anomaly Detector", "Two-level thresholding (warning vs anomaly), relative bounds, categorical fan policy, and persistence tracking (N=3)."),
        ("digital_twin/", "evaluation.py", "Diagnostic Eval Framework", "Deterministic integrated test harness executing Scenarios A-G, ground truth comparison, and detection delay quantification."),
        ("digital_twin/", "experiment_config.py", "Campaign Configs", "Structured configuration dataclasses for systematic research sweeps over network loss, delay, jitter, faults, and seeds."),
        ("digital_twin/", "experiment_runner.py", "Campaign Orchestrator", "Batch experiment orchestrator executing parameter matrices, aggregating cross-layer metrics, and exporting CSV/JSON/manifest."),
        ("digital_twin/", "run_experiments.py", "Campaign CLI Runner", "Command-line tool to execute individual experiment groups or the entire master campaign from terminal."),
        ("digital_twin/", "README.md", "Digital Twin Docs", "Complete guide to DT architecture, residual mathematical models, evaluation scenarios, and campaign sweeps."),
        ("experiments/", "README.md", "Research Methodology", "Scientific framing of experimental variables (independent, controlled, dependent), sweep groups, and research principles."),
        ("tests/", "test_simulator.py", "Simulator Test Suite", "6 unit tests verifying vehicle dynamics, fan actuation hysteresis, noise reproducibility, and fault injection."),
        ("tests/test_network/", "8 test files (test_*.py)", "Network Test Suites", "43 unit tests covering delay models, packet loss, bandwidth, scheduling, priority queue, ordering, and AoI tracker."),
        ("tests/test_digital_twin/", "8 test files (test_*.py)", "Digital Twin Test Suites", "114 unit tests covering models, nominal predictor, state estimator, freshness evaluator, residual generator, detector, and campaigns."),
    ]

    file_table_data = [
        [
            Paragraph("<b>Directory</b>", table_header_style),
            Paragraph("<b>File Name</b>", table_header_style),
            Paragraph("<b>Component Role</b>", table_header_style),
            Paragraph("<b>Core Functionality & Architecture</b>", table_header_style),
        ]
    ]

    for d, f, r, c in file_records:
        file_table_data.append([
            Paragraph(f"<b>{d}</b>", table_cell_bold),
            Paragraph(f, table_cell_code),
            Paragraph(r, table_cell_style),
            Paragraph(c, table_cell_style),
        ])

    file_table = Table(file_table_data, colWidths=[68, 106, 92, 238], repeatRows=1)
    file_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_light]),
        ('PADDING', (0, 0), (-1, -1), 2.4),
    ]))
    story.append(file_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 3: MATHEMATICAL FORMULATIONS & PHYSICS MODELS
    # =========================================================================
    story.append(Paragraph("3. Mathematical Formulations & Physical Dynamic Models", h1_style))
    story.append(Paragraph(
        "The digital twin and network emulation modules are grounded in rigorous mathematical physics and queuing theory:",
        body_style
    ))

    math_sections = [
        ("A. Powertrain Thermal Energy Balance", """
        The physical engine temperature <i>T(t)</i> evolves according to dynamic lumped-parameter heat transfer differential equations:<br/>
        &bull; <b>Heat Generation Rate:</b> <i>Q_in = (k_base + k_load &middot; load) &middot; (rpm / 1000)</i><br/>
        &bull; <b>Heat Dissipation Rate:</b> <i>Q_out = [k_nat + (k_speed &middot; v) + (k_fan &middot; fan_status)] &middot; [T(t) - T_ambient]</i><br/>
        &bull; <b>Dynamic Temperature Derivative:</b> <i>dT/dt = (Q_in - Q_out) / C_thermal</i><br/>
        &bull; <b>ECU Thermostat Hysteresis Control:</b><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;If <i>T &gt;= T_fan_on</i> (95.0 deg C) -&gt; <i>fan_status = 1</i> (Cooling Fan ON)<br/>
        &nbsp;&nbsp;&nbsp;&nbsp;If <i>T &lt;= T_fan_off</i> (90.0 deg C) -&gt; <i>fan_status = 0</i> (Cooling Fan OFF)<br/>
        Numerical integration uses forward Euler discretization: <i>T(t + Delta t) = T(t) + (dT/dt) &middot; Delta t</i>.
        """),
        ("B. Network Channel, Serialization, & Quota Models", """
        Telemetry transmission over capacity-constrained uplinks is governed by physical transmission physics:<br/>
        &bull; <b>Link Serialization Time:</b> <i>T_ser = (packet_size_bytes &middot; 8) / Bandwidth_bps</i><br/>
        &bull; <b>FIFO Channel Non-Overlap:</b> <i>tx_start = max(current_time, link_busy_until)</i>, with <i>tx_complete = tx_start + T_ser</i>.<br/>
        &bull; <b>End-to-End Scheduled Delivery:</b> <i>scheduled_delivery = tx_complete + tau_propagation</i>, where propagation latency <i>tau</i> is drawn from Fixed, Uniform <i>U(min, max)</i>, or Gaussian <i>max(0, N(mu, sigma))</i> distributions.<br/>
        &bull; <b>Byte Quota Accounting:</b> Uplink transmissions are bounded within discrete time windows <i>[k &middot; W, (k+1) &middot; W)</i>. If byte budget is exhausted, packets are either delayed into the next window or rejected.
        """),
        ("C. Age of Information (AoI) Freshness Metrics", """
        Data staleness is tracked per vehicle <i>v</i> and sensor channel <i>s</i> using classical Age of Information formulation:<br/>
        &bull; <b>Instantaneous AoI:</b> <i>AoI_{v,s}(t) = t - u_{v,s}(t)</i>, where <i>u_{v,s}(t) = max { t_gen : valid non-stale update received by time t }</i>.<br/>
        &bull; <b>Linear Sawtooth Evolution:</b> In the absence of newer arrivals, AoI increases linearly with unit slope (<i>dAoI/dt = 1</i>). Upon arrival of a strictly newer packet (<i>t_gen &gt; u(t)</i>), AoI instantaneously drops to the delivery latency (<i>t_rx - t_gen</i>).<br/>
        &bull; <b>Stale Packet Protection:</b> Out-of-order or duplicate packets (<i>t_gen &lt;= u(t)</i>) do NOT reset AoI downward.<br/>
        &bull; <b>Time-Integrated Continuous Average AoI:</b> <i>AoI_avg = (1 / T) integral_0^T AoI(t) dt</i> (calculated geometrically).
        """),
        ("D. Residual Formulations & Epsilon Safety", """
        Discrepancies between physical telemetry observations <i>y_k</i> and cloud model expectations <i>y_hat_k</i> are evaluated defensively:<br/>
        &bull; <b>Raw Residual:</b> <i>r_k = y_k - y_hat_k</i><br/>
        &bull; <b>Absolute Residual:</b> <i>|r_k| = |y_k - y_hat_k|</i><br/>
        &bull; <b>Defensive Relative Residual:</b> <i>r_rel,k = (y_k - y_hat_k) / max(|y_hat_k|, epsilon)</i>, where <i>epsilon = 10^-4</i> prevents zero-division during vehicle standstills.<br/>
        &bull; <b>Categorical Signals:</b> For binary actuator states (e.g., <code>cooling_fan_status</code>), relative residuals are explicitly bypassed, and discrete state equality (<i>observed == expected</i>) is evaluated.
        """),
        ("E. Telemetry Freshness & Diagnostic Eligibility Gating", """
        To prevent communication delays from triggering false mechanical fault alarms, data freshness is classified before diagnostic inference:<br/>
        &bull; <b>FRESH (0 &lt;= AoI &lt;= 1.0s):</b> Eligible for baseline threshold evaluation.<br/>
        &bull; <b>AGING (1.0s &lt; AoI &lt;= 3.0s):</b> Older data retained for downstream reasoning; optionally excluded from immediate alarms.<br/>
        &bull; <b>STALE (AoI &gt; 3.0s):</b> Ineligible for baseline anomaly evaluation; marked <code>NOT_EVALUATED</code> (0 false vehicle alerts).<br/>
        &bull; <b>INVALID / MISSING:</b> Contains NaN, infinite values, negative AoI (causality breach), or dropped fields.
        """),
        ("F. Two-Level Thresholding & Persistence Confirmation", """
        The Baseline Anomaly Detector applies signal-specific two-level physical limits and multi-frame temporal confirmation:<br/>
        &bull; <b>Speed:</b> Warning &gt; 8.0 km/h (15%), Anomaly &gt; 12.0 km/h (25%)<br/>
        &bull; <b>RPM:</b> Warning &gt; 200 RPM (10%), Anomaly &gt; 350 RPM (18%)<br/>
        &bull; <b>Engine Load:</b> Warning &gt; 0.12, Anomaly &gt; 0.20<br/>
        &bull; <b>Engine Temperature:</b> Warning &gt; 5.0 deg C (6%), Anomaly &gt; 8.0 deg C (10%)<br/>
        &bull; <b>Cooling Fan Status:</b> Discrete state mismatch -&gt; Candidate Anomaly.<br/>
        &bull; <b>Temporal Persistence:</b> Requires <i>N = 3</i> consecutive anomalous samples before confirming an alert. A single nominal sample immediately resets the persistence counter to zero, filtering single-sample noise spikes.
        """),
    ]

    for title, desc in math_sections:
        story.append(Paragraph(title, h2_style))
        story.append(Paragraph(desc, body_style))
        story.append(Spacer(1, 2))

    # =========================================================================
    # SECTION 4: EXPERIMENTAL EVALUATION FRAMEWORK & SCENARIOS
    # =========================================================================
    story.append(Paragraph("4. Experimental Scenarios (A-G) & Campaign Matrix (A-H)", h1_style))
    story.append(Paragraph(
        "The framework includes two layers of rigorous evaluation: Stage 4D single-run diagnostic evaluation scenarios and Stage 5 multi-seed automated research campaigns.",
        body_style
    ))

    scenarios = [
        ("Scenario A: Clean Baseline", "Healthy vehicle on an ideal link (10ms fixed delay). Verifies zero false alarms and tight residual tracking."),
        ("Scenario B: Aging & Staleness", "Healthy vehicle with telemetry blackout. AoI escalates, freshness transitions FRESH -> AGING -> STALE. Marked NOT_EVALUATED with 0 false alerts."),
        ("Scenario C: Stochastic Loss", "Evaluates telemetry dropout up to 50% packet loss rate. Demonstrates resilient recovery and AoI degradation windows."),
        ("Scenario D: Delay & Jitter", "Stochastic latency variations (Uniform 50-600ms, Gaussian jitter). Evaluates state estimator tracking under packet arrival jitter."),
        ("Scenario E: Duplicates & Disorder", "High-jitter link with 30% duplicate packet retransmissions. Verifies duplicate rejection and out-of-order sequence protection."),
        ("Scenario F: Injected Vehicle Fault", "Deterministic physical fault (e.g., +15 deg C thermal sensor bias) on a clean channel. Measures detection delay and residual magnitude."),
        ("Scenario G: Fault + Impairment", "Combined real-world test: +15 deg C physical fault over a lossy (25%), jittered (80+-25ms) wireless link. Evaluates diagnostic timeliness under stress."),
    ]

    scen_table_data = [[Paragraph("<b>Scenario</b>", table_header_style), Paragraph("<b>Test Condition & Empirical Verification</b>", table_header_style)]]
    for s_name, s_desc in scenarios:
        scen_table_data.append([Paragraph(f"<b>{s_name}</b>", table_cell_bold), Paragraph(s_desc, table_cell_style)])

    scen_table = Table(scen_table_data, colWidths=[130, 374])
    scen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_light]),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(scen_table)
    story.append(Spacer(1, 6))

    # Campaign Groups
    story.append(Paragraph("Stage 5 Automated Research Campaign Matrix (Groups A through H)", h2_style))
    story.append(Paragraph(
        "The automated experiment runner executes reproducible sweeps across parameters, exporting flattened CSV tables, hierarchical JSON, and declarative manifests:",
        body_style
    ))

    campaign_groups = [
        ("Group A (`baseline`)", "Reference baseline under nominal health and clean 10ms fixed latency."),
        ("Group B (`packet_loss_sweep`)", "Loss rates swept across [0%, 10%, 20%, 35%, 50%] to quantify AoI growth and blackout periods."),
        ("Group C (`delay_sweep`)", "Latencies swept across [10, 50, 100, 300, 600 ms] to measure steady-state AoI elevation."),
        ("Group D (`jitter_sweep`)", "Latency jitter swept across [0, 25, 50, 100, 250 ms] to evaluate arrival stochasticity."),
        ("Group E (`fault_severity_sweep`)", "Thermal biases swept across [+5, +10, +15, +20 deg C] to benchmark detector sensitivity."),
        ("Group F (`fault_packet_loss`)", "+15 deg C thermal fault evaluated under loss rates from 0% to 50% to test fault confirmation resilience."),
        ("Group G (`fault_delay`)", "+15 deg C thermal fault evaluated under latencies from 10ms to 600ms to measure detection delay escalation."),
        ("Group H (`combined_impairment`)", "Realistic multi-impairment benchmark (+15 deg C bias, 25% loss, 80+-25ms delay) across multiple seeds."),
    ]

    camp_table_data = [[Paragraph("<b>Campaign Group</b>", table_header_style), Paragraph("<b>Research Objective & Swept Parameter Range</b>", table_header_style)]]
    for c_id, c_desc in campaign_groups:
        camp_table_data.append([Paragraph(f"<b>{c_id}</b>", table_cell_bold), Paragraph(c_desc, table_cell_style)])

    camp_table = Table(camp_table_data, colWidths=[130, 374])
    camp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secondary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_light]),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(camp_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 5: AUTOMATED TEST SUITE & QUALITY VERIFICATION
    # =========================================================================
    story.append(Paragraph("5. Automated Test Suite & Quality Verification", h1_style))
    story.append(Paragraph(
        "Code reliability and regression prevention are guaranteed by an exhaustive test suite executed via PyTest and Python unittest. All 163 tests pass with 100% success rate in under 2.5 seconds:",
        body_style
    ))

    test_breakdown = [
        ("Vehicle Simulator Suite", "tests/test_simulator.py", "6", "Verifies powertrain kinematics, thermal Euler integration, fan thermostat hysteresis, noise seed reproducibility, and all 5 fault injection modes."),
        ("Network AoI Tracker", "tests/test_network/test_aoi_tracker.py", "7", "Verifies linear sawtooth growth, peak AoI, sample/continuous average AoI, stale packet protection, and multi-vehicle isolation."),
        ("Bandwidth & Quota Model", "tests/test_network/test_bandwidth_model.py", "4", "Validates mathematical serialization formula T_ser = (size*8)/bps, windowed byte consumption, and quota reset triggers."),
        ("Network Delay Model", "tests/test_network/test_delay_model.py", "5", "Validates fixed delay conversion, uniform bounds [min, max], Gaussian delay non-negativity (causality), and input validation."),
        ("Network Emulator Facade", "tests/test_network/test_network_emulator.py", "3", "Tests frame ingestion, independent sensor packet splitting, missing sensor telemetry skip, and performance summary export."),
        ("Packet Loss Engine", "tests/test_network/test_packet_loss.py", "10", "Tests deterministic seed reproducibility, boundary probabilities (0.0 and 1.0), and empirical dropout rate convergence."),
        ("Packet Ordering & Staleness", "tests/test_network/test_packet_ordering.py", "5", "Tests sequence tracking, duplicate packet detection, out-of-order flagging, and stale packet rejection policies."),
        ("Packet Queue Min-Heap", "tests/test_network/test_packet_queue.py", "4", "Tests priority queue chronological delivery, delayed arrival sorting, packet loss drop handling, and empty queue safety."),
        ("Transmission Scheduler", "tests/test_network/test_transmission_scheduler.py", "5", "Verifies FIFO non-overlapping channel locking, single-packet serialization timing, and quota block/reject policies."),
        ("Baseline Anomaly Detector", "tests/test_digital_twin/test_anomaly_detector.py", "31", "Exhaustive tests for two-level thresholds, relative limits, N=3 persistence counters, categorical fan policy, and stream isolation."),
        ("Integrated Diagnostic Eval", "tests/test_digital_twin/test_evaluation.py", "15", "Tests Scenarios A through G end-to-end, true positive fault confirmation, detection delay Delta t, and summary export."),
        ("Experiment Campaign Runner", "tests/test_digital_twin/test_experiments.py", "16", "Validates campaign generation for groups A through H, parameter sweeps, CSV row export, JSON export, and manifest validity."),
        ("Digital Twin Data Models", "tests/test_digital_twin/test_models.py", "7", "Tests dataclass construction, enum serialization, automatic post-init residual computation, and dictionary formatting."),
        ("Nominal Vehicle Model", "tests/test_digital_twin/test_nominal_model.py", "8", "Tests physics prediction forward stepping, expected measurement synthesis, fan thermostat logic, and thermal conservation."),
        ("Residual Generator", "tests/test_digital_twin/test_residual_generator.py", "8", "Tests raw residuals, defensive relative residuals with epsilon, categorical fan handling, and missing telemetry safety."),
        ("State Estimator & Sync", "tests/test_digital_twin/test_state_estimator.py", "7", "Tests asynchronous telemetry fusion, duplicate/stale packet rejection, and sync status (SYNCHRONIZED, STALE, DISCONNECTED)."),
        ("Telemetry Freshness & AoI", "tests/test_digital_twin/test_telemetry_freshness.py", "22", "Tests 5 freshness tiers (FRESH, AGING, STALE, INVALID, MISSING), diagnostic eligibility gating, NaN/inf handling, and negative AoI causality protection."),
    ]

    test_table_data = [
        [
            Paragraph("<b>Test Suite Module</b>", table_header_style),
            Paragraph("<b>Test File Path</b>", table_header_style),
            Paragraph("<b>Tests</b>", table_header_style),
            Paragraph("<b>Key Verification Focus & Covered Subsystems</b>", table_header_style),
        ]
    ]

    for name, path, count, desc in test_breakdown:
        test_table_data.append([
            Paragraph(f"<b>{name}</b>", table_cell_bold),
            Paragraph(path, table_cell_code),
            Paragraph(f"<b>{count}</b>", table_cell_style),
            Paragraph(desc, table_cell_style),
        ])

    test_table_data.append([
        Paragraph("<b>TOTAL PASSING TESTS</b>", table_header_style),
        Paragraph("<b>All 17 Test Modules</b>", table_header_style),
        Paragraph("<b>163</b>", table_header_style),
        Paragraph("<b>100% Success Rate across entire Connected Vehicle Digital Twin Pipeline</b>", table_header_style),
    ])

    test_table = Table(test_table_data, colWidths=[108, 134, 30, 232], repeatRows=1)
    test_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, c_light]),
        ('BACKGROUND', (0, -1), (-1, -1), c_success),
        ('PADDING', (0, 0), (-1, -1), 2.2),
    ]))
    story.append(test_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 6: EXECUTION GUIDE & CLI COMMANDS
    # =========================================================================
    story.append(Paragraph("6. Quick Start & Practical Execution Guide", h1_style))
    story.append(Paragraph(
        "The entire system is executable directly from PowerShell or Linux terminal without requiring external database services:",
        body_style
    ))

    cli_examples = [
        ("Run All 163 Automated Unit Tests", "python -m pytest", "Executes full test suite across simulator, network, and digital twin modules in ~2.4 seconds."),
        ("Run Vehicle Simulator (Normal Scenario)", "python -m simulator.main --scenario normal --duration 30", "Simulates 30s driving cycle and prints formatted telemetry packets."),
        ("Run Vehicle Simulator (Fan Failure Fault)", "python -m simulator.main --scenario fan_failure --start-time 10 --duration 60", "Simulates fan failure at t=10s, observing engine temperature rise above 95 deg C."),
        ("Run Vehicle Simulator (Sensor Bias Fault)", "python -m simulator.main --scenario temp_sensor_bias --start-time 10 --bias-offset 20.0", "Injects +20 deg C offset on thermal sensor while physical state remains normal."),
        ("Run Research Campaign (Packet Loss Sweep)", "python -m digital_twin.run_experiments --group packet_loss --seeds 42 101 202", "Executes loss sweep (0% to 50%) across 3 seeds; exports results to CSV/JSON."),
        ("Run Research Campaign (Full Campaign Matrix)", "python -m digital_twin.run_experiments --all --output-dir experiments/results", "Runs all groups A through H, generating comprehensive empirical dataset."),
    ]

    cli_table_data = [
        [
            Paragraph("<b>Operation</b>", table_header_style),
            Paragraph("<b>Command Syntax</b>", table_header_style),
            Paragraph("<b>Description & Expected Outcome</b>", table_header_style),
        ]
    ]

    for op, cmd, cdesc in cli_examples:
        cli_table_data.append([
            Paragraph(f"<b>{op}</b>", table_cell_bold),
            Paragraph(f"<code>{cmd}</code>", table_cell_style),
            Paragraph(cdesc, table_cell_style),
        ])

    cli_table = Table(cli_table_data, colWidths=[120, 184, 200])
    cli_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_light]),
        ('PADDING', (0, 0), (-1, -1), 3.0),
    ]))
    story.append(cli_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 7: RESEARCH ROADMAP & NEXT PHASES
    # =========================================================================
    story.append(Paragraph("7. Strategic Roadmap & Next Development Phases", h1_style))
    story.append(Paragraph(
        "With Modules 1 through 5 fully implemented and verified, the project roadmap progresses towards advanced decision intelligence and active control:",
        body_style
    ))

    roadmap_items = [
        ("Phase 4: Multi-Hypothesis Bayesian Belief Tracker", "Implement recursive Bayesian belief estimation over discrete fault hypotheses (cooling fan failure vs. coolant leak vs. sensor bias vs. dynamic engine overload). Track diagnostic entropy H(b_k) to quantify uncertainty under packet loss."),
        ("Phase 5: Uncertainty- & Cost-Aware Active Action Engine", "Formulate a Partially Observable Markov Decision Process (POMDP) / Value of Information (VoI) framework that dynamically selects optimal actions: request high-rate burst telemetry, trigger edge ECU diagnostic routine (cycle fan), declare fault, or wait."),
        ("Phase 6: Comparative Benchmark Suite", "Benchmark proposed Active Digital Twin (ADT) against static OBD-II threshold alerts and passive anomaly observers across accuracy, false alarm rate, isolation latency, and cellular bandwidth consumption."),
        ("Phase 7: Interactive Web Analytics Dashboard", "Build a high-performance web dashboard displaying real-time vehicle twin kinematics, network AoI sawtooth curves, residual tracking, and Bayesian fault belief distributions."),
        ("Phase 8: Academic Manuscript & Patentability Dossier", "Compile final research results, LaTeX journal paper for IEEE Transactions / ACM conferences, and intellectual property comparison dossier."),
    ]

    for title, desc in roadmap_items:
        story.append(Paragraph(f"- <b>{title}:</b> {desc}", body_style))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 8: RESEARCH GLOSSARY & SCIENTIFIC DISTINCTION
    # =========================================================================
    story.append(Paragraph("8. Technical Glossary & Defensible Research Contribution", h1_style))
    story.append(Paragraph(
        "<b>Core Scientific Distinction:</b> The primary intellectual contribution of this research is the joint formulation of active diagnostic test selection under non-stationary network impairments (stochastic delay, packet loss, bandwidth budgets) and Age of Information (AoI) staleness constraints in connected vehicles.",
        body_style
    ))

    glossary_items = [
        ("Age of Information (AoI)", "Metric defining the elapsed duration since the generation of the newest delivered telemetry update: AoI(t) = t - u(t). Quantifies staleness rather than network latency."),
        ("Peak AoI", "Maximum staleness attained immediately prior to the arrival of a newer measurement update."),
        ("Diagnostic Eligibility", "Binary qualification gate ensuring that residual discrepancy evaluation is only conducted when telemetry age is strictly within trustworthy limits (FRESH: AoI <= 1.0s)."),
        ("Defensive Relative Residual", "Relative discrepancy normalized against expected value with epsilon protection: (y - y_hat) / max(|y_hat|, 1e-4), avoiding zero-division singularities at idle."),
        ("Alert Persistence (N=3)", "Temporal confirmation rule requiring consecutive anomalous samples to eliminate false alarms caused by transient sensor noise spikes or channel jitter."),
    ]

    glossary_data = [[Paragraph("<b>Concept / Metric</b>", table_header_style), Paragraph("<b>Mathematical & Operational Definition</b>", table_header_style)]]
    for c_name, c_def in glossary_items:
        glossary_data.append([Paragraph(f"<b>{c_name}</b>", table_cell_bold), Paragraph(c_def, table_cell_style)])

    glossary_table = Table(glossary_data, colWidths=[130, 374])
    glossary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secondary),
        ('GRID', (0, 0), (-1, -1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_light]),
        ('PADDING', (0, 0), (-1, -1), 3.0),
    ]))
    story.append(glossary_table)

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=c_primary, spaceBefore=4, spaceAfter=6))
    story.append(Paragraph(
        "<i>Document generated automatically for Annu Tiwari | Capstone Project Repository | Python 3.10 & ReportLab 4.4.3</i>",
        meta_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")


if __name__ == "__main__":
    output_pdf = "Capstone_Project_Comprehensive_Guide.pdf"
    if len(sys.argv) > 1:
        output_pdf = sys.argv[1]
    build_pdf(output_pdf)
