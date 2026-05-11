
import math
import os
import structlog

import geopandas as gpd

from datetime import datetime
from shapely import box

from config.config import SENTINEL2_GRIDS_FILE

logger = structlog.get_logger()

# --- GEOSPATIAL LOGIC ---

def get_sentinel_tiles_from_geometry(geometry_gdf: gpd.GeoDataFrame, geometry_origin: str=None) -> list[str]:
    """Get the Sentinel-2 tile/tiles the geometry is comprised in. Also, insert the geometry origin on last tiles' ID for filenaming purposes...
    Args:
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
    Returns:
        tile_ids (list[str]):
            The Setinel-2 Tile's ID list.
    """
    # Get geometry origin suffix for filename
    if geometry_origin.split(".").pop():
        geom_suffix = geometry_origin.split(".")[0]
    else:
        geom_suffix = geometry_origin

    if not SENTINEL2_GRIDS_FILE or not os.path.exists(SENTINEL2_GRIDS_FILE):
        raise FileNotFoundError(
            f"GEOMETRY_FILE is not set or does not exist: {SENTINEL2_GRIDS_FILE}")
    # Sentinel-2 grid
    grids_geojson = gpd.read_file(SENTINEL2_GRIDS_FILE)

    # Ensure same CRS
    gdf = geometry_gdf.to_crs(grids_geojson.crs)
    
    # Spatial intersection
    result = gpd.overlay(gdf, grids_geojson, how="intersection")

    # Tile IDs
    tile_ids = result["Name"].unique()  # or "tile_id" depending on dataset

    if geom_suffix is not None:
        tile_ids[-1] = f"{tile_ids[-1]}_{str(geom_suffix)}"  # append suffix

    return tile_ids

def get_aster_tiles_from_geometry(geometry_gdf: gpd.GeoDataFrame, geometry_origin: str=None) -> list[str]:
    """
    Returns ASTER GDEM tile IDs covering the input geometry. Also, insert the geometry origin on all tiles' ID for filenaming purposes...

    Tiles follow the format:
        N36W002, S12E045, etc.

    Args:
        geometry_gdf (gpd.GeoDataFrame):
            Input geometry (any CRS)
        geometry_origin (str):
            Used for ASTER TIF file name. Default is `None`.

    Returns:
        list[str]: List of ASTER tile IDs
    """
    # Get geometry origin suffix for filename
    if geometry_origin.split(".").pop():
        geom_suffix = geometry_origin.split(".")[0]
    else:
        geom_suffix = geometry_origin

    # Ensure WGS84 (lat/lon)
    gdf = geometry_gdf.to_crs("EPSG:4326")
    geom = gdf.union_all()  # Get unified geometry for bounds calculation

    minx, miny, maxx, maxy = gdf.total_bounds
    tiles = set()

    for lat in range(math.floor(miny), math.ceil(maxy)):
        for lon in range(math.floor(minx), math.ceil(maxx)):
            tile_geom = box(lon, lat, lon + 1, lat + 1)

            if geom.intersects(tile_geom):
                lat_prefix = "N" if lat >= 0 else "S"
                lon_prefix = "E" if lon >= 0 else "W"

                tile_id = f"{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}"
                
                if geom_suffix is not None:
                    tile_id += f"_{str(geom_suffix)}"  # append suffix
                
                tiles.add(tile_id)

    return sorted(tiles)

def get_year_month_pair(start_date: str, end_date: str) -> list[tuple]:
    """Generates a (`YYYY`, `NN-MMM`) tuple list of the given temporal range.
    Args:
        start_date (str):
            The starting date in ISO format (`YYYY-MM-DD`).
        end_date (str):
            The finishing date in ISO format (`YYYY-MM-DD`).
    Returns:
        year_months (tuple):
            The (`YYYY`, `NN-MMM`) tuple list.
    """
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    # Normalize to first day of the month
    current = start.replace(day=1)
    end = end.replace(day=1)

    year_months = []

    while current <= end:
        year = current.year
        month_num = current.strftime("%m")   # 01, 02, ...
        month_str = current.strftime("%b")   # Jan, Feb, ...

        year_months.append((str(year), f"{month_num}-{month_str}"))

        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return year_months
