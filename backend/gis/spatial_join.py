"""Spatial point-in-polygon join module for weather and ward boundaries.

Maps continuous meteorological point observations/forecasts to municipal ward polygons
using standard geospatial topological operations (within & nearest fallback).
"""

import logging
from typing import Optional
import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)


def join_weather_to_wards(
    weather_df: pd.DataFrame,
    wards_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Spatially join meteorological point observations to municipal ward polygons.

    Converts weather DataFrame lat/lon into Shapely Points and executes a spatial join
    using predicate='within'. If any weather point falls outside all ward polygons
    (e.g., coastal boundary, airport station, buffer edge case), falls back to
    `geopandas.sjoin_nearest` to prevent silent data loss.

    Parameters
    ----------
    weather_df : pd.DataFrame
        Meteorological dataframe containing 'lat' and 'lon' columns.
    wards_gdf : gpd.GeoDataFrame
        Reprojected municipal ward polygons with 'ward_id' and 'ward_name'.

    Returns
    -------
    gpd.GeoDataFrame
        Enriched GeoDataFrame containing all weather attributes, indices, and matched
        ['ward_id', 'ward_name', 'geometry'].

    Raises
    ------
    ValueError
        If inputs are missing required coordinates or attributes.
    """
    if weather_df is None or weather_df.empty:
        logger.warning("Empty weather DataFrame passed to spatial join.")
        return gpd.GeoDataFrame(columns=list(weather_df.columns) if weather_df is not None else [] + ["ward_id", "ward_name", "geometry"], crs="EPSG:4326")

    if wards_gdf is None or wards_gdf.empty:
        raise ValueError("Wards GeoDataFrame cannot be empty.")

    if "lat" not in weather_df.columns or "lon" not in weather_df.columns:
        raise ValueError("Weather DataFrame must contain 'lat' and 'lon' columns.")

    for required_col in ["ward_id", "ward_name", "geometry"]:
        if required_col not in wards_gdf.columns:
            raise ValueError(f"Wards GeoDataFrame is missing mandatory column: '{required_col}'")

    # 1. Ensure matching CRS
    wards_layer = wards_gdf[["ward_id", "ward_name", "geometry"]].copy()
    if wards_layer.crs is None:
        wards_layer.set_crs(epsg=4326, inplace=True)
    elif wards_layer.crs.to_string() != "EPSG:4326":
        wards_layer = wards_layer.to_crs(epsg=4326)

    # 2. Convert weather points to GeoDataFrame
    points_geom = gpd.points_from_xy(weather_df["lon"], weather_df["lat"], crs="EPSG:4326")
    weather_points_gdf = gpd.GeoDataFrame(weather_df.copy(), geometry=points_geom, crs="EPSG:4326")

    # 3. Primary Spatial Join: Point within Polygon
    joined_gdf = gpd.sjoin(
        weather_points_gdf,
        wards_layer,
        how="left",
        predicate="within"
    )

    if "index_right" in joined_gdf.columns:
        joined_gdf.drop(columns=["index_right"], inplace=True)

    # 4. Fallback for Unmatched / Boundary Points (Nearest Ward Assignment)
    unmatched_mask = joined_gdf["ward_id"].isna()
    if unmatched_mask.any():
        num_unmatched = int(unmatched_mask.sum())
        logger.warning(
            "%d meteorological observation(s) fell outside municipal ward polygon boundaries. "
            "Executing fallback nearest-neighbor spatial join (sjoin_nearest) to assign closest ward.",
            num_unmatched
        )

        unmatched_gdf = weather_points_gdf[unmatched_mask].copy()
        # Reproject temporarily to projected metric CRS (EPSG:3857) for accurate Euclidean distances
        unmatched_proj = unmatched_gdf.to_crs(epsg=3857)
        wards_proj = wards_layer.to_crs(epsg=3857)

        # Execute nearest spatial join
        nearest_joined = gpd.sjoin_nearest(
            unmatched_proj,
            wards_proj,
            how="left"
        )

        if "index_right" in nearest_joined.columns:
            nearest_joined.drop(columns=["index_right"], inplace=True)

        # Update unmatched rows with nearest ward attributes
        for idx in unmatched_gdf.index:
            if idx in nearest_joined.index:
                match_row = nearest_joined.loc[idx]
                # If duplicate nearest matches, pick the first
                w_id = match_row["ward_id"].iloc[0] if isinstance(match_row["ward_id"], pd.Series) else match_row["ward_id"]
                w_name = match_row["ward_name"].iloc[0] if isinstance(match_row["ward_name"], pd.Series) else match_row["ward_name"]

                joined_gdf.loc[idx, "ward_id"] = w_id
                joined_gdf.loc[idx, "ward_name"] = w_name

    logger.info(
        "Spatially joined %d weather observations across %d municipal wards.",
        len(joined_gdf), joined_gdf["ward_id"].nunique()
    )
    return joined_gdf
