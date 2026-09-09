"""GIS ward boundary loader and spatial validator.

Loads municipal ward polygon boundaries from GeoJSON or Shapefiles (e.g. DataMeet,
OpenStreetMap Overpass, Municipal GIS Portals).
Handles CRS reprojection to WGS84 (EPSG:4326) and flexible column alias mapping.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import geopandas as gpd

from backend.config import (
    BOUNDARY_COLUMN_ALIASES,
    BOUNDARY_REAL_PATH,
    BOUNDARY_SYNTHETIC_PATH,
    settings,
)

logger = logging.getLogger(__name__)


def _match_column_name(actual_columns: List[str], target_field: str, aliases: List[str]) -> Optional[str]:
    """Find matching column name ignoring case and punctuation."""
    cleaned_actual = {c.lower().strip().replace(" ", "_").replace("-", "_"): c for c in actual_columns}
    for alias in aliases:
        norm_alias = alias.lower().strip().replace(" ", "_").replace("-", "_")
        if norm_alias in cleaned_actual:
            return cleaned_actual[norm_alias]
    return None


def resolve_boundary_path(explicit_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve active ward GeoJSON path based on settings and file presence."""
    if explicit_path is not None:
        return Path(explicit_path).resolve()

    if not settings.use_synthetic_data and BOUNDARY_REAL_PATH.exists():
        logger.info("Using real municipal ward boundaries: %s", BOUNDARY_REAL_PATH)
        return BOUNDARY_REAL_PATH.resolve()

    logger.info("Using synthetic ward boundaries test fixture: %s", BOUNDARY_SYNTHETIC_PATH)
    return BOUNDARY_SYNTHETIC_PATH.resolve()


def load_ward_boundaries(
    geojson_path: Optional[Union[str, Path]] = None,
    custom_column_mapping: Optional[Dict[str, str]] = None
) -> gpd.GeoDataFrame:
    """Load, reproject, and standardize municipal ward polygon geometries.

    Parameters
    ----------
    geojson_path : Optional[Union[str, Path]], optional
        Filesystem path to GeoJSON or Shapefile. If None, resolves real vs synthetic via config.
    custom_column_mapping : Optional[Dict[str, str]], optional
        Manual column rename mapping if standard aliases do not match.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame in EPSG:4326 with standard columns ['ward_id', 'ward_name', 'geometry'].

    Raises
    ------
    FileNotFoundError
        If geojson_path does not exist.
    ValueError
        If the spatial file is empty, missing geometry, or cannot resolve 'ward_id' / 'ward_name'.
    """
    path = resolve_boundary_path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(f"Ward boundary file not found at: {path}")

    logger.info("Loading ward boundary polygons from: %s", path)
    gdf = gpd.read_file(path)

    if gdf.empty:
        raise ValueError(f"Ward boundary file at {path} contains 0 spatial features.")

    if gdf.geometry is None or "geometry" not in gdf.columns:
        raise ValueError(f"File at {path} does not contain valid spatial geometries.")

    # 1. Reproject CRS to WGS84 (EPSG:4326)
    if gdf.crs is None:
        logger.warning("Boundary layer has no CRS specified; assuming EPSG:4326 (WGS84).")
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs.to_string() != "EPSG:4326":
        logger.info("Reprojecting ward boundaries from %s to EPSG:4326.", gdf.crs)
        gdf = gdf.to_crs(epsg=4326)

    # 2. Resolve 'ward_id' and 'ward_name' column aliases
    actual_cols = [c for c in gdf.columns if c != "geometry"]
    rename_dict: Dict[str, str] = {}
    missing_fields: List[str] = []

    for field in ["ward_id", "ward_name"]:
        if custom_column_mapping and field in custom_column_mapping:
            matched_col = custom_column_mapping[field]
            if matched_col in actual_cols:
                rename_dict[matched_col] = field
                continue

        aliases = BOUNDARY_COLUMN_ALIASES.get(field, [field])
        matched = _match_column_name(actual_cols, field, aliases)
        if matched:
            rename_dict[matched] = field
        else:
            missing_fields.append(field)

    if missing_fields:
        raise ValueError(
            f"Failed to identify mandatory ward identifier column(s): {missing_fields}. "
            f"Available layer attributes were: {actual_cols}. "
            f"Please specify custom_column_mapping or update BOUNDARY_COLUMN_ALIASES in backend/config.py."
        )

    # 3. Apply rename and ensure clean types
    standardized_gdf = gdf.rename(columns=rename_dict)
    standardized_gdf["ward_id"] = standardized_gdf["ward_id"].astype(str).str.strip()
    standardized_gdf["ward_name"] = standardized_gdf["ward_name"].astype(str).str.strip()

    # Retain standard columns plus geometry
    cols_to_keep = ["ward_id", "ward_name", "geometry"]
    for extra_col in actual_cols:
        norm_extra = rename_dict.get(extra_col, extra_col)
        if norm_extra not in cols_to_keep and norm_extra in standardized_gdf.columns:
            cols_to_keep.append(norm_extra)

    standardized_gdf = standardized_gdf[cols_to_keep].copy()

    # 4. Defensive deduplication on ward_id
    if standardized_gdf["ward_id"].duplicated().any():
        num_dups = int(standardized_gdf["ward_id"].duplicated().sum())
        logger.warning("Found %d duplicate ward_id in boundary layer; deduplicating (keeping first).", num_dups)
        standardized_gdf = standardized_gdf.drop_duplicates(subset=["ward_id"], keep="first").reset_index(drop=True)

    # 5. Defensive geometry validation and repair
    invalid_mask = ~standardized_gdf.geometry.is_valid
    if invalid_mask.any():
        logger.warning("%d polygon(s) had invalid topologies; repairing with buffer(0).", int(invalid_mask.sum()))
        standardized_gdf.geometry = standardized_gdf.geometry.buffer(0)

    logger.info("Successfully loaded %d ward polygon boundaries.", len(standardized_gdf))
    return standardized_gdf
