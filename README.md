# Satellite Crop & Merge Data Space service:
This respository hosts an application to retrieve satellite data based on the products available in the EDAAn Data Space catalogue. it leverages a [Gradio](https://gradio.app/) interface for simple, intuitive access to KHAOS' MinIO database and Copernicus/Sentinel API.

## 🛠️Features:
- **🔒 Authentication:** Secured login functionality using database credential generation and storage.
- **📡 Multiple sourcing:** Choose between curated data from KHAOS' MinIO database or use Earth obaservation data directly from the Sentinel Hub API. Check [Table 1](#table-1-source-comparison) for further distinctions.
- **✅ Product Accessibility:** Select and access satellite image and spectral indices data over a temporal range.
- **📋 Parcel specific cropping:** Data is applied over the specified parcel geometry, which can be provided in a number of alternatives:
  - **📂 GeoJSON file upload:** Use your parcel's geometry file to cut out the data.
  - **🔗 SIGPAC cadastral reference _(Spain only)_:** Input the parcel's limits directly from the SIGPAC database using a valid reference.
  - **🗺️ Map polygon delimitation:** Use the map interface to manually draw your area of interest.
- **📊 Data handling:** Data is available for local download as a compressed file, along with all necessary documentation to use.

## 📦Requisites:
- 🐍 Python 3.12+
- 📝 All dependencies installed (`requirements.txt`).
- 🔢 All `.env` variables with the following content:
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
>[!NOTE]
>Authentication for development mode will take any input, since login always returns `True` by default here. Input username will be used to create the job directories.

## 💻 Deployment:
You can easily deploy the project using `uvicorn` and indicating both `host` and `port` for deployment:
```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Annex:
### Table 1: Source comparison
| Source | ✔️Pros | ❌Cons |
| --- | --- | --- |
| **KHAOS' MinIO** | · Fast unlimited access.<br>· Topography related products. | · Only avaliable for the Andalusia, Spain region.<br>· Current temporal range limited to Apr. 2017 - Dec. 2025. |
| **Sentinel Hub API** | · All regions in the world available.<br>· Updated spectral data. | · Risk of incurring in API's rate limits. |

