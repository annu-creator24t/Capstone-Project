/**
 * Connected Vehicle Digital Twin - Real-Time Dashboard Controller
 * Handles dynamic gauge rendering, HTML5 canvas real-time multi-stream graphs,
 * REST API communication, fault injection, and experimental campaign data exploration.
 */

// Application State
let isRunning = true;
let currentSpeedMultiplier = 1.0;
let pollIntervalTimer = null;
let campaignData = null;
let lastLogTimestamp = null;

// DOM Elements Cache
const elSimTime = document.getElementById('valSimTime');
const elSpeed = document.getElementById('valSpeed');
const elRpm = document.getElementById('valRpm');
const elLoad = document.getElementById('valLoad');
const elTemp = document.getElementById('valTemp');
const elFanWrapper = document.getElementById('fanIconWrapper');
const elFanStatus = document.getElementById('badgeFanStatus');
const elFanRelay = document.getElementById('valFanRelay');

// Gauge SVG Fills
const gaugeSpeedFill = document.getElementById('gaugeSpeedFill');
const gaugeRpmFill = document.getElementById('gaugeRpmFill');
const gaugeLoadFill = document.getElementById('gaugeLoadFill');
const gaugeTempFill = document.getElementById('gaugeTempFill');

// Alert Banner Elements
const cardAnomalyAlert = document.getElementById('cardAnomalyAlert');
const pillAnomalyStatus = document.getElementById('pillAnomalyStatus');
const valAlertSubtitle = document.getElementById('valAlertSubtitle');
const valPersistence = document.getElementById('valPersistence');
const badgeFreshness = document.getElementById('badgeFreshness');
const badgeEligibility = document.getElementById('badgeEligibility');
const valConfirmedCount = document.getElementById('valConfirmedCount');

// Network Elements
const valDeliveryRatio = document.getElementById('valDeliveryRatio');
const sliderPacketLoss = document.getElementById('sliderPacketLoss');
const valSliderLoss = document.getElementById('valSliderLoss');
const sliderDelay = document.getElementById('sliderDelay');
const valSliderDelay = document.getElementById('valSliderDelay');
const valPacketsSent = document.getElementById('valPacketsSent');
const valPacketsDelivered = document.getElementById('valPacketsDelivered');
const valPacketsDropped = document.getElementById('valPacketsDropped');
const valAoI = document.getElementById('valAoI');

// Digital Twin Panel Elements
const valObservedTemp = document.getElementById('valObservedTemp');
const valNominalTemp = document.getElementById('valNominalTemp');
const valResidualTemp = document.getElementById('valResidualTemp');
const residualMarker = document.getElementById('residualMarker');
const badgeDtState = document.getElementById('badgeDtState');

// Fault Cockpit Elements
const valActiveFaultLabel = document.getElementById('valActiveFaultLabel');

// Canvas Elements
const canvasTemp = document.getElementById('chartTempCanvas');
const ctxTemp = canvasTemp ? canvasTemp.getContext('2d') : null;
const canvasResidual = document.getElementById('chartResidualCanvas');
const ctxResidual = canvasResidual ? canvasResidual.getContext('2d') : null;

// Event Log
const logContainer = document.getElementById('logContainer');
const valLogCount = document.getElementById('valLogCount');

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
  setupCanvasDimensions();
  window.addEventListener('resize', setupCanvasDimensions);
  startPolling();
  loadCampaignData();
});

function setupCanvasDimensions() {
  if (canvasTemp) {
    canvasTemp.width = canvasTemp.parentElement.clientWidth * window.devicePixelRatio;
    canvasTemp.height = canvasTemp.parentElement.clientHeight * window.devicePixelRatio;
    ctxTemp.scale(window.devicePixelRatio, window.devicePixelRatio);
  }
  if (canvasResidual) {
    canvasResidual.width = canvasResidual.parentElement.clientWidth * window.devicePixelRatio;
    canvasResidual.height = canvasResidual.parentElement.clientHeight * window.devicePixelRatio;
    ctxResidual.scale(window.devicePixelRatio, window.devicePixelRatio);
  }
}

// -------------------------------------------------------------
// REST API Polling & Synchronization
// -------------------------------------------------------------

