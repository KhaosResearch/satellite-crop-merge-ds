import math
import os
from affine import Affine
import structlog

import geopandas as gpd
import numpy as np

from datetime import datetime
from sentinelhub import BBox, CRS, SentinelHubRequest
from dateutil.relativedelta import relativedelta
from sentinelhub.constants import MimeType
from sentinelhub.data_collections import DataCollection

from config.config import PRODUCT_TYPE_FILE_IDS, SPECTRAL_INDICES_DATA, SENTINELHUB_CONFIG
from utils.geospatial_utils import get_year_month_pair
from utils.io_utils import save_cropped_data, save_to_zip
from utils.merge_crop_utils import crop_mosaic
from utils.sentinelhub_utils import generate_evalscript

logger = structlog.get_logger()

# --- SENTINELHUB PIPELINE ---

def download_crop_sentinelhub(
        geometry_gdf: gpd.GeoDataFrame,
        start_date: str,
        end_date: str,
        product_key: str,
        job_dir: str
    ) -> str:
    """Downloads, merges and crops Sentinel-2 data for the specified geometry and temporal range.
    Args:
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
        start_date (str):
            The starting date in ISO format (`YYYY-MM-DD`).
        end_date (str):
            The finishing date in ISO format (`YYYY-MM-DD`).
        product_key (str):
            The ID of the product.
    Returns:
        zip_path (str):
            The compressed ZIP filepath with all of the product data.
    """
    # Get product-specific bands and evalscript
    saved_files = []
    if product_key in ["images", "AOT", "TCI", "WVP"]:
        dates = get_year_month_pair(start_date, end_date)
        logger.debug(dates)
        for res in [10, 20, 60]:
            subkey = f"{res}m" if product_key == "images" else ""
            bands = PRODUCT_TYPE_FILE_IDS.get(product_key, None).get(subkey, None)
            saved_files.extend(_crop_monthly_timeseries(product_key, product_key, bands, res, geometry_gdf, start_date, end_date, job_dir))
    else:
        # Retrieve bands for all spectral indices
        subkey = ""
        spectral_indices = PRODUCT_TYPE_FILE_IDS.get(product_key, None).get(subkey, None)
        for index in spectral_indices:
            bands, res = SPECTRAL_INDICES_DATA.get(index, None).get("bands", None), SPECTRAL_INDICES_DATA.get(index, None).get("resolution", None)
            if bands and res:
                #  Get composed spectral indices
                saved_files.extend(_crop_monthly_timeseries(product_key, index, bands, res, geometry_gdf, start_date, end_date, job_dir))

    # Save the data, return the ZIP file paths
    saved_files = list(set(saved_files))
    zip_path = save_to_zip(product_key, job_dir, saved_files)
    return zip_path

