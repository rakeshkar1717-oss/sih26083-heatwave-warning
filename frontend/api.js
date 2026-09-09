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
