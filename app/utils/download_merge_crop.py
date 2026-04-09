import os
import shutil
import structlog
import tempfile

import geopandas as gpd

from datetime import datetime
from minio import Minio
from pathlib import Path

from utils.io_utils import _file_exists_in_minio, create_job_dir, save_to_zip
from utils.geospatial_utils import get_aster_tiles_of_geometry, get_sentinel_tiles_of_geometry, get_year_month_pair, process_merge_crop
from config.config import ASDATA_BUCKET, ASDATA_CLIENT, PRODUCT_TYPE_FILE_IDS, RESULTS_FULL_PATH, SOURCE_BUCKET, SOURCE_CLIENT, SPECTRAL_INDICES_RESOLUTION

logger = structlog.get_logger()

# --- ORCHESTRATORS ---
def get_product_for_parcel(
        product_key: str,
        geometry_gdf: gpd.GeoDataFrame,
        start_date: str,
        end_date: str,
        user: str,
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
    if product_key in ["aspect", "elevation", "slope"]:
        minio_client = ASDATA_CLIENT
        minio_bucket = ASDATA_BUCKET
        tiles = [get_aster_tiles_of_geometry(geometry_gdf)[0]]  # Get the first tile since they don't overlap and all of them have the same data for the overlapping area
    elif product_key not in PRODUCT_TYPE_FILE_IDS.keys():
        ve = ValueError(f"Error: Product key must be one of the following: {str(PRODUCT_TYPE_FILE_IDS.keys()).replace("[","").replace("[","")}. Product key was: {product_key}")
        logger.error(ve)
        raise ve
    else:
        minio_client = SOURCE_CLIENT
        minio_bucket = SOURCE_BUCKET
        tiles = get_sentinel_tiles_of_geometry(geometry_gdf)

    init = datetime.now()
    print()
    logger.info(f"--- STARTING DOWNLOAD-MERGE-CROP PROCESS ---\n")
    logger.debug(f"Tiles:\n{tiles}")
    dates = get_year_month_pair(start_date, end_date)
    logger.debug(dates)

    # Create process data Job Directory
    job_dir = create_job_dir(RESULTS_FULL_PATH, user)

    zip_path = download_merge_crop_minio(
        geometry_gdf=geometry_gdf,
        tiles_list=tiles,
        year_months=dates,
        product_key=product_key,
        job_dir = job_dir,
        minio_client=minio_client,
        minio_bucket=minio_bucket
    )

    # Save geometry as GeoJSON
    optional_geojson_filepath = os.path.join(job_dir, "parcel_geometry.geojson")
    with open(optional_geojson_filepath, "w", encoding="utf-8") as f:
            f.write(geometry_gdf.to_json())
    logger.info(f"Saved parcel's geometry to {optional_geojson_filepath}!")
    print()
    logger.info(f"--- TRANSFERENCE TIME FOR '{product_key.upper()}': {datetime.now() - init} ---\n")

    return zip_path, optional_geojson_filepath

def download_merge_crop_minio(
        geometry_gdf: gpd.GeoDataFrame,
        tiles_list: list[str],
        year_months: list[tuple],
        product_key: str,
        job_dir: Path,
        minio_client: Minio=SOURCE_CLIENT,
        minio_bucket: str=SOURCE_BUCKET
    )-> str:
    """It iterates over the MinIO database, using the args data to build the paths and download all relevant files.
    After collecting filepaths and data by tile, it merges each into its own mosaic file.
    After merging, it crops the geometry and saves the cropped data locally and to a ZIP file.

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
    # Remove old result files
    results_dir = Path(job_dir)
    for item in results_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except OSError:
            pass
    try:
        saved_files = []
        geometry= geometry_gdf.geometry.values[0]
        
        # Check and setup prefix if user requested Sentinel composite data or ASTER data (aspect, elevation or slope)
        if product_key in ["images", "AOT", "TCI", "WVP", "aspect", "elevation", "slope"]:
            product_prefix = product_key
        else:
            product_prefix = os.path.join("indices", product_key)

        temp_dir = tempfile.mkdtemp()

        is_sentinel_data = product_key in PRODUCT_TYPE_FILE_IDS.keys()

        if is_sentinel_data:
            # Download-crop-merge from Sentinel composites data
            product_config = PRODUCT_TYPE_FILE_IDS[product_key]

            saved_files = get_sentinel_composites_data(tiles_list, year_months, product_key, job_dir, minio_client, minio_bucket, saved_files, geometry, product_prefix, product_config, temp_dir)
        else:
            # Download-crop-merge from Aster data
            saved_files = get_aster_gdem_data(tiles_list, product_key, job_dir, minio_client, minio_bucket, saved_files, geometry, temp_dir)
        zip_path = save_to_zip(product_key, job_dir, saved_files)
        return zip_path
    
    except Exception as e:
        raise e
    finally:
        shutil.rmtree(temp_dir)

def get_sentinel_composites_data(
        tiles_list: list[str],
        year_months: list[tuple],
        product_key: str,
        job_dir: str,
        minio_client: Minio,
        minio_bucket: str,
        saved_files: list[str],
        geometry: gpd.GeoDataFrame,
        product_prefix: str,
        product_config: dict,
        temp_dir: str
    )-> list[str]:
    """It iterates over the `sentinel-composites` MinIO bucket and performs the retrieval, merge (when needed) and crop operations for the requested product type data.
    Args:
        tiles_list (list[str]):
            Sentinel-2 tile's ID list.
        year_months (list[tuple]):
            List of `("YYYY", "NN-MMM")` tuples.
        product_key (str):
            Product ID string.
        job_dir (str):
            The Job directory where the cropped files will be saved before being compressed in a ZIP file.
        minio_client (Minio):
            The MinIO client with access to the bucket.
        minio_bucket (str):
            The MinIO bucket name.
        saved_files (list[str]):
            List of saved files associated to the product. It is updated along the process and used to create the ZIP file at the end.
        geometry (gpd.GeoDataFrame):
            The parcel's geometry.
        product_prefix (str):
            First part of the MinIO prefix for the bucket.
        product_config (dict):
            The dictionary with the product configuration in terms of which files are associated to each product key and their respective subfolders.
        temp_dir (str):
            Temporary directory to save the downloaded files from MinIO before merging and cropping.
    Returns:
        saved_files (list[str]):
            List of saved files associated to the product. It is updated along the process and used to create the ZIP file at the end.
    """
    for subfolder, file_ids in product_config.items():
        subfolder = f"R{subfolder}" if len(subfolder) > 0 else subfolder
        for year, month in year_months:
            for file_id in file_ids:
                logger.info(f"Accessing {file_id.upper()} data from {year} {month}...")
                    # Build MinIO filepath
                if product_key == "images":  # For Image bands
                    resolution_tags = [str(subfolder)[1:]] 
                elif "indices" in product_prefix:  # For spectral index
                    resolution_tags = [f"{SPECTRAL_INDICES_RESOLUTION.get(file_id)}m"]
                else:
                    resolution_tags = ["10m", "20m", "60m"]
                for resolution_tag in resolution_tags:
                    local_paths = []
                    for tile in tiles_list:
                        # Build MinIO object path
                        minio_obj_filename = f"T{tile}_{year}{month.split("-")[0]}_comp_{resolution_tag}_{file_id}.tif" 
                        minio_obj_path = os.path.join(product_prefix, tile, year, month, subfolder, minio_obj_filename)
                            
                        # Check if object exists database
                        if not _file_exists_in_minio(minio_obj_path, minio_client, minio_bucket):
                            logger.warning(f"Object does not exist! Skipping {minio_obj_path}")
                            continue
                            
                        # Get the specific object in the MinIO
                        local_file = os.path.join(temp_dir, f"{tile}_{file_id}.tif")
                        minio_client.fget_object(minio_bucket, minio_obj_path, local_file)
                        local_paths.append(local_file)

                    # Process the merge-crop-save process
                    saved_files = process_merge_crop( local_paths,geometry, job_dir, product_key, saved_files, product_prefix, subfolder, file_id, year, month, resolution_tag, minio_client, minio_bucket)

    return saved_files

def get_aster_gdem_data(
    tiles_list: list[str],
    product_key: str,
    job_dir: str,
    minio_client: Minio,
    minio_bucket: str,
    saved_files: list[str],
    geometry: gpd.GeoDataFrame,
    temp_dir: str
)-> list[str]:
    """It iterates over the `aster-gdem-data` MinIO bucket and performs the retrieval, merge (when needed) and crop operations for the requested product type data.
    Args:
        tiles_list (list[str]):
            Sentinel-2 tile's ID list.
        product_key (str):
            Product ID string.
        job_dir (str):
            The Job directory where the cropped files will be saved before being compressed in a ZIP file.
        minio_client (Minio):
            The MinIO client with access to the bucket.
        minio_bucket (str):
            The MinIO bucket name.
        saved_files (list[str]):
            List of saved files associated to the product. It is updated along the process and used to create the ZIP file at the end.
        geometry (gpd.GeoDataFrame):
            The parcel's geometry.
        temp_dir (str):
            Temporary directory to save the downloaded files from MinIO before merging and cropping.
    Returns:
        saved_files (list[str]):
            List of saved files associated to the product. It is updated along the process and used to create the ZIP file at the end.
    """
    logger.info(f"Acessign ASTER GDEM data...")
    # Set the filename pattern for Aster GDEM products
    extensions = [".tif", ".tfw"] if product_key != "elevation" else [".tif"]
    prefix = f"ASTGTMV003_tile" if product_key == "elevation" else product_key

    for ext in extensions:
        # Build object filename pattern and process the download-merge-crop-save process
        filename = f"{prefix}{ext}"
        local_paths = _download_parallel_aster_data(tiles_list, product_key, filename, temp_dir, minio_client, minio_bucket)
        saved_files = process_merge_crop( local_paths, geometry, job_dir, product_key, saved_files, product_prefix=product_key, subfolder="", file_id="", year="", month="", resolution_tag="-".join(tiles_list), minio_client=minio_client, minio_bucket=minio_bucket)

    return saved_files

def _download_parallel_aster_data(
    tiles_list:list[str],
    product_key: str,
    filename: str,
    temp_dir: str,
    minio_client: Minio=ASDATA_CLIENT,
    minio_bucket: str=ASDATA_BUCKET
)->list[str]:
    local_paths = []
    for tile in tiles_list:
        # Generate object name
        filename = filename.replace("tile", f"{tile}_dem")  # For elevation data, does not affect any other product
        minio_prefix = os.path.join(product_key, tile)
        object_name = os.path.join(minio_prefix, filename)
        # Check if object exists database
        if not _file_exists_in_minio(object_name, minio_client, minio_bucket):
            logger.warning(f"Object does not exist! Skipping {object_name}")
            continue

        # Save object to local
        local_file = os.path.join(temp_dir, os.path.basename(object_name))
        minio_client.fget_object(minio_bucket, object_name, local_file)

        # Add to files list for merging
        local_paths.append(local_file)
    return local_paths


if __name__ == "__main__":
    # Test run
    product_key = "BareSoil"  # 'aspect', 'elevation', 'slope' | 'AOT', 'BareSoil', 'images', 'Senescence', 'TCI', 'Vegetation', 'WaterContent', 'WaterMass', 'WVP', 'Yellow'
    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2024-01-01"
    end_date ="2024-12-31"
    user = "user-1234"
    # for product_key in ["slope", "elevation", "aspect"]:
    #     get_product_for_parcel(product_key, geometry_gdf, start_date, end_date, user)
    get_product_for_parcel(product_key, geometry_gdf, start_date, end_date, user)
