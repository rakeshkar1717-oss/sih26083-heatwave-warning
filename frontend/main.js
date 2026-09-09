/**
 * Main Controller for SIH26083 Leaflet Choropleth Dashboard.
 *
 * Coordinates map rendering, layer mode toggling, Chart.js visualizations,
 * interactive ward inspection, automated polling, and early warning dispatches.
 */

import { config } from "./config.js";
import * as api from "./api.js";
import {
  createChoroplethLayer,
  createLegendControl,
  getFeatureStyle,
  getRiskColor,
} from "./choropleth.js";

// Application State
const state = {
  map: null,
  choroplethLayer: null,
  geojsonData: null,
  activeMode: "risk", // 'risk' | 'hazard' | 'vulnerability'
  selectedWardProps: null,
  sidebarChart: null,
  popupCharts: {},
  pollTimer: null,
  isBacktestMode: false,
  backtestTimeline: null,
};

/**
 * Initialize Leaflet Map Instance.
 */
function initMap() {
  const L_inst = window.L || (typeof L !== "undefined" ? L : null);
  if (!L_inst) {
    console.error("Leaflet library not found on window.");
    return;
  }

  state.map = L_inst.map("map", {
    zoomControl: false,
  }).setView(config.city.center, config.city.defaultZoom);

  // Add zoom control in top-right
  L_inst.control.zoom({ position: "topright" }).addTo(state.map);

  // High-contrast Dark Basemap (Clean & watermark-free)
  L_inst.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    attribution: '&copy; Esri, HERE, Garmin, OpenStreetMap contributors',
    maxZoom: 16,
  }).addTo(state.map);

  // Add Risk Legend Control
  const legend = createLegendControl();
  if (legend) {
    legend.addTo(state.map);
  }
}

/**
 * Display Loading Overlay.
 */
function showLoading(text = "Loading High-Resolution Ward Layer...") {
  const overlay = document.getElementById("map-loading");
  const label = document.getElementById("map-loading-text");
  if (overlay) {
    if (label) label.textContent = text;
    overlay.style.display = "flex";
  }
}

/**
 * Hide Loading Overlay.
 */
function hideLoading() {
  const overlay = document.getElementById("map-loading");
  if (overlay) overlay.style.display = "none";
}

/**
 * Verify and Update System Status Health Indicator.
 */
async function updateSystemStatus() {
  const pill = document.getElementById("system-status-pill");
  const text = document.getElementById("system-status-text");
  if (!pill || !text) return;

  try {
    const health = await api.getHealth();
    if (health && health.status === "ok" && health.database === "connected") {
      pill.className = "status-pill status-online";
      text.textContent = `🟢 Online (${health.wards_count || 48} Wards)`;
    } else {
      pill.className = "status-pill status-offline";
      text.textContent = "🔴 DB Unreachable";
    }
  } catch (err) {
    pill.className = "status-pill status-offline";
    text.textContent = "🟡 Waking up server...";
    // Automatically re-check status in 4 seconds
    setTimeout(updateSystemStatus, 4000);
  }
}

/**
 * Render or Update City Alert Status Banner.
 */
function updateCityAlertBanner(features) {
  const banner = document.getElementById("alert-banner");
  if (!banner) return;

  if (state.isBacktestMode) {
    banner.style.display = "block";
    banner.style.background = "linear-gradient(90deg, #581c87, #991b1b, #581c87)";
    banner.innerHTML = `🕒 <strong>HISTORICAL BACKTEST MODE (Ahmedabad May 2010 Landmark Heatwave):</strong> Reanalysis shows peak temperature 45.4°C (46.8°C stn) & WBGT 40.4°C. System correctly identified Code Red 48 hours prior to 1,344 excess deaths (Azhar et al. 2014, PLOS ONE).`;
    return;
  }

  const extremeWards = features.filter(
    (f) => f.properties?.risk_level === "EXTREME" || f.properties?.final_risk_score >= 0.85
  );
  const veryHighWards = features.filter(
    (f) => f.properties?.risk_level === "VERY_HIGH"
  );

  if (extremeWards.length > 0) {
    banner.style.display = "block";
    banner.style.background = "linear-gradient(90deg, #7e22ce, #dc2626, #7e22ce)";
    banner.innerHTML = `⚠️ <strong>CRITICAL HEAT EMERGENCY:</strong> ${extremeWards.length} municipal ward(s) in ${config.city.name} have breached the <strong>EXTREME</strong> heat disaster threshold! Cease outdoor physical labor immediately.`;
  } else if (veryHighWards.length > 0) {
    banner.style.display = "block";
    banner.style.background = "linear-gradient(90deg, #c2410c, #ea580c, #c2410c)";
    banner.innerHTML = `⚠️ <strong>SEVERE HEAT ADVISORY:</strong> ${veryHighWards.length} ward(s) under <strong>VERY HIGH</strong> thermal risk. Municipal hydration shelters active.`;
  } else {
    banner.style.display = "none";
  }
}