def _crop_monthly_timeseries(
        product_key: str,
        id:str,
        bands: list[str],
        res: int,
        geometry_gdf: gpd.GeoDataFrame,
        total_start_date: str,
        total_end_date: str,
        job_dir: str
        )->list[str]:
    """Creates and crops monthly composites of the specified product over the given geometry and returns an organize list of filepaths to compress.
    Args:
        product_key (str):
            The ID of the product.
        id (str):
            The spectral index ID or product key (it depends on whether product was index-related or not respectively).
        res (int):
            Band resolution in m/px.
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
        total_start_date (str):
            The starting date in ISO format (`YYYY-MM-DD`).
        total_end_date (str):
            The finishing date in ISO format (`YYYY-MM-DD`).
        job_dir (str):
            The Job directory where the cropped files will be saved before being compressed in a ZIP file.
    Returns:
        saved_files (list[str]):
            List of saved files associated to the product. It is updated along the process and used to create the ZIP file at the end.
    """
    current_start = datetime.strptime(total_start_date, "%Y-%m-%d")
    final_end = datetime.strptime(total_end_date, "%Y-%m-%d")
    
    saved_files = []
    is_index_data = product_key not in ["images", "AOT", "WVP"]

    dates = get_year_month_pair(total_start_date, total_end_date)
    index_date = 0
    while current_start < final_end:
        year_str, month_str = dates[index_date]
        # Calculate the end of the current month (excludes last date's month to avoid partial data)
        next_month = current_start + relativedelta(months=1)
        current_end = next_month if next_month < final_end else final_end
        logger.info(f"Processing month: {current_start.strftime('%Y-%m')}")
        
        try:
            # Fetch the Monthly Composite
            data = _get_sentinelhub_bands_data(
                id, bands, res, geometry_gdf, 
                current_start.strftime("%Y-%m-%d"), 
                current_end.strftime("%Y-%m-%d"),
            )
            
            if data and len(data) > 0:
                # Pre-process raw data array for indexes
                raw_array = data[0].astype(np.float32)  # Ensure format
                raw_array = np.moveaxis(raw_array, -1, 0)  # Switch dimensions (H, W, C) -> (C, H, W)
                raw_array = np.nan_to_num(raw_array, nan=0.0, posinf=0.0, neginf=0.0)  # Normalize anomalous values

                if id.lower() in SPECTRAL_INDICES_DATA.keys():  # Clip for spectral indices
                    logger.debug(f"Spectral index '{id.upper()}' detected. Clipping data (-1.0, 1.0)")
                    low, high = (0.0, 1.0) if id.lower() == "tci" else (-1.0, 1.0)
                    raw_array = np.clip(raw_array, low, high)

                width, height = raw_array.shape[2], raw_array.shape[1]  # Get dimensions

                # Get BBox and correct transform function
                _, bbox, __, __= _get_sentinelhub_request_params(id, bands, res, geometry_gdf)
                res_x = (bbox.max_x - bbox.min_x) / width
                res_y = (bbox.max_y - bbox.min_y) / height
                transform_tuple = (bbox.min_x, res_x, 0, bbox.max_y, 0, -res_y)
                bbox_transform = Affine.from_gdal(*transform_tuple)  # transform is now simple because units are METERS
               
                # Get mosaic metadata
                target_crs = f"EPSG:{bbox.crs.value}"
                parcel_geometry = geometry_gdf.to_crs(target_crs).geometry.values[0]
                meta = {
                    "driver": "GTiff",
                    "nodata": 0,
                    "width": width,
                    "height": height,
                    "count": raw_array.shape[0],
                    "dtype": "float32",
                    "crs": target_crs,
                    "transform": bbox_transform,
                }

                # Crop stack data from geometry
                cropped_data, cropped_meta = crop_mosaic(raw_array, meta, parcel_geometry)

                # Build filepath to save cropped data
                resolution_tag=f"{str(res)}m"

                if not is_index_data:
                    product_prefix = product_key 
                    subfolder = f"R{resolution_tag}"
                    for i, band_id in enumerate(bands):
                        # Isolate a single band (H, W) but keep it 3D for the saver: (1, H, W)
                        single_band_data = cropped_data[i:i+1, :, :]
                        
                        # Update meta for a single channel
                        single_band_meta = cropped_meta.copy()
                        single_band_meta.update({"count": 1})

                        saved_files.extend(
                            save_cropped_data(
                                job_dir=job_dir, 
                                product_key=product_key, 
                                saved_files=saved_files, 
                                product_prefix=product_prefix,
                                subfolder=subfolder, 
                                file_id=band_id,
                                year=year_str, 
                                month=month_str,
                                resolution_tag=resolution_tag, 
                                out_image=single_band_data, 
                                out_meta=single_band_meta
                            )
                        )
                else:
                    product_prefix = os.path.join("indices", product_key) if product_key != "TCI" else product_key
                    subfolder = ""
                
                    # Generate path and save files
                    saved_files.extend(
                        save_cropped_data(
                            job_dir=job_dir, product_key=product_key, saved_files= saved_files, product_prefix=product_prefix,
                            subfolder=subfolder, file_id=id, year=year_str, month=month_str,
                            resolution_tag=resolution_tag, out_image=cropped_data, out_meta=cropped_meta)
                        )

        except Exception as e:
            logger.error(f"Failed to fetch data for {current_start.strftime('%Y-%m')}: {e}")

        # Continue with next month        
        index_date += 1
        current_start = next_month

    return saved_files

