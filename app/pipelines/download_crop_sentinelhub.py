import math
import os
from typing import Literal
from affine import Affine
import structlog

import geopandas as gpd
import numpy as np

from datetime import datetime
from dateutil.relativedelta import relativedelta
from sentinelhub.constants import MimeType
from sentinelhub.data_collections import DataCollection

from sentinelhub import BBox, CRS, SentinelHubRequest

from utils.geospatial_utils import get_year_month_pair
from utils.io_utils import save_cropped_data
from utils.merge_crop_utils import crop_mosaic
from config.config import PRODUCT_TYPE_FILE_IDS, SPECTRAL_INDICES_DATA, SENTINELHUB_CONFIG

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
    subkey = "" if product_key != "images" else "60m"
    spectral_indices = PRODUCT_TYPE_FILE_IDS.get(product_key, None).get(subkey, None)
    if product_key in ["images", "AOT", "TCI", "WVP"]:
        bands = spectral_indices
        dates = get_year_month_pair(start_date, end_date)
        logger.debug(dates)
        for res in [10, 20, 60]:
            saved_files = _crop_monthly_timeseries(product_key, product_key, bands, res, geometry_gdf, start_date, end_date, job_dir)

    else:
        # Retrieve bands for all spectral indices
        for index in spectral_indices:
            bands, res = SPECTRAL_INDICES_DATA.get(index, None).get("bands", None), SPECTRAL_INDICES_DATA.get(index, None).get("resolution", None)
            if bands and res:
                #  Get composed spectral indices
                saved_files = _crop_monthly_timeseries(product_key, index, bands, res, geometry_gdf, start_date, end_date, job_dir)

    # TODO: Save the data, return the ZIP file paths

def _crop_monthly_timeseries(product_key, id, bands, res, geometry_gdf, total_start, total_end, job_dir):
    """Creates monthly composites using the `_get_sentinelhub_bands_data` and returns them in a dictionary.
    """
    current_start = datetime.strptime(total_start, "%Y-%m-%d")
    final_end = datetime.strptime(total_end, "%Y-%m-%d")
    
    saved_files = []
    
    dates = get_year_month_pair(start_date, end_date)
    index_date = 0
    while current_start < final_end:
        year_str, month_str = dates[index_date]
        # Calculate the end of the current month (excludes last date's month to avoid partial data)
        next_month = current_start + relativedelta(months=1)
        current_end = next_month if next_month < final_end else final_end
        
        logger.info(f"Processing month: {current_start.strftime('%Y-%m')}")
        
        try:
            # TODO: Account for images (N=4, N=9, N=11), AOT (N=3), TCI (N=3) & WVP (N=3) (those have bands, not spectral indices, hence data will include all N bands required)
            # Fetch the Monthly Composite
            data = _get_sentinelhub_bands_data(
                id, bands, res, geometry_gdf, 
                current_start.strftime("%Y-%m-%d"), 
                current_end.strftime("%Y-%m-%d")
            )
            
            if data and len(data) > 0:
                # Pre-process raw data array for indexes
                raw_array = data[0]
                # raw_array = data[0].astype(np.float32)  # Ensure format
                raw_array = np.moveaxis(raw_array, -1, 0)  # Switch dimensions (H, W, C) -> (C, H, W)
                raw_array = np.nan_to_num(raw_array, nan=0.0, posinf=0.0, neginf=0.0)  # Normalize anomalous values
                if id.lower() in SPECTRAL_INDICES_DATA.keys():  # Clip for spectral indices
                    logger.debug(f"Spectral index '{id.upper()}' detected. Clipping data (-1.0, 1.0)")
                    raw_array[..., 0] = np.clip(raw_array[..., 0], -1.0, 1.0)
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

                # Crop data from geometry
                cropped_data, cropped_meta = crop_mosaic(raw_array, meta, parcel_geometry)

                # Build filepath to save cropped data
                resolution_tag=f"{str(res)}m"

                if product_key in ["images", "AOT", "TCI", "WVP"]:
                    product_prefix = product_key 
                    subfolder = f"R{resolution_tag}m"
                else:
                    product_prefix = os.path.join("indices", product_key)
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

