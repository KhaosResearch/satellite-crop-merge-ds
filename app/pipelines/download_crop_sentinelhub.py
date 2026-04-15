import ast
import math
import os
from typing import Literal
import structlog

import geopandas as gpd
import numpy as np

from datetime import datetime
from sentinelhub.constants import MimeType
from sentinelhub.data_collections import DataCollection

from sentinelhub import BBox, CRS, SentinelHubRequest

from utils.geospatial_utils import get_year_month_pair
from config.config import SPECTRAL_INDICES_BANDS, PRODUCT_TYPE_INDEX, SENTINELHUB_CONFIG, SPECTRAL_INDICES_RESOLUTION

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
    spectral_indices = PRODUCT_TYPE_INDEX.get(product_key, [])
    if product_key in ["images", "AOT", "TCI", "WVP"]:
        bands = spectral_indices
        dates = get_year_month_pair(start_date, end_date)
        logger.debug(dates)
        for res in [10, 20, 60]:
            data = _get_sentinelhub_bands_data(bands, res, geometry_gdf, start_date, end_date)


    else:
        # Retrieve bands for all spectral indices
        for index in spectral_indices:
            bands, res = SPECTRAL_INDICES_BANDS.get(index, None), SPECTRAL_INDICES_RESOLUTION.get(index, None)
            if bands and res:
                # Get index-related bands at broadest resolution
                data = _get_sentinelhub_bands_data(bands, res, geometry_gdf, start_date, end_date)
                i = 0
                bands_dict = {}
                while i < len(bands):
                    bands_dict[bands[i]] = data[0][:, :, i]

                # Compose spectral indices
                index_data = calculate_index(index, bands_dict)

    # TODO: Crop and save the data, return the ZIP file paths

def _get_sentinelhub_bands_data(bands: list[str], res: int, geometry_gdf: gpd.GeoDataFrame, start_date: str, end_date: str, max_cloud_concentration: float=0.3):
    """Get Sentinel-2 band data via `SentinelHubRequest`.
    Args:
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
            Maximum cloud concentration on band data.
    Returns:
        data (list):
            Returns `data = [array(... shape=(width_px, height_px, total_num_bands), dtype=uint8)]`.
            Band data is presented in the same order as in the `bands` arg. To access a specific band, use `band_data = data[0][:, :, band_index]`

    """
    # Get request parameters
    evalscript, bbox, width_px, height_px = _get_sentinelhub_request_params(bands, res, geometry_gdf)
    if width_px > 2500 or height_px > 2500:
        logger.warning("WARNING: Image size cannot be greater than 2500px on any dimension for current Sentinehl Hub request. Try the SH implementation for large images if you must.")
        width_px = 2500 if width_px > 2500 else width_px
        height_px = 2500 if height_px > 2500 else height_px
        logger.warning(f"Capping dimensions at {width_px}x{height_px}")
    
    logger.debug(f"Evalscript:\n{evalscript}")
    logger.debug(f"Size: {width_px}x{height_px} px")

    config = SENTINELHUB_CONFIG
    logger.debug(f"SentinelHub config:\n{config}")

    # Build and send request
    sh_request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A.define_from(
                    "s2l2a",
                    service_url=config.sh_base_url),
                time_interval=(
                    start_date,
                    end_date),
                maxcc=max_cloud_concentration,
            )
        ],
        responses=[SentinelHubRequest.output_response(
            "default", MimeType.TIFF)],
        bbox=bbox,
        size=(width_px, height_px),
        config=config,
    )

    data = sh_request.get_data()

    return data

def _get_sentinelhub_request_params(
        bands: list[str],
        res: int,
        geometry_gdf: gpd.GeoDataFrame,
    )->tuple:
    
    # Get EvalScript
    evalscript = generate_evalscript(bands)

    # Get size in meters
    gdf_m = geometry_gdf.to_crs("EPSG:3857")
    minx, miny, maxx, maxy = gdf_m.total_bounds
    logger.debug(f"Size: {maxx - minx}x{maxy - miny} m")

    # Get BBox data from geometry
    bbox = BBox(
        bbox=tuple(geometry_gdf.to_crs("EPSG:4326").total_bounds),
        crs=CRS.WGS84
    )

    # Get size in px
    width_px = math.ceil((maxx - minx) / res)
    height_px = math.ceil((maxy - miny) / res)

    

    return evalscript, bbox, width_px, height_px

# --- UTILS ---

