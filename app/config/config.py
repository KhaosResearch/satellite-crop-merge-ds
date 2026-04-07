import os
from dotenv import load_dotenv
from pathlib import Path

from  config.minio_client import get_src_minio_client

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR_NAME = "results"
RESULTS_FULL_PATH = ROOT_DIR / RESULTS_DIR_NAME

# --- MINIO CREDENTIALS ---
SOURCE_BUCKET = os.environ.get('MINIO_BUCKET_NAME')
SOURCE_CLIENT = get_src_minio_client()
SENTINEL2_GRIDS_FILE = os.environ.get('SENTINEL2_GRIDS_FILE')

# --- MINIO PRODUCT TYPE DATA ---
PRODUCT_TYPE_FILE_IDS = {
    "images": {
        "10m": [ 'B02', 'B03', 'B04', 'B08'],
        "20m": [ 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B11', 'B12'],
        "60m": ['B01', 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B09', 'B11', 'B12']
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

SPECTRAL_INDICES_RESOLUTION = {
    "evi": "10",
    "evi2": "10",
    "ndre": "20",  # TODO: update to 60 when MinIO NDRE obj are also updated to 60
    "ndvi": "10",
    "osavi": "10",
    "ri": "10",
    "ndwi": "10",
    "gvmi": "20",
    "mndwi": "20",
    "ndsi": "20",
    "ndyi": "10",
    "bri": "20",
    "cri1": "20",
    "bsi": "20",
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
