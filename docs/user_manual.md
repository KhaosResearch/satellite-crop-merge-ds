# User Manual

Welcome to the Satellite Crop & Merge Data Space service. This manual provides a quick guide on how to use the interface to retrieve satellite imagery for your specific area of interest.

## 1. Getting Started
Access the service via your web browser (usually at `http://localhost:8000` or `http://localhost:7860` depending on the deployment).

## 2. Authentication
Enter your username and password provided by the administrator. 
*Note: In development environments, the password check may be disabled.*

## 3. Selecting the Data Source
You can choose between two sources:
- **KHAOS MinIO**: Curated, fast access to data for the Andalusia region (Spain).
- **Sentinel Hub**: Global coverage directly from Copernicus. Note that this might be slower and subject to API rate limits.

## 4. Defining the Area of Interest (Parcel)
There are three ways to specify the geometry for cropping:

### A. GeoJSON File Upload
1. Select the "File" option.
2. Upload a `.geojson` file containing a single polygon or multipolygon.
3. The system will automatically use this geometry to crop the satellite data.

### B. SIGPAC Cadastral Reference (Spain)
1. Select the "SIGPAC" option.
2. Enter the Province, Municipality, Sector, Poligono, and Parcela.
3. The system will retrieve the official geometry from the Spanish Cadastre.

### C. Interactive Map
1. Select the "Map" option.
2. Use the drawing tools on the map to create a polygon around your area of interest.

## 5. Temporal Range & Products
1. Select the desired start and end dates.
2. Choose the specific satellite products or spectral indices you need (e.g., NDVI, RGB, Moisture).

## 6. Downloading Data
1. Click the "Submit" or "Process" button.
2. Once the processing is complete, a download link for a `.zip` file will appear.
3. This file contains the cropped raster data, metadata, and a copy of the geometry used.