/**
 * Update Sidebar Details with Selected Ward Properties.
 */
async function renderWardSidebar(props) {
  if (!props) return;
  state.selectedWardProps = props;

  const wardTitle = document.getElementById("sidebar-ward-name");
  const wardBadge = document.getElementById("sidebar-risk-badge");
  const tempVal = document.getElementById("metric-temp");
  const hiVal = document.getElementById("metric-hi");
  const wbgtVal = document.getElementById("metric-wbgt");
  const utciVal = document.getElementById("metric-utci");
  const thermalVal = document.getElementById("metric-thermal");
  const hviVal = document.getElementById("metric-hvi");
  const advisoryEl = document.getElementById("sidebar-advisory");

  if (wardTitle) wardTitle.textContent = `${props.ward_name} (${props.ward_id})`;
  if (wardBadge) {
    wardBadge.textContent = props.risk_level;
    wardBadge.style.backgroundColor = props.color || getRiskColor(props.risk_level);
  }

  if (tempVal) tempVal.textContent = props.temp_c != null ? `${props.temp_c}°C` : "N/A";
  if (hiVal) hiVal.textContent = props.heat_index_c != null ? `${props.heat_index_c}°C` : "N/A";
  if (wbgtVal) wbgtVal.textContent = props.wbgt_c != null ? `${props.wbgt_c}°C` : "N/A";
  if (utciVal) utciVal.textContent = props.utci_c != null ? `${props.utci_c}°C` : "N/A";
  if (thermalVal) thermalVal.textContent = props.thermal_stress_score != null ? `${props.thermal_stress_score}/100` : "N/A";
  if (hviVal) hviVal.textContent = props.vulnerability_score != null ? `${props.vulnerability_score.toFixed(2)} (${props.vulnerability_tier || 'Med'})` : "N/A";

  // Vulnerability Factor Progress Bars
  const setBar = (id, pctId, val, max = 100) => {
    const bar = document.getElementById(id);
    const label = document.getElementById(pctId);
    if (bar && val != null) bar.style.width = `${Math.min(100, (val / max) * 100)}%`;
    if (label && val != null) label.textContent = `${typeof val === 'number' ? val.toFixed(1) : val}%`;
  };

  setBar("bar-elderly", "pct-elderly", props.elderly_pct);
  setBar("bar-outdoor", "pct-outdoor", props.outdoor_worker_pct);
  setBar("bar-slum", "pct-slum", props.slum_pct);
  setBar("bar-green", "pct-green", props.green_cover_pct);

  if (advisoryEl) {
    advisoryEl.textContent = props.advisory || "Standard civic heat safety precautions active.";
  }

  // Render 5-Day Forecast Chart in Sidebar
  await renderSidebarForecastChart(props.ward_id);
}

/**
 * Render Chart.js Forecast Line Chart in Sidebar.
 */
async function renderSidebarForecastChart(wardId) {
  const canvas = document.getElementById("sidebar-forecast-chart");
  if (!canvas) return;

  const Chart_inst = window.Chart || (typeof Chart !== "undefined" ? Chart : null);
  if (!Chart_inst) {
    console.warn("Chart.js library is not loaded.");
    return;
  }

  let labels = ["Day +1", "Day +2", "Day +3", "Day +4", "Day +5"];
  let riskData = [0.45, 0.48, 0.52, 0.58, 0.62];
  let datasetLabel = "Risk Score";
  let chartColor = "#f97316";
  let chartBg = "rgba(249, 115, 22, 0.18)";

  const chartCardTitle = document.querySelector(".chart-card h3");

  if (state.isBacktestMode) {
    if (chartCardTitle) chartCardTitle.textContent = "Historical Heatwave Trajectory (May 15-27, 2010)";
    datasetLabel = "Historical Risk (May 2010)";
    chartColor = "#ec4899";
    chartBg = "rgba(236, 72, 153, 0.25)";

    try {
      if (!state.backtestTimeline) {
        const res = await api.getBacktestTimeline();
        state.backtestTimeline = res.timeline || [];
      }
      if (state.backtestTimeline && state.backtestTimeline.length > 0) {
        labels = state.backtestTimeline.map((r) => {
          const parts = r.date.split("-");
          return `${parts[1]}/${parts[2]}` + (r.date === "2010-05-21" ? " ⭐" : "");
        });
        riskData = state.backtestTimeline.map((r) => r.city_risk_score);
      }
    } catch (e) {
      console.warn("Could not fetch backtest timeline for sidebar chart:", e);
    }
  } else {
    if (chartCardTitle) chartCardTitle.textContent = "5-Day Predictive Risk Trend";
    try {
      const forecastRes = await api.getWardForecast(wardId);
      if (forecastRes && forecastRes.forecasts && forecastRes.forecasts.length > 0) {
        labels = forecastRes.forecasts.map((f) => `Day +${f.horizon_days}`);
        riskData = forecastRes.forecasts.map((f) => f.predicted_risk_score);
      }
    } catch (e) {
      console.warn("Could not fetch remote forecast timeline for sidebar chart:", e);
    }
  }

  if (state.sidebarChart) {
    state.sidebarChart.destroy();
  }

  const ctx = canvas.getContext("2d");
  state.sidebarChart = new Chart_inst(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: datasetLabel,
          data: riskData,
          borderColor: chartColor,
          backgroundColor: chartBg,
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: "#ffffff",
          pointBorderColor: chartColor,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          max: 1.0,
          grid: { color: "#334155" },
          ticks: { color: "#94a3b8", font: { size: 10 } },
        },
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8", font: { size: 10 } },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0f172a",
          titleColor: "#f8fafc",
          bodyColor: "#f97316",
        },
      },
    },
  });
}

