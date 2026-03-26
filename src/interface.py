import json
import folium
import os

import geopandas as gpd
import gradio as gr
import pandas as pd

from branca.element import Element
from folium.plugins import Draw
from datetime import datetime, timedelta, timezone

from sigpac_tools.find import find_from_cadastral_registry

from config.config import HIDE_MAP_TEXTBOX_CSS, JS_RECIEVER, PRODUCT_TYPE_FILE_IDS, get_draw_map_custom_script
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

# --- UI Layout ---
with gr.Blocks(theme="soft", title="Geo-Downloader", head=JS_RECIEVER) as demo:
    # State management for language
    lang = "es"  # Start in Spanish by deafult
    lang_state = gr.State(lang)
    with gr.Row():
        lang_selector = gr.Radio(choices=["en", "es"], value="es", label="Language / Idioma")
    
    title_md = gr.Markdown(get_text(lang, "title"))
    subtitle_md = gr.Markdown(get_text(lang, "subtitle"))
    description_md = gr.Markdown(read_markdown(lang))

    with gr.Row():
        # --- Product & Geometry ---
        with gr.Column(scale=1):
            with gr.Row(scale=1, equal_height=True):
                # Products
                product_select = gr.Radio(
                    choices=["AOT", "images", "TCI", "WVP", "BareSoil", "Senescence", "Vegetation", "WaterContent", "WaterMass", "Yellow"],
                    label=get_text(lang, "lbl_prod"),
                    value="images",
                )
                
                with gr.Column(scale=1):
                    # Dates
                    max_date = datetime(2025,12,31)
                    year_ago = max_date - timedelta(days=364)
                    start_date = gr.DateTime(include_time=False, label=get_text(lang, "lbl_start"), value=year_ago.strftime('%Y-%m-%d'))
                    end_date = gr.DateTime(include_time=False, label=get_text(lang, "lbl_end"), value=max_date.strftime('%Y-%m-%d'))

            geom_type = gr.Radio(
                choices=["GeoJSON Upload", "Sigpac Cadastral", "Draw on Map"],
                label=get_text(lang, "lbl_geom"),
                value="GeoJSON Upload",
            )

            # Conditional inputs for geometry
            file_input = gr.File(
                label=get_text(lang, "lbl_file"),
                visible=True,
                file_types=[".json", ".geojson"])
            
            sigpac_input = gr.Textbox(label=get_text(lang, "lbl_sigpac"), placeholder="i.e: 14049A033000130000ID...", visible=False)
            
            # Hidden textbox to receive JS geometry data
            hidden_map_data = gr.Textbox(
                label="Internal Map Storage", 
                elem_id="map_data_input",
                visible=True  # Hides inmediately because of HIDE_MAP_TEXTBOX_CSS
            )
            # Map hidden container
            map_box = gr.HTML(create_map(), visible=False)
        

    get_data_btn = gr.Button(get_text(lang, "btn_run"), variant="primary")
    with gr.Row():
        output_log = gr.Textbox(label=get_text(lang, "lbl_logs"))
        output_zip_file = gr.File(label=get_text(lang, "lbl_zip"))
        
    # The 'load' function triggers our JS listener on page start
    demo.load(None, None, None, js=JS_RECIEVER)
    
    # --- Reactivity Logic ---

    # Language Switcher
    def update_language(lang):
        return [
            gr.update(value=get_text(lang, "title")),
            gr.update(value=get_text(lang, "subtitle")),
            gr.update(value=read_markdown(lang)),
            gr.update(label=get_text(lang, "lbl_geom")),
            gr.update(label=get_text(lang, "lbl_start")),
            gr.update(label=get_text(lang, "lbl_end")),
            gr.update(label=get_text(lang, "lbl_prod")),
            gr.update(value=get_text(lang, "btn_run")),
            gr.update(label=get_text(lang, "lbl_file")),
            gr.update(label=get_text(lang, "lbl_sigpac")),
            gr.update(label=get_text(lang, "lbl_logs")),
            gr.update(label=get_text(lang, "lbl_zip")),
            lang
        ]

    lang_selector.change(
        update_language, 
        inputs=[lang_selector], 
        outputs=[title_md, subtitle_md, description_md, geom_type, start_date, end_date, product_select, get_data_btn, file_input, sigpac_input, output_log, output_zip_file, lang_state]
    )

    # Geometry Visibility
    def toggle_geom_ui(choice):
        if choice != "Draw on Map":
            hidden_map_data.value = ""
        return [
            gr.update(visible=(choice == "GeoJSON Upload")),
            gr.update(visible=(choice == "Sigpac Cadastral")),
            gr.update(visible=(choice == "Draw on Map"))
        ]
    
    geom_type.change(toggle_geom_ui, inputs=[geom_type], outputs=[file_input, sigpac_input, map_box])

    # Execution Logic
    def process_request(lang, product_key, file, sigpac_reference, map_data, start_date, end_date):
        get_data_btn.interactive = False
        try:
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
            errors = validate_input(lang, product_key, file, sigpac_reference, map_data, start_date, end_date)
            # 🚨 Raise if any errors
            if errors:
                message = "Input Error:\n- " + "\n- ".join(errors)
                raise gr.Error(message)

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
                gr.Info(get_text(lang, "msg_map_sync"))
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
                    gr.Error(get_text(lang, "msg_error_geom", str(e)))
                    return None, f"Error parsing map data: {str(e)}"
            else:
                print(placeholder_out)
                raise ValueError("Check input!")
            gr.Info(get_text(lang, "msg_start"))
            
            start_date = str(datetime.fromtimestamp(start_date, tz=timezone.utc)).split(" ")[0]
            end_date = str(datetime.fromtimestamp(end_date, tz=timezone.utc)).split(" ")[0]

            output_zip = get_product_for_parcel(product_key, geometry_gdf, start_date, end_date)
            
            gr.Success(get_text(lang, "msg_success"))

            return output_zip, placeholder_out
        finally:
            get_data_btn.interactive = True

    def validate_input(lang, product_key, file, sigpac_reference, map_data, start_date, end_date):
        errors = []

        # Language
        if lang not in ("en", "es"):
            errors.append(f"Language must be 'en' or 'es'. Got: {lang}")

        # Product key
        if product_key not in PRODUCT_TYPE_FILE_IDS:
            valid = ", ".join(PRODUCT_TYPE_FILE_IDS.keys())
            errors.append(f"Product must be one of: {valid}. Got: {product_key}")

        # Dates (assuming timestamps)
        try:
            start_dt = datetime.fromtimestamp(start_date, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_date, tz=timezone.utc)
            today = datetime.now(timezone.utc)

            if start_dt > end_dt:
                errors.append("Start date cannot be greater than end date.")

            if start_dt > today or end_dt > today:
                errors.append("Dates cannot be greater than today.")

        except Exception:
            errors.append("Invalid date format.")

        # Geometry input
        if not file and not sigpac_reference and not map_data:
            errors.append(
                "Parcel geometry not specified. Upload a GeoJSON file, "
                "provide a SIGPAC reference, or draw on the map."
            )

        
        return errors
        
    get_data_btn.click(
        process_request,
        inputs=[lang_selector, product_select, file_input, sigpac_input, hidden_map_data, start_date, end_date],
        outputs=[output_zip_file, output_log]
    )

demo.launch(css=HIDE_MAP_TEXTBOX_CSS)