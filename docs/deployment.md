# Deployment Guide

This document describes the strategies and steps required to deploy and run the Satellite Crop & Merge Data Space service.

## Environment Requirements
- **OS**: Linux (Recommended), macOS, or Windows.
- **Python**: Version 3.12 or higher.
- **Network**: Internet access for Sentinel Hub API and SIGPAC data retrieval.

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/KhaosResearch/satellite-crop-merge-ds.git
   cd satellite-crop-merge-ds
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Configuration
The application uses environment variables for configuration. Create a `.env` file in the root directory based on the `.env.template` provided:

```bash
# MinIO Credentials
MINIO_HOST="your-minio-host"
MINIO_PORT="your-minio-port"
MINIO_ACCESS_KEY="your-access-key"
MINIO_SECRET_KEY="your-secret-key"
MINIO_BUCKET_NAME="your-bucket-name"

# Sentinel Hub API
SENTINEL2_GRIDS_FILE="path/to/sentinel2-grids.kml"
SENTINEL2_API_KEY="your-sentinel-hub-api-key"
```

## Running the Application

### Development Mode
For development purposes, you can run the Gradio interface directly:
```bash
cd app
python interface.py
```
*Note: In development mode, authentication is bypassed by default.*

### Production Deployment
The recommended way to deploy the service in production is using `uvicorn` to serve the FastAPI application:

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Deployment Strategies
1. **Local Deployment**: Suitable for testing and internal research projects.
2. **Docker Deployment** (Optional): While not explicitly provided in the root, the application structure is compatible with containerization. A typical Dockerfile would use `python:3.12-slim`, install `libgdal-dev` (for GeoPandas/Rasterio), and run `uvicorn`.
3. **Cloud Hosting**: Can be deployed on any cloud provider supporting Python/FastAPI (e.g., AWS EC2, Azure App Service, Google Cloud Run).