function startPolling() {
  if (pollIntervalTimer) clearInterval(pollIntervalTimer);
  pollIntervalTimer = setInterval(fetchSimulationState, 150);
}

async function fetchSimulationState() {
  try {
    const res = await fetch('/api/state');
    if (!res.ok) return;
    const data = await res.json();
    updateUI(data);
  } catch (err) {
    // Graceful silent recovery on momentary connection blips
  }
}

// -------------------------------------------------------------
// UI Updates from Simulation Snapshot
// -------------------------------------------------------------

function updateUI(data) {
  const latest = data.latest;
  if (!latest) return;

  // 1. Header & Time
  elSimTime.textContent = latest.time_s.toFixed(1) + 's';
  isRunning = data.is_running;
  document.getElementById('playText').textContent = isRunning ? 'Pause' : 'Resume';
  document.getElementById('playIcon').textContent = isRunning ? '⏸' : '▶';

  // 2. Instrument Cluster Gauges
  // Speed (0 - 120 km/h) -> stroke-dashoffset: 220 to 0
  const speed = latest.speed_kmh;
  elSpeed.textContent = speed.toFixed(1);
  const speedRatio = Math.min(1.0, Math.max(0.0, speed / 110.0));
  gaugeSpeedFill.style.strokeDashoffset = 220 - (220 * speedRatio);

  // RPM (0 - 6000 RPM)
  const rpm = latest.rpm;
  elRpm.textContent = Math.round(rpm);
  const rpmRatio = Math.min(1.0, Math.max(0.0, rpm / 5000.0));
  gaugeRpmFill.style.strokeDashoffset = 220 - (220 * rpmRatio);

  // Engine Load (0 - 100%)
  const load = latest.engine_load;
  elLoad.textContent = load.toFixed(1);
  const loadRatio = Math.min(1.0, Math.max(0.0, load / 100.0));
  gaugeLoadFill.style.strokeDashoffset = 220 - (220 * loadRatio);

  // Coolant Temp (60°C - 130°C)
  const temp = latest.physical_temp_c;
  elTemp.textContent = temp.toFixed(1);
  const tempRatio = Math.min(1.0, Math.max(0.0, (temp - 60.0) / 70.0));
  gaugeTempFill.style.strokeDashoffset = 220 - (220 * tempRatio);

  // Coolant Temp Gauge Color shift based on heat
  if (temp > 105.0) {
    gaugeTempFill.style.stroke = 'var(--accent-rose)';
  } else if (temp > 95.0) {
    gaugeTempFill.style.stroke = 'var(--accent-amber)';
  } else {
    gaugeTempFill.style.stroke = 'var(--accent-emerald)';
  }

  // 3. Cooling Fan Actuator
  const fanActive = latest.cooling_fan_status === 1;
  const fanFault = latest.cooling_fan_fault === true;
  if (fanActive) {
    elFanWrapper.classList.add('fan-spinning');
    elFanStatus.textContent = 'ACTIVE (ON)';
    elFanStatus.className = 'badge-status badge-fresh';
  } else {
    elFanWrapper.classList.remove('fan-spinning');
    elFanStatus.textContent = 'OFF (STANDBY)';
    elFanStatus.className = 'badge-status badge-mono';
  }

  if (fanFault) {
    elFanRelay.textContent = 'RELAY FAILURE (OFF)';
    elFanRelay.style.color = 'var(--accent-rose)';
  } else {
    elFanRelay.textContent = 'Nominal Functional';
    elFanRelay.style.color = 'var(--accent-emerald)';
  }

  // 4. Anomaly Alert Cockpit & Banner
  const isConfirmed = latest.is_confirmed;
  const alertLevel = latest.anomaly_level;
  const persistence = latest.persistence;

  valPersistence.textContent = `${persistence} / 3`;
  valConfirmedCount.textContent = latest.confirmed_count;

  cardAnomalyAlert.classList.remove('alert-warning', 'alert-danger');
  if (isConfirmed) {
    cardAnomalyAlert.classList.add('alert-danger');
    pillAnomalyStatus.textContent = 'CONFIRMED ANOMALY';
    valAlertSubtitle.textContent = `Physical/Sensor discrepancy verified over ${persistence} cycles!`;
  } else if (alertLevel === 'warning') {
    cardAnomalyAlert.classList.add('alert-warning');
    pillAnomalyStatus.textContent = 'WARNING';
    valAlertSubtitle.textContent = `Residual elevated (|r| = ${latest.residual_temp_c}°C) - Gating persistence...`;
  } else {
    pillAnomalyStatus.textContent = 'NORMAL';
    valAlertSubtitle.textContent = 'Residual within nominal bounds (< 5.0°C)';
  }

  // Freshness & Eligibility
  badgeFreshness.textContent = latest.freshness.toUpperCase();
  badgeFreshness.className = `badge-status badge-${latest.freshness.toLowerCase()}`;

  badgeEligibility.textContent = latest.is_eligible ? 'ELIGIBLE' : 'NOT EVALUATED';
  badgeEligibility.className = latest.is_eligible
    ? 'badge-status badge-fresh'
    : 'badge-status badge-stale';

  // 5. Network Panel
  valDeliveryRatio.textContent = `${latest.packet_delivery_rate}% PDR`;
  valPacketsSent.textContent = latest.packets_transmitted.toLocaleString();
  valPacketsDelivered.textContent = latest.packets_delivered.toLocaleString();
  valPacketsDropped.textContent = latest.packets_dropped.toLocaleString();
  valAoI.textContent = `${latest.aoi_ms.toFixed(1)} ms`;

  // 6. Cloud Digital Twin Estimator Panel
  valObservedTemp.textContent = `${latest.observed_temp_c.toFixed(1)}°C`;
  valNominalTemp.textContent = `${latest.nominal_temp_c.toFixed(1)}°C`;
  const sign = latest.residual_temp_c >= 0 ? '+' : '';
  valResidualTemp.textContent = `${sign}${latest.residual_temp_c.toFixed(2)}°C`;

  if (Math.abs(latest.residual_temp_c) > 8.0) {
    valResidualTemp.style.color = 'var(--accent-rose)';
    badgeDtState.textContent = 'FAULT DETECTED';
    badgeDtState.className = 'badge-status badge-stale';
  } else if (Math.abs(latest.residual_temp_c) > 5.0) {
    valResidualTemp.style.color = 'var(--accent-amber)';
    badgeDtState.textContent = 'DIVERGING';
    badgeDtState.className = 'badge-status badge-aging';
  } else {
    valResidualTemp.style.color = 'var(--accent-emerald)';
    badgeDtState.textContent = 'SYNCHRONIZED';
    badgeDtState.className = 'badge-status badge-fresh';
  }

  // Residual Track Marker position (0°C to 15°C maps to 0% to 100%)
  const resMarkerPct = Math.min(100, Math.max(0, (Math.abs(latest.residual_temp_c) / 15.0) * 100));
  residualMarker.style.left = `${resMarkerPct}%`;

  // 7. Active Fault Indicator in Cockpit
  valActiveFaultLabel.textContent = latest.current_fault.toUpperCase();
  updateActiveFaultButton(latest.current_fault);

  // 8. Event Log Updates
  if (data.alerts && data.alerts.length > 0) {
    renderAlertLogs(data.alerts);
  }

  // 9. Real-time Multi-Stream Graphs
  if (data.history && data.history.length > 1) {
    renderCharts(data.history);
  }
}

