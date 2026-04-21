To provide access to the maps offered in the EDAAn catalog, the Geospatial Data Download service has been created. Through this interface, users can obtain results by following these steps:

1. **Select data source:**
   - **`minio`:** **For the Andalusia Spain area only.** The database contains the region's Sentinel spectral products and ASTER topography products. 
   - **`sentinel`:** **For the rest of the world.** Depends on Sentinel Hub's API. Only spectral products available. More infor [on this link](https://docs.sentinel-hub.com/api/latest/). 
2. **Select your desired product:** Correspondence tables linking product keys to their catalog entries are provided below.
3. **Specify the time range (only Sentinel products):**
   - **`minio`:** The available temporal range covers from **April 2017 to December 2025 included.**
   - **`sentinel`:** Time range is considerably extended, same as Copernicus. It is recommended to check the specific documentation.
4. **Input the parcel geometry:** This allows the system to clip the available data to your specific area of interest (AOI) and return targeted results.
   - **`GeoJSON Upload`:** Use your parcel's geometry file to cut out the data.
   - **`SIGPAC Cadastral` _(Spain only)_:** Input the parcel's limits straight from the SIGPAC database using a valid reference.
   - **`Draw on Map`:** Use the map interface to manually draw your area of interest.

>**Please note that broad time ranges will take longer to process, especially for products with high file counts (such as `images` or `Vegetation`).**

<details><summary style="cursor: pointer;">Table 1: Correspondence between Sentinel product keys and catalog entries.</summary>

---

| Catalog Entry | Product Key | Description |
| :--- | :---: | --- |
| **Aerosols** | `AOT` | Aerosol Optical Thickness. |
| **Satellite Imagery of Andalusia** | `images` | Monthly Sentinel-2 satellite images of Andalusia. Range 2017-2025. Cloud cover <5%. 10 m pixel resolution. Monthly composites per band (12 bands) in TIF format, plus natural color PNG. |
| **True Color Image** | `TCI` | Natural color composite. |
| **Water Vapor** | `WVP` | Water Vapor content maps. |
| **Bare Soil Maps of Andalusia** | `BareSoil` | Monthly bare soil presence maps. 20m resolution. Values from -1 (visible bare soil) to 1 (hidden soil). |
| **Vegetation Senescence Maps of Andalusia** | `Senescence` | Monthly senescence maps. 10m resolution. Values from -1 (green) to 1 (brown/reddish). Indicates dormancy or mortality. |
| **Vegetation Productivity Maps of Andalusia** | `Vegetation` | Monthly productivity maps. 10m resolution. Values from -1 (dead) to 1 (high productivity). Associated with health, phenology, and biomass. |
| **Vegetation Water Content of Andalusia** | `WaterContent` | Monthly water content maps. 20m resolution. Values from -1 (dry) to 1 (high water content). |
| **Surface Water Mass Maps of Andalusia** | `WaterMass` | Monthly surface water maps. 20m resolution. Values from 0 (no water) to 1 (water). |
| **Vegetation Yellowing Maps of Andalusia** | `Yellow` | Monthly yellowing maps. 10m resolution. Values from -1 (green) to 1 (yellow). Due to flowering or seasonal changes. |

</details>

>

<details><summary style="cursor: pointer;">Table 2: Correspondence between ASTER product keys and catalog entries.</summary>

---

| Catalog Entry | Product Key | Description |
| :--- | :---: | --- |
| **Topographic Orientation Maps of Andalusia** | `aspect` | Digital map of slope orientations in the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted parcel sections, in TIF format. Range of values from 0 to 359 degrees, with 0 indicating north orientation, 180 south orientation, 90 east orientation, and 270 west orientation. |
| **Topographic Maps of Andalusia** | `elevation` | Digital elevation map of the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 to 4000 m, in meters. |
| **Topographic Slope Maps of Andalusia** | `slope` | Digital map of ground slopes of the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 to 90, in degrees of slope, with 0 being horizontal and 90 vertical. |

</details>

---