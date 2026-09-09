/**
 * Choropleth Visualization & Interaction Engine for Leaflet.
 *
 * Renders municipal ward boundaries with dynamic styling,
 * interactive hover effects, click selection, and custom legend controls.
 */

import { config } from "./config.js";

/**
 * Resolve color for risk level.
 */
export function getRiskColor(level) {
  const norm = (level || "").toUpperCase();
  return config.riskColors[norm] || config.riskColors.MODERATE;
}

/**
 * Resolve color for 0-100 thermal stress score.
 */
export function getHazardColor(score) {
  if (score == null) return "#94a3b8";
  if (score < 25) return config.riskColors.LOW;
  if (score < 50) return config.riskColors.MODERATE;
  if (score < 75) return config.riskColors.HIGH;
  if (score < 90) return config.riskColors.VERY_HIGH;
  return config.riskColors.EXTREME;
}

/**
 * Resolve color for 0.0 - 1.0 HVI score.
 */
export function getHVIColor(score) {
  if (score == null) return "#94a3b8";
  if (score < 0.30) return config.riskColors.LOW;
  if (score < 0.50) return config.riskColors.MODERATE;
  if (score < 0.75) return config.riskColors.HIGH;
  return config.riskColors.EXTREME;
}

/**
 * Generate feature style based on current layer mode.
 */
export function getFeatureStyle(feature, mode = "risk") {
  const props = feature.properties || {};
  let fillColor = "#3498db";

  if (mode === "risk") {
    fillColor = props.color || getRiskColor(props.risk_level);
  } else if (mode === "hazard") {
    fillColor = getHazardColor(props.thermal_stress_score);
  } else if (mode === "vulnerability") {
    fillColor = getHVIColor(props.vulnerability_score);
  }

  return {
    fillColor: fillColor,
    weight: 2,
    opacity: 1,
    color: "#0f172a",
    dashArray: "2",
    fillOpacity: 0.78,
  };
}

/**
 * Build Leaflet GeoJSON layer with hover highlights, popups, and click callbacks.
 */
export function createChoroplethLayer(geojsonData, options = {}) {
  const L_inst = window.L || (typeof L !== "undefined" ? L : null);
  if (!L_inst) {
    throw new Error("Leaflet library is not loaded.");
  }

  const mode = options.mode || "risk";
  const onWardSelect = options.onWardSelect || (() => {});
  const onPopupOpen = options.onPopupOpen || (() => {});

  const geojsonLayer = L_inst.geoJSON(geojsonData, {
    style: (feature) => getFeatureStyle(feature, mode),
    onEachFeature: (feature, layer) => {
      const props = feature.properties || {};

      // Hover Tooltip
      layer.bindTooltip(
        `<strong>${props.ward_name}</strong> (${props.ward_id})<br/>` +
        `Risk: <span style="font-weight:700;color:${props.color || getRiskColor(props.risk_level)}">${props.risk_level}</span>`,
        { sticky: true, direction: "top", className: "ward-tooltip" }
      );

      // Mouse Interaction
      layer.on({
        mouseover: (e) => {
          const l = e.target;
          l.setStyle({
            weight: 4,
            color: "#ffffff",
            dashArray: "",
            fillOpacity: 0.92,
          });
          if (!L_inst.Browser.ie && !L_inst.Browser.opera && !L_inst.Browser.edge) {
            l.bringToFront();
          }
        },
        mouseout: (e) => {
          geojsonLayer.resetStyle(e.target);
        },
        click: (e) => {
          onWardSelect(props, layer);
        },
      });

      // Ward Popup with Embedded Canvas for Forecast Chart
      const popupContent = document.createElement("div");
      popupContent.className = "ward-popup-card";
      popupContent.innerHTML = `
        <div class="popup-header">
          <h4>${props.ward_name}</h4>
          <span class="popup-badge" style="background:${props.color || getRiskColor(props.risk_level)}">${props.risk_level}</span>
        </div>
        <div class="popup-grid">
          <div class="metric"><label>Temp</label><span>${props.temp_c != null ? props.temp_c + " °C" : "N/A"}</span></div>
          <div class="metric"><label>WBGT</label><span>${props.wbgt_c != null ? props.wbgt_c + " °C" : "N/A"}</span></div>
          <div class="metric"><label>HVI</label><span>${props.vulnerability_score != null ? props.vulnerability_score.toFixed(2) : "N/A"}</span></div>
          <div class="metric"><label>Risk Score</label><span>${props.final_risk_score != null ? props.final_risk_score.toFixed(2) : "N/A"}</span></div>
        </div>
        <div class="popup-chart-container">
          <div class="chart-title">5-Day Risk Trend Projections</div>
          <canvas id="popup-chart-${props.ward_id}" width="260" height="120"></canvas>
        </div>
        <div class="popup-advisory">
          <small>${props.advisory || "Standard heat precautions recommended."}</small>
        </div>
      `;

      layer.bindPopup(popupContent, { maxWidth: 320, minWidth: 280 });

      layer.on("popupopen", (e) => {
        onPopupOpen(props, popupContent);
      });
    },
  });

  return geojsonLayer;
}

/**
 * Create a Leaflet Map Legend Control.
 */
export function createLegendControl() {
  const L_inst = window.L || (typeof L !== "undefined" ? L : null);
  if (!L_inst) return null;

  const legend = L_inst.control({ position: "bottomright" });

  legend.onAdd = function () {
    const div = L_inst.DomUtil.create("div", "info-legend");
    div.innerHTML = `
      <div class="legend-header">Heatwave Risk Tiers</div>
      <div class="legend-row"><i style="background:${config.riskColors.LOW}"></i><span>Low Risk (< 0.25)</span></div>
      <div class="legend-row"><i style="background:${config.riskColors.MODERATE}"></i><span>Moderate (0.25 - 0.50)</span></div>
      <div class="legend-row"><i style="background:${config.riskColors.HIGH}"></i><span>High Alert (0.50 - 0.70)</span></div>
      <div class="legend-row"><i style="background:${config.riskColors.VERY_HIGH}"></i><span>Very High (0.70 - 0.85)</span></div>
      <div class="legend-row"><i style="background:${config.riskColors.EXTREME}"></i><span>Extreme Danger (≥ 0.85)</span></div>
    `;
    return div;
  };

  return legend;
}
