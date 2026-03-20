import os
from dotenv import load_dotenv

from  config.minio_client import get_src_minio_client

load_dotenv()

# MinIO Credentials
SOURCE_BUCKET = os.environ.get('MINIO_BUCKET_NAME')
SOURCE_CLIENT = get_src_minio_client()
SENTINEL2_GRIDS_FILE = os.environ.get('SENTINEL2_GRIDS_FILE')