import os
from typing import Iterator
import zipfile
from minio import Minio
from minio.datatypes import Object
import rasterio
import tempfile
import structlog

import geopandas as gpd

from datetime import datetime
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge

from config.config import PRODUCT_TYPE_FILE_IDS, SENTINEL2_GRIDS_FILE, SOURCE_BUCKET, SOURCE_CLIENT

logger = structlog.get_logger()

def get_product_for_parcel(product: str, geometry: gpd.GeoDataFrame, start_date: str, end_date: str):    
    
    # TODO
    None

def download_merge_crop_band_files(
        geometry_gdf: gpd.GeoDataFrame,
        tiles_list: list[str],
        year_months: list[tuple],
        product_key: str,
        minio_client: Minio=SOURCE_CLIENT
    ) -> tuple:
    """It iterates over the MinIO using the args data to build the paths and downloads all relevant files.
    After collecting monthly composite band's filepaths and content, it merges them into a single mosaic file.
    After merging, it crops the geometry and saves the cropped data in a ZIP file.

    Args:
        geometry (gpd.GeoDataFrame):
            The geometry to crop.
        tiles_list (list[str]):
            Sentinel-2 tile's ID list.
        year_months (list[tuple]):
            List of `("YYYY", "NN-MMM")` tuples.
        product_key (str):
            Product ID string.
    """
    try:
        saved_files = []
        geometry= geometry_gdf.geometry.values[0]
        
        if product_key not in ["images", "AOT", "TIC", "WVP"]:
            product_prefix = os.path.join("indices", product_key)
        else:
            product_prefix = product_key
        
        product_config = PRODUCT_TYPE_FILE_IDS[product_key]


        for subfolder, file_ids in product_config.items():
            subfolder = f"R{subfolder}" if len(subfolder) > 0 else subfolder
            os.path.join(product_prefix, subfolder)
            for file_id in file_ids:
                for year, month in year_months:
                    datasets = []
                    temp_files = []
                    for tile in tiles_list:

                        # Get all files in specific product-geometry-date prefix
                        minio_product_prefix = os.path.join(product_prefix, tile, year, month, subfolder)
                        product_dir_list = minio_client.list_objects(SOURCE_BUCKET, prefix=minio_product_prefix, recursive=True)

                        datasets, temp_files = _get_object_files_data(minio_client, file_id, datasets, temp_files, product_dir_list)
                    
                    if not datasets:
                        continue
                    
                    mosaic, out_meta = _merge_image_data_to_mosaic(datasets)

                    # Cleanup after each month
                    for ds in datasets:
                        ds.close()
                    for f in temp_files:
                        try:
                            os.remove(f)
                        except:
                            pass

                    out_image, out_meta = _crop_mosaic(mosaic, out_meta, geometry)

                    saved_files = _save_cropped_data(product_key, saved_files, product_prefix, subfolder, file_id, year, month, out_meta, out_image)

        zip_path = os.path.join(os.getcwd(), "results", "result.zip")
        logger.debug(f"Zipping {zip_path}...")
        with zipfile.ZipFile(zip_path, "w") as z:
            for file in saved_files:
                z.write(file, arcname=file)
    except Exception as e:
        raise e

def _get_tiles_of_geometry(geojson):
    """It gets the tile/tiles the geometry is comprised in."""
    if not SENTINEL2_GRIDS_FILE or not os.path.exists(SENTINEL2_GRIDS_FILE):
        raise FileNotFoundError(
            f"GEOMETRY_FILE is not set or does not exist: {SENTINEL2_GRIDS_FILE}")
    # Sentinel-2 grid
    grids_geojson = gpd.read_file(SENTINEL2_GRIDS_FILE)

    # Ensure same CRS
    gdf = geojson.to_crs(grids_geojson.crs)
    
    # Spatial intersection
    result = gpd.overlay(gdf, grids_geojson, how="intersection")

    # Tile IDs
    tile_ids = result["Name"].unique()  # or "tile_id" depending on dataset

    return tile_ids

def _get_year_month_pair(start_date: str, end_date: str):
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

def _get_object_files_data(minio_client: Minio, file_id: str, datasets: list, temp_files: list[str], product_dir_list: Iterator[Object]) -> tuple:
    for obj  in product_dir_list:
        if not file_id.lower() in obj.object_name.lower() or not obj.object_name.endswith(".tif"):
            logger.warning(f"Skipping {obj.object_name}")
            continue

                            # Read and download file content to temp file
        response = minio_client.get_object(SOURCE_BUCKET, obj.object_name)

        tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        tmp.write(response.read())
        tmp.close()

        logger.debug(f"Downloaded:\n\t\t\t\t   {obj.object_name}\n\t\t\t\tto temp file as:\n\t\t\t\t   {tmp.name}")
                            
        # Add file name and data to lists
        
        datasets.append(rasterio.open(tmp.name))
    
    return datasets, temp_files

def _merge_image_data_to_mosaic(datasets):
    # TODO: Ensure same CRS before merging
    # Merge datasets for the month
    logger.debug(f"Merging {len(datasets)} files...")
    mosaic, transform = merge(datasets)
    logger.debug(f"Merging complete!")

    # Use metadata from first dataset
    out_meta = datasets[0].meta.copy()
    out_meta.update({
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": transform
    })

    return mosaic, out_meta

def _crop_mosaic(mosaic, meta, geometry):
    logger.debug(f"Cropping mosaic...")

    meta = meta.copy()
    with MemoryFile() as memfile:
        with memfile.open(**meta) as dataset:
            dataset.write(mosaic)

            # Reproject geometry to raster CRS
            geom_gdf = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326")
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
                "transform": out_transform
            })

            return out_image, out_meta

def _save_cropped_data(product_key, saved_files, product_prefix, subfolder, file_id, year, month, out_meta, out_image):
    year_month = f"{year}{month.split("-")[0]}"
    output_dir = os.path.join(
                        "results",
                        product_prefix,
                        year,
                        month,
                        subfolder
                    )
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{os.path.join(product_key, year_month, subfolder, file_id)}.tif".replace("/","_")
    output_path = os.path.join(output_dir, output_filename)
                    
    logger.debug(f"Cropped image metadadata:\n{out_meta}")
    logger.debug(f"Saving cropped image data to local as:\n\t\t\t\t   {output_path}")

    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(out_image)

    saved_files.append(output_path)

    return saved_files

if __name__ == "__main__":
    init = datetime.now()
    logger.info(f"--- STARTING DOWNLOAD-MERGE-CROP PROCESS ---\n")
    gdf = gpd.read_file("../misc/geometry.geojson")
    tiles = _get_tiles_of_geometry(gdf)
    logger.debug(f"Tiles:\n{tiles}")
    dates = _get_year_month_pair("2024-01-01", "2024-01-01")
    logger.debug(dates)

    product_key="images"

    download_merge_crop_band_files(
        geometry_gdf=gdf,
        tiles_list=tiles,
        year_months=dates,
        product_key=product_key  # or whatever your bucket structure is
    )
    print()
    logger.info(f"--- TRANSFERENCE TIME FOR '{product_key.upper()}': {datetime.now() - init}---\n")
