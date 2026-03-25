To provide access to the maps offered in the EDAAn catalog, the Geospatial Data Download service has been created. Through this interface, users can obtain results by following these steps:

1. **Select your desired product:** A correspondence table linking product keys to their catalog entries is provided below.
2. **Specify the time range:** The available temporal range covers from April 2017 to December 2025 inclusive.
3. **Input the parcel geometry:** This allows the system to clip the available data to your specific area of interest (AOI) and return targeted results.

>**Please note that broad time ranges will take longer to process, especially for products with high file counts (such as `images` or `Vegetation`).**

<details><summary>Table 1: Correspondence between product keys and catalog entries.</summary>



| Catalog Entry | Product Key | Description |
| :--- | :---: | --- |
| **Aerosols** | `AOT` | Aerosol Optical Thickness. |
| **Satellite Imagery of Andalusia** | `images` | Monthly Sentinel-2 satellite images of Andalusia. Range 2017-2025. Cloud cover <5%. 10 m pixel resolution. Downloadable in 110x110 km tiles. Monthly composites per band (12 bands) in TIF format, plus natural color PNG. |
| **True Color Image** | `TCI` | Natural color composite. |
| **Water Vapor** | `WVP` | Water Vapor content maps. |
| **Bare Soil Maps of Andalusia** | `BareSoil` | Monthly bare soil presence maps. 20m resolution. Values from -1 (visible bare soil) to 1 (hidden soil). |
| **Vegetation Senescence Maps** | `Senescence` | Monthly senescence maps. 10m resolution. Values from -1 (green) to 1 (brown/reddish). Indicates dormancy or mortality. |
| **Vegetation Productivity Maps** | `Vegetation` | Monthly productivity maps. 10m resolution. Values from -1 (dead) to 1 (high productivity). Associated with health, phenology, and biomass. |
| **Vegetation Water Content** | `WaterContent` | Monthly water content maps. 20m resolution. Values from -1 (dry) to 1 (high water content). |
| **Surface Water Mass Maps** | `WaterMass` | Monthly surface water maps. 20m resolution. Values from 0 (no water) to 1 (water). |
| **Vegetation Yellowing Maps** | `Yellow` | Monthly yellowing maps. 10m resolution. Values from -1 (green) to 1 (yellow). Due to flowering or seasonal changes. |

</details>