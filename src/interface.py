import json
import folium

import geopandas as gpd
import gradio as gr
import pandas as pd

from branca.element import Element
from folium.plugins import Draw
from datetime import datetime, timedelta, timezone

from sigpac_tools.find import find_from_cadastral_registry

from config.config import HIDE_MAP_TEXTBOX_CSS, JS_RECIEVER, get_draw_map_custom_script
from utils.download_merge_crop import get_product_for_parcel

# --- Multilingual Logic ---
def load_translations():
    try:
        df = pd.read_csv("assets/multilanguage.csv", index_col='index')
        return df.to_dict()
    except:
        # Fallback if file doesn't exist yet
        return {"es": {"title": "# App"}, "en": {"title": "# App"}}

translations = load_translations()

def get_text(lang, key):
    return translations.get(lang.lower(), {}).get(key, key)

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

# --- UI Layout ---
with gr.Blocks(theme="soft", title="Geo-Downloader", head=JS_RECIEVER) as demo:
    # State management for language
    lang_state = gr.State("en")
    with gr.Row():
        lang_selector = gr.Radio(choices=["es", "en"], value="es", label="Language / Idioma")
    
    title_md = gr.Markdown(get_text("es", "title"))
    subtitle_md = gr.Markdown(get_text("es", "subtitle"))

    with gr.Row():
        # --- Product & Geometry ---
        with gr.Column(scale=1):
            
            # Products
            product_select = gr.Radio(
                choices=["AOT", "images", "TCI", "WVP", "BareSoil", "Senescence", "Vegetation", "WaterContent", "WaterMass", "Yellow"],
                label="Catalogue Product",
                value="images",
            )
            
            # Dates
            today = datetime.now()
            year_ago = today - timedelta(days=365)
            
            start_date = gr.DateTime(include_time=False, label="Start Date", value=year_ago.strftime('%Y-%m-%d'))
            end_date = gr.DateTime(include_time=False, label="End Date", value=today.strftime('%Y-%m-%d'))

            geom_type = gr.Radio(
                choices=["GeoJSON Upload", "Sigpac Cadastral", "Draw on Map"],
                label="Geometry Input",
                value="GeoJSON Upload",
            )

            # Conditional inputs for geometry
            file_input = gr.File(
                label="Upload GeoJSON",
                visible=True,
                file_types=[".json", ".geojson"])
            sigpac_input = gr.Textbox(label="Sigpac Reference", placeholder="i.e: 14049A033000130000ID...", visible=False)
            
            # Hidden textbox to receive JS geometry data
            hidden_map_data = gr.Textbox(
                label="Internal Map Storage", 
                elem_id="map_data_input",
                visible=True  # Hides inmediately because of HIDE_MAP_TEXTBOX_CSS
            )
            # Map hidden container
            map_box = gr.HTML(create_map(), visible=False)
        

    get_data_btn = gr.Button("Obtener Datos", variant="primary")
    with gr.Row():
        output_log = gr.Textbox(label="Status / Logs")
        output_zip_file = gr.File(label="Output ZIP")
        
    # The 'load' function triggers our JS listener on page start
    demo.load(None, None, None, js=JS_RECIEVER)
    
    # --- Reactivity Logic ---

    # Language Switcher
    def update_language(lang):
        return [
            gr.update(value=get_text(lang, "title")),
            gr.update(value=get_text(lang, "subtitle")),
            gr.update(label=get_text(lang, "lbl_geom")),
            gr.update(label=get_text(lang, "lbl_start")),
            gr.update(label=get_text(lang, "lbl_end")),
            gr.update(label=get_text(lang, "lbl_prod")),
            gr.update(value=get_text(lang, "btn_run")),
            lang
        ]

    lang_selector.change(
        update_language, 
        inputs=[lang_selector], 
        outputs=[title_md, subtitle_md, geom_type, start_date, end_date, product_select, get_data_btn, lang_state]
    )

    # Geometry Visibility
    def toggle_geom_ui(choice):
        return [
            gr.update(visible=(choice == "GeoJSON Upload")),
            gr.update(visible=(choice == "Sigpac Cadastral")),
            gr.update(visible=(choice == "Draw on Map"))
        ]
    
    geom_type.change(toggle_geom_ui, inputs=[geom_type], outputs=[file_input, sigpac_input, map_box])

    # Execution Logic
    def process_request(product_key, file, sigpac_reference, map_data, start_date, end_date):
        placeholder_out = f"""Inputs:
        product_key:
            type: {type(product_key)}
            {product_key}
        file:
            type: {type(file)}
            {file}
        sigpac_reference:
            type: {type(sigpac_reference)}
            {sigpac_reference}
        map_data:
            type: {type(map_data)}
            {map_data}
        start_date:
            type: {type(start_date)}
            {start_date}
        end_date:
            type: {type(end_date)}
            {end_date}
        """

        if file:
            geometry_gdf = gpd.read_file(file,)

        elif sigpac_reference:
            # Convert from dict to geojson
            geometry, __  = find_from_cadastral_registry(sigpac_reference)
            geojson = {
                "type": "Feature",
                "geometry": {
                    "type": geometry["type"],
                    "coordinates": [list(map(list, geometry["coordinates"][0]))]
                },
                "properties": {}
            }
            placeholder_out += f"geojson:\n{str(geojson)[:100]} ... {str(geojson)[-100:]}"

            # Convert to GeoDataFrame
            geometry_gdf = gpd.GeoDataFrame.from_features([geojson], crs="EPSG:4258")

        elif map_data:
            try:
                # map_data arrives as a JSON string
                data = json.loads(map_data)
                
                # Use GeoPandas to read the JSON directly
                # We wrap it in a list if it's a single Feature
                if data.get("type") == "Feature":
                    geometry_gdf = gpd.GeoDataFrame.from_features([data], crs="EPSG:4258")
                else:
                    # Handle FeatureCollection
                    geometry_gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4258")
                    
                placeholder_out += f"Map geometry converted to GDF: {geometry_gdf.shape}"
            except Exception as e:
                return None, f"Error parsing map data: {str(e)}"
        else:
            print(placeholder_out)
            raise ValueError("Check input!")
        
        start_date = str(datetime.fromtimestamp(start_date, tz=timezone.utc)).split(" ")[0]
        end_date = str(datetime.fromtimestamp(end_date, tz=timezone.utc)).split(" ")[0]


        output_zip = get_product_for_parcel(product_key, geometry_gdf, start_date, end_date)
        
        return output_zip, placeholder_out

    get_data_btn.click(
        process_request,
        inputs=[product_select, file_input, sigpac_input, hidden_map_data, start_date, end_date],
        outputs=[output_zip_file, output_log]
    )

demo.launch(css=HIDE_MAP_TEXTBOX_CSS)