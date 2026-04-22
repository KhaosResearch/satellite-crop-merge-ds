import structlog

from typing import Literal

from config.config import SPECTRAL_INDICES_DATA

logger = structlog.get_logger()

# --- UTILS ---

def generate_evalscript(
    bands: list[str] = None,
    index_id: str = None,
    mosaicking_type: Literal["SIMPLE", "ORBIT", "TILE"] = "ORBIT",
    units: Literal["REFLECTANCE", "OPTICAL_DEPTH", "DN."] = "REFLECTANCE",
    sample_type: Literal["INT8", "UINT8", "INT16", "UINT16", "FLOAT32", "AUTO"] = "FLOAT32",
    mask: bool = True
)->str:
    """
    Generate an evalscript for SentinelHub requests. The script is dinamically generated with the values provided.

    DOC: https://docs.sentinel-hub.com/api/latest/evalscript/v3/

    Args:
        bands (list | str | None): 
            Bands to include, e.g. `"B02"` or `["B02", "B03", "B04"]`.
        index_id (str | None):
            The spectral index ID. If it's not an spectral index ID, the `bands` arg is used to acquire the band data.
        mosaicking_type (str | None):
            Type of mosaicking. Default is `"ORBIT"`.
        units (str | None):
            Units of the input bands or index. Default is `"REFLECTANCE"`.
        sample_type (str | None):
            Bit scale of output bands. If None, `"FLOAT32"`.
        mask (bool):
            Whether to output mask. If None, omitted.
    Returns:
        evalscript (str):
            The generated evalscript for SentinelHub image request.
    """

    # Determine Logic Path: Raw Bands vs Spectral index composition
    if index_id and index_id.lower() in SPECTRAL_INDICES_DATA:
        cfg = SPECTRAL_INDICES_DATA[index_id.lower()]
        formula_template = cfg["formula"]
        req_bands = cfg["bands"]
        is_rgb = (index_id.lower() == "tci")
    else:
        formula_template = None
        req_bands = bands if bands else []
        is_rgb = False
        units = "DN" if index_id == "AOT" else units
    # Sync Input Bands
    input_bands = list(dict.fromkeys(req_bands + (["dataMask"] if mask else [])))
    bands_str = ", ".join([f'"{b}"' for b in input_bands])
    
    # sE Output Configuration
    base_channels = 3 if is_rgb else 1
    if not formula_template:
        base_channels = len(req_bands)
    
    out_channels = base_channels + (1 if mask else 0)
    
    sig, body = _generate_evaluatepixel_function(mosaicking_type, formula_template, is_rgb, out_channels, mask, req_bands)

    return f"""//VERSION=3
function setup() {{
  return {{
    input: [{{ bands: [{bands_str}], units: "{units}" }}],
    output: {{ bands: {out_channels}, sampleType: "{sample_type}" }},
    mosaicking: "{mosaicking_type}"
  }};
}}

function evaluatePixel({sig}) {{
  {body}
}}"""

def _generate_evaluatepixel_function(
        mosaicking_type: str,
        formula_template: str,
        is_rgb: bool,
        out_channels: int,
        mask: bool,
        req_bands: list[str]
    )->tuple:
    """Generate the `evaluatePixel` function to compose the index or return the requested bands.
    Args:
        mosaicking_type (str):
            Type of mosaicking.
        formula_template (str): 
            Formula template to compose the index or return the bands.
        is_rgb (bool):
            If true, it composes a True Color image.
        out_channels (int):
            Number of output channels. For spectral indices: 1 for index + 1 for mask. For bands: N for bands +1 for mask.
        mask (bool):
            Whether to output mask. If None, omitted.
        req_bands (list[str]):
            List of band IDs required for the composition or processing.
    Returns:
        sig,body (tuple(str)):
            The `evaluatePixel` function signature and method body.
    """
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

    # Construct the Return Logic
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
    return sig, body