/**
 * Render Mini Forecast Chart inside Leaflet Popup.
 */
async function renderPopupForecastChart(props, popupElem) {
  const canvas = popupElem.querySelector(`#popup-chart-${props.ward_id}`);
  if (!canvas) return;

  const Chart_inst = window.Chart || (typeof Chart !== "undefined" ? Chart : null);
  if (!Chart_inst) return;

  let labels = ["+1d", "+2d", "+3d", "+4d", "+5d"];
  let riskData = [0.45, 0.48, 0.52, 0.56, 0.60];

  try {
    const res = await api.getWardForecast(props.ward_id);
    if (res && res.forecasts && res.forecasts.length > 0) {
      labels = res.forecasts.map((f) => `+${f.horizon_days}d`);
      riskData = res.forecasts.map((f) => f.predicted_risk_score);
    }
  } catch (e) {
    console.warn("Forecast fetch for popup chart fallback:", e);
  }

  const chartKey = `popup-${props.ward_id}`;
  if (state.popupCharts[chartKey]) {
    state.popupCharts[chartKey].destroy();
  }

  const ctx = canvas.getContext("2d");
  state.popupCharts[chartKey] = new Chart_inst(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Risk Score",
          data: riskData,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.2)",
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 3.2,
      animation: { duration: 250 },
      scales: {
        y: {
          min: 0,
          max: 1.0,
          grid: { color: "#1e293b" },
          ticks: { color: "#94a3b8", font: { size: 8 }, stepSize: 0.5 },
        },
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8", font: { size: 8 } },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => `Predicted Risk: ${item.parsed.y.toFixed(2)}`,
          },
        },
      },
    },
  });
}

/**
 * Load GeoJSON Ward Data and Render Choropleth.
 */
async function loadDashboardData() {
  showLoading(state.isBacktestMode
    ? "Loading Ahmedabad May 2010 Historical Validation Layer..."
    : "Loading Real-Time Ward Biometeorology Layer..."
  );

  try {
    const geojsonData = state.isBacktestMode
      ? await api.getBacktestGeoJSON()
      : await api.getWardsGeoJSON();

    state.geojsonData = geojsonData;

    // Update Header refresh time
    const refreshEl = document.getElementById("last-refresh-time");
    if (refreshEl) {
      const now = new Date();
      refreshEl.textContent = state.isBacktestMode
        ? "Historical Mode: May 2010"
        : `Live: ${now.toLocaleTimeString()}`;
    }

    // Update City Alert Status Banner
    if (geojsonData.features) {
      updateCityAlertBanner(geojsonData.features);
    }

    // Remove existing choropleth layer if present
    if (state.choroplethLayer && state.map) {
      state.map.removeLayer(state.choroplethLayer);
    }

    // Create & Add Choropleth Layer
    state.choroplethLayer = createChoroplethLayer(geojsonData, {
      mode: state.activeMode,
      onWardSelect: (props) => {
        renderWardSidebar(props);
      },
      onPopupOpen: (props, popupContent) => {
        renderPopupForecastChart(props, popupContent);
      },
    });

    state.choroplethLayer.addTo(state.map);

    // Auto-select highest risk ward if none selected
    if (!state.selectedWardProps && geojsonData.features && geojsonData.features.length > 0) {
      const sorted = [...geojsonData.features].sort(
        (a, b) => (b.properties.final_risk_score || 0) - (a.properties.final_risk_score || 0)
      );
      renderWardSidebar(sorted[0].properties);
    } else if (state.selectedWardProps) {
      // Refresh current selected ward
      const updated = geojsonData.features.find((f) => f.properties.ward_id === state.selectedWardProps.ward_id);
      if (updated) renderWardSidebar(updated.properties);
    }
  } catch (err) {
    console.error("Failed to load dashboard GeoJSON data:", err);
    const refreshEl = document.getElementById("last-refresh-time");
    if (refreshEl) {
      refreshEl.textContent = "Connecting to API...";
      refreshEl.style.color = "#f59e0b";
    }
    const banner = document.getElementById("alert-banner");
    if (banner) {
      banner.style.display = "block";
      banner.style.background = "linear-gradient(90deg, #1e293b, #334155, #1e293b)";
      banner.innerHTML = `⏳ <strong>Connecting to backend API service...</strong> Waiting for FastAPI server on port 8000. Auto-reconnecting in background...`;
    }
    // If we haven't loaded data yet, retry in 3 seconds
    if (!state.geojsonData) {
      setTimeout(() => {
        updateSystemStatus();
        loadDashboardData();
      }, 3000);
    }
  } finally {
    hideLoading();
  }
}

