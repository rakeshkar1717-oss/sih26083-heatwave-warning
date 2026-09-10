# SIH26083 Forecast Accuracy Report: Stage 1 - Baseline (Single-Source Open-Meteo)

> **Document Type**: Scientific Validation & Operational Accuracy Audit  
> **Evaluation Horizon**: Day 1 to Day 5 Forward Projections (24h to 120h Lead Times)  
> **Evaluation Sample**: 4 Summer Seasons (April–June 2021–2024, Ahmedabad, Gujarat)  
> **Sample Size**: 5,160 Ward-Horizon Forecast Evaluations (1,032 Daily Multi-Vulnerability Ground Truths)  
> **Generated**: 2026-09-10 11:39:46 UTC

---

## 1. Executive Summary & Core Results

Represents the pre-improvement system state relying exclusively on single-source numerical weather prediction (Open-Meteo) and standard default risk thresholds (LOW: 0.25, MODERATE: 0.50, HIGH: 0.70, VERY_HIGH: 0.85).

| Metric | Measured Value | Meteorological Benchmark Context |
|:---|:---:|:---|
| **Overall Classification Accuracy** | **83.47%** | Exact match across 5 canonical heat risk tiers |
| **Adjacent-Tier Accuracy (±1 Tier)** | **100.00%** | Standard operational tolerance in numerical weather prediction |
| **Total Evaluations** | **5,160** | Rigorous multi-horizon evaluation across 3 vulnerability archetypes |
| **Correct Alert Classifications** | **4,307 / 5,160** | Zero data leakage; strict historical cutoffs |
| **Max Temperature MAE** | **1.731°C** | Mean Absolute Error against ground truth observations |
| **Max Temperature RMSE** | **2.436°C** | Root Mean Square Error penalizing large synoptic misses |
| **Biometeorological Hazard MAE** | **4.508 / 100** | Composite NOAA HI, WBGT, and UTCI error |
| **Composite Risk Score MAE** | **0.0270** | Continuous 0.00 to 1.00 ward risk index error |

---

## 2. Multi-Horizon Skill Degradation Curve (Day 1 to Day 5)

Operational weather forecasts experience atmospheric error growth as lead time increases. The table below documents the empirical skill curve from 24-hour lead time down to 120-hour (5-day) lead time:

| Forecast Horizon | Lead Time | Total Forecasts | Correct Classifications | Accuracy % | Temperature MAE (°C) | Risk MAE |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Day 1** | 24 hours | 1032 | 884 | **85.66%** | 1.191°C | 0.0240 |
| **Day 2** | 48 hours | 1032 | 864 | **83.72%** | 1.552°C | 0.0265 |
| **Day 3** | 72 hours | 1032 | 860 | **83.33%** | 1.796°C | 0.0271 |
| **Day 4** | 96 hours | 1032 | 854 | **82.75%** | 1.983°C | 0.0278 |
| **Day 5** | 120 hours | 1032 | 845 | **81.88%** | 2.132°C | 0.0299 |

> **Key Observation**: The forecasting engine demonstrates robust skill across all operational horizons. Even at Day 5 (120 hours out), the model retains strong predictive skill (81.88% accuracy), providing municipal authorities with actionable lead time to mobilize water tankers and cooling shelters.

---

## 3. Confusion Matrix (Ground Truth vs. Predicted Tier)

| Actual \ Predicted | LOW | MODERATE | HIGH | VERY_HIGH | EXTREME | Total Actual | Recall % |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **LOW** | 0 | 0 | 0 | 0 | 0 | **0** | **0.0%** |
| **MODERATE** | 0 | 578 | 227 | 0 | 0 | **805** | **71.8%** |
| **HIGH** | 0 | 300 | 2404 | 101 | 0 | **2805** | **85.7%** |
| **VERY_HIGH** | 0 | 0 | 225 | 1325 | 0 | **1550** | **85.5%** |
| **EXTREME** | 0 | 0 | 0 | 0 | 0 | **0** | **0.0%** |

---

## 4. Tier-Specific Classification Performance

| Risk Tier | Support (Ground Truth) | Predicted Count | Precision % | Recall % | F1 Score |
|:---|:---:|:---:|:---:|:---:|:---:|
| **LOW** | 0 | 0 | 0.00% | 0.00% | 0.00 |
| **MODERATE** | 805 | 878 | 65.83% | 71.80% | 68.69 |
| **HIGH** | 2805 | 2856 | 84.17% | 85.70% | 84.93 |
| **VERY_HIGH** | 1550 | 1426 | 92.92% | 85.48% | 89.04 |
| **EXTREME** | 0 | 0 | 0.00% | 0.00% | 0.00 |

---

## 5. Methodological & Rigor Statement
- **Zero Future Data Leakage**: For each forecast target date $T$, the simulation strictly restricted all autoregressive predictors, rolling climatology windows, and trend projections to days $t \le T - h$.
- **Multi-Factor Biometeorology**: Predictions synthesize three distinct human thermoregulatory models: NOAA Heat Index, Liljegren Outdoor Wet Bulb Globe Temperature (WBGT), and Universal Thermal Climate Index (UTCI).
- **Vulnerability Archetypes**: Evaluations span Low-vulnerability residential wards ($V=0.15$), City Median average wards ($V=0.42$), and High-vulnerability slum/outdoor-worker wards ($V=0.75$).
