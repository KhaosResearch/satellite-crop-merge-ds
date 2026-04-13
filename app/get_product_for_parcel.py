import os
import structlog

import geopandas as gpd

from datetime import datetime

from config.config import ASDATA_BUCKET, ASDATA_CLIENT, PRODUCT_TYPE_FILE_IDS, RESULTS_FULL_PATH, SOURCE_BUCKET, SOURCE_CLIENT
from pipelines.download_merge_crop_minio import download_merge_crop_minio
from utils.io_utils import create_job_dir
from utils.geospatial_utils import get_aster_tiles_from_geometry, get_sentinel_tiles_from_geometry, get_year_month_pair

logger = structlog.get_logger()

# --- MAIN ORCHESTRATOR ---

def get_product_for_parcel(
        src: str,
        product_key: str,
        geometry_gdf: gpd.GeoDataFrame,
        start_date: str,
        end_date: str,
        user: str,
    ) -> str:
    """Retrieve the specified product type for the given geometry and temporal range as a compressed ZIP file.
    Args:
        src (str):
            The ID of data source.
        product_key (str):
            The ID of the product.
        geometry_gdf (gpd.GeoDataFrame):
            The parcel's geometry.
        start_date (str):
            The starting date in ISO format (`YYYY-MM-DD`).
        end_date (str):
            The finishing date in ISO format (`YYYY-MM-DD`).
    Returns:
        zip_path (str):
            The compressed ZIP filepath with all of the product data.
    """
    use_minio_src = src == "minio"
    if use_minio_src and product_key in ["aspect", "elevation", "slope"]:
        minio_client = ASDATA_CLIENT
        minio_bucket = ASDATA_BUCKET
        tiles = get_aster_tiles_from_geometry(geometry_gdf)
    elif product_key not in PRODUCT_TYPE_FILE_IDS.keys():
        ve = ValueError(f"Error: Product key must be one of the following: {str(PRODUCT_TYPE_FILE_IDS.keys()).replace("[","").replace("[","")}. Product key was: {product_key}")
        logger.error(ve)
        raise ve
    else:
        minio_client = SOURCE_CLIENT
        minio_bucket = SOURCE_BUCKET
        tiles = get_sentinel_tiles_from_geometry(geometry_gdf)

    init = datetime.now()
    print()
    logger.info(f"--- STARTING DOWNLOAD-MERGE-CROP PROCESS ---\n")
    logger.debug(f"Tiles:\n{tiles}")
    dates = get_year_month_pair(start_date, end_date)
    logger.debug(dates)

    # Create process data Job Directory
    job_dir = create_job_dir(RESULTS_FULL_PATH, user)
    
    if use_minio_src:
        logger.info(f"Getting data from KHAOS' MinIO...\n")
        zip_path = download_merge_crop_minio(
            geometry_gdf=geometry_gdf,
            tiles_list=tiles,
            year_months=dates,
            product_key=product_key,
            job_dir = job_dir,
            minio_client=minio_client,
            minio_bucket=minio_bucket
        )
    else:
        logger.info(f"Getting data from Sentinel Hub...\n")
        # zip_path = download_merge_crop_sentinel
    # Save geometry as GeoJSON
    optional_geojson_filepath = os.path.join(job_dir, "parcel_geometry.geojson")
    with open(optional_geojson_filepath, "w", encoding="utf-8") as f:
            f.write(geometry_gdf.to_json())
    logger.info(f"Saved parcel's geometry to {optional_geojson_filepath}!")
    print()
    logger.info(f"--- TRANSFERENCE TIME FOR '{product_key.upper()}': {datetime.now() - init} ---\n")

    return zip_path, optional_geojson_filepath


if __name__ == "__main__":
    # Test run
    src = "minio"  # "sentinel" | "minio"
    product_key = "BareSoil"  # 'aspect' | 'elevation' | 'slope' | 'AOT' | 'BareSoil' | 'images' | 'Senescence' | 'TCI' | 'Vegetation' | 'WaterContent' | 'WaterMass' | 'WVP' | 'Yellow'
    geometry_gdf = gpd.read_file("../misc/geometry.geojson")
    start_date ="2024-01-01"
    end_date ="2024-12-31"
    user = "user-1234"
    # for product_key in ["slope", "elevation", "aspect"]:  # UNCOMMENT TO TEST ASTER PRODUCTS
    #     src = "minio"
    #     get_product_for_parcel(src, product_key, geometry_gdf, start_date, end_date, user)
    get_product_for_parcel(src, product_key, geometry_gdf, start_date, end_date, user)
