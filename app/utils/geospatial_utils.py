
import math
import os
from pathlib import Path
import rasterio
import structlog

import geopandas as gpd

from datetime import datetime
from rasterio.io import MemoryFile
from rasterio.mask import mask
from shapely import box

from config.config import SENTINEL2_GRIDS_FILE

logger = structlog.get_logger()

# --- GEOSPATIAL LOGIC ---

def get_sentinel_tiles_from_geometry(geometry_gdf: gpd.GeoDataFrame, geometry_origin: str=None) -> list[str]:
    """Get the Sentinel-2 tile/tiles the geometry is comprised in. Also, insert the geometry origin on last tiles' ID for filenaming purposes...
    Args:
        geometry_gdf (gpd.GeoDataFrame): The parcel's geometry.
    Returns:
        tile_ids (list[str]): The Setinel-2 Tile's ID list.
    """
    # Get geometry origin suffix for filename
    if geometry_origin and geometry_origin.split(".").pop():
        geom_suffix = geometry_origin.split(".")[0]
    else:
        geom_suffix = geometry_origin

    if not SENTINEL2_GRIDS_FILE or not os.path.exists(SENTINEL2_GRIDS_FILE):
        raise FileNotFoundError(f"GRID_FILE is not set or does not exist: {SENTINEL2_GRIDS_FILE}")
        
    # Sentinel-2 grid
    grids_geojson = gpd.read_file(SENTINEL2_GRIDS_FILE)

    # Ensure same CRS
    grids_metric = grids_geojson.to_crs("EPSG:3857")
    gdf_metric = geometry_gdf.to_crs("EPSG:3857")
    
    # Spatial intersection
    result = gpd.overlay(gdf_metric, grids_metric, how="intersection")
    tile_ids = result["Name"].unique().tolist()
    
    # Filter overlapping tiles using the precise file geometries
    tile_ids = remove_overlapping_tiles(tile_ids, gdf_metric, grids_metric)
    
    if geom_suffix is not None and tile_ids:
        tile_ids[-1] = f"{tile_ids[-1]}_{str(geom_suffix)}"

    return tile_ids

def remove_overlapping_tiles(tile_ids: list[str], gdf_metric: gpd.GeoDataFrame, grids_metric: gpd.GeoDataFrame)->list[str]:
    """
    Retrieves tile geometry and checks it geometry is completely contained in it.
    If so, returns the first tile to do so.
    Else, returns all found tiles.
    """
    best_coverage = 0.0
    best_tile = None
    parcel_geom_m = gdf_metric.geometry.union_all()
    parcel_area_m = parcel_geom_m.area

    for tile in tile_ids:
        if parcel_area_m == 0:
            continue
            
        # Extract the precise local geometric feature matching this tile name
        tile_feat = grids_metric[grids_metric["Name"] == tile].geometry.iloc[0]
        
        # Calculate precise overlap coverage ratio in meters
        intersection_area = tile_feat.intersection(parcel_geom_m).area
        coverage = intersection_area / parcel_area_m
        
        logger.debug(f"Tile: {tile} | Metric Coverage: {coverage:.4f}")
        
        if coverage > best_coverage:
            best_coverage = coverage
            best_tile = tile

    # If the absolute best tile cleanly fits your parcel, drop the partial fragments
    if best_coverage >= 0.999 and best_tile is not None:
        logger.debug(f"Geometry is {int(best_coverage*100)}% covered by tile {best_tile}!")
        tile_ids = [best_tile]
    return tile_ids

def get_tile_coverage_of_geometry(tile_geometry, geometry_gdf: gpd.GeoDataFrame) -> float:
    """
    Gets the tile coverage of the given geometry.
    Calculates the ratio of the geometry's area that falls within the tile bounding box.
    """
    if geometry_gdf.empty:
        return 0.0

    # 1. Convert tile geometry container to standard Shapely Polygon
    if hasattr(tile_geometry, "bounds"):
        minx, miny, maxx, maxy = tile_geometry.bounds
        tile_poly = box(minx, miny, maxx, maxy)
    elif isinstance(tile_geometry, (list, tuple)) and len(tile_geometry) == 4:
        tile_poly = box(*tile_geometry)
    else:
        tile_poly = tile_geometry

    # 2. Build GeoDataFrames for both pieces in WGS84 (EPSG:4326)
    # This guarantees we align the inputs cleanly regardless of original source systems
    tile_gdf = gpd.GeoDataFrame(geometry=[tile_poly], crs="EPSG:4326")
    parcel_gdf = geometry_gdf.to_crs("EPSG:4326")

    # 3. Reproject both to a metric CRS (EPSG:3857) for precise area calculations in meters
    tile_gdf_metric = tile_gdf.to_crs("EPSG:3857")
    parcel_gdf_metric = parcel_gdf.to_crs("EPSG:3857")

    # 4. Extract metric shape elements
    tile_poly_m = tile_gdf_metric.geometry.iloc[0]
    parcel_geom_m = parcel_gdf_metric.geometry.union_all()

    if parcel_geom_m.area == 0:
        return 0.0

    # 5. Compute metric ratio mapping
    intersection_area = tile_poly_m.intersection(parcel_geom_m).area
    coverage_ratio = intersection_area / parcel_geom_m.area
    
    return float(coverage_ratio)

def mask_tif_from_minio(
    minio_client,
    bucket_name: str,
    object_name: str,
    geometry: gpd.GeoDataFrame,
    output_path: Path,
) -> bool:
    """
    Download a GeoTIFF from MinIO, apply GeoJSON mask, and save result locally.
    """

    try:
        # 1. Get object from MinIO as bytes
        response = minio_client.get_object(bucket_name, object_name)
        tif_bytes = response.read()
        response.close()
        response.release_conn()

        # 2. Load bytes
        with MemoryFile(tif_bytes) as memfile:
            with memfile.open() as src:

                # 3. Reproject geometry to raster CRS
                gdf_reprojected = geometry.to_crs(src.crs)

                shapes = [
                    geom.__geo_interface__
                    for geom in gdf_reprojected.geometry
                    if geom is not None
                ]

                if not shapes:
                    logger.warning(f"No valid geometries detected.")
                    return False

                # 4. Mask raster
                try:
                    out_image, out_transform = mask(src, shapes, crop=True)
                except ValueError as e:
                    logger.debug(f"No intersection with AOI: {e}")
                    return False

                if out_image.size == 0:
                    return False

                # 5. Write GeoTIFF
                output_path.parent.mkdir(parents=True, exist_ok=True)

                out_meta = src.meta.copy()
                out_meta.update({
                    "driver": "GTiff",
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform,
                    "compress": "deflate",
                })

                with rasterio.open(output_path, "w", **out_meta) as dst:
                    dst.write(out_image)

                return out_image, out_meta

    except Exception as e:
        logger.warning(f"Failed masking {object_name}: {e}")
        raise e

def get_aster_tiles_from_geometry(geometry_gdf: gpd.GeoDataFrame, geometry_origin: str=None) -> list[str]:
    """
    Returns ASTER GDEM tile IDs covering the input geometry. Also, insert the geometry origin on all tiles' ID for filenaming purposes...

    Tiles follow the format:
        N36W002, S12E045, etc.

    Args:
        geometry_gdf (gpd.GeoDataFrame): Input geometry (any CRS)
        geometry_origin (str): Used for ASTER TIF file name. Default is `None`.

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
        start_date (str): The starting date in ISO format (`YYYY-MM-DD`).
        end_date (str): The finishing date in ISO format (`YYYY-MM-DD`).
    Returns:
        year_months (tuple): The (`YYYY`, `NN-MMM`) tuple list.
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
