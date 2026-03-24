# Satellite Crop & Merge Data Space service:
This respository hosts an application to retrieve satellite data based on the products available in the EDAAn Data Space catalogue. it leverages a [Gradio](https://gradio.app/) interface for simple, intuitive access to KHAOS' MinIO database and Copernicus/Sentinel API.

## 🛠️Features:
- **Authentication (`TODO`):** Secured login functionality using database credential generation and storage.
- **Product Accessibility:** Select and access satellite image and spectral indices data over a temporal range.
- **Parcel specific cropping:** Data is applied over the specified parcel geometry, which can be provided in a number of alternatives (GeoJSON file upload, SIGPAC cadastral reference or map polygon delimitation).
- **Data handling:** Data is available for local download as a compressed file, along with all necessary documentation to use.

## 📦Requisites:
- Python 3.12+
- All dependencies installed (`requirements.txt`).
- All `.env` variables with the following content:
```bash
# MinIO Root Credentials
MINIO_HOST="minio-host"
MINIO_PORT="minio-port"
MINIO_ACCESS_KEY="minio-access-key"
MINIO_SECRET_KEY="minio-secret-key"
MINIO_BUCKET_NAME="minio-bucket-name"

SENTINEL2_GRIDS_FILE="path-to-sentinel2-grids-file"
SENTINEL2_API_KEY="your-sentinel2-api.key"
```
>[!NOTE]
>The `SENTINEL2_GRIDS_FILE` variable is a `kml` file to identify which tiles contain the geometry to retrieve. A GeoJSON version was generated [here](https://github.com/ubukawa/sentinel-2-grid).

## 🚀Quickstart (development):
In order to setup the app for development, do the following:

```bash
# Clone and access the project
git clone https://github.com/KhaosResearch/satellite-crop-merge-ds.git
cd satellite-crop-merge-ds

# Generate Virtual Env and install necesary dependencies
python -m venv venv
source venv/bin/activate
# venv\scripts\activate  # For Windows
pip install --upgrade pip
pip install -r requirements.txt

# Access and run the app interface
cd src
python interface.py 
```
