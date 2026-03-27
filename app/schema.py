schema = {
    "name": "khaos-research/Satellite-Crop-Merge",
    "description": """# Satellite Crop and Merge Downloader 
Quick_desc

## Getting Started
The app is available at [https://github.com/KhaosResearch/satellite-crop-merge-ds](https://github.com/KhaosResearch/satellite-crop-merge-ds).
You can access the platform using the credentials provided by the platform administrator.

### Application Structure

The platform is organized into one single main section providing all specific inputs for data retrieval:

- The Satellite Crop and Merge Downloader is an agrotech application designed for the EDAAn Data Space. It allows users to acquire different satellite product in the form of a compressed collection of TIF files. Data is cut from the geometry input the user provides. The application takes a determined date range, takes the images from the source (MinIO or Sentinel Hub) and performs the Crop & Merge operations

### Input Information
The application accepts the following parameters for analysis:

- **Product key:** The selected product's ID.
  - The app's description on the interface provides a detail of which product keys correspond to what entries in the EDAAn product catalogue.
- **Date range:** Date inputs to specify the temporal coverage.
  - The dats must be in ISO format (YYYY-MM-DD).
  - MinIO takes only YYYY and MM to retrieve data since the database is made of monthly composites.
  - Senintel Hub does need the exact date to calculate its coverage amd retrieve exact data.
- **Geometry input:** Specific parcel's geometry to crop the data from.
  - Several options are offered:
    - GeoJSON file upload: User will need to hace the geometry file prepared beforehand.
    - SIGPAC Cadastral Reference: It will corss-reference the SIGPAC Spanish database to retrieve the geometry.
    - Draw limits on map: The most intuitive form to input the geometry. Draw a polygon and process the data found on it.
- **Data Source (TODO):** Choose between MinIO or Sentinel Hub as the source of the satellite products data
  - MinIO only covers some tiles, particularly, the ones in the Andalusia, Spain region.
  - Sentinel Hub uses the public API to retrieve Sentinel-2 satellite data from virtually anywhere.
...


### Output
1. **Compressed Product Data files (ZIP)**:
   - The ZIP file contains an ordered logical directory structure whenre the TIF files can be found, along with some light documentation. 

2. **Geometry GeoJSON file**:
   - An optional file to download. It contains the geometry data used as a GeoJSON file. 

---

## About
This application is an initiative developed by the Khaos research group.

## Contact
If you have any questions, please contact us at [edaan@uma.com](mailto:edaan@uma.com).""",
    "labels": ["web-application", "data-service", "satellite", "crop", "merge"],
    "jsonforms:schema": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "readOnly": True},
            "password": {"type": "string", "readOnly": True},
        },
    },
    "jsonforms:uischema": {
        "type": "VerticalLayout",
        "elements": [
            {"type": "Label", "text": "Credentials"},
            {"type": "Control", "scope": "#/properties/username", "label": "Username"},
            {"type": "Control", "scope": "#/properties/password", "label": "Password"},
        ],
    },
    "jsonforms:data": {"username": "", "password": ""},
    "embed": "",
}