import json

import geopandas as gpd
import gradio as gr

from datetime import datetime, timedelta, timezone

from sigpac_tools.find import find_from_cadastral_registry

from config.config import HIDE_MAP_TEXTBOX_CSS, JS_RECIEVER, PRODUCT_TYPE_FILE_IDS
from get_product_for_parcel import get_product_for_parcel
from utils.interface_utils import create_map, get_text, read_markdown

# --- UI Layout ---

with gr.Blocks(title="Geo-Downloader") as interface:
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
                source_selector = gr.Radio(choices=["minio", "sentinel"], value="minio", label=get_text(lang, "lbl_src"))

            with gr.Row(scale=1, equal_height=True):
                
                # ASTER Products
                product_select_ast = gr.Radio(
                    choices=["aspect", "elevation", "slope"],
                    label=get_text(lang, "lbl_prod_ast"),
                    value=None, 
                )
                
                # SENTINEL Products
                product_select_sen = gr.Radio(
                    choices=["AOT", "images", "TCI", "WVP", "BareSoil", "Senescence", "Vegetation", "WaterContent", "WaterMass", "Yellow"],
                    label=get_text(lang, "lbl_prod_sen"),
                    value="images",
                )
                
                
                # We wrap the dates in a Column we can hide
                with gr.Column(scale=1) as date_column:
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
    with gr.Row(equal_height=True):
        optional_geojson_file = gr.File(label=get_text(lang, "lbl_opt_geo"))
        with gr.Column(scale=3):
            output_zip_file = gr.File(label=get_text(lang, "lbl_zip"))
        
    # The 'load' function triggers our JS listener on page start
    interface.load(None, None, None, js=JS_RECIEVER)
    
    # --- Reactivity Logic ---

    # Product selection update
    def on_sentinel_change(value):
        # If Sentinel is selected, clear ASTER and show dates
        if value:
            return gr.update(value=None), gr.update(visible=True)
        return gr.update(), gr.update()
    
    product_select_sen.change(
        fn=on_sentinel_change,
        inputs=[product_select_sen],
        outputs=[product_select_ast, date_column]
    )


    def on_aster_change(value):
        # If ASTER is selected, clear Sentinel and hide dates
        if value:
            return gr.update(value=None), gr.update(visible=False)
        return gr.update(), gr.update()
    
    product_select_ast.change(
        fn=on_aster_change,
        inputs=[product_select_ast],
        outputs=[product_select_sen, date_column]
    )

    def on_source_change(src_value, sen_value):
        if src_value == "sentinel":
            sen_value = sen_value if sen_value is not None else "images"
            return gr.update(visible=False, value=None), gr.update(visible=True, value=sen_value)
        else:
            return gr.update(visible=True), gr.update(value=product_select_sen.value)
    
    source_selector.change(
        fn=on_source_change,
        inputs=[source_selector, product_select_sen],
        outputs=[product_select_ast, product_select_sen]
    )

    # Language Switcher
    def update_language(lang):
        return [
            gr.update(value=get_text(lang, "title")),
            gr.update(value=get_text(lang, "subtitle")),
            gr.update(value=read_markdown(lang)),
            gr.update(label=get_text(lang, "lbl_geom")),
            gr.update(label=get_text(lang, "lbl_start")),
            gr.update(label=get_text(lang, "lbl_end")),
            gr.update(label=get_text(lang, "lbl_src")),
            gr.update(label=get_text(lang, "lbl_prod_sen")),
            gr.update(label=get_text(lang, "lbl_prod_ast")),
            gr.update(value=get_text(lang, "btn_run")),
            gr.update(label=get_text(lang, "lbl_file")),
            gr.update(label=get_text(lang, "lbl_sigpac")),
            gr.update(label=get_text(lang, "lbl_opt_geo")),
            gr.update(label=get_text(lang, "lbl_zip")),
            lang
        ]

    lang_selector.change(
        update_language, 
        inputs=[lang_selector], 
        outputs=[title_md, subtitle_md, description_md, geom_type, start_date, end_date, source_selector, product_select_sen, product_select_ast, get_data_btn, file_input, sigpac_input, optional_geojson_file, output_zip_file, lang_state]
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
    def process_request(lang, source_selector, product_key_sen, product_key_ast, file, sigpac_reference, map_data, start_date, end_date, request: gr.Request):
        get_data_btn.interactive = False
        if product_key_sen is not None:
            product_key = product_key_sen
        else:
            product_key = product_key_ast
            start_date, end_date = 0.0, 0.1  # Not needed for ASTER products
        try:
            # Gradio automatically populates request.username if auth is enabled
            user = request.username if request and request.username is not None else "user-1234"
            errors = validate_input(lang, source_selector, product_key_sen, product_key_ast, file, sigpac_reference, map_data, start_date, end_date)
            # Raise if any errors
            if errors:
                message = f"{get_text(lang, "err_prefix")}<br>- " + "<br>- ".join(errors)
                raise gr.Error(message)
            else:
                gr.Info(get_text(lang, "msg_start"))

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

                # Convert to GeoDataFrame
                geometry_gdf = gpd.GeoDataFrame.from_features([geojson], crs="EPSG:4326")

            elif map_data:
                gr.Info(get_text(lang, "msg_map_sync"))
                try:
                    # map_data arrives as a JSON string
                    data = json.loads(map_data)
                    
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
            
            start_date = str(datetime.fromtimestamp(start_date, tz=timezone.utc)).split(" ")[0]
            end_date = str(datetime.fromtimestamp(end_date, tz=timezone.utc)).split(" ")[0]
            src = source_selector
            output_zip, optional_geojson = get_product_for_parcel(src, product_key, geometry_gdf, start_date, end_date, user)
            gr.Success(get_text(lang, "msg_success"))

            return output_zip, optional_geojson
        
        finally:
            get_data_btn.interactive = True

    def validate_input(lang, source_selector, product_key_sen, product_key_ast, file, sigpac_reference, map_data, start_date, end_date):
        errors = []

        # Language
        if lang not in ("en", "es"):
            errors.append(get_text(lang, "err_lang", lang))
        if source_selector not in ("minio", "sentinel"):
            errors.append(get_text(lang, "err_src_sel", str(source_selector)))
        elif source_selector == 'sentinel' and product_key_ast is not None:
            errors.append(get_text(lang, "err_src_ast", "sentinel"))
        
        # Product key
        if product_key_sen is not None and product_key_sen not in PRODUCT_TYPE_FILE_IDS:
            errors.append(get_text(lang, "err_prod_sen", str(product_key_sen)))
        if product_key_ast is not None and product_key_ast not in ["aspect", "elevation", "slope"]:
            errors.append(get_text(lang, "err_prod_ast", str(product_key_ast)))

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
        
    get_data_btn.click(
        process_request,
        inputs=[lang_selector, source_selector, product_select_sen, product_select_ast, file_input, sigpac_input, hidden_map_data, start_date, end_date],
        outputs=[output_zip_file, optional_geojson_file]
    )

if __name__ == "__main__":
    interface.launch(theme="gradio/monochrome", head=JS_RECIEVER, css=HIDE_MAP_TEXTBOX_CSS, auth=lambda u, p: True)