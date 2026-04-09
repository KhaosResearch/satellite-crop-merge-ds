
import math
import numpy
import os
import rasterio
import shutil
import structlog

import geopandas as gpd

from minio import Minio
from datetime import datetime
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge
from shapely import box

from utils.io_utils import save_cropped_data
from utils.io_utils import save_cropped_data
from config.config import SENTINEL2_GRIDS_FILE, SOURCE_BUCKET, SOURCE_CLIENT

logger = structlog.get_logger()

# --- GEOSPATIAL LOGIC ---

def get_sentinel_tiles_of_geometry(geometry_gdf: gpd.GeoDataFrame) -> list[str]:
    """Get the tile/tiles the geometry is comprised in.
    Args:
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
    Returns:
        tile_ids (list[str]):
            The Setinel-2 Tile's ID list.
    """
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

    return tile_ids

def get_aster_tiles_of_geometry(geometry_gdf: gpd.GeoDataFrame) -> list[str]:
    """
    Returns ASTER GDEM tile IDs covering the input geometry.

    Tiles follow the format:
        N36W002, S12E045, etc.

    Args:
        geometry_gdf (gpd.GeoDataFrame): Input geometry (any CRS)

    Returns:
        list[str]: List of ASTER tile IDs
    """

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

def process_merge_crop(
    local_paths: list[str],
    geometry: dict,
    job_dir: str,
    product_key: str,
    saved_files: list[str],
    product_prefix: str,
    subfolder: str,
    file_id: str,
    year: str,
    month: str,
    resolution_tag: str,
    minio_client: Minio=SOURCE_CLIENT,
    minio_bucket: str=SOURCE_BUCKET
):
    """Merges multiple raster datasets into a mosaic, crops them to a specific geometry, saves the result, and cleans up temporary local source files.

    Args:
        local_paths (list): List of strings/Paths to the downloaded temporary .tif files.
        geometry (dict/GeoJSON): The geometry used to mask/crop the mosaic.
        job_dir (str): Directory where the final output will be stored.
        product_key (str): Identifier for the specific satellite product.
        saved_files (list): Accumulated list of paths to successfully saved files.
        product_prefix, subfolder, file_id, year, month, resolution_tag: 
            Metadata strings used for naming the output file.
        minio_client (optional): Client object if uploading directly to MinIO.
        minio_bucket (optional): Target bucket name for MinIO uploads.

    Returns:
        list: The updated 'saved_files' list including the new processed file.
    """
    
    datasets = []
    output_dir = os.path.join(job_dir, product_prefix, year, month, subfolder)

    try:
        # Open all datasets
        for p in local_paths:
            if p.endswith(".tfw"):
                # Save and add TFW file to saved files
                tiles_tag = resolution_tag  # Used store the tiles str for ASTER products
                crop_tag = "crop" if not "-" in tiles_tag else "merge-crop"  # Multiple tiles = merge + crop, Single tile = only crop
                output_filename = f"{"_".join(["ASTGTMV003", product_key, tiles_tag, crop_tag])}.tfw"
                tfw_output_path = os.path.join(output_dir, output_filename)
                logger.debug(f"Saving TFW file to local as:\n\t\t\t\t   {tfw_output_path}")
                shutil.copy(p, tfw_output_path)
                saved_files.append(tfw_output_path)
            else:
                datasets.append(rasterio.open(p))
        
        if not datasets:
            return saved_files

        # Merge logic
        mosaic, out_meta = _merge_image_data_to_mosaic(datasets)

        # Crop logic
        out_image, out_meta = _crop_mosaic(mosaic, out_meta, geometry)

        # Save logic
        saved_files = save_cropped_data(
            job_dir, product_key, saved_files, product_prefix, subfolder, 
            file_id, year, month, resolution_tag, out_image, out_meta, 
            minio_client, minio_bucket
        )

    finally:
        # Close datasets and remove files
        for ds in datasets:
            ds.close()
            
        for f in local_paths:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Warning: Could not remove temp file {f}: {e}")

    return saved_files

def _merge_image_data_to_mosaic(datasets: list[rasterio.io.DatasetReader])->tuple:
    """Merges all same image data from different tiles into one mosaic.
    Args:
        datasets (list[rasterio.io.DatasetReader]):
            The list of datasets associated to the files found.
    Returns:
        tuple:
            The mosaic's data and metadata.
    """
    if len(datasets) == 1:
        ds = datasets[0]

        mosaic = ds.read()  # read full raster
        transform = ds.transform

        out_meta = ds.meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": transform
        })

        logger.info("Single dataset detected → skipping merge")
    else:
        # Merge datasets for the month
        logger.info(f"Merging {len(datasets)} files...")
        mosaic, transform = merge(datasets)
        logger.info(f"Merging complete!")

        # Use metadata from first dataset
        out_meta = datasets[0].meta.copy()
        out_meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": transform
        })
    return mosaic, out_meta

def _crop_mosaic(mosaic: numpy.ndarray, meta: dict, geometry_gdf: gpd.geodataframe)->tuple:
    """Crops the mosaic given the parcel's geometry.
    Args:
        mosaic (numpy.ndarray):
            The mosaic data from te merge.
        meta (dict):
            The mosaics metadata.
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
    Returns:
        tuple:
            The cropped image data and metadata.
        """
    try:    
        logger.info(f"Cropping mosaic...")

        meta = meta.copy()
        with MemoryFile() as memfile:
            with memfile.open(**meta) as dataset:
                dataset.write(mosaic)

                # Reproject geometry to raster CRS
                geom_gdf = gpd.GeoDataFrame(geometry=[geometry_gdf], crs="EPSG:4326")
                geom_gdf = geom_gdf.to_crs(dataset.crs)

                out_image, out_transform = mask(
                    dataset,
                    geom_gdf.geometry,
                    crop=True
                )

                out_meta = dataset.meta.copy()
                out_meta.update({
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform,
                })

                return out_image, out_meta
    except Exception as e:
        raise Exception(f"Error while cropping: {e}")
    finally:
        del mosaic
