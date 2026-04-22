import os
from dotenv import load_dotenv
from pathlib import Path

from  config.minio_client import get_src_minio_client

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR_NAME = "results"
RESULTS_FULL_PATH = ROOT_DIR / RESULTS_DIR_NAME

ANDALUSIA_GEOJSON_FILEPATH = ROOT_DIR / "assets" / "andalucia.geojson"
PRODUCTS_DICT = {
    "en":{
        "Atmospheric Aerosols": "AOT",
        "Satellite Imagery": "images",
        "True Color Image": "TCI",
        "Atmospheric Humidity": "WVP",
        "Bare Soil": "BareSoil",
        "Vegetation Senescence": "Senescence ",
        "Vegetation Productivity": "Vegetation",
        "Vegetation Water Content": "WaterContent",
        "Water Masses": "WaterMass",
        "VegetationYellowing": "Yellow",
        "Terrain Orientation": "aspect",
        "Terrain Elevation": "elevation",
        "Terrain Slope": "slope",
    },
    "es": {
        "Aerosoles Atmosféricos": "AOT",
        "Imágenes de Satélite": "images",
        "Imágenes a Color": "TCI",
        "Humedad Atmosférica": "WVP",
        "Suelo Desnudo": "BareSoil",
        "Senescencia Vegetal": "Senescence ",
        "Productividad Vegetal": "Vegetation",
        "Contenido hídrico en plantas": "WaterContent",
        "Masas de aguas": "WaterMass",
        "Amarillamiento Vegetal": "Yellow",
        "Orientaciones del Terreno": "aspect",
        "Topografía del Terreno": "elevation",
        "Pendientes del Terreno": "slope",
    }
}
PRODUCT_KEY_LIST = ["AOT", "images", "TCI", "WVP", "BareSoil", "Senescence", "Vegetation", "WaterContent", "WaterMass", "Yellow", "aspect", "elevation", "slope"],

# --- MINIO CREDENTIALS ---
SOURCE_BUCKET = os.environ.get('MINIO_BUCKET_NAME')
SOURCE_CLIENT = get_src_minio_client()

ASDATA_CLIENT = get_src_minio_client(os.environ.get('ASDATA_MINIO_ACCESS_KEY'), os.environ.get('ASDATA_MINIO_SECRET_KEY'))
ASDATA_BUCKET = os.environ.get('ASDATA_MINIO_BUCKET_NAME')

SENTINEL2_GRIDS_FILE = os.environ.get('SENTINEL2_GRIDS_FILE')

