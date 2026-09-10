# SIH26083 Forecast Accuracy Report: Stage 2 - Multi-Source Meteorological Data Fusion

> **Document Type**: Scientific Validation & Operational Accuracy Audit  
> **Evaluation Horizon**: Day 1 to Day 5 Forward Projections (24h to 120h Lead Times)  
> **Evaluation Sample**: 4 Summer Seasons (April–June 2021–2024, Ahmedabad, Gujarat)  
> **Sample Size**: 5,160 Ward-Horizon Forecast Evaluations (1,032 Daily Multi-Vulnerability Ground Truths)  
> **Generated**: 2026-09-10 11:39:46 UTC

---

## 1. Executive Summary & Core Results

Introduces real multi-source data fusion combining ground-derived models from Open-Meteo with orbital satellite surface solar irradiance and atmospheric profiles from NASA POWER. A 50/50 weighted consensus reduces sensor drift and microclimatic bias, reducing temperature prediction error across all 5 operational forecast horizons.

| Metric | Measured Value | Meteorological Benchmark Context |
|:---|:---:|:---|
| **Overall Classification Accuracy** | **83.53%** | Exact match across 5 canonical heat risk tiers |
| **Adjacent-Tier Accuracy (±1 Tier)** | **100.00%** | Standard operational tolerance in numerical weather prediction |
| **Total Evaluations** | **5,160** | Rigorous multi-horizon evaluation across 3 vulnerability archetypes |
| **Correct Alert Classifications** | **4,310 / 5,160** | Zero data leakage; strict historical cutoffs |
| **Max Temperature MAE** | **1.616°C** | Mean Absolute Error against ground truth observations |
| **Max Temperature RMSE** | **2.246°C** | Root Mean Square Error penalizing large synoptic misses |
| **Biometeorological Hazard MAE** | **4.480 / 100** | Composite NOAA HI, WBGT, and UTCI error |
| **Composite Risk Score MAE** | **0.0269** | Continuous 0.00 to 1.00 ward risk index error |

---

## 2. Multi-Horizon Skill Degradation Curve (Day 1 to Day 5)

Operational weather forecasts experience atmospheric error growth as lead time increases. The table below documents the empirical skill curve from 24-hour lead time down to 120-hour (5-day) lead time:

| Forecast Horizon | Lead Time | Total Forecasts | Correct Classifications | Accuracy % | Temperature MAE (°C) | Risk MAE |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Day 1** | 24 hours | 1032 | 890 | **86.24%** | 1.038°C | 0.0227 |
| **Day 2** | 48 hours | 1032 | 867 | **84.01%** | 1.462°C | 0.0259 |
| **Day 3** | 72 hours | 1032 | 860 | **83.33%** | 1.694°C | 0.0270 |
| **Day 4** | 96 hours | 1032 | 857 | **83.04%** | 1.875°C | 0.0283 |
| **Day 5** | 120 hours | 1032 | 836 | **81.01%** | 2.014°C | 0.0305 |

> **Key Observation**: The forecasting engine demonstrates robust skill across all operational horizons. Even at Day 5 (120 hours out), the model retains strong predictive skill (81.01% accuracy), providing municipal authorities with actionable lead time to mobilize water tankers and cooling shelters.

---

## 3. Confusion Matrix (Ground Truth vs. Predicted Tier)

| Actual \ Predicted | LOW | MODERATE | HIGH | VERY_HIGH | EXTREME | Total Actual | Recall % |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **LOW** | 0 | 0 | 0 | 0 | 0 | **0** | **0.0%** |
| **MODERATE** | 0 | 603 | 202 | 0 | 0 | **805** | **74.9%** |
| **HIGH** | 0 | 282 | 2434 | 89 | 0 | **2805** | **86.8%** |
| **VERY_HIGH** | 0 | 0 | 277 | 1273 | 0 | **1550** | **82.1%** |
| **EXTREME** | 0 | 0 | 0 | 0 | 0 | **0** | **0.0%** |

---

## 4. Tier-Specific Classification Performance

| Risk Tier | Support (Ground Truth) | Predicted Count | Precision % | Recall % | F1 Score |
|:---|:---:|:---:|:---:|:---:|:---:|
| **LOW** | 0 | 0 | 0.00% | 0.00% | 0.00 |
| **MODERATE** | 805 | 885 | 68.14% | 74.91% | 71.36 |
| **HIGH** | 2805 | 2913 | 83.56% | 86.77% | 85.13 |
| **VERY_HIGH** | 1550 | 1362 | 93.47% | 82.13% | 87.43 |
| **EXTREME** | 0 | 0 | 0.00% | 0.00% | 0.00 |

---

## 5. Methodological & Rigor Statement
- **Zero Future Data Leakage**: For each forecast target date $T$, the simulation strictly restricted all autoregressive predictors, rolling climatology windows, and trend projections to days $t \le T - h$.
- **Multi-Factor Biometeorology**: Predictions synthesize three distinct human thermoregulatory models: NOAA Heat Index, Liljegren Outdoor Wet Bulb Globe Temperature (WBGT), and Universal Thermal Climate Index (UTCI).
- **Vulnerability Archetypes**: Evaluations span Low-vulnerability residential wards ($V=0.15$), City Median average wards ($V=0.42$), and High-vulnerability slum/outdoor-worker wards ($V=0.75$).
