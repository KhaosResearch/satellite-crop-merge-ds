
import os
import shutil
import zipfile
import numpy
import rasterio
import structlog
import time
import uuid

from minio import Minio
from pathlib import Path

from config.config import PRODUCT_TYPE_FILE_IDS, RESULTS_FULL_PATH, SOURCE_BUCKET, SOURCE_CLIENT

logger = structlog.get_logger()

# --- I/O LOGIC ---

def save_cropped_data(
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
            The identifier to find the specific file/files. Usually, band/index name.
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
        output_dir = os.path.join(job_dir, product_prefix, year, month, subfolder)
        
        # Generate results dir and filepath
        os.makedirs(output_dir, exist_ok=True)
        if product_key not in PRODUCT_TYPE_FILE_IDS.keys():
            tiles_tag = resolution_tag  # Used store the tiles str for ASTER products
            crop_tag = "crop" if not "-" in tiles_tag else "merge-crop"  # Multiple tiles = merge + crop, Single tile = only crop
            output_filename = f"{"_".join(["ASTGTMV003", product_key, tiles_tag, crop_tag])}.tif"
        else:
            output_filename = f"{"_".join([product_key, year_month, "comp", resolution_tag, file_id])}.tif"
        output_path = os.path.join(output_dir, output_filename)
                        
        logger.debug(f"Saving cropped image data to local as:\n\t\t\t\t   {output_path}")

        # Save results
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(out_image)

        saved_files.append(output_path)
   
        # Get and save README
        if not any("README" in file for file in saved_files):
            saved_files = _save_readme(job_dir, product_prefix, product_key, saved_files, minio_client, minio_bucket)

        return saved_files
    except Exception as e:
        raise Exception(f"Error while saving: {e}")

def save_to_zip(product_key: str, job_dir: str, saved_files: list[str])->str:
    zip_path = os.path.join(job_dir, f"results_{product_key}.zip")
    logger.info(f"Zipping {zip_path}...")
    with zipfile.ZipFile(zip_path, "w") as z:
        for file in saved_files:
            if file.endswith(".tif") or file.endswith(".tfw"):
                filepath = Path(file).relative_to(job_dir)
                if "/indices/" in file:
                    filepath = Path(str(filepath).split("indices/").pop())
            elif file.endswith(".pdf"): 
                filepath = os.path.basename(file)
            else:
                continue
            z.write(file, arcname=filepath)
    return zip_path

def create_job_dir(base_dir: Path, user: str) -> Path:
    job_id = str(uuid.uuid4())[:8]
    job_dir = base_dir / user / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir

def cleanup_old_jobs(base_dir: Path=Path(RESULTS_FULL_PATH), max_age_hours=2):
    while True:
        try:
            run_cleanup_pass(base_dir, max_age_hours)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        time.sleep(1800) 

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
    minio_path = os.path.join(product_prefix, f"README_{product_key}_v2.pdf")
    output_path = os.path.join(job_dir, minio_path)
    readme_exists_in_minio = _file_exists_in_minio(minio_path, minio_client, minio_bucket)
    
    if not readme_exists_in_minio:
        output_path = output_path.replace("_v2", "")  # Try OG README if the v2 does not exist
        readme_exists_in_minio = _file_exists_in_minio(minio_path, minio_client, minio_bucket)
    
    try:
        if readme_exists_in_minio:
            logger.debug(f"Downloading README file for {product_key.upper()}")
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

def _file_exists_in_minio(minio_path, minio_client: Minio=SOURCE_CLIENT, bucket_name: str=SOURCE_BUCKET):
    """Checks if a file exists in MinIO.
    Args:
        minio_path (str): The path of the file in the MinIO bucket.
        minio_client (Minio): The MinIO client with access to the bucket.
        bucket_name (str): The name of the MinIO bucket.
    Returns:
        bool: `True` if the file exists, `False` otherwise.
    """
    try:
        minio_client.stat_object(bucket_name, minio_path)
        file_exists = True
    except Exception:
        file_exists = False
    return file_exists

def run_cleanup_pass(base_dir: Path=Path(RESULTS_FULL_PATH), max_age_hours=2):
    """Deletes job directories older than `max_age_hours` hours.
    Args:
        base_dir (Path): The base directory where job directories are stored.
        max_age_hours (int): The maximum age in hours for job directories to keep. Directories older than this will be deleted.
    """
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
