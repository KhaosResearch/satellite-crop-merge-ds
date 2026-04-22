To provide access to the maps offered in the EDAAn catalogue, the Geospatial Data Download service has been created. Through this interface, users can obtain results by following these steps:

1. **Select your desired product:** Correspondence tables linking product keys to their catalogue entries are provided below.
2. **Specify the time range (only Sentinel products):** For spectral data, indicate the temporal range. For topographic products it will not be necessary.
3. **Input the parcel geometry:** This allows the system to clip the available data to your specific area of interest (AOI) and return targeted results.
   - **`GeoJSON`:** Use your parcel's geometry file to crop out the data.
   - **`SIGPAC` _(Spain only)_:** Input the parcel's limits using a cadastral reference directly from the SIGPAC database.
   - **`Map`:** Use the map interface to manually draw your area of interest.

>**Please note that broad time ranges will take longer to process, especially for products with high file counts (such as `images` or `Vegetation`).**

<details><summary style="cursor: pointer;">Table 1: Correspondence between Sentinel product keys and catalogue entries.</summary>

---

| Catalogue Entry | Product Key | Description |
| :--- | :---: | --- |
| **Aerosols** | `Atmospheric Aerosols` | Aerosol Optical Thickness. |
| **Satellite Imagery of Andalusia** | `Satellite Imagery` | Monthly Sentinel-2 satellite images of Andalusia. Range 2017-2025. Cloud cover <5%. 10 m pixel resolution. Monthly composites per band (12 bands) in TIF format, plus natural color PNG. |
| **Water Vapor** | `Atmospheric Humidity` | Water Vapor content maps. |
| **Bare Soil Maps of Andalusia** | `Bare Soil` | Monthly bare soil presence maps. 20m resolution. Values from -1 (visible bare soil) to 1 (hidden soil). |
| **Vegetation Senescence Maps of Andalusia** | `Vegetation Senescence` | Monthly senescence maps. 10m resolution. Values from -1 (green) to 1 (brown/reddish). Indicates dormancy or mortality. |
| **Vegetation Productivity Maps of Andalusia** | `Vegetation Productivity` | Monthly productivity maps. 10m resolution. Values from -1 (dead) to 1 (high productivity). Associated with health, phenology, and biomass. |
| **Vegetation Water Content of Andalusia** | `Vegetation Water Content` | Monthly water content maps. 20m resolution. Values from -1 (dry) to 1 (high water content). |
| **Surface Water Mass Maps of Andalusia** | `Water Masses` | Monthly surface water maps. 20m resolution. Values from 0 (no water) to 1 (water). |
| **Vegetation Yellowing Maps of Andalusia** | `Vegetation Yellowing` | Monthly yellowing maps. 10m resolution. Values from -1 (green) to 1 (yellow). Due to flowering or seasonal changes. |

</details>

>

<details><summary style="cursor: pointer;">Table 2: Correspondence between ASTER product keys and catalogue entries.</summary>

---

| Catalogue Entry | Product Key | Description |
| :--- | :---: | --- |
| **Topographic Orientation Maps of Andalusia** | `Terrain Orientation` | Digital map of slope orientations in the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted parcel sections, in TIF format. Range of values from 0 to 359 degrees, with 0 indicating north orientation, 180 south orientation, 90 east orientation, and 270 west orientation. |
| **Topographic Maps of Andalusia** | `Terrain Elevation` | Digital elevation map of the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 to 4000 m, in meters. |
| **Topographic Slope Maps of Andalusia** | `Terrain Slope` | Digital map of ground slopes of the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 to 90, in degrees of slope, with 0 being horizontal and 90 vertical. |

</details>

>

<details><summary style="cursor: pointer;">About vailable data source limitations.</summary>

| Source | ✔️Pros | ❌Cons |
| --- | --- | --- |
| **KHAOS' MinIO database** | · Fast unlimited access.<br>· Topography related products. | · Only avaliable for the Andalusia, Spain region.<br>· Current temporal range limited to Apr. 2017 - Dec. 2025 included. |
| **Sentinel Hub API** | · All regions in the world available.<br>· Updated spectral data. | · Risk of incurring in API's rate limits. |

> Sentienl Hub API documentation [on this link](https://docssentinel-hub.com/api/latest/). 

</details>

---