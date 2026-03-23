import folium

import geopandas as gpd
import gradio as gr
import pandas as pd

from folium.plugins import Draw
from datetime import datetime, timedelta, timezone

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
    
    # JavaScript to push drawing data to a hidden Gradio component
    map_html = m._repr_html_()
    script = """
    <script>
    var map = document.querySelector('iframe').contentWindow.map;
    map.on('draw:created', function (e) {
        var layer = e.layer;
        var shape = layer.toGeoJSON();
        var shape_for_gradio = JSON.stringify(shape);
        parent.postMessage({type: 'map_geometry', data: shape_for_gradio}, '*');
    });
    </script>
    """
    return map_html

# --- UI Layout ---
with gr.Blocks(theme="soft", title="Geo-Downloader") as demo:
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
                choices=["AOT", "images", "TIC", "WVP", "BareSoil", "Senescence", "Vegetation", "WaterContent", "WaterMass", "Yellow"],
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
            file_input = gr.File(label="Upload GeoJSON", visible=True)
            sigpac_input = gr.Textbox(label="Sigpac Reference", placeholder="i.e: 14049A033000130000ID...", visible=False)
            
            # Map hidden container
            map_box = gr.HTML(create_map(), visible=False)
            # Hidden textbox to receive JS geometry data
            hidden_geom_data = gr.Textbox(visible=False)
        

        # --- Storage Configuration ---
        with gr.Column(scale=1, visible=False):
            storage_type = gr.Radio(
                choices=["S3", "Azure"],
                label="Provider",
                value="Almacenamiento S3"
            )
            
            # S3 Fields
            with gr.Group(visible=False) as s3_group:
                s3_id = gr.Textbox(label="ID de acceso")
                s3_key = gr.Textbox(label="Clave de Acceso", type="password")
                s3_url = gr.Textbox(label="Dirección de almacenamiento (URL)")
                s3_bucket = gr.Textbox(label="Nombre del bucket")
                s3_path = gr.Textbox(label="Ruta del objeto (opcional)")
            
            # Azure Fields
            with gr.Group(visible=False) as azure_group:
                az_token = gr.Textbox(label="Token SAS")
                az_url = gr.Textbox(label="Ruta SAS completa")
            
            gr.Markdown("---")
            warning_md = gr.Warning(get_text("es", "warn_space"))

    get_data_btn = gr.Button("Obtener Datos", variant="primary")

    output_log = gr.File(label="Output ZIP")

    output_log = gr.Textbox(label="Status / Logs")

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
            gr.update(label=get_text(lang, "lbl_storage")),
            gr.update(value=get_text(lang, "btn_run")),
            lang
        ]

    lang_selector.change(
        update_language, 
        inputs=[lang_selector], 
        outputs=[title_md, subtitle_md, geom_type, start_date, end_date, product_select, storage_type, get_data_btn, lang_state]
    )

    # Geometry Visibility
    def toggle_geom_ui(choice):
        return [
            gr.update(visible=(choice == "GeoJSON Upload")),
            gr.update(visible=(choice == "Sigpac Cadastral")),
            gr.update(visible=(choice == "Draw on Map"))
        ]
    
    geom_type.change(toggle_geom_ui, inputs=[geom_type], outputs=[file_input, sigpac_input, map_box])

    # Storage Visibility
    def toggle_storage_ui(choice):
        if "S3" in choice:
            return gr.update(visible=True), gr.update(visible=False)
        return gr.update(visible=False), gr.update(visible=True)

    storage_type.change(toggle_storage_ui, inputs=[storage_type], outputs=[s3_group, azure_group])

    # Execution Logic
    def process_request(product_key, file, sigpac_reference, map_data, start_date, end_date):
        if file:
            geometry_gdf = gpd.read_file(file)

        elif sigpac_reference:
            # TODO
            geometry_gdf  = None
        elif map_data:
            # TODO
            geometry_gdf  = None
        else:
            raise ValueError("Check input!")
        
        start_date = str(datetime.fromtimestamp(start_date, tz=timezone.utc)).split(" ")[0]
        end_date = str(datetime.fromtimestamp(end_date, tz=timezone.utc)).split(" ")[0]

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

        get_product_for_parcel(product_key, geometry_gdf, start_date, end_date)
        
        return placeholder_out

    get_data_btn.click(
        process_request,
        inputs=[product_select, file_input, sigpac_input, hidden_geom_data, start_date, end_date],
        outputs=[output_log]
    )

demo.launch()