# --- UTILS ---
def generate_evalscript(
    bands: list[str] = None,
    index_id: str = None,
    mosaicking_type: Literal["SIMPLE", "ORBIT", "TILE"] = "ORBIT",
    sample_type: Literal["INT8", "UINT8", "INT16", "UINT16", "FLOAT32", "AUTO"] = "FLOAT32",
    mask: bool = True
)->str:
    """
    Generate an evalscript for SentinelHub requests. The script is dinamically generated with the values provided.

    DOC: https://docs.sentinel-hub.com/api/latest/evalscript/v3/

    Arguments:
        bands (list | str | None): 
            Bands to include, e.g. `"B02"` or `["B02", "B03", "B04"]`.
        index_id (str | None):
            The spectral index ID. If it's not an spectral index ID, the `bands` arg is used to acquire the band data.
        mosaicking_type (str | None):
            Type of mosaicking. If None, omitted.
        sample_type (str | None):
            Bit scale of output bands. If None, `"AUTO"`.
        mask (bool):
            Whether to output mask. If None, omitted.
    Returns:
        evalscript (str): The generated evalscript for SentinelHub image request.
    """

    # Determine Logic Path: Raw Bands vs Spectral index composition
    if index_id and index_id.lower() in SPECTRAL_INDICES_DATA:
        cfg = SPECTRAL_INDICES_DATA[index_id.lower()]
        formula_template = cfg["formula"]
        req_bands = cfg["bands"]
        is_rgb = (index_id.lower() == "rgb")
    else:
        formula_template = None
        req_bands = bands if bands else []
        is_rgb = False
    
    # Sync Input Bands
    input_bands = list(dict.fromkeys(req_bands + (["dataMask"] if mask else [])))
    bands_str = ", ".join([f'"{b}"' for b in input_bands])
    
    # sE Output Configuration
    base_channels = 3 if is_rgb else 1
    if not formula_template:
        base_channels = len(req_bands)
    
    out_channels = base_channels + (1 if mask else 0)

    # Handle Mosaicking / Signature
    is_temporal = mosaicking_type in ["ORBIT", "TILE"]
    sig = "samples" if is_temporal else "sample"
    s_pref = "samples[i]." if is_temporal else "sample."

    # Build evaluatePixel Body with Stability Guard
    if formula_template:
        # We wrap the formula in a JS helper to prevent Infinity/NaN
        calc_expr = formula_template.replace("s.", s_pref)
        
        # If the result is not finite, return 0. 
        
        if is_rgb:
            # RGB logic usually returns 3 channels; assuming calc_expr returns array
            pixel_val = f"var val = {calc_expr}; return isFinite(val[0]) ? [...val"
        else:
            pixel_val = f"var val = {calc_expr}; var res = isFinite(val) ? val : 0;"

    # 6. Construct the Return Logic
    if is_temporal:
        if formula_template:
            # Index Calculation Path
            body = f"""
    for (var i = 0; i < samples.length; i++) {{
        if (samples[i].dataMask === 1) {{
            {pixel_val}
            return [res{f', samples[i].dataMask' if mask else ''}];
        }}
    }}
    return new Array({out_channels}).fill(0);"""
        else:
            # Raw Bands Path
            band_vals = ", ".join([f"samples[i].{b}" for b in req_bands])
            pixel_val = f"[{band_vals}{f', samples[i].dataMask' if mask else ''}]"
            body = f"""
    for (var i = 0; i < samples.length; i++) {{
        if (samples[i].dataMask === 1) {{
            return {pixel_val};
        }}
    }}
    return new Array({out_channels}).fill(0);"""
    else:
        # Simple Mosaicking
        if formula_template:
            body = f"{pixel_val} return [res{f', sample.dataMask' if mask else ''}];"
        else:
            band_vals = ", ".join([f"sample.{b}" for b in req_bands])
            body = f"return [{band_vals}{f', sample.dataMask' if mask else ''}];"

    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{ bands: [{bands_str}], units: "REFLECTANCE" }}],
    output: {{ bands: {out_channels}, sampleType: "{sample_type}" }},
    mosaicking: "{mosaicking_type}"
  }};
}}

function evaluatePixel({sig}) {{
  {body}
}}"""

if __name__ is "__main__":
    init = datetime.now()
    print()
    logger.info(f"--- STARTING SENTINELHUB PIPELINE ---\n\n")

    bands = ["B02", "B03", "B04", "B08"]
    bands = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B09', 'B11', 'B12']
    res = 10
    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2025-03-01"
    end_date ="2025-03-31"

    job_dir = "/home/miguel/Dev/satellite-crop-merge-ds/app/results/123/88d46fa7"
    product_key = "Vegetation"
    for index in PRODUCT_TYPE_FILE_IDS.get(product_key).get(""):
        logger.debug(f"Now getting {index.upper()} index.")
        bands, res = SPECTRAL_INDICES_DATA.get(index, None).get("bands", None), SPECTRAL_INDICES_DATA.get(index, None).get("resolution", None)

        saved_files = _crop_monthly_timeseries(product_key, index, bands, res, geometry_gdf, start_date, end_date, job_dir)
    print()
    logger.info(f"--- TRANSFERENCE TIME DOWNLOADING FOR {product_key.upper()} FROM {start_date} TO {end_date} AT {res}M/PX: {datetime.now() - init} ---\n")
