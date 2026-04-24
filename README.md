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

# Setup environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the app
cd app
python interface.py
```

## 📄 License
This project is licensed under the **Apache License 2.0**. See the [LICENSE](LICENSE) file for the full text.

## 🔄 Changelog
See [CHANGELOG.md](CHANGELOG.md) for a detailed record of versions and changes.
