import json
import structlog

import geopandas as gpd
import gradio as gr

from datetime import datetime, timedelta, timezone

from sigpac_tools.find import find_from_cadastral_registry

from config.config import ANDALUSIA_GEOJSON_FILEPATH, HIDE_MAP_TEXTBOX_CSS, JS_RECIEVER, PRODUCTS_DICT
from get_product_for_parcel import get_product_for_parcel
from utils.interface_utils import create_map, get_text, read_markdown

logger = structlog.get_logger()

# --- UI Layout ---

with gr.Blocks(title="EDAAn Geo-Downloader") as interface:
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
            with gr.Column(scale=1):
                geom_type = gr.Radio(
                    choices=["GeoJSON", "SIGPAC", "Map"],
                    label=get_text(lang, "lbl_geom"),
                    value="GeoJSON",
                )

                # Conditional inputs for geometry
                file_input = gr.File(
                    label=get_text(lang, "lbl_file"),
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
        
            with gr.Row(scale=1, equal_height=True):
                # We wrap the dates in a Column we can hide
                with gr.Column(scale=1) as date_column:
                    max_date = datetime(2025,12,31)
                    year_ago = max_date - timedelta(days=364)
                    start_date = gr.DateTime(include_time=False, label=get_text(lang, "lbl_start"), value=year_ago.strftime('%Y-%m-%d'))
                    end_date = gr.DateTime(include_time=False, label=get_text(lang, "lbl_end"), value=max_date.strftime('%Y-%m-%d'))                
                
                # Catalogue Products
                product_select = gr.Radio(
                    choices=PRODUCTS_DICT[lang].keys(),
                    label=get_text(lang, "lbl_prod_sel"),
                    value=list(PRODUCTS_DICT[lang].keys())[1],
                    scale=2
                )
                
    get_data_btn = gr.Button(get_text(lang, "btn_run"), variant="primary")
    with gr.Row(equal_height=True):
        optional_geojson_file = gr.File(label=get_text(lang, "lbl_opt_geo"))
        with gr.Column(scale=3):
            output_zip_file = gr.File(label=get_text(lang, "lbl_zip"))
        
    # The 'load' function triggers our JS listener on page start
    interface.load(None, None, None, js=JS_RECIEVER)
    
    # Language Switcher
    def update_language(lang, selected_product):
        # Preserve selected product across languages
        prev_lang = "es" if lang == "en" else "en"
        product_dict_index = list(PRODUCTS_DICT[prev_lang].keys()).index(selected_product)
        return [
            gr.update(value=get_text(lang, "title")),
            gr.update(value=get_text(lang, "subtitle")),
            gr.update(value=read_markdown(lang)),
            gr.update(label=get_text(lang, "lbl_geom")),
            gr.update(label=get_text(lang, "lbl_start")),
            gr.update(label=get_text(lang, "lbl_end")),
            gr.update(label=get_text(lang, "lbl_prod_sel"), choices=PRODUCTS_DICT[lang].keys(), value=list(PRODUCTS_DICT[lang].keys())[product_dict_index]),
            gr.update(value=get_text(lang, "btn_run")),
            gr.update(label=get_text(lang, "lbl_file")),
            gr.update(label=get_text(lang, "lbl_sigpac")),
            gr.update(label=get_text(lang, "lbl_opt_geo")),
            gr.update(label=get_text(lang, "lbl_zip")),
            lang
        ]

    lang_selector.change(
        update_language, 
        inputs=[lang_selector, product_select], 
        outputs=[title_md, subtitle_md, description_md, geom_type, start_date, end_date, product_select,get_data_btn, file_input, sigpac_input, optional_geojson_file, output_zip_file, lang_state]
    )

    # Geometry Visibility
    def toggle_geom_ui(choice):
        if "map" in str(choice).lower():
            hidden_map_data.value = ""
        return [
            gr.update(visible=("geojson" in str(choice).lower())),
            gr.update(visible=("sigpac" in str(choice).lower())),
            gr.update(visible=("map" in str(choice).lower()))
        ]
    
    geom_type.change(toggle_geom_ui, inputs=[geom_type], outputs=[file_input, sigpac_input, map_box])

    # Execution Logic
    def process_request(lang, product_select, geometry_selection, file, sigpac_reference, map_data, start_date, end_date, request: gr.Request):
        product_key = PRODUCTS_DICT.get(lang, None).get(product_select, None)
        get_data_btn.interactive = False
        data_source = _get_source(product_key, file, sigpac_reference, map_data, start_date, end_date)
        try:
            # Gradio automatically populates request.username if auth is enabled
            user = request.username if request and request.username is not None else "user-1234"
            errors = _validate_input(lang, data_source, product_key, file, sigpac_reference, map_data, start_date, end_date)
            # Raise if any errors
            if errors:
                message = f'{get_text(lang, "err_prefix")}<br>- ' + "<br>- ".join(errors)
                raise gr.Error(message)
            else:
                gr.Info(get_text(lang, "msg_start"))

            # Get geometry based on input priority
            geometry_gdf = _get_geometry_gdf(geometry_selection, file, sigpac_reference, map_data)
            
            start_date = str(datetime.fromtimestamp(start_date, tz=timezone.utc)).split(" ")[0]
            end_date = str(datetime.fromtimestamp(end_date, tz=timezone.utc)).split(" ")[0]
            src = data_source
            output_zip, optional_geojson = get_product_for_parcel(src, product_key, geometry_gdf, start_date, end_date, user)
            gr.Success(get_text(lang, "msg_success"))

            return output_zip, optional_geojson
        
        finally:
            get_data_btn.interactive = True

    def _get_source(product_select: str, file_input: str, sigpac_input: str, hidden_map_data: str, start_date: str, end_date: str)->str:
        # Set Sentinel source by default
        src = "sentinel"

        # Check if selected product is topographic
        if product_select is not None:
            is_topographic_product = product_select in ["aspect", "elevation", "slope", "WVP"]  # WVP only present in MinIO (for now...)
        else:
            message = f'{get_text(lang, "err_prefix")}<br>- ' + "<br>- ".join(get_text(lang, "err_prod_sel"))
            raise gr.Error(message)

        # Check if input date range is within max MinIO temporal range
        min_start_date = "2017-04-01"
        max_end_date = "2025-12-31"
        # Get date range in ISO format
        start_date = str(datetime.fromtimestamp(start_date, tz=timezone.utc)).split(" ")[0]
        end_date = str(datetime.fromtimestamp(end_date, tz=timezone.utc)).split(" ")[0]
        is_in_temporal_range = min_start_date <= start_date <= max_end_date and min_start_date <= end_date <= max_end_date
        
        # Get Sigpac input
        is_sigpac_geometry = file_input is None and sigpac_input is not None

        # Get Andalusia geometry
        andalusia_gfd = gpd.read_file(str(ANDALUSIA_GEOJSON_FILEPATH),) 

        # Get geometry based on input priority
        if file_input:
            geometry_gdf = gpd.read_file(file_input,) 
        elif hidden_map_data:
            # map_data arrives as a JSON string
            data = json.loads(hidden_map_data)
            
            # Use GeoPandas to read the JSON directly
            if data.get("type") == "Feature":
                geometry_gdf = gpd.GeoDataFrame.from_features([data], crs="EPSG:4326")
            else:
                # Handle FeatureCollection
                geometry_gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
        
        # Check if geometry is completely contained in Andalusia
        geometry_gdf = geometry_gdf.to_crs(andalusia_gfd.crs)  # match both CRSs
        andalusia_geom = andalusia_gfd.union_all()  # merge into one single geometry
        is_geometry_in_andalusia = geometry_gdf.geometry.within(andalusia_geom).all()
        
        # Get correct data source
        if is_sigpac_geometry or is_geometry_in_andalusia:
            if is_topographic_product or is_in_temporal_range:
                src = "minio"
        message = f'{get_text(lang, "msg_src_sel")} {src.upper()}'
        gr.Info(message)
        logger.debug(f"Selected source: {src.upper()}")
        return src
    
    def _validate_input(lang, data_source, product_key, file, sigpac_reference, map_data, start_date, end_date):
        errors = []

        # Language
        if lang not in ("en", "es"):
            errors.append(get_text(lang, "err_lang", lang))
        if data_source not in ("minio", "sentinel"):
            errors.append(get_text(lang, "err_src_sel", str(data_source)))
        
        # Product key
        if product_key is not None and product_key not in list(PRODUCTS_DICT.get(lang).values()):
            errors.append(get_text(lang, "err_prod_sel", str(product_key)))

        # Dates (assuming timestamps)
        try:
            start_dt = datetime.fromtimestamp(start_date, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_date, tz=timezone.utc)
            today = datetime.now(timezone.utc)

            if start_dt > end_dt:
                errors.append(get_text(lang, "err_end_date_gt"))


            if start_dt > today or end_dt > today:
                errors.append(get_text(lang, "err_date_gt_today"))

        except Exception:
            errors.append(get_text(lang, "err_date_format"))

        # Geometry input
        if not file and not sigpac_reference and not map_data:
            errors.append(get_text(lang, "err_geom"))
        
        return errors
    
    def _get_geometry_gdf(geometry_selection, file_input, sigpac_input, hidden_map_data):
        
        if geometry_selection.lower() == "geojson" and file_input:
            geometry_gdf = gpd.read_file(file_input,)

        elif geometry_selection.lower() == "sigpac" and sigpac_input:
            # Convert from dict to geojson
            geometry, __  = find_from_cadastral_registry(sigpac_input)
            geojson = {
                "type": "Feature",
                "geometry": {
                    "type": geometry["type"],
                    "coordinates": [list(map(list, geometry["coordinates"][0]))]
                },
                "properties": {}
            }

            # Convert to GeoDataFrame
            geometry_gdf = gpd.GeoDataFrame.from_features([geojson], crs="EPSG:4326")

        elif geometry_selection.lower() == "map" and hidden_map_data:
            gr.Info(get_text(lang, "msg_map_sync"))
            try:
                # map_data arrives as a JSON string
                data = json.loads(hidden_map_data)
                
                # Use GeoPandas to read the JSON directly
                if data.get("type") == "Feature":
                    geometry_gdf = gpd.GeoDataFrame.from_features([data], crs="EPSG:4326")
                else:
                    # Handle FeatureCollection
                    geometry_gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
            except Exception as e:
                raise gr.Error(get_text(lang, "msg_error_geom", str(e)))
        
        else:
            raise ValueError("Check input!")

        return geometry_gdf

    get_data_btn.click(
        process_request,
        inputs=[lang_selector, product_select, geom_type, file_input, sigpac_input, hidden_map_data, start_date, end_date],
        outputs=[output_zip_file, optional_geojson_file],
        scroll_to_output = True,
    )
    
if __name__ == "__main__":
    interface.launch(theme="gradio/monochrome", head=JS_RECIEVER, css=HIDE_MAP_TEXTBOX_CSS, auth=lambda u, p: True)