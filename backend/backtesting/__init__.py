"""SIH26083 Historical Backtesting & Validation Subsystem.

Provides historical weather reanalysis ingestion, multi-day pipeline backtesting,
and scientific validation reporting against documented historical heatwaves.
"""

from backend.backtesting.historical_puller import pull_historical_weather
from backend.backtesting.validation_report import run_backtest_pipeline, generate_validation_report

__all__ = [
    "pull_historical_weather",
    "run_backtest_pipeline",
    "generate_validation_report",
]
