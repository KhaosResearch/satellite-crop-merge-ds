import os
from dotenv import load_dotenv
from minio import Minio

load_dotenv()

def get_src_minio_client(access_key: str=None, secret_key: str=None) -> Minio:
    """
    Create and return a Minio client based on environment variables.
    
    Returns:
        Minio: A configured Minio client.
    """
    # Use source MinIO credentials
    endpoint=f"{os.environ.get('MINIO_HOST')}:{os.environ.get('MINIO_PORT')}"
    access_key=access_key if access_key is not None else os.environ.get("MINIO_ACCESS_KEY")
    secret_key=secret_key if secret_key is not None else os.environ.get("MINIO_SECRET_KEY")

    return Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False
    )
