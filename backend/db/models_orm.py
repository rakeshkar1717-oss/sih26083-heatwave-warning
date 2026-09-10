"""SQLAlchemy ORM Models for SIH26083 Extreme Heatwave Early Warning System.

Defines the relational schema for:
- WardBoundary: Municipal spatial boundaries and metadata
- WardVulnerability: Socio-demographic Heat Vulnerability Index (HVI) records
- WeatherReading: Observed and interpolated meteorological readings and thermal indices
- RiskForecast: Multi-day predictive heatwave risk projections
- AlertLog: Audited log of automated civic and public alerts
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class WardBoundary(Base):
    """Municipal ward administrative boundaries and spatial attributes."""

    __tablename__ = "ward_boundaries"

    ward_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    ward_name: Mapped[str] = mapped_column(String(100), nullable=False)
    geometry_geojson: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="Ahmedabad")
    zone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    area_sqkm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    vulnerability: Mapped[Optional["WardVulnerability"]] = relationship(
        "WardVulnerability",
        back_populates="ward",
        uselist=False,
        cascade="all, delete-orphan",
    )
    weather_readings: Mapped[List["WeatherReading"]] = relationship(
        "WeatherReading",
        back_populates="ward",
        cascade="all, delete-orphan",
    )
    risk_forecasts: Mapped[List["RiskForecast"]] = relationship(
        "RiskForecast",
        back_populates="ward",
        cascade="all, delete-orphan",
    )
    alert_logs: Mapped[List["AlertLog"]] = relationship(
        "AlertLog",
        back_populates="ward",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WardBoundary(ward_id='{self.ward_id}', ward_name='{self.ward_name}', city='{self.city}')>"


class WardVulnerability(Base):
    """Heat Vulnerability Index (HVI) and socio-demographic indicators per ward."""

    __tablename__ = "ward_vulnerabilities"

    ward_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ward_boundaries.ward_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    elderly_pct: Mapped[float] = mapped_column(Float, nullable=False)
    outdoor_worker_pct: Mapped[float] = mapped_column(Float, nullable=False)
    slum_pct: Mapped[float] = mapped_column(Float, nullable=False)
    green_cover_pct: Mapped[float] = mapped_column(Float, nullable=False)
    hospital_bed_density: Mapped[float] = mapped_column(Float, nullable=False)
    vulnerability_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_indices_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Absolute population counts
    total_population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=100000)
    count_age_0_5: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    count_age_6_17: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    count_age_18_59: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    count_age_60_plus: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    count_outdoor_labor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    count_indoor_labor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    count_slum_residents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    # Provenance Tracking (Part A)
    data_source_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_pulled_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    ward: Mapped["WardBoundary"] = relationship("WardBoundary", back_populates="vulnerability")

    def __repr__(self) -> str:
        return f"<WardVulnerability(ward_id='{self.ward_id}', score={self.vulnerability_score:.3f}, tier='{self.risk_tier}')>"


class WeatherReading(Base):
    """Meteorological observations, interpolated readings, and calculated thermal indices."""

    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ward_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ward_boundaries.ward_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    solar_radiation_wm2: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    heat_index_c: Mapped[float] = mapped_column(Float, nullable=False)
    wbgt_c: Mapped[float] = mapped_column(Float, nullable=False)
    utci_c: Mapped[float] = mapped_column(Float, nullable=False)
    thermal_stress_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    ward: Mapped["WardBoundary"] = relationship("WardBoundary", back_populates="weather_readings")

    __table_args__ = (
        Index("idx_ward_timestamp", "ward_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<WeatherReading(ward_id='{self.ward_id}', timestamp='{self.timestamp}', temp={self.temp_c}°C)>"


class RiskForecast(Base):
    """Multi-day forecast projections of thermal stress and composite heatwave risk."""

    __tablename__ = "risk_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ward_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ward_boundaries.ward_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    forecast_date: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    forecast_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_risk_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    ward: Mapped["WardBoundary"] = relationship("WardBoundary", back_populates="risk_forecasts")

    def __repr__(self) -> str:
        return f"<RiskForecast(ward_id='{self.ward_id}', horizon={self.forecast_horizon_days}d, score={self.predicted_risk_score:.3f})>"


class AlertLog(Base):
    """Audit trail for automated early warning alerts dispatched to authorities/citizens."""

    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ward_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ward_boundaries.ward_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    risk_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    message_sent: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, default=1)
    success: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    ward: Mapped["WardBoundary"] = relationship("WardBoundary", back_populates="alert_logs")

    def __repr__(self) -> str:
        return f"<AlertLog(id={self.id}, ward_id='{self.ward_id}', channel='{self.channel}', success={self.success})>"
