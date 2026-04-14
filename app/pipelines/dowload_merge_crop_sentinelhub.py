import structlog

import geopandas as gpd
import numpy as np

from sentinelhub import geometry
from shapely.geometry import shape

from config.config import INDEX_BANDS, PRODUCT_TYPE_INDEX

logger = structlog.get_logger()

# --- SENTINELHUB PIPELINE ---

def download_crop_sentinelhub(
        geometry_gdf: gpd.GeoDataFrame,
        start_date: str,
        end_date: str,
        product_key: str,
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
    # TODO: Step 1 - Get all inputs for Sentinel Hub Request's evalscript and configuration
    
    # Build bbox from geometry
    parcel_center = shape(geometry_gdf.geometry.values[0]).representative_point()
    parcel_bounds = geometry_gdf.geometry.values[0].bounds
    min_lon, min_lat, max_lon, max_lat = parcel_bounds
    center_lat, center_lon = parcel_center.y, parcel_center.x
    
    # Get size from max geometry bounds
    width, heigth = 128, 128  # Sentinel Hub returns crops of W x H px images around lat & lon

    # Get product-specific bands and evalscript
    spectral_indices = PRODUCT_TYPE_INDEX.get(product_key, [])
    if product_key not in ["images", "AOT", "TCI", "WVP"]:
        bands = spectral_indices
    else:
        bands = set()
        for index in spectral_indices:
            bands.update(INDEX_BANDS.get(index, []))
    
    evalscript = generate_evalscript(bands)

    # TODO: Step 2 - Get request's response and compose for spectral indices or return bands for image products

    # TODO: Step 3 - Crop and save the data, return the ZIP file paths

def generate_evalscript(
    bands: list[str],
    units: str="REFLECTANCE",
    data_type: str=None,
    mosaicking_type: str="SIMPLE",
    bit_scale: str="UINT8",
    id: str=None,
    rendering: bool=None,
    mask: bool=None,
    resampling: str=None,
    clip_range: tuple=(0.0, 0.3),
    gamma: float=1.0,
):
    """
    Generate an evalscript for SentinelHub requests. The script is dinamically generated with the values provided.

    DOC: https://docs.sentinel-hub.com/api/latest/evalscript/v3/

    Arguments:
        bands (list | None): 
            Bands to include, e.g. `"B02"` or `["B02", "B03", "B04"]`.
        units (str | None):
            Units of the input bands (e.g. `"DN"`, `"REFLECTANCE"`). If None, omitted.
        data_type (str | None):
            Data type for input bands. If None, omitted.
        mosaicking_type (str | None):
            Type of mosaicking. If None, omitted.
        bit_scale (str | None):
            Bit scale of output bands. If None, `"AUTO"`.
        id (str):
            Response ID. If None, omitted.
        rendering (bool):
            Whether to apply rendering/visualization. If None, omitted.
        mask (bool):
            Whether to output mask. If None, omitted.
        resampling (str):
            Resampling method. If None, omitted.
        clip_range (tuple):
            Range for clipping values. If None, omitted.
        gamma (float):
            Gamma correction value. If None, omitted.

    Returns:
        evalscript (str): The generated evalscript for SentinelHub image request.
    """
    bands_str = ", ".join([f'"{band}"' for band in bands])

    input_opts = [f"bands: [{bands_str}]"]
    if units:
        input_opts.append(f'units: "{units}"')
    if data_type:
        input_opts.append(f'dataType: "{data_type}"')
    if mosaicking_type:
        input_opts.append(f'mosaicking: "{mosaicking_type}"')

    output_opts = [f"bands: {len(bands)}"]
    if id:
        output_opts.append(f'id: "{id}"')
    if bit_scale:
        output_opts.append(f'sampleType: "{bit_scale}"')
    if rendering is not None:
        output_opts.append(f"rendering: {str(rendering).lower()}")
    if mask is not None:
        output_opts.append(f"mask: {str(mask).lower()}")
    if resampling:
        output_opts.append(f'resampling: "{resampling}"')

    input_str = ",\n\t\t".join(input_opts)
    output_str = ",\n\t\t".join(output_opts)

    minv, maxv = clip_range
    stretch = f"(val - {minv}) / ({maxv - minv})"
    stretch = f"Math.max(0, Math.min(1, {stretch}))"
    if gamma != 1.0:
        stretch = f"Math.pow({stretch}, 1.0/{gamma})"

    # multiply by 255 if UINT8
    mult = " * 255" if bit_scale == "UINT8" else ""

    # apply stretch for each band
    out_expr = ", ".join(
        [f"{stretch.replace('val', f'sample.{b}')}{mult}" for b in bands])

    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{
      {input_str}
    }}],
    output: {{
      {output_str}
    }}
  }};
}}

