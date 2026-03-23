import os
from typing import Iterator
import zipfile
from minio import Minio
from minio.datatypes import Object
import numpy
import rasterio
import tempfile
import structlog

import geopandas as gpd

from datetime import datetime
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling

from config.config import PRODUCT_TYPE_FILE_IDS, SENTINEL2_GRIDS_FILE, SOURCE_BUCKET, SOURCE_CLIENT, SPECTRAL_INDICES_RESOLUTION

logger = structlog.get_logger()

def get_product_for_parcel(
        product_key: str,
        geometry_gdf: gpd.GeoDataFrame,
        start_date: str,
        end_date: str
    ) -> str:
    """Retrieve the specified product type for the given geometry and temporal range as a compressed ZIP file.
    Args:
        product_key (str):
            The ID of the product.
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
        start_date (str):
            The starting date in ISO format (`YYYY-MM-DD`).
        end_date (str):
            The finishing date in ISO format (`YYYY-MM-DD`).
    Returns:
        zip_path (str):
            The compressed ZIP filepath with all of the product data.
    """
    if product_key not in PRODUCT_TYPE_FILE_IDS.keys():
        ve = ValueError(f"Error: Product key must be one of the following: {str(PRODUCT_TYPE_FILE_IDS.keys()).replace("[","").replace("[","")}. Product key was: {product_key}")
        logger.error(ve)
        raise ve
    init = datetime.now()
    print()
    logger.info(f"--- STARTING DOWNLOAD-MERGE-CROP PROCESS ---\n")
    tiles = _get_tiles_of_geometry(geometry_gdf)
    logger.debug(f"Tiles:\n{tiles}")
    dates = _get_year_month_pair(start_date, end_date)
    logger.debug(dates)

    zip_path = download_merge_crop_band_files(
        geometry_gdf=geometry_gdf,
        tiles_list=tiles,
        year_months=dates,
        product_key=product_key
    )
    print()
    logger.info(f"--- TRANSFERENCE TIME FOR '{product_key.upper()}': {datetime.now() - init} ---\n")

    return zip_path

def download_merge_crop_band_files(
        geometry_gdf: gpd.GeoDataFrame,
        tiles_list: list[str],
        year_months: list[tuple],
        product_key: str,
        minio_client: Minio=SOURCE_CLIENT
    ) -> str:
    """It iterates over the MinIO using the args data to build the paths and downloads all relevant files.
    After collecting monthly composite band's filepaths and content, it merges them into a single mosaic file.
    After merging, it crops the geometry and saves the cropped data in a ZIP file.

    Args:
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
        tiles_list (list[str]):
            Sentinel-2 tile's ID list.
        year_months (list[tuple]):
            List of `("YYYY", "NN-MMM")` tuples.
        product_key (str):
            Product ID string.
    Returns:
        zip_path (str):
            The compressed ZIP filepath with all of the product data.

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
                    logger.info(f"Acessing data from {year}-{month}...")
                    datasets = []
                    temp_files = []
                    for tile in tiles_list:

                        # Get all files in specific product-geometry-date prefix
                        minio_product_prefix = os.path.join(product_prefix, tile, year, month, subfolder)
                        product_dir_list = minio_client.list_objects(SOURCE_BUCKET, prefix=minio_product_prefix, recursive=True)

                        datasets, temp_files = _get_object_files_data(minio_client, file_id, geometry_gdf, datasets, temp_files, product_dir_list)
                    
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

        zip_path = os.path.join(os.getcwd(), "results", f"results_{product_key}.zip")
        logger.info(f"Zipping {zip_path}...")
        with zipfile.ZipFile(zip_path, "w") as z:
            for file in saved_files:
                z.write(file, arcname=file)
        return zip_path
    except Exception as e:
        raise e

def _get_tiles_of_geometry(geometry_gdf: gpd.GeoDataFrame) -> list[str]:
    """Get the tile/tiles the geometry is comprised in.
    Args:
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
    Returns:
        tile_ids (list[str]):
            The Setinel-2 Tile's ID list.
    """
    if not SENTINEL2_GRIDS_FILE or not os.path.exists(SENTINEL2_GRIDS_FILE):
        print(os.getcwd())
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

def _get_year_month_pair(start_date: str, end_date: str) -> list[tuple]:
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

def _get_object_files_data(
        minio_client: Minio,
        file_id: str,
        geometry_gdf: gpd.GeoDataFrame,
        datasets: list[rasterio.io.DatasetReader],
        temp_files: list[str],
        product_dir_list: Iterator[Object]
    ) -> tuple:
    """It retrieves all data from files in the specific MinIO directory using the input as prefix.
    Args:
        minio_client (Minio):
            The MinIO client with access to the bucket.
        file_id (str):
            The identifier to find the specific file/files. Usually, band/index name withpout extensions.
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
        datasets (list[rasterio.io.DatasetReader]):
            The list of datasets associated to the files found.
        temp_files (list[str]):
            The list of filenames associated to the files found.
        product_dir_list (Iterator[Object]):
            The list of objects found in the bucket's prefix.
    Returns:
        tuple:
            The data and filenames associates to the files found.
    """
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
        temp_files.append(tmp.name)
        dataset_entry = rasterio.open(tmp.name)
        aligned_dataset_entry = _align_crs(dataset_entry, str(geometry_gdf.crs))
        datasets.append(aligned_dataset_entry)
    
    return datasets, temp_files

def _align_crs(dataset_entry: rasterio.io.DatasetReader, target_crs: str)->rasterio.io.DatasetReader:
    """
    Checks dataset entry against a target CRS. 
    If a dataset differs, it warps it in memory and returns a new MemoryFile-backed dataset.
    Args:
        datasets (list[rasterio.io.DatasetReader]):
            The list of datasets associated to the files found.
        target_crs (str):
            The specific Coorinates Reference System to use.
    Returns:
        aligned_dataset_entry (rasterio.io.DatasetReader):
            The aligned data.
    """
    aligned_dataset_entry = dataset_entry
    
    if not dataset_entry.crs == target_crs:
        logger.debug(f"Warping dataset from {dataset_entry.crs} to {target_crs}")
        
        # Calculate transform for the new CRS
        transform, width, height = calculate_default_transform(
            dataset_entry.crs, target_crs, dataset_entry.width, dataset_entry.height, *dataset_entry.bounds
        )
        kwargs = dataset_entry.meta.copy()
        kwargs.update({
            'crs': target_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        # Warp into a MemoryFile
        mem_file = MemoryFile()
        with mem_file.open(**kwargs) as dest:
            reproject(
                source=rasterio.band(dataset_entry, 1),
                destination=rasterio.band(dest, 1),
                src_transform=dataset_entry.transform,
                src_crs=dataset_entry.crs,
                dst_transform=transform,
                dst_crs=target_crs,
                resampling=Resampling.nearest
            )
        # Open the memory file to keep it active for the merge
        aligned_dataset_entry = mem_file.open()
            
    return aligned_dataset_entry

def _merge_image_data_to_mosaic(datasets: list[rasterio.io.DatasetReader])->tuple:
    """Merges all same image data from different tiles into one mosaic
    Args:
        datasets (list[rasterio.io.DatasetReader]):
            The list of datasets associated to the files found.
    Returns:
    tuple:
        The moasic's data and metadata.
    """
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

def _crop_mosaic(mosaic: numpy.ndarray, meta: dict, geometry_gdf: gpd.geodataframe):
    """Crops the mosaic given the parcel's geometry
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

def _save_cropped_data(
        product_key: str,
        saved_files: list[str],
        product_prefix: str,
        subfolder: str,
        file_id: str,
        year: str,
        month: str,
        out_image: numpy.ndarray,
        out_meta: dict,
    )->list[str]:
    """It saves locally all files associated to the product.
    It uses the arguments to mimic the MinIO dir structure on local.
    Args:
        product_key (str):
            The ID of the product.
        saved_files (list[str]):
            List of saved files associated to the product.
        product_prefix (str):
            First part of the MinIO prefix for the bucket.
        subfolder (str):
            Subfolder inside the prefix.
        file_id (str):
            The identifier to find the specific file/files. Usually, band/index name withpout extensions.
        year (str):
            Year `YYYY` string.
        month (str):
            Months `NN-MMM` string.
        out_image (numpy.ndarray):
            Cropped image data.
        out_meta (dict):
            Cropped image metadata.
    Returns:
        saved_files (list[str]):
            List of saved files associated to the product.
"""
    year_month = f"{year}{month.split("-")[0]}"
    output_dir = os.path.join(
                        f"results",
                        product_prefix,
                        year,
                        month,
                        subfolder
                    )
    if len(subfolder) > 0:  # For Image bands
        resolution_tag = str(subfolder)[1:] 
    else:  # For spectral index
        resolution_tag = f"{SPECTRAL_INDICES_RESOLUTION.get(file_id)}m"
    
    # Generate results dir and filepath
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{os.path.join(product_key, year_month, "comp", resolution_tag, file_id)}.tif".replace("/","_")
    output_path = os.path.join(output_dir, output_filename)
                    
    # logger.debug(f"Cropped image metadadata:\n{out_meta}")
    logger.debug(f"Saving cropped image data to local as:\n\t\t\t\t   {output_path}")

    # Save results
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(out_image)

    saved_files.append(output_path)

    return saved_files

if __name__ == "__main__":
    
    product_key = "images"
    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2024-01-01"
    end_date ="2024-01-01"

    get_product_for_parcel(product_key, geometry_gdf, start_date, end_date)