function updateActiveFaultButton(faultType) {
  const btnMap = {
    normal: 'btnFaultNormal',
    fan_failure: 'btnFaultFan',
    temp_sensor_bias: 'btnFaultBias',
    temp_sensor_freeze: 'btnFaultFreeze',
    high_load: 'btnFaultLoad',
  };
  document.querySelectorAll('.btn-fault').forEach((btn) => btn.classList.remove('active'));
  const activeId = btnMap[faultType];
  if (activeId && document.getElementById(activeId)) {
    document.getElementById(activeId).classList.add('active');
  }
}

function renderAlertLogs(alerts) {
  valLogCount.textContent = `${alerts.length} events`;
  logContainer.innerHTML = alerts
    .map(
      (a) => `
    <div class="log-entry log-entry-${a.level.toLowerCase()}">
      <span class="log-time">${a.timestamp}</span>
      <span class="log-tag tag-${a.level.toLowerCase()}">${a.level}</span>
      <span class="log-msg">${a.message}</span>
    </div>
  `
    )
    .join('');
}

// -------------------------------------------------------------
// Real-Time Canvas Graph Rendering
// -------------------------------------------------------------

function renderCharts(history) {
  if (!ctxTemp || !ctxResidual) return;

  const w = canvasTemp.parentElement.clientWidth;
  const h = canvasTemp.parentElement.clientHeight;

  // Clear Canvases
  ctxTemp.clearRect(0, 0, w, h);
  ctxResidual.clearRect(0, 0, w, h);

  // Draw Grid Lines on both
  drawGrid(ctxTemp, w, h);
  drawGrid(ctxResidual, w, h);

  // 1. Chart 1: Temperatures (60°C to 125°C)
  const minTemp = 65;
  const maxTemp = 125;
  const tempRange = maxTemp - minTemp;

  // Observed Line (Cyan)
  drawLineSeries(
    ctxTemp,
    history,
    (d) => h - ((d.observed_temp_c - minTemp) / tempRange) * (h - 20) - 10,
    '#38bdf8',
    2.5
  );

  // Nominal Line (Indigo)
  drawLineSeries(
    ctxTemp,
    history,
    (d) => h - ((d.nominal_temp_c - minTemp) / tempRange) * (h - 20) - 10,
    '#818cf8',
    2.0,
    [4, 4]
  );

  // 2. Chart 2: Residual (0 to 20°C) & Threshold Line (8°C)
  const maxResidual = 20;

  // Warning Threshold Line (5°C)
  const yWarn = h - (5.0 / maxResidual) * (h - 20) - 10;
  ctxResidual.beginPath();
  ctxResidual.setLineDash([3, 3]);
  ctxResidual.strokeStyle = 'rgba(245, 158, 11, 0.4)';
  ctxResidual.lineWidth = 1;
  ctxResidual.moveTo(0, yWarn);
  ctxResidual.lineTo(w, yWarn);
  ctxResidual.stroke();

  // Anomaly Threshold Line (8°C)
  const yAnom = h - (8.0 / maxResidual) * (h - 20) - 10;
  ctxResidual.beginPath();
  ctxResidual.setLineDash([4, 4]);
  ctxResidual.strokeStyle = 'rgba(244, 63, 94, 0.6)';
  ctxResidual.lineWidth = 1.5;
  ctxResidual.moveTo(0, yAnom);
  ctxResidual.lineTo(w, yAnom);
  ctxResidual.stroke();
  ctxResidual.setLineDash([]);

  // Residual Line (Amber)
  drawLineSeries(
    ctxResidual,
    history,
    (d) => h - (Math.min(maxResidual, Math.abs(d.residual_temp_c)) / maxResidual) * (h - 20) - 10,
    '#fbbf24',
    2.5
  );
}

