import folium
import os

import pandas as pd

from branca.element import Element
from folium.plugins import Draw

from config.config import get_draw_map_custom_script

# --- Multilingual Logic ---
def load_translations():
    try:
        df = pd.read_csv("assets/multilanguage.csv", index_col='index')
        return df.to_dict()
    except:
        # Fallback if file doesn't exist yet
        return {"es": {"title": "# App"}, "en": {"title": "# App"}}

translations = load_translations()

def get_text(lang, key, msg: str=""):
    msg = "\n"+ msg if len(msg) > 0 else msg
    return f"{translations.get(lang.lower(), {}).get(key, key)}{msg}"

def read_markdown(lang):
    path = f"assets/desc_{lang.lower()}.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "Description not found."

# --- Map Generation (Leaflet/Folium) ---
def create_map():
    m = folium.Map(location=[40.4167, -3.7033], zoom_start=6, tiles="Stadia.AlidadeSatellite")
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
