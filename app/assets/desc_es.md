Para poder tener acceso a los mapas ofertados en el catálogo del EDAAn, se ha creado el servicio de Descarga de Datos Geoespaciales. A través de la interfaz, el usuario puede obtener el resultado de la siguiente forma:

1. **Seleccione el producto que desea:** Más adelante encontrará tablas de correspondencia de la clave del producto con su entrada en el catálogo.
2. **Especifique el rango temporal a cubrir:** Para productos espectrales, indique el rango temporal. Para productos topográficos no es necesario.
3. **Introduzca el área de interés para el análisis:** Esto permitirá recortar la parcela sobre los datos disponibles y devolver resultados que se apliquen sobre ese área de interés.
   - **`GeoJSON`:** Use un archivo con la geometría de su parcela para recortar los datos.
   - **`SIGPAC` _(Sólo España)_:** Introduzca los límites de la parcela usando una referencia catastral directamente de la base de datos de SIGPAC.
   - **`Map`:** Utilice la interfaz del mapa para dibujar manualmente si área de interés.

>**Tenga en cuenta que los rangos temporales amplios tomarán su tiempo de procesar, especialmente para productos con muchos archivos asociados (`images` o `Vegetation`).**

<details><summary style="cursor: pointer;">Tabla 1: Correspondencia de claves de productos Sentinel con entradas en el catálogo.</summary>

---

| Entrada del catálogo | Clave del producto | Descripción |
| :--- | :---: | --- |
| **Densidad Óptica del Aerosol** | `Aerosoles Atmosféricos` | Densidad Óptica del Aerosol |
| **Imágenes de Satélite de Andalucía** | `Imágenes de Satélite` | Imágenes mensuales del satélite Sentinel-2 de la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Porcentaje de nubes >5%. Mapas en formato imagen, a 10m, 20m y 60m de resolución de píxel. Descargable en recortes de parcela adaptados. Las imágenes disponibles son compuestos mensuales por banda (12 bandas) en formato TIF, junto con una imagen compuesta a color natural de la cuadrícula en formato PNG. |
| **Evotranspiración** | `Humedad Atmosférica` | Evotranspiración |
| **Mapas de suelo desnudo de Andalucía** | `Suelo Desnudo` | Mapas mensuales de presencia de suelo desnudo en la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Mapas en formato imagen, a 20 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de -1 (suelo desnudo visible) a 1 (suelo no visible o cubierto de vegetación). |
| **Mapas de senescencia de la vegetación de Andalucía** | `Senescencia Vegetal` | Mapas mensuales de senescencia de la vegetación en la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Mapas en formato imagen, a 10 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de -1 (zonas sin vegetación o vegetación verde) a 1 (zonas de vegetación marrón o rojiza). La senescencia en las plantas indica la época de dormancia de los árboles caducifolios en el invierno, o signos tempranos de mortalidad.  |
| **Mapas de productividad vegetal de Andalucía** | `Productividad Vegetal` | Mapas mensuales de productividad vegetal de la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Mapas en formato imagen, a 10m , 20m y 60m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de -1 (zonas sin vegetación o vegetación muerta) a 1 (zonas de alta productividad vegetal). Las zonas de vegetación comprenden los rangos entre 0.2 y 0.8. La productividad vegetal está asociada al tipo de vegetación (cultivos, pastos, matorral o bosque), la salud de la planta, estado fenológico (estacionalidad) o la cantidad de biomasa verde. Ofrecemos mapas de productividad adaptados a zonas de vegetación escasa o de alta densidad de vegetación, para proporcionar una precisión mayor. |
| **Mapas de contenido hídrico en la vegetación de Andalucía** | `Contenido hídrico en plantas` | Mapas mensuales de contenido hídrico de la vegetación en la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Mapas en formato imagen, a 20 m de resolución de píxel. Descargable en cuadrícula , en formato TIF. Rango de valores de -1 (zonas sin vegetación o vegetación seca) a 1 (zonas de vegetación con alto contenido en agua). El contenido en agua de las plantas está asociada al tipo de vegetación (cultivos, pastos, matorral o bosque), respuesta de la planta a las condiciones ambientales, la salud de la planta o régimen de irrigación. |
| **Mapas de masas de aguas superficiales de Andalucía** | `Masas de aguas` | Mapas mensuales de las masas de agua superficiales en la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Mapas en formato imagen, a 20 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de 0 (zonas sin agua) a 1 (masas de agua) |
| **Mapas de amarillamiento de la vegetación de Andalucía** | `Amarillamiento Vegetal` | Mapas mensuales de amarilleamiento de la vegetación en la región de Andalucía. El rango temporal incluye desde el año 2017 hasta el 2025. Mapas en formato imagen, a 10 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de -1 (zonas sin vegetación o vegetación verde) a 1 (zonas de vegetación amarilla).El amarillamiento de las plantas se puede deber a floración amarilla (por ejemplo, la colza) o la época de otoño (por ejemplo, en castañares o alamedas). |

</details>

>

<details><summary style="cursor: pointer;">Tabla 2: Correspondencia de claves de productos ASTER con entradas en el catálogo.</summary>

---

| Entrada del catálogo | Clave del producto | Descripción |
| :--- | :---: | --- |
| **Mapa de orientaciones topográficas de Andalucía** | `Orientaciones del Terreno` | Mapa digital de orientaciones de las pendientes de la región de Andalucía en formato imagen, a 25 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de 0 a 359 grados, siendo 0 orientación norte, 180 orientación sur, 90 orientación este y 270 orientación oeste.|
| **Mapa topográfico de Andalucía** | `Topografía del Terreno` | Mapa digital de elevaciones de la región de Andalucia en formato imagen, a 25 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de 0 a 4000 m, en metros. |
| **Mapa de pendientes topográficas de Andalucía** | `Pendientes del Terreno` | Mapa digital de pendientes del suelo de la región de Andalucía en formato imagen, a 25 m de resolución de píxel. Descargable en recortes de parcela adaptados, en formato TIF. Rango de valores de 0 a 90, en grados de inclinación, siendo 0 la horizontal y 90 la vertical. |

</details>

>

<details><summary style="cursor: pointer;">Sobre las limitaciones de las fuentes de datos disponibles.</summary>

| Fuente | ✔️Ventajas | ❌Límitaciones |
| --- | --- | --- |
| **Base de datos KHAOS MinIO** | · Acceso rápido e ilimitado.<br>· Incluye productos topográficos. | · Sólo disponible para la región de Andalcía, España.<br>· Rango temporal actual limitado a Abr. 2017 - Dic. 2025 inclusive. |
| **Sentinel Hub API** | · Todas las regiones del mundo disponibles.<br>· Datos espectrales actualizados. | · Riesgo de incurrir en los límites de llamadas a la API. |

> Documentación de Sentienl Hub API [en este enlace](https://docssentinel-hub.com/api/latest/). 
</details>

---