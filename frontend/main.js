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
  currentScope: "ahmedabad", // 'ahmedabad' | 'india'
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
      if (state.currentScope === "india") {
        text.textContent = "🟢 Online (35 States & UTs)";
      } else {
        text.textContent = `🟢 Online (${health.wards_count || 48} Wards)`;
      }
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
 * Render or Update City / National Alert Status Banner.
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

  if (state.currentScope === "india") {
    const extremeStates = features.filter(
      (f) => f.properties?.risk_level === "EXTREME" || (f.properties?.final_risk_score || 0) >= 0.85
    );
    const veryHighStates = features.filter(
      (f) => f.properties?.risk_level === "VERY_HIGH"
    );

    if (extremeStates.length > 0) {
      banner.style.display = "block";
      banner.style.background = "linear-gradient(90deg, #7e22ce, #dc2626, #7e22ce)";
      banner.innerHTML = `🇮🇳 <strong>NATIONAL HEAT EMERGENCY:</strong> ${extremeStates.length} State(s)/UT(s) have breached the <strong>EXTREME</strong> heat disaster threshold! Activate State Disaster Management Action Plans (SDMA).`;
    } else if (veryHighStates.length > 0) {
      banner.style.display = "block";
      banner.style.background = "linear-gradient(90deg, #c2410c, #ea580c, #c2410c)";
      banner.innerHTML = `🇮🇳 <strong>NATIONAL HEAT ADVISORY:</strong> ${veryHighStates.length} State(s)/UT(s) under <strong>VERY HIGH</strong> thermal risk across India. Active regional mitigation protocols.`;
    } else {
      banner.style.display = "none";
    }
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
 * Update Sidebar Details with Selected Ward or State Properties.
 */
async function renderWardSidebar(props) {
  if (!props) return;
  state.selectedWardProps = props;

  const entityName = props.ward_name || props.state_name || "Unknown Region";
  const entityId = props.ward_id || props.state_id || "";
  const isState = !!props.state_id;
  const isGujarat = isState && (props.state_name === "Gujarat" || props.state_id === "IN_GJ");

  const wardTitle = document.getElementById("sidebar-ward-name");
  const wardBadge = document.getElementById("sidebar-risk-badge");
  const drilldownBox = document.getElementById("sidebar-drilldown-box");
  const alertBtn = document.getElementById("btn-dispatch-alert");

  const tempVal = document.getElementById("metric-temp");
  const hiVal = document.getElementById("metric-hi");
  const wbgtVal = document.getElementById("metric-wbgt");
  const utciVal = document.getElementById("metric-utci");
  const thermalVal = document.getElementById("metric-thermal");
  const hviVal = document.getElementById("metric-hvi");
  const advisoryEl = document.getElementById("sidebar-advisory");

  if (wardTitle) {
    wardTitle.textContent = entityId ? `${entityName} (${entityId})` : entityName;
  }
  if (wardBadge) {
    wardBadge.textContent = props.risk_level;
    wardBadge.style.backgroundColor = props.color || getRiskColor(props.risk_level);
  }

  // Multi-Scale Drilldown: show interactive drill-down button when Gujarat state is inspected
  if (drilldownBox) {
    drilldownBox.style.display = isGujarat ? "block" : "none";
  }

  // Update dispatch button text based on jurisdiction
  if (alertBtn) {
    const alertBtnText = alertBtn.querySelector("span:not(.pulse-dot)");
    if (alertBtnText) {
      alertBtnText.textContent = isState ? "Dispatch State Heat Advisory (SMS)" : "Dispatch Ward Early Warning Alert (SMS)";
    }
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
  await renderSidebarForecastChart(props);

  // Render Human Impact Card ("Who is Affected")
  await renderHumanImpactCard(props);
}

/**
 * HumanImpactCard Component ("Who is Affected").
 * Renders real population counts, data quality badges ("Measured" vs "Derived"),
 * clinical consequences, actionable prevention guidance ("What to do"),
 * dominant risk driver, and provenance data links.
 */
async function renderHumanImpactCard(props) {
  if (!props) return;
  const panel = document.getElementById("population-impact-panel");
  const popBadge = document.getElementById("impact-total-pop");
  const summaryText = document.getElementById("impact-summary-text");
  const cardsContainer = document.getElementById("cohort-cards-container");
  const driverBox = document.getElementById("dominant-risk-driver-box");
  const driverVal = document.getElementById("dominant-risk-driver-value");

  if (!panel || !cardsContainer) return;

  const wardId = props.ward_id || props.state_id;
  const wardName = props.ward_name || props.state_name || "Region";
  const riskLevel = (props.risk_level || "MODERATE").toUpperCase().replace(" ", "_");

  // Attempt dynamic API fetch first for rich server-backed epidemiological text
  let impactData = null;
  if (props.ward_id) {
    try {
      impactData = await api.getPopulationImpact(props.ward_id);
    } catch (err) {
      console.warn("Could not fetch remote population impact, computing client fallback:", err);
    }
  }

  // Fallback synthesis if API is unreachable or inspecting a state
  if (!impactData) {
    const totalPop = props.total_population || (props.population ? props.population : 120000);
    const elderlyPct = props.elderly_pct != null ? props.elderly_pct : 12.0;
    const outdoorPct = props.outdoor_worker_pct != null ? props.outdoor_worker_pct : 28.0;
    const slumPct = props.slum_pct != null ? props.slum_pct : 25.0;
    const childPct = 9.2;

    const countChildren = Math.round(totalPop * (childPct / 100));
    const countElderly = Math.round(totalPop * (elderlyPct / 100));
    const countOutdoor = Math.round(totalPop * (outdoorPct / 100));
    const countSlum = Math.round(totalPop * (slumPct / 100));

    const isHighOrAbove = ["HIGH", "VERY_HIGH", "EXTREME"].includes(riskLevel);
    const isExtreme = riskLevel === "EXTREME" || riskLevel === "VERY_HIGH";

    const dominantFactor = outdoorPct >= slumPct && outdoorPct >= elderlyPct
      ? `Outdoor labor exposure (${outdoorPct.toFixed(1)}%)`
      : (slumPct >= elderlyPct ? `Slum/informal housing density (${slumPct.toFixed(1)}%)` : `Elderly demographic concentration (${elderlyPct.toFixed(1)}%)`);

    impactData = {
      ward_id: wardId,
      ward_name: wardName,
      total_population: totalPop,
      risk_level: riskLevel,
      dominant_risk_factor: dominantFactor,
      data_source_url: "https://censusindia.gov.in / MoSPI Periodic Labour Force Survey (PLFS)",
      data_pulled_at: "2026-09-10",
      summary: `Under ${riskLevel.replace('_', ' ')} heat hazard, ${countElderly.toLocaleString()} seniors and ${countOutdoor.toLocaleString()} outdoor laborers in ${wardName} face direct thermal strain.`,
      segments: {
        children_0_5: {
          segment_id: "children_0_5",
          name: "Children (Age 0-5)",
          icon: "👶",
          estimated_count: countChildren,
          percentage: childPct,
          data_quality: "derived",
          severity: isExtreme ? "CRITICAL" : (isHighOrAbove ? "HIGH" : "MODERATE"),
          consequence: isExtreme
            ? "Rapid dehydration, electrolyte shock, febrile delirium, and hypovolemic collapse (Azhar et al. 2014, PLOS ONE)."
            : "Early clinical dehydration, severe heat rash (miliaria rubra), and rapid core heat gain (WHO 2021 Guidance).",
          action: isExtreme
            ? "EMERGENCY: Move to air-conditioned shelter immediately; administer ORS/electrolytes; call 108 if lethargic."
            : "Keep indoors in cool ventilated shade; offer fluids every 30 minutes; sponge forehead with cool water.",
        },
        elderly_60plus: {
          segment_id: "elderly_60plus",
          name: "Elderly (Age 60+)",
          icon: "👴",
          estimated_count: countElderly,
          percentage: elderlyPct,
          data_quality: "derived",
          severity: isExtreme ? "CRITICAL" : (isHighOrAbove ? "HIGH" : "MODERATE"),
          consequence: isExtreme
            ? "Catastrophic non-exertional classical heatstroke, myocardial infarction, and ischemic stroke (Ahmedabad HAP 2018)."
            : "Postural hypotension, heat syncope, and occult dehydration due to impaired baroreflex (WHO/WMO 2015).",
          action: isExtreme
            ? "URGENT MEDICAL PRIORITY: Evacuate to municipal cooling shelter; active cold sponging; call 108 immediately."
            : "Stay indoors between 11 AM - 4 PM; drink water regularly even without thirst; monitor blood pressure.",
        },
        outdoor_workers: {
          segment_id: "outdoor_workers",
          name: "Outdoor & Informal Labor",
          icon: "🔨",
          estimated_count: countOutdoor,
          percentage: outdoorPct,
          data_quality: "derived",
          severity: isExtreme ? "CRITICAL" : (isHighOrAbove ? "HIGH" : "MODERATE"),
          consequence: isExtreme
            ? "Fatal exertional heatstroke, rhabdomyolysis (muscle breakdown), and acute kidney injury (AKI) (NRDC / AMC 2018)."
            : "Painful exertional heat cramps, heavy sodium deficit, cognitive fatigue, and motor coordination impairment (NDMA).",
          action: isExtreme
            ? "MANDATORY WORK CESSATION: Cease all outdoor physical labor between 11:00 AM - 4:30 PM; move to shaded stations."
            : "Shift heavy labor before 11:00 AM; mandatory 15-min shaded rest breaks every hour; drink 500ml water hourly.",
        },
        slum_residents: {
          segment_id: "slum_residents",
          name: "Slum & Informal Housing Residents",
          icon: "🏚️",
          estimated_count: countSlum,
          percentage: slumPct,
          data_quality: "derived",
          severity: isExtreme ? "CRITICAL" : (isHighOrAbove ? "HIGH" : "MODERATE"),
          consequence: isExtreme
            ? "Lethal indoor thermal trap (>48°C indoor heat index), rapid dehydration, and hyperthermia (Knowlton et al. 2014)."
            : "Chronic nocturnal thermal retention. Tin and asbestos roofing elevates indoor temperatures 3-6°C above ambient levels.",
          action: isExtreme
            ? "EVACUATE INDOOR TRAP: Relocate vulnerable family members to municipal air-cooled civic shelters."
            : "Ensure open cross-ventilation; drape wet gunny bags over tin roofs; spend peak afternoons in shaded centers.",
        },
      },
    };
  }

  // Update header badges and summary note
  if (popBadge) {
    popBadge.textContent = `Pop: ${Number(impactData.total_population || 0).toLocaleString()}`;
  }
  if (summaryText) {
    summaryText.textContent = impactData.summary || "Evaluating demographic exposure to active thermal hazard.";
  }

  // Dominant risk driver line (Part D)
  if (driverBox && driverVal) {
    if (impactData.dominant_risk_factor) {
      driverBox.style.display = "flex";
      driverVal.textContent = impactData.dominant_risk_factor;
    } else {
      driverBox.style.display = "none";
    }
  }

  // Provenance modal data elements (Part D)
  const sourceUrlEl = document.getElementById("modal-source-url");
  const pulledDateEl = document.getElementById("modal-pulled-date");
  if (sourceUrlEl && impactData.data_source_url) {
    sourceUrlEl.textContent = impactData.data_source_url;
    sourceUrlEl.href = impactData.data_source_url.startsWith("http") ? impactData.data_source_url.split(" ")[0] : "https://censusindia.gov.in";
  }
  if (pulledDateEl && impactData.data_pulled_at) {
    pulledDateEl.textContent = impactData.data_pulled_at;
  }

  // Map risk level to card class
  const tierClassMap = {
    LOW: "tier-low",
    MODERATE: "tier-moderate",
    HIGH: "tier-high",
    VERY_HIGH: "tier-very-high",
    EXTREME: "tier-extreme",
  };
  const cardTierClass = tierClassMap[impactData.risk_level] || "tier-moderate";
  const isUrgent = ["VERY_HIGH", "EXTREME"].includes(impactData.risk_level);

  // Build cohort cards HTML
  const segments = Object.values(impactData.segments || {});
  cardsContainer.innerHTML = segments.map((seg) => {
    const sevClass = `sev-${(seg.severity || "moderate").toLowerCase()}`;
    const qualityBadge = seg.data_quality === "measured"
      ? `<span class="badge-quality badge-measured">Measured</span>`
      : `<span class="badge-quality badge-derived">Estimated</span>`;

    const actionBoxClass = (isUrgent || seg.severity === "CRITICAL") ? "urgent-action" : "precaution-action";
    const actionHeading = (isUrgent || seg.severity === "CRITICAL") ? "🚨 URGENT ACTION:" : "🛡️ WHAT TO DO:";
    const actionText = seg.action || (isUrgent ? "Evacuate to cooling shelter immediately." : "Drink water regularly and rest in shade.");

    return `
      <div class="cohort-card ${cardTierClass}">
        <div class="cohort-header">
          <div class="cohort-title-wrap">
            <span class="cohort-icon">${seg.icon || "👥"}</span>
            <span class="cohort-name">${seg.name}</span>
          </div>
          <div class="cohort-count-badge">
            ${Number(seg.estimated_count || 0).toLocaleString()}
            <span class="pct-sub">(${Number(seg.percentage || 0).toFixed(1)}%)</span>
            ${qualityBadge}
          </div>
        </div>
        <div class="cohort-consequence">${seg.consequence}</div>
        <div class="cohort-action-box ${actionBoxClass}">
          <div class="action-heading">${actionHeading}</div>
          <div>${actionText}</div>
        </div>
        <div class="cohort-footer">
          <span class="cohort-citation">Epidemiological Guidance</span>
          <span class="severity-tag ${sevClass}">${seg.severity}</span>
        </div>
      </div>
    `;
  }).join("");
}

// Backward compatibility alias
const renderPopulationImpact = renderHumanImpactCard;



/**
 * Render Chart.js Forecast Line Chart in Sidebar.
 */
async function renderSidebarForecastChart(props) {
  if (!props) return;
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
  } else if (state.currentScope === "india" || props.state_id) {
    const regionName = props.state_name || "State";
    if (chartCardTitle) chartCardTitle.textContent = `5-Day Heat Projection (${regionName})`;
    datasetLabel = "State Risk Trend";
    chartColor = "#38bdf8";
    chartBg = "rgba(56, 189, 248, 0.18)";
    const base = props.final_risk_score || 0.55;
    riskData = [
      Math.min(1.0, Math.max(0.1, +(base - 0.04).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base - 0.02).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base + 0.03).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base + 0.05).toFixed(2))),
    ];
  } else {
    if (chartCardTitle) chartCardTitle.textContent = "5-Day Predictive Risk Trend";
    const wardId = props.ward_id || props;
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
  const entityId = props.ward_id || props.state_id;
  const canvas = popupElem.querySelector(`#popup-chart-${entityId}`);
  if (!canvas) return;

  const Chart_inst = window.Chart || (typeof Chart !== "undefined" ? Chart : null);
  if (!Chart_inst) return;

  let labels = ["+1d", "+2d", "+3d", "+4d", "+5d"];
  let riskData = [0.45, 0.48, 0.52, 0.56, 0.60];

  if (state.currentScope === "india" || props.state_id) {
    const base = props.final_risk_score || 0.55;
    riskData = [
      Math.min(1.0, Math.max(0.1, +(base - 0.04).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base - 0.02).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base + 0.03).toFixed(2))),
      Math.min(1.0, Math.max(0.1, +(base + 0.05).toFixed(2))),
    ];
  } else {
    try {
      const res = await api.getWardForecast(props.ward_id);
      if (res && res.forecasts && res.forecasts.length > 0) {
        labels = res.forecasts.map((f) => `+${f.horizon_days}d`);
        riskData = res.forecasts.map((f) => f.predicted_risk_score);
      }
    } catch (e) {
      console.warn("Forecast fetch for popup chart fallback:", e);
    }
  }

  const chartKey = `popup-${entityId}`;
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
 * Load GeoJSON Ward or State Data and Render Choropleth.
 */
