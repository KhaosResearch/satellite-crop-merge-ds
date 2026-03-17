import os
from dotenv import load_dotenv
from minio import Minio

load_dotenv()

def get_src_minio_client() -> Minio:
    """
    Create and return a Minio client based on environment variables.
    
    Returns:
        Minio: A configured Minio client.
    """
    # Use source MinIO credentials
    endpoint=f"{os.environ.get('SOURCE_MINIO_HOST')}:{os.environ.get('SOURCE_MINIO_PORT')}"
    access_key=os.environ.get("SOURCE_MINIO_ACCESS_KEY")
    secret_key=os.environ.get("SOURCE_MINIO_SECRET_KEY")

    return Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False
    )
