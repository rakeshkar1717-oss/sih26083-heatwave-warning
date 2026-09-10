"""Validation package for data cross-checks, demographic benchmarks, and model integrity."""

from backend.validation.population_crosscheck import (
    run_population_crosscheck,
    print_validation_report,
)
from backend.validation.forecast_accuracy import (
    load_or_pull_summer_era5,
    compute_daily_ground_truth,
    simulate_3day_ahead_forecasts,
    evaluate_accuracy,
    run_full_accuracy_pipeline,
    print_accuracy_report,
)

__all__ = [
    "run_population_crosscheck",
    "print_validation_report",
    "load_or_pull_summer_era5",
    "compute_daily_ground_truth",
    "simulate_3day_ahead_forecasts",
    "evaluate_accuracy",
    "run_full_accuracy_pipeline",
    "print_accuracy_report",
]