# --- MINIO PRODUCT TYPE DATA ---
PRODUCT_TYPE_FILE_IDS = {
    "images": {
        "10m": [ 'B02', 'B03', 'B04', 'B08'],
        "20m": [ 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B11', 'B12'],
        "60m": [ 'B01', 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B09', 'B11', 'B12']
    },
    "BareSoil": {"": ["bsi"]},
    "Senescence": {"": ["bri", "cri1"]},
    "Vegetation": {"": ["evi", "evi2", "ndre", "ndvi", "osavi", "ri"]},
    "WaterContent": {"": ["ndsi", "mndwi"]},
    "WaterMass": {"": ["ndwi", "gvmi"]},
    "Yellow": {"": ["ndyi"]},
    "AOT": {"": ["AOT"]},
    "TCI": {"": ["TCI"]},
    "WVP": {"": ["WVP"]},
}

SPECTRAL_INDICES_DATA = {
    "bsi": {
        "bands": ["B02", "B04", "B08", "B11"],
        "resolution": 20,
        "formula": "((s.B11 + s.B04) - (s.B08 + s.B02)) / ((s.B11 + s.B04) + (s.B08 + s.B02))"
    },
    "bri": {
        "bands": ["B03", "B05", "B08"],
        "resolution": 20,
        "formula": "((1 / s.B03) - (1 / s.B05)) / s.B08"
    },
    "cri1": {
        "bands": ["B03", "B02"],
        "resolution": 20,
        "formula": "(1 / s.B02) / (1 / s.B03)",
    },
    "evi": {
        "bands": ["B02", "B04", "B08"],
        "resolution": 10,
        "formula": "(2.5 * (s.B08 - s.B04)) / ((s.B08 + 6 * s.B04 - 7.5 * s.B02) + 1)"
    },
    "evi2": {
        "bands": ["B04", "B08"],
        "resolution": 10,
        "formula": "2.4 * ((s.B08 - s.B04) / (s.B08 + s.B04 + 1.0))"
    },
    "gvmi": {
        "bands": ["B8A", "B11"],
        "resolution": 20,
        "formula": "(s.B8A - s.B11) / (s.B8A + s.B11)"
    },
    "mndwi": {
        "bands": ["B03", "B11"],
        "resolution": 20,
        "formula": "(s.B03 - s.B11) / (s.B03 + s.B11)"
    },
    "ndsi": {
        "bands": ["B03", "B11"],
        "resolution": 20,
        "formula": "((s.B03 - s.B11) / (s.B03 + s.B11) > 0.42) ? 1.0 : 0.0"
    },
    "ndre": {
        "bands": ["B05", "B09"],
        "resolution": 20,  # TODO: update to 60 when MinIO NDRE obj are also updated to 60
        "formula": "(s.B09 - s.B05) / (s.B09 + s.B05)"
    },
    "ndvi": {
        "bands": ["B04", "B08"],
        "resolution": 10,
        "formula": "((s.B08 + s.B04) == 0) ? 0: (s.B08 - s.B04) / (s.B08 + s.B04)"
    },
    "ndwi": {
        "bands": ["B03", "B08"],
        "resolution": 10,
        "formula": "(s.B03 - s.B08) / (s.B03 + s.B08)"
    },
    "ndyi": {
        "bands": ["B03", "B02"],
        "resolution": 10,
        "formula": "(s.B03 - s.B02) / (s.B03 + s.B02)"
    },
    "osavi": {
        "bands": ["B04", "B08"],
        "resolution": 10,
        "formula": "1.16 * (s.B08 - s.B04) / (s.B08 + s.B04 + 0.16)"
    },
    "ri": {
        "bands": ["B03", "B04"],
        "resolution": 10,
        "formula": "(s.B04 - s.B03) / (s.B04 + s.B03)"
    },
    "tci": {
        "bands": ["B02", "B03", "B04"],
        "resolution": 10,
        "formula": None
    },

}

# --- JS INTERFACE SCRIPTS ---
JS_RECIEVER = """
function() {
    if (window.gradioMapListenerAdded) return;
    window.gradioMapListenerAdded = true;

    window.addEventListener("message", (event) => {
        if (event.data && event.data.type === 'map_geometry') {
            const container = document.getElementById('map_data_input');
            if (!container) {
                console.error("Map Data Input container not found in DOM");
                return;
            }

            const textarea = container.querySelector('textarea');
            if (textarea) {
                // Set the value directly
                textarea.value = event.data.data;
                
                // Force sync with the internal Svelte state
                const updateEvent = new Event('input', { bubbles: true });
                textarea.dispatchEvent(updateEvent);
                
                // Also trigger change for good measure
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
                
                console.log("DOM Synced: Map data updated.");
            }
        }
    });
}
"""

HIDE_MAP_TEXTBOX_CSS = """
#map_data_input { 
    display: none !important; 
}
"""

def get_draw_map_custom_script(map_id: str):
    """Gets drawn shapes and clears previous layers before sending the new one"""
    
    return f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        var map_instance = window['{map_id}'];
        
        if (map_instance) {{
            // This set will hold our drawn layers so we can track them
            var drawnItems = new L.FeatureGroup();
            map_instance.addLayer(drawnItems);

            map_instance.on('draw:created', function(e) {{
                // 1. Clear all previous shapes from the map
                drawnItems.clearLayers();
                
                // 2. Add the new shape to our tracking group
                var layer = e.layer;
                drawnItems.addLayer(layer);
                
                // 3. Prepare data for Gradio
                var shape = layer.toGeoJSON();
                var dataString = JSON.stringify(shape);
                
                console.log("New Shape Captured (Previous Cleared):", dataString);
                
                // 4. Send to Gradio parent
                window.parent.postMessage({{type: 'map_geometry', data: dataString}}, '*');
            }});
        }}
    }});
    </script>
    """

# --- SENTINEL PRODUCT TYPE DATA ---
from sentinelhub import SHConfig

# Setup Copernicus client credentials
CLIENT_ID = os.getenv('COPERNICUS_CLIENT_ID')
CLIENT_SECRET = os.getenv('COPERNICUS_CLIENT_SECRET')
CONFIG_NAME = str(os.getenv('COPERNICUS_CONFIG_NAME'))

# Setup config params for Copernicus dataspace Ecosystem users
SENTINELHUB_CONFIG = SHConfig()

SENTINELHUB_CONFIG.sh_client_id = CLIENT_ID
SENTINELHUB_CONFIG.sh_client_secret = CLIENT_SECRET
SENTINELHUB_CONFIG.sh_base_url = 'https://sh.dataspace.copernicus.eu'
SENTINELHUB_CONFIG.sh_token_url = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'

SENTINELHUB_CONFIG.save(CONFIG_NAME)
