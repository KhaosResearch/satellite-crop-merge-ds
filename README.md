# Satellite Crop & Merge Data Space Service

This repository hosts an application to retrieve, crop, and merge satellite data based on products available in the EDAAn Data Space catalogue. It provides a simple and intuitive interface for accessing KHAOS' MinIO database and the Copernicus/Sentinel API.

## 🌟 Key Features
- **Flexible Sourcing**: Choose between curated local data (MinIO) or global Sentinel Hub API.
- **Multiple Geometry Inputs**: Support for GeoJSON uploads, SIGPAC cadastral references, and interactive map drawing.
- **Precision Cropping**: Automatic data clipping to the exact parcel geometry.
- **Temporal Analysis**: Retrieve satellite image and spectral indices over custom time ranges.

## 📖 Documentation
Detailed technical documentation is available in the `docs/` directory:

- [**Software Architecture**](docs/architecture.md): System design, modules, and interdependencies.
- [**Deployment Guide**](docs/deployment.md): Instructions for setup, configuration, and production deployment.
- [**Technology Stack**](docs/technologies.md): Comprehensive list of tools and libraries used.
- [**User Manual**](docs/user_manual.md): A brief guide for end-users on how to use the interface.

## 🚀 Quick Start (Development)
```bash
# Clone the repository
git clone https://github.com/KhaosResearch/satellite-crop-merge-ds.git
cd satellite-crop-merge-ds

# Generate Virtual Env and install necesary dependencies
uv sync

# Access and run the app interface
uv run app/interface.py 
```
>[!NOTE]
>Authentication for development mode will take any input, since login always returns `True` by default here. Input username will be used to create the job directories.

## 💻 Deployment:
You can easily deploy the project using `uvicorn` and indicating both `host` and `port` for deployment:
```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### 🐳 Docker:
**Build the image:**
```bash
docker build -t satellite-crop-merge-ds .
```

**Run the container** (pass your `.env` file as environment source):
```bash
docker run -d \
  --name satellite-crop-merge-ds \
  --env-file .env \
  -p 8080:8080 \
  satellite-crop-merge-ds
```

## 📄 License
This project is licensed under the **Apache License 2.0**. See the [LICENSE](LICENSE) file for the full text.

## 🔄 Changelog
See [CHANGELOG.md](CHANGELOG.md) for a detailed record of versions and changes.
