import math
import os
import shutil
import zipfile
import numpy
import rasterio
from shapely import box
import structlog
import tempfile
import time
import uuid

import geopandas as gpd

from datetime import datetime
from minio import Minio
from pathlib import Path
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge

from config.config import ASDATA_BUCKET, ASDATA_CLIENT, PRODUCT_TYPE_FILE_IDS, RESULTS_FULL_PATH, SENTINEL2_GRIDS_FILE, SOURCE_BUCKET, SOURCE_CLIENT, SPECTRAL_INDICES_RESOLUTION

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
        tiles = [_get_aster_tiles_of_geometry(geometry_gdf)[0]]  # Get the first tile since they don't overlap and all of them have the same data for the overlapping area
    elif product_key not in PRODUCT_TYPE_FILE_IDS.keys():
        ve = ValueError(f"Error: Product key must be one of the following: {str(PRODUCT_TYPE_FILE_IDS.keys()).replace("[","").replace("[","")}. Product key was: {product_key}")
        logger.error(ve)
        raise ve
    else:
        minio_client = SOURCE_CLIENT
        minio_bucket = SOURCE_BUCKET
        tiles = _get_sentinel_tiles_of_geometry(geometry_gdf)

    init = datetime.now()
    print()
    logger.info(f"--- STARTING DOWNLOAD-MERGE-CROP PROCESS ---\n")
    logger.debug(f"Tiles:\n{tiles}")
    dates = _get_year_month_pair(start_date, end_date)
    logger.debug(dates)

    # Create process data Job Directory
    job_dir = _create_job_dir(RESULTS_FULL_PATH, user)

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
    After collecting monthly composite bands/indices filepaths and content, it merges each into its own mosaic file.
    After merging, it crops the geometry and saves the cropped data locally and in a ZIP file.

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
        
        # Check and setup if user requested Sentinel composite data or Aster data (aspect, elevation or slope)
        if product_key in ["images", "AOT", "TCI", "WVP", "aspect", "elevation", "slope"]:
            product_prefix = product_key
        else:
            product_prefix = os.path.join("indices", product_key)

        temp_dir = tempfile.mkdtemp()

        is_sentinel_data = product_key in ["images", "AOT", "TCI", "WVP"]

        if is_sentinel_data:
            # Download-crop-merge from Sentinel composites data
            product_config = PRODUCT_TYPE_FILE_IDS[product_key]

            saved_files = get_sentinel_composites_data(tiles_list, year_months, product_key, job_dir, minio_client, minio_bucket, saved_files, geometry, product_prefix, product_config, temp_dir)
        else:
            # Download-crop-merge from Aster data
            saved_files = get_aster_gdem_data(tiles_list, product_key, job_dir, minio_client, minio_bucket, saved_files, geometry, temp_dir)
        zip_path = _save_to_zip(product_key, job_dir, saved_files)
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

                    datasets = [rasterio.open(p) for p in local_paths]

                    if not datasets:
                        continue
                    mosaic, out_meta = _merge_image_data_to_mosaic(datasets)

                        # Cleanup after each month
                    for ds in datasets:
                        ds.close()
                    for f in local_paths:
                        try:
                            os.remove(f)
                        except:
                            pass

                    out_image, out_meta = _crop_mosaic(mosaic, out_meta, geometry)
                    saved_files = _save_cropped_data(job_dir, product_key, saved_files, product_prefix, subfolder, file_id, year, month, resolution_tag, out_image, out_meta, minio_client, minio_bucket)
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
    if product_key != "elevation":
        filename = f"{product_key}.tif"
        local_paths = _download_parallel_aster_data(tiles_list, product_key, filename, temp_dir, minio_client, minio_bucket)
    else:
        elevation_filenames_prefix =f"ASTGTMV003_tile"
        local_paths = _download_parallel_aster_data(tiles_list, product_key, elevation_filenames_prefix, temp_dir, minio_client, minio_bucket)

    datasets = [rasterio.open(p) for p in local_paths]
    mosaic, out_meta = _merge_image_data_to_mosaic(datasets)

        # Cleanup after each month
    for ds in datasets:
        ds.close()
    for f in local_paths:
        try:
            os.remove(f)
        except:
            pass

    out_image, out_meta = _crop_mosaic(mosaic, out_meta, geometry)
    saved_files = _save_cropped_data(job_dir, product_key, saved_files, product_key, "", file_id="", year="", month="", resolution_tag="", out_image=out_image, out_meta=out_meta, minio_client=minio_client, minio_bucket=minio_bucket)

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
        filename = filename.replace("tile", f"{tile}_dem.tif")  # For elevation data, does not affect any other product
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

# --- GEOSPATIAL LOGIC ---
def _get_sentinel_tiles_of_geometry(geometry_gdf: gpd.GeoDataFrame) -> list[str]:
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

def _get_aster_tiles_of_geometry(geometry_gdf: gpd.GeoDataFrame) -> list[str]:
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

def _merge_image_data_to_mosaic(datasets: list[rasterio.io.DatasetReader])->tuple:
    """Merges all same image data from different tiles into one mosaic
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

# --- I/O LOGIC ---
def _create_job_dir(base_dir: Path, user: str) -> Path:
    job_id = str(uuid.uuid4())[:8]
    job_dir = base_dir / user / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir

def _save_cropped_data(
        job_dir: Path,
        product_key: str,
        saved_files: list[str],
        product_prefix: str,
        subfolder: str,
        file_id: str,
        year: str,
        month: str,
        resolution_tag: str,
        out_image: numpy.ndarray,
        out_meta: dict,
        minio_client: Minio=SOURCE_CLIENT,
        minio_bucket: str=SOURCE_BUCKET
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
        resolution_tag (str):
            Resolution tag for the filename.
        month (str):
            Months `NN-MMM` string.
        out_image (numpy.ndarray):
            Cropped image data.
        out_meta (dict):
            Cropped image metadata.
        minio_client (Minio):
            The MinIO client with access to the bucket. Only needed if `saved_files` has not got the README.
    Returns:
        saved_files (list[str]):
            List of saved files associated to the product.
"""
    try:
        year_month = f"{year}{month.split("-")[0]}"
        output_dir = os.path.join(
                            job_dir,
                            product_prefix,
                            year,
                            month,
                            subfolder
                        )
        
        # Generate results dir and filepath
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{"_".join([product_key, year_month, "comp", resolution_tag, file_id])}.tif"
        output_path = os.path.join(output_dir, output_filename)
                        
        # logger.debug(f"Cropped image metadadata:\n{out_meta}")
        logger.debug(f"Saving cropped image data to local as:\n\t\t\t\t   {output_path}")

        # Save results
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(out_image)

        saved_files.append(output_path)
        
        if not any("README" in file for file in saved_files):
            saved_files = _save_readme(job_dir, product_prefix, product_key, saved_files, minio_client, minio_bucket)

        return saved_files
    except Exception as e:
        raise Exception(f"Error while saving: {e}")

def _save_readme(
        job_dir: Path,
        product_prefix: str,
        product_key: str,
        saved_files: list[str],
        minio_client: Minio=SOURCE_CLIENT,
        minio_bucket: str=SOURCE_BUCKET
    )->list[str]:
    """It specifically downloads and saves the selected product type readme from MinIO.
    Args:
        product_prefix (str):
            First part of the MinIO prefix for the bucket.
        product_key (str):
            The ID of the product.
        saved_files (list[str]):
            List of saved files associated to the product.
        minio_client (Minio):
            The MinIO client with access to the bucket.
    Returns:
        saved_files (list[str]):
            List of saved files associated to the product.
    """
    minio_path = os.path.join(product_prefix, f"README_{product_key}.pdf")
    output_path = os.path.join(job_dir, minio_path)
    readme_exists_in_minio = _file_exists_in_minio(minio_path, minio_client, minio_bucket)
    try:
        if readme_exists_in_minio:
            logger.debug(f"Downloading README_{product_key} file")
            # Download object from MinIO
            response = minio_client.get_object(minio_bucket, minio_path)
            
            # Save to local file
            with open(output_path, "wb") as file_data:
                for chunk in response.stream(32 * 1024):
                    file_data.write(chunk)

            response.close()
            response.release_conn()

            saved_files.append(output_path)
        else:
            logger.warning(f"Object {minio_path} does not exist in {minio_bucket}. Cancelling README download...")

        return saved_files

    except Exception as e:
        logger.error(f"Error downloading README in {minio_path}: {e}")
        raise Exception(f"Error downloading README in {minio_path}: {e}")

def _save_to_zip(product_key: str, job_dir: str, saved_files: list[str])->str:
    zip_path = os.path.join(job_dir, f"results_{product_key}.zip")
    logger.info(f"Zipping {zip_path}...")
    with zipfile.ZipFile(zip_path, "w") as z:
        for file in saved_files:
            if file.endswith(".tif"):
                filepath = Path(file).relative_to(job_dir)
                if "/indices/" in file:
                    filepath = Path(str(filepath).split("indices/").pop())
            elif file.endswith(".pdf"): 
                filepath = os.path.basename(file)
            else:
                continue
            z.write(file, arcname=filepath)
    return zip_path

def _file_exists_in_minio(minio_path, minio_client: Minio=SOURCE_CLIENT, bucket_name: str=SOURCE_BUCKET):
    try:
        minio_client.stat_object(bucket_name, minio_path)
        file_exists = True
    except Exception:
        file_exists = False
    return file_exists

def cleanup_old_jobs(
        base_dir: Path=Path(RESULTS_FULL_PATH),
        max_age_hours=2
    ):
    while True:
        try:
            run_cleanup_pass(base_dir, max_age_hours)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        time.sleep(1800) 

def run_cleanup_pass(
        base_dir: Path=Path(RESULTS_FULL_PATH),
        max_age_hours=2
    ):

    now = time.time()

    for user_dir in base_dir.iterdir():
        if not user_dir.is_dir():
            continue

        for job_dir in user_dir.iterdir():
            try:
                age = now - job_dir.stat().st_mtime
                logger.info(f"{job_dir} age: {age/3600:.2f} hours")
                if age > max_age_hours * 3600:
                    shutil.rmtree(job_dir)
                    logger.info(f"Deleted old job directory: {job_dir}")
            except Exception as e:
                logger.error(f"Error occurred while cleaning up old job directory {job_dir}: {e}") # every 30 min

if __name__ == "__main__":
    # Test run
    product_key = "WVP"
    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2024-01-01"
    end_date ="2024-12-01"
    user = "user-1234"
    for product_key in ["slope", "elevation", "aspect"]:
        get_product_for_parcel(product_key, geometry_gdf, start_date, end_date, user)