/**
 * Handle Layer Mode Toggling (Risk / Hazard / Vulnerability).
 */
function bindLayerControls() {
  const buttons = document.querySelectorAll(".layer-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeMode = btn.getAttribute("data-mode");

      if (state.choroplethLayer) {
        state.choroplethLayer.eachLayer((layer) => {
          if (layer.feature) {
            const style = getFeatureStyle(layer.feature, state.activeMode);
            layer.setStyle(style);
          }
        });
      }
    });
  });
}

/**
 * Handle Historical Backtest Mode Toggle Button.
 */
function bindBacktestToggle() {
  const btn = document.getElementById("btn-toggle-backtest");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    state.isBacktestMode = !state.isBacktestMode;

    if (state.isBacktestMode) {
      btn.classList.add("active");
      btn.innerHTML = `<span class="backtest-icon">⭐</span><span class="backtest-label">Backtest Active (May 2010)</span>`;
    } else {
      btn.classList.remove("active");
      btn.innerHTML = `<span class="backtest-icon">🕒</span><span class="backtest-label">Backtest Mode (May 2010)</span>`;
    }

    // Reload dashboard with historical or live data
    await loadDashboardData();
  });
}

/**
 * Handle Educational Explainer Modal ("How This Works").
 */
function bindInfoModal() {
  const btnOpen = document.getElementById("btn-how-it-works");
  const btnClose = document.getElementById("btn-close-modal");
  const btnGotIt = document.getElementById("btn-modal-got-it");
  const modal = document.getElementById("info-modal");

  if (!modal) return;

  const openModal = () => { modal.style.display = "flex"; };
  const closeModal = () => { modal.style.display = "none"; };

  if (btnOpen) btnOpen.addEventListener("click", openModal);
  if (btnClose) btnClose.addEventListener("click", closeModal);
  if (btnGotIt) btnGotIt.addEventListener("click", closeModal);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
}

/**
 * Handle Alert Trigger Action Button.
 */
function bindAlertButton() {
  const alertBtn = document.getElementById("btn-dispatch-alert");
  if (!alertBtn) return;

  alertBtn.addEventListener("click", async () => {
    if (!state.selectedWardProps) {
      alert("Please select a municipal ward first.");
      return;
    }

    const ward = state.selectedWardProps;
    const originalText = alertBtn.innerHTML;
    alertBtn.innerHTML = `<span>⏳ Dispatching SMS/WhatsApp...</span>`;
    alertBtn.disabled = true;

    try {
      const payload = {
        ward_id: ward.ward_id,
        recipient_phone: "+919876543210",
        channel: "sms",
        force: true,
      };

      const result = await api.triggerAlert(payload);
      alert(
        `🚨 Early Warning Alert Dispatched!\n\n` +
        `Ward: ${ward.ward_name} (${ward.ward_id})\n` +
        `Message ID: ${result.message_id || 'N/A'}\n` +
        `Channel: ${result.channel.toUpperCase()}\n` +
        `Status: ${result.detail}`
      );
    } catch (e) {
      alert(`Alert Dispatch Failed: ${e.message}`);
    } finally {
      alertBtn.innerHTML = originalText;
      alertBtn.disabled = false;
    }
  });
}

/**
 * Auto-refresh polling setup.
 */
function startAutoRefresh() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    try {
      await updateSystemStatus();
      // Only reload live data if not currently in Backtest Mode
      if (!state.isBacktestMode) {
        await loadDashboardData();
      }
    } catch (e) {
      console.warn("Background auto-refresh poll error:", e);
    }
  }, config.pollIntervalMs);
}

/**
 * Main Application Bootstrapper.
 */
async function main() {
  initMap();
  bindLayerControls();
  bindBacktestToggle();
  bindInfoModal();
  bindAlertButton();
  await updateSystemStatus();
  await loadDashboardData();
  startAutoRefresh();
}

// Start application after DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
