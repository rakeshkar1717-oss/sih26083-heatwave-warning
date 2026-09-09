"""Scheduled Batch Job for Multi-Day Predictive Heatwave Risk Projections.

Iterates over all municipal wards, computes 3-5 day forward risk forecasts,
and updates the persistent RiskForecast relational table in the database.
Can be executed as a daily cron job in production or triggered before live demos.
"""

import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

from backend.db.session import SessionLocal, init_db
from backend.db.models_orm import WardBoundary, RiskForecast
from backend.forecasting.forecast_engine import generate_forecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_forecast_job(
    db: Optional[Session] = None,
    horizon_days: int = 5,
    clear_existing: bool = True
) -> Dict[str, int]:
    """Execute forecast projection job for all registered wards."""
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True

    try:
        init_db()
        wards = db.query(WardBoundary).all()
        if not wards:
            logger.warning("No wards found in database. Please run backend.db.seed first.")
            return {"wards_processed": 0, "forecasts_generated": 0}

        logger.info("Executing predictive heatwave forecasting for %d wards (Horizon: %d days)...", len(wards), horizon_days)

        if clear_existing:
            db.query(RiskForecast).delete()
            db.commit()

        total_forecasts = 0
        for ward in wards:
            forecasts = generate_forecast(
                ward_id=ward.ward_id,
                horizon_days=horizon_days,
                db=db,
            )

            for fc in forecasts:
                record = RiskForecast(
                    ward_id=fc["ward_id"],
                    forecast_date=fc["forecast_date"],
                    forecast_horizon_days=fc["horizon_days"],
                    predicted_risk_score=fc["predicted_risk_score"],
                    predicted_risk_tier=fc["predicted_risk_tier"],
                    generated_at=fc["generated_at"],
                )
                db.add(record)
                total_forecasts += 1

        db.commit()
        logger.info("Forecasting batch job completed successfully. Generated %d forecast records across %d wards.", total_forecasts, len(wards))
        return {"wards_processed": len(wards), "forecasts_generated": total_forecasts}

    except Exception as e:
        db.rollback()
        logger.error("Forecast batch job encountered an error: %s", e, exc_info=True)
        raise
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    run_forecast_job(horizon_days=5)
