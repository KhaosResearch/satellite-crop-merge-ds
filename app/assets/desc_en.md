To provide access to the maps offered in the EDAAn catalogue, the Geospatial Data Download service has been created. Through this interface, users can obtain results by following these steps:

1. **Select your desired product:** Correspondence tables linking product keys to their catalogue entries are provided below.
2. **Specify the time range (only Sentinel products):** For spectral data, indicate the temporal range. For topographic products it will not be necessary.
3. **Input the parcel geometry:** This allows the system to clip the available data to your specific area of interest (AOI) and return targeted results.
   - **`GeoJSON`:** Use your parcel's geometry file to crop out the data.
   - **`SIGPAC` _(Spain only)_:** Input the parcel's limits using a cadastral reference directly from the SIGPAC database.
   - **`Map`:** Use the map interface to manually draw your area of interest.

>**Please note that broad time ranges will take longer to process, especially for products with high file counts (such as `images` or `Vegetation`).**

<details><summary style="cursor: pointer;">List of available products.</summary>

---

| Catalogue Entry | Product Key | Description |
| :--- | :---: | --- |
| **Aerosols** | `Atmospheric Aerosols` | Aerosol Optical Thickness. |
| **Satellite Imagery of Andalusia** | `Satellite Imagery` | Monthly images from the Sentinel-2 satellite of the Andalusia region. The time range includes from the year 2017 to 2025. Cloud percentage >5%. Maps in image format, at 10m, 20m, and 60m pixel resolution. Downloadable in adapted parcel cuts. The available images are monthly composites by band (12 bands) in TIF format, along with a natural color composite image of the grid in PNG format. ... |
| **Water Vapor** | `Atmospheric Humidity` | Water Vapor content maps. |
| **Bare Soil Maps of Andalusia** | `Bare Soil` | Monthly maps of bare soil presence in the region of Andalusia. The time range includes from the year 2017 to 2025. Maps in image format, with a 20 m pixel resolution. Downloadable in adapted parcel sections, in TIF format. Value range from -1 (visible bare soil) to 1 (non-visible or vegetation-covered soil). |
| **Vegetation Senescence Maps of Andalusia** | `Vegetation Senescence` | Monthly vegetation senescence maps for the Andalusia region. The temporal range covers from the year 2017 to 2025. Maps are in image format, with a 10 m pixel resolution. Downloadable in adapted plot cutouts, in TIF format. Value range from -1 (areas without vegetation or green vegetation) to 1 (areas of brown or reddish vegetation). Senescence in plants indicates the dormancy period of deciduous trees in winter, or early signs of mortality. |
| **Vegetation Productivity Maps of Andalusia** | `Vegetation Productivity` | Monthly vegetation productivity maps of the Andalusia region. The time range spans from 2017 to 2025. Maps in image format, at 10m, 20m, and 60m pixel resolution. Downloadable in adapted plot-level sections, in TIF format. Value range from -1 (areas without vegetation or dead vegetation) to 1 (areas of high vegetation productivity). Vegetation areas include ranges between 0.2 and 0.8. Vegetation productivity is associated with the type of vegetation (crops, pastures, shrubland, or forest), plant health, phenological state (seasonality), or the amount of green biomass. We offer productivity maps adapted to areas with sparse vegetation or high vegetation density to provide greater accuracy. |
| **Vegetation Water Content of Andalusia** | `Vegetation Water Content` | Monthly maps of water content in vegetation in the Andalusia region. The time range includes the years from 2017 to 2025. Maps in image format, with a 20 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from -1 (areas without vegetation or dry vegetation) to 1 (areas of vegetation with high water content). The water content of plants is associated with the type of vegetation (crops, pastures, shrubland, or forest), the plant's response to environmental conditions, plant health, or irrigation regime. |
| **Surface Water Mass Maps of Andalusia** | `Water Masses` | Monthly maps of surface water bodies in the Andalusia region. The time range includes the years from 2017 to 2025. Maps in image format, with a 20 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 (areas without water) to 1 (water bodies) |
| **Vegetation Yellowing Maps of Andalusia** | `Vegetation Yellowing` | Monthly maps of vegetation yellowing in the Andalusia region. The time range includes from the year 2017 to 2025. Maps in image format, with 10 m pixel resolution. Downloadable in adapted plot cuts, in TIF format. Value range from -1 (areas without vegetation or green vegetation) to 1 (areas of yellow vegetation). The yellowing of plants can be due to yellow flowering (for example, rapeseed) or the autumn season (for example, in chestnut groves or poplar groves). |
| **Land Cover Maps of Andalusia** | `Land Cover` | Land cover map of the Andalusia region in image format, at 10 m pixel resolution, for the year 2021. Downloadable in adapted parcel cutouts, in TIF or PNG format. Contains 9 classes. The map legend is provided in .qml format, compatible with QGIS image viewing and analysis software. |
| **Forest Species Maps of Andalusia** | `Forest Species` | Map of forest species of the Andalusia region from the year 2021 in image or polygon format. Maps in image format are offered at 10 m pixel resolution, downloadable in adapted plot sections, in TIF or PNG format. Contains a total of 17 plant species. Types of forest species are separated into dense forests (50-100% tree cover) and open forests (30-50% tree cover). The cartography legend is provided in .qml format, compatible with QGIS. |
| **Topographic Orientation Maps of Andalusia** | `Terrain Orientation` | Digital map of slope orientations in the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted parcel sections, in TIF format. Range of values from 0 to 359 degrees, with 0 indicating north orientation, 180 south orientation, 90 east orientation, and 270 west orientation. |
| **Topographic Maps of Andalusia** | `Terrain Elevation` | Digital elevation map of the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 to 4000 m, in meters. |
| **Topographic Slope Maps of Andalusia** | `Terrain Slope` | Digital map of ground slopes of the Andalusia region in image format, with a 25 m pixel resolution. Downloadable in adapted plot sections, in TIF format. Value range from 0 to 90, in degrees of slope, with 0 being horizontal and 90 vertical. |

</details>

<!-- >

<details><summary style="cursor: pointer;">About vailable data source limitations.</summary>

>

| Source | ✔️Pros | ❌Cons |
| --- | --- | --- |
| **KHAOS' MinIO database** | · Fast unlimited access.<br>· Topography related products. | · Only avaliable for the Andalusia, Spain region.<br>· Current temporal range limited to Apr. 2017 - Dec. 2025 included. |
| **Sentinel Hub API** | · All regions in the world available.<br>· Updated spectral data. | · Risk of incurring in API's rate limits. |

> Sentienl Hub API documentation [on this link](https://docssentinel-hub.com/api/latest/). 

</details> -->

---