/**
 * Central Frontend Configuration for SIH26083 Leaflet Dashboard.
 * 
 * Supports dynamic environment resolution via Vite (VITE_API_BASE_URL)
 * with graceful fallback for standalone static web servers.
 */

function resolveApiBaseUrl() {
  try {
    const envUrl = import.meta.env?.VITE_API_BASE_URL;
    if (typeof envUrl === "string" && envUrl.trim().length > 0) {
      return envUrl.trim();
    }
  } catch (_) {}

  if (typeof window !== "undefined" && window.location) {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return "http://127.0.0.1:8000";
    }
  }

  return "https://heatwave-api.onrender.com";
}

export const config = {
  // Backend API Base URL (robust production auto-resolution)
  apiBaseUrl: resolveApiBaseUrl(),

  // Demo Pilot City Center Coordinates (Ahmedabad Municipal Corporation)
  city: {
    name: "Ahmedabad",
    state: "Gujarat",
    center: [23.0225, 72.5714],
    defaultZoom: 12,
  },

  // National View Coordinates (All India - 35 States & UTs)
  india: {
    name: "India",
    center: [22.8, 80.0],
    defaultZoom: 5,
  },

  // Auto-Refresh interval for live health & telemetry polling (in ms)
  pollIntervalMs: 60000,

  // Risk Tier Color Scales (Compliant with NDMA / SIH Guidelines)
  riskColors: {
    LOW: "#2ecc71",       // Vibrant Green
    MODERATE: "#f1c40f",  // Warning Yellow
    HIGH: "#e67e22",      // Alert Orange
    VERY_HIGH: "#e74c3c", // Danger Red
    EXTREME: "#8e44ad",   // Emergency Purple
  },

  // Heat Vulnerability Tiers
  vulnerabilityColors: {
    Low: "#2ecc71",
    Medium: "#f1c40f",
    High: "#e67e22",
    Extreme: "#e74c3c",
  },
};