def generate_evalscript(
        bands: list[str],
        units: Literal["DN", "REFLECTANCE"]="REFLECTANCE",
        data_type: str=None,
        mosaicking_type: Literal["SIMPLE", "ORBIT", "TILE"]="SIMPLE",
        sample_type: Literal["INT8", "UINT8", "INT16", "UINT16", "FLOAT32", "AUTO"]="FLOAT32",
        mask: bool=True,
        clip_range: tuple=(0.0, 0.3),
        gamma: float=1.0,
        is_scientific: bool=True
    ):
    """
    Generate an evalscript for SentinelHub requests. The script is dinamically generated with the values provided.

    DOC: https://docs.sentinel-hub.com/api/latest/evalscript/v3/

    Arguments:
        bands (list | str | None): 
            Bands to include, e.g. `"B02"` or `["B02", "B03", "B04"]`.
        units (str | None):
            Units of the input bands (e.g. `"DN"`, `"REFLECTANCE"`). If None, omitted.
        data_type (str | None):
            Data type for input bands. If None, omitted.
        mosaicking_type (str | None):
            Type of mosaicking. If None, omitted.
        sample_type (str | None):
            Bit scale of output bands. If None, `"AUTO"`.
        mask (bool):
            Whether to output mask. If None, omitted.
        clip_range (tuple):
            Range for clipping values. If None, omitted.
        gamma (float):
            Gamma correction value. If None, omitted.
        is_scientific (bool):
            If `True`, it handles data for scientific usage (raw) instead of optimizing for visualization (pre-processed).
    Returns:
        evalscript (str): The generated evalscript for SentinelHub image request.
    """

    if isinstance(bands, str):
        bands = ast.literal_eval(bands)
    
    # 1. Handle Mask Integration
    actual_input_bands = bands.copy()
    if mask and "dataMask" not in actual_input_bands:
        actual_input_bands.append("dataMask")

    bands_str = ", ".join([f'"{band}"' for band in actual_input_bands])

    # 2. Input Options
    input_opts = [f"bands: [{bands_str}]", f'units: "{units}"']
    if data_type: input_opts.append(f'dataType: "{data_type}"')
    if mosaicking_type: input_opts.append(f'mosaicking: "{mosaicking_type}"')

    # 3. Output Options - Increment band count if mask is requested
    out_band_count = len(bands) + (1 if mask else 0)
    output_opts = [f"bands: {out_band_count}"]
    if sample_type: output_opts.append(f'sampleType: "{sample_type}"')
    if mask is not None: output_opts.append(f"mask: {str(mask).lower()}")
    # ... (other output opts remain same)

    # 4. Expression Logic
    if is_scientific:
        # Raw spectral values
        expressions = [f"sample.{b}" for b in bands]
    else:
        # Visualization stretch
        minv, maxv = clip_range
        stretch = f"Math.max(0, Math.min(1, (val - {minv}) / ({maxv - minv})))"
        if gamma != 1.0: stretch = f"Math.pow({stretch}, 1.0/{gamma})"
        mult = " * 255" if sample_type == "UINT8" else ""
        expressions = [f"{stretch.replace('val', f'sample.{b}')}{mult}" for b in bands]

    if mask:
        expressions.append("sample.dataMask")
    
    out_expr = ", ".join(expressions)

    # 5. Handle Mosaicking Signature
    sig = "samples" if mosaicking_type in ["ORBIT", "TILE"] else "sample"
    # If using ORBIT, we pick the first valid sample in the stack for the monthly composite
    body = f"return [{out_expr}];" if sig == "sample" else f"return [{out_expr.replace('sample.', 'samples[0].')}];"

    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{
      {", ".join(input_opts)}
    }}],
    output: {{
      {", ".join(output_opts)}
    }}
  }};
}}

