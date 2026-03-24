import os
from dotenv import load_dotenv

from  config.minio_client import get_src_minio_client

load_dotenv()

# MinIO Credentials
SOURCE_BUCKET = os.environ.get('MINIO_BUCKET_NAME')
SOURCE_CLIENT = get_src_minio_client()
SENTINEL2_GRIDS_FILE = os.environ.get('SENTINEL2_GRIDS_FILE')

PRODUCT_TYPE_FILE_IDS = {
    "images": {
        "10m": [ 'B02', 'B03', 'B04', 'B08'],
        "20m": [ 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B11', 'B12'],
        "60m": ['B01', 'B02', 'B03', 'B04', 'B05', 'B06','B07', 'B8A', 'B09', 'B10', 'B11', 'B12']
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
    "ndre": "60",
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