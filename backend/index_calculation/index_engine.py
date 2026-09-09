"""Unified Thermal Indices Engine.

Enriches standardized meteorological dataframes with NOAA Heat Index,
Outdoor Wet Bulb Globe Temperature (WBGT), Universal Thermal Climate Index (UTCI),
and a normalized 0-100 composite thermal stress score.
"""

import logging
import numpy as np
import pandas as pd

from backend.config import THERMAL_STRESS_WEIGHTS
from backend.models import (
    FIXED_WEATHER_COLUMNS,
    HeatStressCategory,
    validate_weather_dataframe,
)
from backend.index_calculation.heat_index import calculate_heat_index
from backend.index_calculation.wbgt import calculate_wbgt
from backend.index_calculation.utci import calculate_utci

logger = logging.getLogger(__name__)


def _classify_stress_tier(score: float) -> str:
    """Categorize 0-100 thermal stress score into standard hazard tiers."""
    if score < 25.0:
        return HeatStressCategory.NORMAL.value
    elif score < 50.0:
        return HeatStressCategory.CAUTION.value
    elif score < 75.0:
        return HeatStressCategory.EXTREME_CAUTION.value
    elif score < 90.0:
        return HeatStressCategory.DANGER.value
    else:
        return HeatStressCategory.EXTREME_DANGER.value


def compute_thermal_indices(weather_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate and append all biometeorological thermal indices to a weather DataFrame.

    Weighting & Normalization Logic for `thermal_stress_score` (0 - 100):
    --------------------------------------------------------------------
    Individual indices operate on distinct physical scales and are normalized to [0, 100]:
    1. Heat Index:
       Normalized between 25.0°C (0, no added heat sensation) and 54.0°C (100, extreme danger).
    2. WBGT (Outdoor):
       Normalized between 22.0°C (0, unrestricted outdoor labor) and 34.0°C (100, mandatory work cessation).
    3. UTCI:
       Normalized between 26.0°C (0, thermal neutrality) and 46.0°C (100, extreme heat stress).

    Composite Score:
       thermal_stress_score = (
           w_hi * norm_hi +
           w_wbgt * norm_wbgt +
           w_utci * norm_utci
       )
       Where weights (from config.py) are:
       - 40% WBGT: Direct occupational solar/wind convective safety standard (ISO 7243).
       - 35% Heat Index: Public perceived apparent temperature (NOAA/NDMA).
       - 25% UTCI: Dynamic multi-node physiological heat budget.

    Parameters
    ----------
    weather_df : pd.DataFrame
        Standardized DataFrame from Day 1 data ingestion.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame with columns:
        [..., heat_index_c, wbgt_c, utci_c, thermal_stress_score, stress_category]
    """
    if weather_df is None or weather_df.empty:
        logger.warning("Empty weather DataFrame passed to compute_thermal_indices.")
        res = weather_df.copy() if weather_df is not None else pd.DataFrame(columns=FIXED_WEATHER_COLUMNS)
        for col in ["heat_index_c", "wbgt_c", "utci_c", "thermal_stress_score", "stress_category"]:
            res[col] = []
        return res

    # Validate incoming schema matches Day 1 contract
    validated_df = validate_weather_dataframe(weather_df)
    df = validated_df.copy()

    # 1. Compute Individual Indices
    t = df["temp_c"]
    rh = df["humidity_pct"]
    ws = df["wind_speed_ms"]
    sol = df["solar_radiation_wm2"]

    df["heat_index_c"] = calculate_heat_index(t, rh)
    df["wbgt_c"] = calculate_wbgt(t, rh, ws, sol)
    df["utci_c"] = calculate_utci(t, rh, ws, sol)

    # 2. Normalize each index to 0 - 100 scale
    # Heat Index: 25°C -> 0, 54°C -> 100
    norm_hi = np.clip((df["heat_index_c"] - 25.0) / (54.0 - 25.0), 0.0, 1.0) * 100.0

    # WBGT: 22°C -> 0, 34°C -> 100
    norm_wbgt = np.clip((df["wbgt_c"] - 22.0) / (34.0 - 22.0), 0.0, 1.0) * 100.0

    # UTCI: 26°C -> 0, 46°C -> 100
    norm_utci = np.clip((df["utci_c"] - 26.0) / (46.0 - 26.0), 0.0, 1.0) * 100.0

    # 3. Apply Configured Weights
    w_hi = THERMAL_STRESS_WEIGHTS.get("heat_index", 0.35)
    w_wbgt = THERMAL_STRESS_WEIGHTS.get("wbgt", 0.40)
    w_utci = THERMAL_STRESS_WEIGHTS.get("utci", 0.25)

    composite = (w_hi * norm_hi) + (w_wbgt * norm_wbgt) + (w_utci * norm_utci)
    df["thermal_stress_score"] = composite.round(2)

    # 4. Classify Categorical Stress Tier
    df["stress_category"] = df["thermal_stress_score"].apply(_classify_stress_tier)

    logger.info("Computed thermal indices for %d records. Mean thermal_stress_score: %.2f", len(df), df["thermal_stress_score"].mean())
    return df
