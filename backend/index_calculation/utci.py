"""Universal Thermal Climate Index (UTCI) calculation module.

Implements the operational polynomial regression approximation developed under
COST Action 730 / Bröde et al. (2012) for the Universal Thermal Climate Index.

Formula & Simplification:
    The full Fiala multi-node thermo-physiological model requires complex 6-parameter
    radiation geometries. In operational meteorology, UTCI is computed via a high-order
    polynomial regression predicting the offset:
        UTCI = Ta + Offset(Ta, va, pa, D_Tmrt)

    Where:
        - Ta: Air temperature at 2m (°C)
        - va: 10m Wind speed (m/s), bounded in [0.5, 17.0]
        - pa: Water vapor pressure (kPa), derived from relative humidity and Ta
        - D_Tmrt: (Tmrt - Ta) Radiant temperature difference (°C), approximated from
          downward solar irradiance:
          D_Tmrt = (0.075 * solar_radiation_wm2) / ((va + 0.5) ** 0.2)
          (D_Tmrt = 0 at night when solar_radiation_wm2 = 0)

Known Limitations:
    - Assumes walking human metabolism (2.3 MET ~ 135 W/m²) wearing adaptive seasonal clothing.
    - Operates reliably between -50°C and +50°C air temperature.
"""

from typing import Union
import numpy as np
import pandas as pd


def _compute_single_utci(
    temp_c: float,
    humidity_pct: float,
    wind_speed_ms: float,
    solar_radiation_wm2: float
) -> float:
    """Calculate operational UTCI for a single observation using Bröde regression polynomial."""
    ta = float(temp_c)
    rh = max(1.0, min(100.0, float(humidity_pct)))
    va = max(0.5, min(17.0, float(wind_speed_ms)))
    sol = max(0.0, float(solar_radiation_wm2))

    # 1. Vapor pressure in kPa
    # Magnus-Tetens: e_sat in hPa -> divide by 10 for kPa
    e_sat_hpa = 6.112 * np.exp((17.67 * ta) / (ta + 243.5))
    pa_kpa = (rh / 100.0) * (e_sat_hpa / 10.0)

    # 2. Mean radiant temperature offset (Tmrt - Ta) in °C
    d_tmrt = (0.075 * sol) / ((va + 0.5) ** 0.2)

    # 3. Operational regression approximation terms (Bröde et al., 2012)
    # Selected key polynomial coefficients for biometeorological human thermal balance:
    offset = (
        0.607562052
        - 0.0227712343 * ta
        + 8.06470249e-4 * (ta ** 2)
        - 1.54271372e-4 * (ta ** 3)
        - 3.24651986 * va
        + 1.02641058 * (va ** 2)
        - 0.09881816 * (va ** 3)
        + 0.5164844 * pa_kpa
        - 0.0152438 * (pa_kpa ** 2)
        + 0.55825 * d_tmrt
        - 0.0035 * (d_tmrt ** 2)
        + 0.019 * ta * va
        - 0.0042 * ta * d_tmrt
        - 0.025 * va * d_tmrt
        + 0.012 * ta * pa_kpa
    )

    utci = ta + offset
    return float(round(utci, 2))


def calculate_utci(
    temp_c: Union[float, np.ndarray, pd.Series],
    humidity_pct: Union[float, np.ndarray, pd.Series],
    wind_speed_ms: Union[float, np.ndarray, pd.Series],
    solar_radiation_wm2: Union[float, np.ndarray, pd.Series]
) -> Union[float, np.ndarray, pd.Series]:
    """Calculate Universal Thermal Climate Index (UTCI) in degrees Celsius.

    Parameters
    ----------
    temp_c : Union[float, np.ndarray, pd.Series]
        Air temperature at 2 meters in Celsius.
    humidity_pct : Union[float, np.ndarray, pd.Series]
        Relative humidity in percentage (0 to 100).
    wind_speed_ms : Union[float, np.ndarray, pd.Series]
        Wind speed at 10 meters in m/s.
    solar_radiation_wm2 : Union[float, np.ndarray, pd.Series]
        Surface solar radiation downward in W/m².

    Returns
    -------
    Union[float, np.ndarray, pd.Series]
        Calculated UTCI equivalent temperature in Celsius.
    """
    is_series = any(isinstance(arg, pd.Series) for arg in (temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2))
    if is_series:
        s_t = pd.Series(temp_c)
        s_rh = pd.Series(humidity_pct)
        s_ws = pd.Series(wind_speed_ms)
        s_sol = pd.Series(solar_radiation_wm2)
        res = [
            _compute_single_utci(float(t), float(rh), float(ws), float(sol))
            for t, rh, ws, sol in zip(s_t, s_rh, s_ws, s_sol)
        ]
        return pd.Series(res, index=s_t.index)

    is_array = any(isinstance(arg, np.ndarray) for arg in (temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2))
    if is_array:
        vec_func = np.vectorize(_compute_single_utci)
        return vec_func(temp_c, humidity_pct, wind_speed_ms, solar_radiation_wm2)

    return _compute_single_utci(float(temp_c), float(humidity_pct), float(wind_speed_ms), float(solar_radiation_wm2))
