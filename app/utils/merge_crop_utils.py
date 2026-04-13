import numpy
import os
import rasterio
import shutil
import structlog
import tempfile

import geopandas as gpd

from minio import Minio
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling

from utils.io_utils import save_cropped_data
from utils.io_utils import save_cropped_data
from config.config import SOURCE_BUCKET, SOURCE_CLIENT

logger = structlog.get_logger()

# --- MERGE-CROP LOGIC ---

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
        local_paths (list):
            List of strings/Paths to the downloaded temporary .tif files.
        geometry (dict/GeoJSON):
            The geometry used to mask/crop the mosaic.
        job_dir (str):
            Directory where the final output will be stored.
        product_key (str):
            Identifier for the specific satellite product.
        saved_files (list):
            Accumulated list of paths to successfully saved files.
        product_prefix, subfolder, file_id, year, month, resolution_tag: Metadata strings used for naming the output file.
        minio_client (Minio):
            Optional. Client object if uploading directly to MinIO. Default: `SOURCE_CLIENT`
        minio_bucket (str): 
            Optional. Target bucket name for MinIO uploads. Default: `SOURCE_BUCKET`

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
                tiles_tag = os.path.dirname(p).split("/").pop()  # Assuming tile ID is parent directory
                output_filename = f"{"_".join(["ASTGTMV003", product_key, tiles_tag])}.tfw"
                tfw_output_path = os.path.join(output_dir, output_filename)
                if tfw_output_path not in saved_files:
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
    try:
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
            
            target_crs = datasets[0].crs
            aligned_datasets = [datasets[0]]
            # Use a temporary directory for any reprojected files
            with tempfile.TemporaryDirectory() as temp_warp_dir:
                for ds in datasets[1:]:
                    if ds.crs != target_crs:
                        logger.warning(f"CRS mismatch: {ds.name} ({ds.crs}) vs {target_crs}. Reprojecting...")
                        aligned_ds = _ensure_matching_crs(ds, target_crs, temp_warp_dir)
                        aligned_datasets.append(aligned_ds)
                    else:
                        aligned_datasets.append(ds)
                
                # Use the aligned list for the merge
                mosaic, transform = merge(aligned_datasets)
                
                # Close the reprojected datasets (not the originals)
                for ds in aligned_datasets:
                    if "reprojected_" in ds.name:
                        ds.close()
            logger.info(f"Merging complete!")

            # Use metadata from first dataset
            out_meta = datasets[0].meta.copy()
            out_meta.update({
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": transform
            })
        return mosaic, out_meta
    except Exception as e:
        ex = Exception(f"Error while merging: {e}")
        logger.error(str(ex))
        raise ex

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

def _ensure_matching_crs(src_dataset, target_crs, temp_dir):
    """Reprojects a dataset to the target CRS if they don't match."""
    if src_dataset.crs == target_crs:
        return src_dataset
    
    # Calculate transform for new CRS
    transform, width, height = calculate_default_transform(
        src_dataset.crs, target_crs, src_dataset.width, src_dataset.height, *src_dataset.bounds
    )
    kwargs = src_dataset.meta.copy()
    kwargs.update({'crs': target_crs, 'transform': transform, 'width': width, 'height': height})

    # Create a temporary file for the reprojected version
    temp_path = os.path.join(temp_dir, f"reprojected_{os.path.basename(src_dataset.name)}")
    with rasterio.open(temp_path, 'w', **kwargs) as dst:
        for i in range(1, src_dataset.count + 1):
            reproject(
                source=rasterio.band(src_dataset, i),
                destination=rasterio.band(dst, i),
                src_transform=src_dataset.transform,
                src_crs=src_dataset.crs,
                dst_transform=transform,
                dst_crs=target_crs,
                resampling=Resampling.nearest
            )
    return rasterio.open(temp_path)
