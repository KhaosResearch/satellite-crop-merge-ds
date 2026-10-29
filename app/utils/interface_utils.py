import folium
import os

import pandas as pd

from branca.element import Element
from folium.plugins import Draw
from pathlib import Path

from config.config import MULTILANGUAGE_FILEPATH, get_draw_map_custom_script

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# --- Multilingual Logic ---
def load_translations():
    try:
        df = pd.read_csv(MULTILANGUAGE_FILEPATH, index_col='index')
        return df.to_dict()
    except:
        # Fallback if file doesn't exist yet
        return {"es": {"title": "# App"}, "en": {"title": "# App"}}

translations = load_translations()

def get_text(lang, key, msg: str=""):
    msg = "\n"+ msg if len(msg) > 0 else msg
    return f"{translations.get(lang.lower(), {}).get(key, key)}{msg}"

def read_markdown(lang):
    path = str(ASSETS_DIR / f"desc_{lang.lower()}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "Description not found."

# --- Map Generation (Leaflet/Folium) ---
def create_map():
    # Option A: Stadia (needs API key for prod, fine for testing in locahost)
    # m = folium.Map(location=[40.4167, -3.7033], zoom_start=6, tiles="Stadia.AlidadeSatellite")
    
    # Option B:  Esri World Imagery (Free Satellite Tiles)
    m = folium.Map(
        location=[40.4167, -3.7033], 
        zoom_start=6, 
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri"
    )
    
    # Option B: CartoDB Positron (Clean, light theme)
    # m = folium.Map(location=[40.4167, -3.7033], zoom_start=6, tiles="CartoDB positron")
    
    # Option C: Standard OpenStreetMap
    # m = folium.Map(location=[40.4167, -3.7033], zoom_start=6, tiles="OpenStreetMap")
    draw = Draw(
        export=False,
        draw_options={
            'polyline': False, 'rectangle': True, 'polygon': True, 'circle': False, 'marker': False, 'circlemarker': False
        }
    )
    draw.add_to(m)
    map_id = m.get_name()
    m.get_root().header.add_child(Element(get_draw_map_custom_script(map_id)))

    return m._repr_html_()    
