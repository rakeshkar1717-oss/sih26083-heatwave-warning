"""Outdoor Wet Bulb Globe Temperature (WBGT) calculation module.

Implements a simplified empirical outdoor WBGT model based on the Australian Bureau of
Meteorology (BOM) / OSHA approximation formula, incorporating solar irradiance and convective
wind cooling without requiring astronomical solar zenith angle calculations.

Formula Variant:
    1. Vapor pressure e (hPa):
       e = (humidity_pct / 100.0) * 6.105 * exp((17.27 * temp_c) / (237.7 + temp_c))

    2. Shade / Indoor WBGT (BOM / Stull formulation):
       WBGT_shade = 0.567 * temp_c + 0.393 * e + 3.94

    3. Direct Solar & Wind Convective Adjustment:
       Solar flux adds radiant thermal load to the globe temperature, while wind
       dissipates heat through forced convection:
       delta_solar = (solar_radiation_wm2 / 100.0) * 0.75 / ((wind_speed_ms + 0.5) ** 0.25)

    4. Total Outdoor WBGT:
       WBGT_outdoor = WBGT_shade + delta_solar

Known Limitations:
    - Assumes standard ground albedo (~0.2) and typical human skin/clothing emissivity.
    - Suitable for macro-scale municipal early warning; micro-climatic indoor industrial
      furnaces or complex terrain should utilize the complete 6-parameter Liljegren model.
"""

from typing import Union
import numpy as np
import pandas as pd


def _compute_single_wbgt(
    temp_c: float,
    humidity_pct: float,
    wind_speed_ms: float,
    solar_radiation_wm2: float
) -> float:
    """Compute outdoor WBGT for a single observation."""
    # Ensure physical limits
    t = float(temp_c)
    rh = max(0.0, min(100.0, float(humidity_pct)))
    ws = max(0.1, float(wind_speed_ms))
    sol = max(0.0, float(solar_radiation_wm2))

    # Water vapor pressure in hPa (Tetens formula)
    e = (rh / 100.0) * 6.105 * np.exp((17.27 * t) / (237.7 + t))

    # Shade component
    wbgt_shade = 0.567 * t + 0.393 * e + 3.94

    # Solar radiant & wind convective adjustment
    delta_solar = (sol / 100.0) * 0.75 / ((ws + 0.5) ** 0.25)

    wbgt_outdoor = wbgt_shade + delta_solar
    return float(round(wbgt_outdoor, 2))


def calculate_wbgt(
    temp_c: Union[float, np.ndarray, pd.Series],
    humidity_pct: Union[float, np.ndarray, pd.Series],
    wind_speed_ms: Union[float, np.ndarray, pd.Series],
    solar_radiation_wm2: Union[float, np.ndarray, pd.Series]
) -> Union[float, np.ndarray, pd.Series]:
    """Calculate outdoor Wet Bulb Globe Temperature (WBGT) in degrees Celsius.

    Parameters
    ----------
    temp_c : Union[float, np.ndarray, pd.Series]
        Air temperature at 2 meters in Celsius.
    humidity_pct : Union[float, np.ndarray, pd.Series]
        Relative humidity in percentage (0 to 100).
    wind_speed_ms : Union[float, np.ndarray, pd.Series]
        Wind speed at 10 meters in m/s.
    solar_radiation_wm2 : Union[float, np.ndarray, pd.Series]
        Surface downward solar radiation in W/m².

    Returns
    -------
    Union[float, np.ndarray, pd.Series]
        Calculated outdoor WBGT in Celsius.
    """
    is_series = any(isinstance(arg, pd.Series) for arg in (temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2))
    if is_series:
        s_t = pd.Series(temp_c)
        s_rh = pd.Series(humidity_pct)
        s_ws = pd.Series(wind_speed_ms)
        s_sol = pd.Series(solar_radiation_wm2)
        res = [
            _compute_single_wbgt(float(t), float(rh), float(ws), float(sol))
            for t, rh, ws, sol in zip(s_t, s_rh, s_ws, s_sol)
        ]
        return pd.Series(res, index=s_t.index)

    is_array = any(isinstance(arg, np.ndarray) for arg in (temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2))
    if is_array:
        vec_func = np.vectorize(_compute_single_wbgt)
        return vec_func(temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2)

    return _compute_single_wbgt(float(temp_c), float(humidity_pct), float(wind_speed_ms), float(solar_radiation_wm2))
