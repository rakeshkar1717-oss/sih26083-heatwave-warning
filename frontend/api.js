/**
 * REST API Client Module for SIH26083 Backend Microservices.
 *
 * Implements fetch wrappers matching the Day 5 & Day 7 API contract.
 */

import { config } from "./config.js";

const BASE_URL = config.apiBaseUrl;

/**
 * Handle HTTP response and return JSON or raise descriptive error.
 */
async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (data.detail) {
        errorDetail = data.detail;
      }
    } catch (_) {}
    throw new Error(errorDetail);
  }
  return await response.json();
}

/**
 * Service and database health check.
 * GET /health
 */
export async function getHealth() {
  const response = await fetch(`${BASE_URL}/health`);
  return handleResponse(response);
}

/**
 * Retrieve GeoJSON FeatureCollection with joined real-time risk attributes.
 * GET /api/wards/geojson
 */
export async function getWardsGeoJSON() {
  const response = await fetch(`${BASE_URL}/api/wards/geojson`);
  return handleResponse(response);
}

/**
 * Retrieve composite heat risk rating, scores, and civic advisory.
 * GET /api/risk/{wardId}
 */
export async function getWardRisk(wardId) {
  const response = await fetch(`${BASE_URL}/api/risk/${encodeURIComponent(wardId)}`);
  return handleResponse(response);
}

/**
 * Retrieve current meteorological observations and 24-hour history.
 * GET /api/weather/{wardId}
 */
export async function getWardWeather(wardId) {
  const response = await fetch(`${BASE_URL}/api/weather/${encodeURIComponent(wardId)}`);
  return handleResponse(response);
}

/**
 * Retrieve 5-day predictive heatwave risk projections.
 * GET /api/forecast/{wardId}
 */
export async function getWardForecast(wardId) {
  const response = await fetch(`${BASE_URL}/api/forecast/${encodeURIComponent(wardId)}`);
  return handleResponse(response);
}

/**
 * Dispatch automated early warning alert via SMS or WhatsApp.
 * POST /api/alert/trigger
 */
export async function triggerAlert(payload) {
  const response = await fetch(`${BASE_URL}/api/alert/trigger`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

/**
 * Retrieve historical backtest event metadata and validation summary.
 * GET /api/backtest/summary
 */
export async function getBacktestSummary() {
  const response = await fetch(`${BASE_URL}/api/backtest/summary`);
  return handleResponse(response);
}

/**
 * Retrieve daily historical heatwave timeline observations.
 * GET /api/backtest/timeline
 */
export async function getBacktestTimeline() {
  const response = await fetch(`${BASE_URL}/api/backtest/timeline`);
  return handleResponse(response);
}

/**
 * Retrieve GeoJSON FeatureCollection with peak historical heatwave conditions (May 21, 2010).
 * GET /api/backtest/geojson
 */
export async function getBacktestGeoJSON() {
  const response = await fetch(`${BASE_URL}/api/backtest/geojson`);
  return handleResponse(response);
}

/**
 * Retrieve All-India 35 States & UTs GeoJSON FeatureCollection with joined thermal risk attributes.
 * GET /api/india/geojson
 */
export async function getIndiaGeoJSON() {
  const response = await fetch(`${BASE_URL}/api/india/geojson`);
  return handleResponse(response);
}

/**
 * Retrieve population-segmented health consequence breakdown for a specific ward.
 * GET /api/population-impact/{wardId}
 */
export async function getPopulationImpact(wardId) {
  const response = await fetch(`${BASE_URL}/api/population-impact/${encodeURIComponent(wardId)}`);
  return handleResponse(response);
}

/**
 * Send conversational inquiry to Heat Copilot assistant.
 * POST /api/copilot/chat
 */
export async function sendCopilotMessage(payload) {
  const response = await fetch(`${BASE_URL}/api/copilot/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

/**
 * Calculate personalized real-time heat risk profile.
 * POST /api/personal-risk/calculate
 */
export async function calculatePersonalRisk(payload) {
  const response = await fetch(`${BASE_URL}/api/personal-risk/calculate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return handleResponse(response);
}

/**
 * Retrieve list of all 6 curated profession modes.
 * GET /api/profession-modes
 */
export async function getProfessionModes() {
  const response = await fetch(`${BASE_URL}/api/profession-modes`);
  return handleResponse(response);
}

/**
 * Retrieve hourly risk trajectory and tailored advice for a specific profession mode.
 * GET /api/profession-mode/{modeId}
 */
export async function getProfessionModeRisk(modeId, params = {}) {
  const query = new URLSearchParams();
  if (params.ward_id) query.append("ward_id", params.ward_id);
  if (params.lat != null) query.append("lat", params.lat);
  if (params.lon != null) query.append("lon", params.lon);
  if (params.location) query.append("location", params.location);
  if (params.hours_ahead != null) query.append("hours_ahead", params.hours_ahead);

  const qs = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(`${BASE_URL}/api/profession-mode/${encodeURIComponent(modeId)}${qs}`);
  return handleResponse(response);
}



