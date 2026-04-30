import os
import tempfile
import structlog

from config.config import LANDCOVER_BUCKET, LANDCOVER_CLIENT, SOURCE_BUCKET, SOURCE_CLIENT
from utils.io_utils import _file_exists_in_minio

logger = structlog.get_logger(__name__)

# Step 1: Iterate over the Andalusia S2 tiles list
# Step 2: get sl_classification_s2TileId.tif and classification_s2TileId.tif files from source bucket (etc-classifications)
# Step 3: Save files in 
#   sentinel2-composites/LandCover/s2TileId/YYYY/LC_s2TileId_YYYY.tif + .png + LC_leyenda.qml
#   sentinel2-composites/ForestMap/s2TileId/YYYY/FM_s2TileId_YYYY.tif + .png + FM_leyenda.qml

ANDALUSIA_TILES = ["29SPC", "29SQC", "30STH", "30SUH", "30SVH", "30SWH", "30SXH", "30SYH", "30SXG", 
            "30SWG", "30SVG", "30SUG", "30STG", "29SQB" ,"29SPB", "30STF", "30SUF", 
            "30SVF", "30SWF"
            ]

def add_landcover_forestmap_data(tiles=ANDALUSIA_TILES):
    """Adds collected land cover and forest map classification data to destiny MinIO bucket.
    Checks if files are already included in destiny bucket.

    Args:
        tiles (list[str]): List of S2 tile IDs to process. If not provided, the default list of Andalusia Spain region tiles will be used.
    """
    classif_prefix = "valenciav4"
    missing_tiles = []
    temp_dir = tempfile.mkdtemp()
    local_files_list = []

    try:
        logger.info(f"Starting landcover and forestmap upload for {len(tiles)} tiles...\n")

        for tile in tiles:
            year = "2021"  # Only year for LC and FM data

            for product_type in ["LandCover", "ForestMap"]:
                # Generate src and destiny filepaths as stored in their respectives buckets
                src_filename = f"{'sl_' if product_type == 'ForestMap' else ''}classification_{tile}.tif"
                src_filepath = os.path.join(classif_prefix, src_filename)
                destiny_filename = f"{'FM' if product_type == 'ForestMap' else 'LC'}_{tile}_{year}.tif"
                destiny_filepath = os.path.join(product_type, tile, year, destiny_filename)
            
                # Get from src minio
                logger.info(f"Processing {product_type.upper()} data on tile {tile}: Checking for file {src_filepath} in source bucket {LANDCOVER_BUCKET.upper()}...")
                if not _file_exists_in_minio(destiny_filepath, SOURCE_CLIENT, SOURCE_BUCKET):
                    if _file_exists_in_minio(src_filepath, LANDCOVER_CLIENT, LANDCOVER_BUCKET):
                        logger.info(f"File {src_filepath} exists in minio bucket {LANDCOVER_BUCKET.upper()}.")

                        # Generate local temp file
                        os.makedirs(temp_dir, exist_ok=True)
                        local_file = os.path.join(temp_dir, src_filename)
                        local_files_list.append(local_file)
                        
                        # Download src data file
                        LANDCOVER_CLIENT.fget_object(LANDCOVER_BUCKET, src_filepath, local_file)
                    else:
                        logger.exception(f"File {src_filepath} does not exist in minio bucket {LANDCOVER_BUCKET.upper()}.")
                        missing_tiles.append(tile)
                        print()
                        continue

                    # Generate (local filepath, destiny filepath) tuples list to upload
                    destiny_files_tuples_list = get_destiny_files_tuples_list(product_type, tile, year="2021")
                    destiny_files_tuples_list.append((local_file, destiny_filepath))  # Add the src data file

                    # Put in destiny minio
                    logger.warning(f"File {src_filepath} is not included in minio bucket {SOURCE_BUCKET.upper()}.")
                    # Upload files
                    for local_origin_file, destiny_minio_filepath in destiny_files_tuples_list:
                        SOURCE_CLIENT.fput_object(SOURCE_BUCKET, destiny_minio_filepath, local_origin_file)
                        logger.info(f"File {local_origin_file} uploaded to {SOURCE_BUCKET.upper()} as {destiny_minio_filepath}.")
                else:
                    logger.info(f"File {src_filepath} already exists in minio bucket {SOURCE_BUCKET.upper()} as {destiny_filepath}. Skipping upload.")
                    print()
                    continue
                print()
    finally:
    # Delete generated local temp files
        for local_file in local_files_list:
            if os.path.exists(local_file):
                try:
                    os.remove(local_file)
                except Exception as e:
                    logger.warning(f"Warning: Could not remove temp file {local_file}: {e}")
        if len(missing_tiles) > 0:
            logger.warning(f"Missing tiles: {set(missing_tiles)}")

def get_destiny_files_tuples_list(product_type, tile, year="2021"):
    """Generates a list of tuples with local filepaths and destiny MinIO filepaths for the given product type, tile and year.
    It includes the classification data file, the legend file and the readme file.
    
    Args:
        product_type (str):
            The type of product ('LandCover' or 'ForestMap').
        tile (str):
            The S2 tile ID.
        year (str):
            The year for which to generate file paths.
    Returns:
        destiny_files_tuples_list (list[tuple[str, str]]):
            A list of tuples containing local filepaths and destiny MinIO filepaths.
    """
    destiny_files_tuples_list = []
    legend_prefix = os.path.join(product_type, tile, year)
    readme_prefix = os.path.join(product_type)
    files_dir = f"{'FM' if product_type == 'ForestMap' else 'LC'}_files"

    for filepath in os.listdir(os.path.join(os.path.dirname(__file__), files_dir)):
        filepath = os.path.join(os.path.dirname(__file__), files_dir, filepath)
        filename, ext = os.path.splitext(os.path.basename(filepath))
        prefix = readme_prefix if ext == ".pdf" else legend_prefix
        destiny_filepath = os.path.join(prefix, filename + ext)
        destiny_files_tuples_list.append((filepath, destiny_filepath))
    
    return destiny_files_tuples_list

if __name__ == "__main__":
    add_landcover_forestmap_data()


