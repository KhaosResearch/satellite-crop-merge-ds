import os
import zipfile
from minio import Minio
import rasterio
import tempfile
import structlog

import geopandas as gpd

from datetime import datetime
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge

from config.config import SENTINEL2_GRIDS_FILE, SOURCE_BUCKET, SOURCE_CLIENT

logger = structlog.get_logger()

def get_product_for_parcel(product: str, geometry: gpd.GeoDataFrame, start_date: str, end_date: str):

    parcel_geometry = geometry
    product_key = product
    
    # Get tiles the parcel containing the parcel
    tiles_list = get_tiles_of_geometry(parcel_geometry)

    # Get date range (years & months)
    year_months = get_year_month_pair(start_date, end_date)
    
    # Download (and merge) tile files from MinIO (filtered by product)
    mosaic, meta = download_merge_crop_tile_files(tiles_list, year_months, product_key)
    transform = meta["transform"]

    # Crop once
    out_image, out_meta = crop_mosaic(mosaic, transform, meta, parcel_geometry-geometry.values[0])    
    
    # TODO: ZIP all and return (keep dir structure)
    None

def get_tiles_of_geometry(geojson):
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

def get_year_month_pair(start_date: str, end_date: str):
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

def download_merge_crop_tile_files(
        geometry_gdf: gpd.GeoDataFrame,
        tiles_list: list[str],
        year_months: list[tuple],
        product_key: str,
        minio_client: Minio=SOURCE_CLIENT
    ) -> tuple:
    """It iterates over the MinIO using the args data to build the paths and downloads all relevant files.
    After collecting filepaths and file content it merges them into a single mosaic file to crop the geometry over it.
    After merging, it crops the geometry and returns the cropped data.

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
        for year, month in year_months:
            for tile in tiles_list:
                datasets = []
                temp_files = []
                # Get al files in specific product-geometry_zone-date prefix
                minio_product_prefix = os.path.join(product_key, tile, year, month)
                product_dir_list = minio_client.list_objects(SOURCE_BUCKET, prefix=minio_product_prefix, recursive=True)

                for obj  in product_dir_list:
                    if not obj.object_name.endswith(".tif"):
                        logger.warning(f"Skipping {obj.object_name}")
                        continue

                    # Read and download file content to temp file
                    response = minio_client.get_object(SOURCE_BUCKET, obj.object_name)

                    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
                    tmp.write(response.read())
                    tmp.close()

                    logger.debug(f"Downloaded:\n\t\t\t\t   {obj.object_name}\n\t\t\t\tto temp file as:\n\t\t\t\t   {tmp.name}")
                    # Add file name and data to lists
                    temp_files.append(tmp.name)
                    datasets.append(rasterio.open(tmp.name))

                # Merge datasets for the month
                if not datasets:
                    continue
                    # return None, None

                # Merge all tiles
                logger.debug("Merging...")
                mosaic, transform = merge(datasets)

                # Use metadata from first dataset
                out_meta = datasets[0].meta.copy()
                out_meta.update({
                    "height": mosaic.shape[1],
                    "width": mosaic.shape[2],
                    "transform": transform
                })
                # return mosaic, out_meta

                logger.debug(f"Cropping mosaic...\n{mosaic}")
                out_image, out_meta = crop_mosaic(mosaic, out_meta, geometry)
                os.makedirs("res", exist_ok=True)
                output_filename = f"{product_key}_{tile}_{year}_{month}.tif"
                output_path = os.path.join(os.getcwd(),"res", output_filename)
                
                logger.debug(f"Cropped image metadadata:\n{out_meta}")
                logger.debug(f"Saving cropped image data to local as:\n\t\t\t\t   {output_path}")

                with rasterio.open(output_path, "w", **out_meta) as dest:
                    dest.write(out_image)

                saved_files.append(output_path)

                # Cleanup after each month
                for ds in datasets:
                    ds.close()
                for f in temp_files:
                    try:
                        os.remove(f)
                    except:
                        pass

        zip_path = os.path.join(os.getcwd(), "res", "result.zip")
        logger.debug(f"Zipping {zip_path}...")
        with zipfile.ZipFile(zip_path, "w") as z:
            for file in saved_files:
                z.write(file, arcname=os.path.basename(file))
    except Exception as e:
        raise e

def crop_mosaic(mosaic, meta, geometry):
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

if __name__ == "__main__":
    gdf = gpd.read_file("../misc/geometry.geojson")
    tiles = get_tiles_of_geometry(gdf)
    logger.debug(f"Tiles:\n{tiles}")
    dates = get_year_month_pair("2024-01-01", "2024-02-01")
    logger.debug(dates)
    download_merge_crop_tile_files(
        geometry_gdf=gdf,
        tiles_list=tiles,
        year_months=dates,
        product_key="images"  # or whatever your bucket structure is
    )