"""Unit tests for Census Demographic Population Crosscheck Validation (Part F)."""

import pytest
from backend.validation.population_crosscheck import run_population_crosscheck
from backend.config import OFFICIAL_CITY_POPULATION_BENCHMARK


def test_population_crosscheck_totals():
    """Verify population cross-check calculates correct sums and within acceptable bounds."""
    results = run_population_crosscheck()

    assert results["num_wards"] == 48
    assert results["total_population"] > 5000000
    assert results["official_2011_benchmark"] == OFFICIAL_CITY_POPULATION_BENCHMARK
    assert results["variance_2020_expanded_pct"] < 5.0
    assert results["passed_expansion_variance"] is True


def test_population_crosscheck_cohorts_validity():
    """Ensure demographic cohort distributions conform to urban standards."""
    results = run_population_crosscheck()

    assert results["all_cohorts_valid"] is True
    assert results["overall_valid"] is True

    cohorts = results["cohort_checks"]
    assert "children_0_5_pct" in cohorts
    assert "elderly_60plus_pct" in cohorts
    assert "outdoor_labor_pct" in cohorts
    assert "slum_housing_pct" in cohorts

    # Check 0-5 children is ~9.2%
    assert 8.0 <= cohorts["children_0_5_pct"]["percentage"] <= 10.5
    # Check 60+ seniors is ~11.9%
    assert 9.0 <= cohorts["elderly_60plus_pct"]["percentage"] <= 14.0