function evaluatePixel(sample) {{
  return [{out_expr}];
}}
"""

def calculate_index(index: str, b2: np.ndarray, b3: np.ndarray, b4: np.ndarray, b5: np.ndarray, b8: np.ndarray, b8a: np.ndarray, b9: np.ndarray, b11: np.ndarray):
    """
    It calculates the index out of the available provided bands
    
    Arguments:
        index (str): Index ID to calculate
        b2 (numpy.ndarray): B02 band (Blue)
        b3 (numpy.ndarray): B03 band (Gree)
        b4 (numpy.ndarray): B04 band (Red)
        b5 (numpy.ndarray): B05 band (Red Edge)
        b8 (numpy.ndarray): B08 band (Near Infra-Red)
        b8a (numpy.ndarray): B08a band
        b9 (numpy.ndarray): B09 band
        b11 (numpy.ndarray): B11 band (SWIR 1)
    Returns:
        index_calc (NDArray[unsignedinteger[_8Bit]] | Any | list): Index calculation data
    """
    index_calc = []
    is_float_index = True
    match index.lower():
        case "rgb":  # True Color Image
            # Compose true color image.
            b2_clean = np.nan_to_num(b2, nan=0.0)
            b3_clean = np.nan_to_num(b3, nan=0.0)
            b4_clean = np.nan_to_num(b4, nan=0.0)

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
            index_calc = (b8 - b4) / (b8 + b4)

        case "ndsi":  # Normalized Difference Snow Index
            index_calc = (b3 - b11) / (b3 + b11)
            index_calc = (index_calc > 0.42) * 1.0  # threshold values above 0.42 are regarded as snowy

        case "ndwi":  # Normalized Difference Water Index
            index_calc = (b3 - b8) / (b3 + b8)

        case "evi2":  # Two-band Enhanced Vegetation Index
            index_calc = 2.4 * ((b8 - b4) / (b8 + b4 + 1.0))

        case "osavi":  # Optimized Soil-Adjusted Vegetation Index
            y_coeff = 0.16
            index_calc = (1 + y_coeff) * (b8 - b4) / (b8 + b4 + y_coeff)
        
        case "ndre":  # Normalized Difference Red Edge Index
            index_calc = (b9 - b5) / (b9 + b5)

        case "mndwi":  # Modified Normalized Difference Water Index
            index_calc = (b3 - b11) / (b3 + b11)

        case "bri":  # Brightness Index
            index_calc = (1 / b3 - 1 / b5) / b8
            
        case "evi":  # Enhanced Vegetation Index
            index_calc = (2.5 * (b8 - b4)) / ((b8 + 6 * b4 - 7.5 * b2) + 1)
        
        case "ndyi":  # Normalized Difference Yellowness Index
            index_calc = (b3 - b2) / (b3 + b2)

        case "ri":  # Redness Index
            index_calc = (b4 - b3) / (b4 + b3)

        case "cri1":  # Chlorophyll Redness Index 1
            index_calc = (1 / b2) / (1 / b3)

        case "bsi":  # Bare Soil Index
            index_calc = ((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2))
        
        case "exg":  # Excess Green index
            index_calc = 2 * b3 - b4 - b2

    if is_float_index:
            index_calc[index_calc == np.inf] = np.nan
            index_calc[index_calc == -np.inf] = np.nan
            index_calc = index_calc.astype(np.float32)

    # Return index calculation data
    return index_calc


# --- UTILS ---
