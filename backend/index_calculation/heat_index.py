"""NOAA / OSHA Heat Index calculation module.

Implements the official National Oceanic and Atmospheric Administration (NOAA) /
Occupational Safety and Health Administration (OSHA) Heat Index algorithm based on
Steadman's multi-parameter human biometeorological model and Rothfusz regression equation.

Unit conversions:
    Input:  Air temperature in Celsius (°C) and Relative Humidity in % (0 - 100).
    Internal: Converted to Fahrenheit (°F) for the empirical regression equations.
    Output: Returned in Celsius (°C) matching the project's canonical schema.
"""

from typing import Union
import numpy as np
import pandas as pd


def _compute_single_heat_index(temp_c: float, rh: float) -> float:
    """Compute NOAA Heat Index for a single (temp_c, humidity_pct) pair."""
    # Convert Celsius to Fahrenheit
    t = (temp_c * 9.0 / 5.0) + 32.0

    # Under mild/cool conditions (T < 40°F / 4.4°C), Heat Index is effectively air temperature
    if t < 40.0:
        return temp_c

    # Steadman simple formula
    hi_simple = 0.5 * (t + 61.0 + ((t - 68.0) * 1.2) + (rh * 0.094))

    # If the simple average is below 80°F, use simple Heat Index
    if (hi_simple + t) / 2.0 < 80.0:
        hi_f = hi_simple
    else:
        # Full Rothfusz regression equation
        hi_f = (
            -42.379
            + 2.04901523 * t
            + 10.14333127 * rh
            - 0.22475541 * t * rh
            - 0.00683783 * (t ** 2)
            - 0.05481717 * (rh ** 2)
            + 0.00122874 * (t ** 2) * rh
            + 0.00085282 * t * (rh ** 2)
            - 0.00000199 * (t ** 2) * (rh ** 2)
        )

        # Adjustment 1: Dry conditions (RH < 13% and 80 <= T <= 112°F)
        if rh < 13.0 and 80.0 <= t <= 112.0:
            diff = 17.0 - abs(t - 95.0)
            if diff > 0:
                adjustment = ((13.0 - rh) / 4.0) * np.sqrt(diff / 17.0)
                hi_f -= adjustment

        # Adjustment 2: High humidity conditions (RH > 85% and 80 <= T <= 87°F)
        elif rh > 85.0 and 80.0 <= t <= 87.0:
            adjustment = ((rh - 85.0) / 10.0) * ((87.0 - t) / 5.0)
            hi_f += adjustment

    # Convert Fahrenheit back to Celsius
    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return float(round(hi_c, 2))


def calculate_heat_index(
    temp_c: Union[float, np.ndarray, pd.Series],
    humidity_pct: Union[float, np.ndarray, pd.Series]
) -> Union[float, np.ndarray, pd.Series]:
    """Calculate the official NOAA / OSHA Heat Index in degrees Celsius.

    Parameters
    ----------
    temp_c : Union[float, np.ndarray, pd.Series]
        Air temperature at 2 meters in Celsius.
    humidity_pct : Union[float, np.ndarray, pd.Series]
        Relative humidity in percentage (0 to 100).

    Returns
    -------
    Union[float, np.ndarray, pd.Series]
        Heat Index in Celsius (same type as input).

    Examples
    --------
    >>> calculate_heat_index(32.22, 50.0)  # 90°F, 50% RH -> approx 35.6°C (96°F)
    35.56
    """
    if isinstance(temp_c, pd.Series) or isinstance(humidity_pct, pd.Series):
        s_t = pd.Series(temp_c)
        s_rh = pd.Series(humidity_pct)
        res = [
            _compute_single_heat_index(float(t), float(rh))
            for t, rh in zip(s_t, s_rh)
        ]
        return pd.Series(res, index=s_t.index)

    if isinstance(temp_c, np.ndarray) or isinstance(humidity_pct, np.ndarray):
        arr_t = np.asarray(temp_c, dtype=float)
        arr_rh = np.asarray(humidity_pct, dtype=float)
        vec_func = np.vectorize(_compute_single_heat_index)
        return vec_func(arr_t, arr_rh)

    return _compute_single_heat_index(float(temp_c), float(humidity_pct))