function drawGrid(ctx, w, h) {
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let y = 20; y < h; y += 40) {
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
  }
  for (let x = 40; x < w; x += 60) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
  }
  ctx.stroke();
}

function drawLineSeries(ctx, data, yAccessor, color, lineWidth = 2, dash = []) {
  if (data.length < 2) return;
  const w = ctx.canvas.parentElement.clientWidth;
  const stepX = w / (data.length - 1);

  ctx.beginPath();
  ctx.setLineDash(dash);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;

  data.forEach((item, index) => {
    const x = index * stepX;
    const y = yAccessor(item);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();
  ctx.setLineDash([]);
}

// -------------------------------------------------------------
// Interactive User Actions & Control API
// -------------------------------------------------------------

async function togglePlayPause() {
  isRunning = !isRunning;
  await postControl({ is_running: isRunning });
}

async function stepSimulation() {
  try {
    const res = await fetch('/api/step', { method: 'POST' });
    const record = await res.json();
    fetchSimulationState();
  } catch (err) {}
}

async function resetSimulation() {
  try {
    await fetch('/api/reset', { method: 'POST' });
    fetchSimulationState();
  } catch (err) {}
}

async function setSpeed(speed) {
  currentSpeedMultiplier = speed;
  document.querySelectorAll('.btn-speed').forEach((btn) => {
    btn.classList.toggle('active', btn.textContent === `${speed}x`);
  });
  await postControl({ speed: speed });
}

async function setFaultMode(faultType, biasOffset = 15.0) {
  await postControl({
    fault_type: faultType,
    bias_offset_c: biasOffset,
  });
  fetchSimulationState();
}

async function onNetworkParamChange() {
  const lossVal = parseFloat(sliderPacketLoss.value);
  const delayVal = parseFloat(sliderDelay.value);

  valSliderLoss.textContent = `${lossVal}%`;
  valSliderDelay.textContent = `${delayVal} ms`;

  await postControl({
    loss_rate: lossVal / 100.0,
    delay_ms: delayVal,
  });
}

async function postControl(payload) {
  try {
    await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (err) {}
}

function clearAlertLog() {
  logContainer.innerHTML = '<div class="log-entry log-entry-info"><span class="log-time">Now</span><span class="log-tag tag-info">INFO</span><span class="log-msg">Alert history cleared.</span></div>';
  valLogCount.textContent = '0 events';
}

// -------------------------------------------------------------
// TAB 2: Research Campaign Explorer
// -------------------------------------------------------------

function switchTab(tabId) {
  document.querySelectorAll('.nav-tab').forEach((t) => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach((c) => c.classList.remove('active'));

  if (tabId === 'live') {
    document.getElementById('tabBtnLive').classList.add('active');
    document.getElementById('tabLive').classList.add('active');
    setupCanvasDimensions();
  } else {
    document.getElementById('tabBtnCampaign').classList.add('active');
    document.getElementById('tabCampaign').classList.add('active');
    if (!campaignData) loadCampaignData();
  }
}

async function loadCampaignData() {
  try {
    const res = await fetch('/api/campaign');
    if (!res.ok) return;
    campaignData = await res.json();
    populateCampaignTable(campaignData);
  } catch (err) {
    const tbody = document.getElementById('campaignTableBody');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color: var(--accent-rose); padding: 20px;">Run full campaign via `python -m digital_twin.run_experiments --all` to populate dataset.</td></tr>';
    }
  }
}

function filterCampaignTable() {
  const selectedGroup = document.getElementById('selectGroupFilter').value;
  if (!campaignData) return;

  const filtered =
    selectedGroup === 'ALL'
      ? campaignData
      : campaignData.filter((r) => r.group.toLowerCase().includes(selectedGroup.toLowerCase()));

  document.getElementById('valFilteredRunCount').textContent = `Showing ${filtered.length} of ${campaignData.length} runs`;
  populateCampaignTable(filtered);
}

function populateCampaignTable(runs) {
  const tbody = document.getElementById('campaignTableBody');
  if (!tbody || !runs) return;

  tbody.innerHTML = runs
    .map((r) => {
      const confirmedCount = r.confirmed_anomaly_count ?? r.anomaly_confirmed_count ?? 0;
      const isAnom = confirmedCount > 0;
      const statusPill = isAnom
        ? `<span class="badge-status badge-stale">CONFIRMED (${confirmedCount})</span>`
        : `<span class="badge-status badge-fresh">HEALTHY</span>`;

      return `
      <tr>
        <td style="color: var(--accent-cyan);">${r.experiment_id}</td>
        <td><span class="badge-mono">${r.group}</span></td>
        <td>${r.fault_type} ${r.fault_magnitude > 0 ? `(+${r.fault_magnitude}°C)` : ''}</td>
        <td class="${r.packet_loss_rate > 0 ? 'text-rose' : ''}">${(r.packet_loss_rate * 100).toFixed(0)}%</td>
        <td>${r.delay_ms.toFixed(0)} ms</td>
        <td>${r.total_generated_frames}</td>
        <td class="text-emerald">${r.total_packets_delivered}</td>
        <td>${r.fresh_count}</td>
        <td class="${isAnom ? 'text-rose' : 'text-emerald'}">${confirmedCount}</td>
        <td>${statusPill}</td>
      </tr>
    `;
    })
    .join('');
}
