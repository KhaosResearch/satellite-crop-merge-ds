# Technology Stack

This document outlines the tools and technologies used in the Satellite Crop & Merge Data Space service.

## Core Backend
- **Python 3.12+**: The primary programming language used for the service logic.
- **FastAPI / Uvicorn**: Used for serving the application and handling API requests.
- **SQLModel**: An ORM for interacting with the database, combining SQLAlchemy and Pydantic.
- **Structlog**: For structured and readable logging.

## Frontend & User Interface
- **Gradio**: Framework used to build the interactive web interface, allowing for rapid prototyping and easy access to machine learning models or data processing pipelines.
- **Folium**: Used within Gradio for interactive map visualizations and polygon delimitation.

## Data Processing & GIS
- **GeoPandas**: For handling geospatial data structures (GeoDataFrames) and operations.
- **Rasterio**: For reading and writing geospatial raster data (satellite images).
- **Shapely**: For manipulation and analysis of planar geometric objects.
- **Sentinel Hub Python SDK**: To interact with the Copernicus/Sentinel API and retrieve satellite imagery.
- **SIGPAC Tools**: A custom library developed by KHAOS Research to retrieve cadastral information from the Spanish SIGPAC system.

## Storage & Database
- **MinIO**: High-performance object storage used to store and retrieve curated satellite data.
- **SQLite (via SQLModel)**: Likely used for local metadata and user credential storage.

## Security & Utils
- **Bcrypt**: Used for secure password hashing and authentication.
- **Python-dotenv**: For managing environment variables.
- **Pandas**: For general data manipulation and analysis.