def _get_sentinelhub_bands_data(
        id:str,
        bands: list[str],
        res: int,
        geometry_gdf: gpd.GeoDataFrame,
        start_date: str,
        end_date: str,
        max_cloud_concentration: float=0.5
    ):
    """Get Sentinel-2 band data via `SentinelHubRequest`.
    Args:
        id (str):
            Product key or spectral index ID.
        bands (list[str]):
            Band identifiers list (i.e `["B02", "B03", "B04", "B08"]`).
        res (int):
            Band resolution in m/px.
        geometry_gdf (gpd.GeoDataFrame):
            Geometry GeoDataFrame of the parcel.
        start_date (str):
            Initial date for time range.
        end_date (str):
            Final date for time range.
        max_cloud_concentration (float):
            Maximum cloud concentration allowed on band data.
    Returns:
        data (list):
            Returns `data = [array(... shape=(width_px, height_px, total_num_bands), dtype=uint8)]`.
            Band data is presented in the same order as in the `bands` arg. To access a specific band, use `band_data = data[0][:, :, band_index]`
    """
    # Get request parameters
    evalscript, bbox, width_px, height_px = _get_sentinelhub_request_params(id, bands, res, geometry_gdf)

    if width_px > 2500 or height_px > 2500:
        logger.warning("WARNING: Image size cannot be greater than 2500px on any dimension for current Sentinehl Hub request. Try the SH implementation for large images if you must.")
        width_px = min(width_px, 2500)
        height_px = min(height_px, 2500)
        logger.warning(f"Capping dimensions at {width_px}x{height_px}")

    config = SENTINELHUB_CONFIG

    # Build and send request
    sh_request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A.define_from("s2l2a", service_url=config.sh_base_url),
                time_interval=(start_date, end_date),
                maxcc=max_cloud_concentration,
                mosaicking_order= 'leastCC',  # least cloudy
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=(width_px, height_px),
        config=config,
    )

    data = sh_request.get_data()
    
    return data

def _get_sentinelhub_request_params(
        id: str,
        bands: list[str],
        res: int,
        geometry_gdf: gpd.GeoDataFrame,
    )->tuple:
    """Get all SentinelHubRequest necessary parameters for satellite data download.
    Args:
        id (str):
            Product key or spectral index ID.
        bands (list[str]):
            Band identifiers list (i.e `["B02", "B03", "B04", "B08"]`).
        res (int):
            Band resolution in m/px.
        geometry_gdf (gpd.GeoDataFrame):
            Geometry GeoDataFrame of the parcel.
    Returns:
        evalscript,bbox,width_px,height_px (tuple):
            A tuple with the `evalscript` (str), the geometry's `bbox` (BBox) and the `width_px` (int) and `height_px` (int).
    """
    # Get EvalScript
    evalscript = generate_evalscript(bands, index_id=id)

    # Get size in meters
    utm_crs = geometry_gdf.estimate_utm_crs()
    utm_gdf = geometry_gdf.to_crs(utm_crs)
    minx, miny, maxx, maxy = utm_gdf.total_bounds
    logger.debug(f"Geometry Size: {round(maxx - minx, 3)} x {round(maxy - miny, 2)} m")
    
    # Get BBox data from geometry
    bbox = BBox(
        bbox=tuple(geometry_gdf.to_crs("EPSG:4326").total_bounds),
        crs=CRS.WGS84
    )

    # Get size in px
    width_px = math.ceil((maxx - minx) / res)
    height_px = math.ceil((maxy - miny) / res)
    logger.debug(f"Geometry Size at {res}m/px: {width_px}x{height_px} px")

    return evalscript, bbox, width_px, height_px

if __name__ == "__main__":
    init = datetime.now()
    print()
    logger.info(f"--- STARTING SENTINELHUB PIPELINE ---\n")

    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2025-03-01"
    end_date ="2025-03-31"
    product_key = "images"
    job_dir = "/home/miguel/Dev/satellite-crop-merge-ds/app/results/123/88d46fa7"

    zip_path = download_crop_sentinelhub(geometry_gdf, start_date, end_date, product_key, job_dir)

    print()
    logger.info(f"--- TRANSFERENCE TIME DOWNLOADING FOR {product_key.upper()} FROM {start_date} TO {end_date}: {datetime.now() - init} ---\n")