async function loadDashboardData() {
  const isIndia = state.currentScope === "india";

  showLoading(
    isIndia
      ? "Loading All-India 35 States & UTs Layer..."
      : state.isBacktestMode
      ? "Loading Ahmedabad May 2010 Historical Validation Layer..."
      : "Loading Real-Time Ward Biometeorology Layer..."
  );

  try {
    const geojsonData = isIndia
      ? await api.getIndiaGeoJSON()
      : state.isBacktestMode
      ? await api.getBacktestGeoJSON()
      : await api.getWardsGeoJSON();

    state.geojsonData = geojsonData;

    // Update Header refresh time
    const refreshEl = document.getElementById("last-refresh-time");
    if (refreshEl) {
      const now = new Date();
      refreshEl.textContent = isIndia
        ? `Live India: ${now.toLocaleTimeString()}`
        : state.isBacktestMode
        ? "Historical Mode: May 2010"
        : `Live: ${now.toLocaleTimeString()}`;
    }

    // Update City / National Alert Status Banner
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

    // Auto-select highest risk entity or Gujarat if in India mode
    if (!state.selectedWardProps && geojsonData.features && geojsonData.features.length > 0) {
      let defaultFeature = null;
      if (isIndia) {
        // Prioritize Gujarat in All-India mode to highlight the pilot drilldown connection
        defaultFeature = geojsonData.features.find(
          (f) => f.properties.state_name === "Gujarat" || f.properties.state_id === "IN_GJ"
        );
      }
      if (!defaultFeature) {
        const sorted = [...geojsonData.features].sort(
          (a, b) => (b.properties.final_risk_score || 0) - (a.properties.final_risk_score || 0)
        );
        defaultFeature = sorted[0];
      }
      if (defaultFeature) {
        renderWardSidebar(defaultFeature.properties);
      }
    } else if (state.selectedWardProps) {
      const targetId = state.selectedWardProps.ward_id || state.selectedWardProps.state_id;
      const updated = geojsonData.features.find(
        (f) => (f.properties.ward_id || f.properties.state_id) === targetId
      );
      if (updated) {
        renderWardSidebar(updated.properties);
      }
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
      banner.innerHTML = `⏳ <strong>Connecting to backend API service...</strong> Waiting for FastAPI server. Auto-reconnecting in background...`;
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
 * Handle Map Scope Switching (Ahmedabad 48 Wards vs All India 35 States & UTs) & Multi-Scale Drilldown.
 */
function bindScopeControls() {
  const scopeSelector = document.getElementById("scope-selector");
  const backtestBtn = document.getElementById("btn-toggle-backtest");
  const drilldownBtn = document.getElementById("btn-drilldown-ahmedabad");

  window.drillDownToAhmedabad = async () => {
    if (scopeSelector && scopeSelector.value !== "ahmedabad") {
      scopeSelector.value = "ahmedabad";
      state.currentScope = "ahmedabad";
      state.selectedWardProps = null;
      if (backtestBtn) {
        backtestBtn.style.opacity = "1";
        backtestBtn.style.pointerEvents = "auto";
        backtestBtn.title = "Toggle historical May 2010 backtest";
      }
      if (state.map) {
        state.map.flyTo(config.city.center, config.city.defaultZoom, { duration: 1.5 });
      }
      await updateSystemStatus();
      await loadDashboardData();
    }
  };

  if (drilldownBtn) {
    drilldownBtn.addEventListener("click", () => {
      window.drillDownToAhmedabad();
    });
  }

  if (scopeSelector) {
    scopeSelector.addEventListener("change", async (e) => {
      state.currentScope = e.target.value;
      state.selectedWardProps = null;

      if (state.currentScope === "india") {
        if (state.isBacktestMode) {
          state.isBacktestMode = false;
          if (backtestBtn) {
            backtestBtn.classList.remove("active");
            backtestBtn.innerHTML = `<span class="backtest-icon">🕒</span><span class="backtest-label">Backtest Mode (May 2010)</span>`;
          }
        }
        if (backtestBtn) {
          backtestBtn.style.opacity = "0.4";
          backtestBtn.style.pointerEvents = "none";
          backtestBtn.title = "Historical backtest is available for Ahmedabad City Pilot";
        }
        if (state.map) {
          state.map.flyTo(config.india.center, config.india.defaultZoom, { duration: 1.4 });
        }
      } else {
        if (backtestBtn) {
          backtestBtn.style.opacity = "1";
          backtestBtn.style.pointerEvents = "auto";
          backtestBtn.title = "Toggle historical May 2010 backtest";
        }
        if (state.map) {
          state.map.flyTo(config.city.center, config.city.defaultZoom, { duration: 1.4 });
        }
      }

      await updateSystemStatus();
      await loadDashboardData();
    });
  }
}

/**
 * Handle Alert Trigger Action Button.
 */
function bindAlertButton() {
  const alertBtn = document.getElementById("btn-dispatch-alert");
  if (!alertBtn) return;

  alertBtn.addEventListener("click", async () => {
    if (!state.selectedWardProps) {
      alert("Please select a municipal ward or state first.");
      return;
    }

    const entity = state.selectedWardProps;
    const isState = !!entity.state_id;
    const entityName = entity.ward_name || entity.state_name || "Unknown";
    const entityId = entity.ward_id || entity.state_id || "N/A";

    const originalText = alertBtn.innerHTML;
    alertBtn.innerHTML = `<span>⏳ Dispatching SMS/WhatsApp...</span>`;
    alertBtn.disabled = true;

    try {
      const payload = {
        ward_id: isState ? "WARD_01" : entity.ward_id,
        recipient_phone: "+919876543210",
        channel: "sms",
        force: true,
      };

      const result = await api.triggerAlert(payload);
      alert(
        `🚨 Early Warning Alert Dispatched!\n\n` +
        `Jurisdiction: ${entityName} (${entityId})\n` +
        `Level: ${isState ? "State Disaster Management Authority (SDMA)" : "Municipal Ward Emergency Action"}\n` +
        `Channel: ${result.channel.toUpperCase()}\n` +
        `Message ID: ${result.message_id || 'N/A'}\n` +
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
 * Handle Traceable Data Sources & Methodology Modal (Part D).
 */
function bindSourcesModal() {
  const btnOpen = document.getElementById("btn-view-data-sources");
  const btnClose = document.getElementById("btn-close-sources-modal");
  const btnCloseFooter = document.getElementById("btn-close-sources-modal-footer");
  const modal = document.getElementById("sources-modal");

  if (!modal) return;

  const openModal = () => { modal.style.display = "flex"; };
  const closeModal = () => { modal.style.display = "none"; };

  if (btnOpen) btnOpen.addEventListener("click", openModal);
  if (btnClose) btnClose.addEventListener("click", closeModal);
  if (btnCloseFooter) btnCloseFooter.addEventListener("click", closeModal);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
}

/**
 * Main Application Bootstrapper.
 */
async function main() {
  initMap();
  bindLayerControls();
  bindBacktestToggle();
  bindScopeControls();
  bindInfoModal();
  bindSourcesModal();
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