function evaluatePixel({sig}) {{
  {body}
}}
"""
def calculate_index(index: str, bands_dict: dict):
    """It calculates the index out of the available provided bands
    
    Arguments:
        index (str): Index ID to calculate
        bands_dict (dict): Dictionary with band data.
    Returns:
        index_calc (NDArray[unsignedinteger[_8Bit]] | Any | list): Index calculation data
    """
    # Retrieve bands and prepare outputs
    b02 = bands_dict.get("B02", None)  # B02 band (Blue)
    b03 = bands_dict.get("B03", None)  # B03 band (Gree)
    b04 = bands_dict.get("B04", None)  # B04 band (Red)
    b05 = bands_dict.get("B05", None)  # B05 band (Red Edge)
    b08 = bands_dict.get("B08", None)  # B08 band (Near Infra-Red)
    b8a = bands_dict.get("B8A", None)  # B8A band
    b09 = bands_dict.get("B09", None)  # B09 band
    b11 = bands_dict.get("B11", None)  # B11 band (SWIR 1)

    index_calc = []
    is_float_index = True

    match index.lower():
        case "rgb":  # True Color Image
            # Compose true color image.
            b2_clean = np.nan_to_num(b02, nan=0.0)
            b3_clean = np.nan_to_num(b03, nan=0.0)
            b4_clean = np.nan_to_num(b04, nan=0.0)

            # Adjust each band by the min-max, so it will plot as RGB.
            rgb_image_raw = np.stack((b4_clean, b3_clean, b2_clean), axis=0)

            # Normalization
            max_pixel_value = rgb_image_raw.max(initial=0)
            index_calc = np.multiply(rgb_image_raw, 255.0)
            index_calc = np.divide(index_calc, max_pixel_value)

            # NaN and overflowing values handling
            index_calc = np.nan_to_num(index_calc, nan=0.0)
            index_calc = np.clip(index_calc, 0, 255)

            # Conversion to uint8
            index_calc = index_calc.astype(np.uint8)
    
            is_float_index = False

        case "gvmi":  # Normalized Difference Moisture Index
            index_calc = (b8a - b11) / (b8a + b11)

        case "ndvi":  # Normalized Difference Vegetation Index
            index_calc = (b08 - b04) / (b08 + b04)

        case "ndsi":  # Normalized Difference Snow Index
            index_calc = (b03 - b11) / (b03 + b11)
            index_calc = (index_calc > 0.42) * 1.0  # threshold values above 0.42 are regarded as snowy

        case "ndwi":  # Normalized Difference Water Index
            index_calc = (b03 - b08) / (b03 + b08)

        case "evi2":  # Two-band Enhanced Vegetation Index
            index_calc = 2.4 * ((b08 - b04) / (b08 + b04 + 1.0))

        case "osavi":  # Optimized Soil-Adjusted Vegetation Index
            y_coeff = 0.16
            index_calc = (1 + y_coeff) * (b08 - b04) / (b08 + b04 + y_coeff)
        
        case "ndre":  # Normalized Difference Red Edge Index
            index_calc = (b09 - b05) / (b09 + b05)

        case "mndwi":  # Modified Normalized Difference Water Index
            index_calc = (b03 - b11) / (b03 + b11)

        case "bri":  # Brightness Index
            index_calc = (1 / b03 - 1 / b05) / b08
            
        case "evi":  # Enhanced Vegetation Index
            index_calc = (2.5 * (b08 - b04)) / ((b08 + 6 * b04 - 7.5 * b02) + 1)
        
        case "ndyi":  # Normalized Difference Yellowness Index
            index_calc = (b03 - b02) / (b03 + b02)

        case "ri":  # Redness Index
            index_calc = (b04 - b03) / (b04 + b03)

        case "cri1":  # Chlorophyll Redness Index 1
            index_calc = (1 / b02) / (1 / b03)

        case "bsi":  # Bare Soil Index
            index_calc = ((b11 + b04) - (b08 + b02)) / ((b11 + b04) + (b08 + b02))
        
        case "exg":  # Excess Green index
            index_calc = 2 * b03 - b04 - b02

    if is_float_index:
            index_calc[index_calc == np.inf] = np.nan
            index_calc[index_calc == -np.inf] = np.nan
            index_calc = index_calc.astype(np.float32)

    # Return index calculation data
    return index_calc


if __name__ is "__main__":
    init = datetime.now()
    print()
    logger.info(f"--- STARTING SENTINELHUB PIPELINE ---\n\n")

    bands = ["B02", "B03", "B04", "B08"]
    bands = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B09', 'B11', 'B12']
    res = 10
    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2025-01-01"
    end_date ="2025-12-31"

    data = _get_sentinelhub_bands_data(bands, res, geometry_gdf, start_date, end_date)
    logger.info(f"DATA\n{data}")
    logger.info(f"Type: {type(data)}")
    print()
    logger.info(f"--- TRANSFERENCE TIME DOWNLOADING {len(bands)} BANDS FROM {start_date} TO {end_date} AT {res}M/PX: {datetime.now() - init} ---\n")
