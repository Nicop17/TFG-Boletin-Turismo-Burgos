# Módulo de configuración

Este directorio contiene los parámetros operativos, credenciales, umbrales lógicos y configuraciones técnicas que gobiernan el pipeline de extracción, transformación y carga (ETL) del Boletín de Turismo. 

Al aislar estas variables en un archivo JSON en la raíz, se garantiza la portabilidad del sistema y se permite modificar el comportamiento del scraper y del cargador de datos sin alterar el código fuente en Python.

**MUY IMPORTANTE**: No dejar en blanco ningún campo salvo que se indique expresamente que existe la opción en este manual para que el scraper pueda ejecutarse correctamente.

---

## Estructura y parámetros de `config.json`

### 1. `google_cloud`
Centraliza las credenciales de conexión con la infraestructura de Google Cloud Platform (BigQuery).
* **`credentials_file`**: Nombre del archivo de clave privada en formato JSON (`key.json`) que contiene el token de la cuenta de servicio (SA) para autenticar las llamadas de las APIs de Google.
* **`project_id`**: Identificador único y global del proyecto en la consola de GCP (ej. `tfg-boletin-turismo-burgos`).
* **`dataset_id`**: Nombre del conjunto de datos dentro de BigQuery donde residen y se crean las tablas del sistema (ej. `ds_turismo_reviews`).
* **`tables`**: Diccionario que mapea los nombres físicos de las 6 tablas en la base de datos. Si se han creado las tablas con otro nombre, se deben modificar aquí para que haga referencia al nombre de tabla correcto de la base de datos de cada una de las 6 tablas utilizadas en el proyecto.

### 2. `tori_logic`
Parámetros numéricos que calibran y controlan los límites del algoritmo de puntuación y analítica del boletín de turismo. Da la opción de modificar la escala de valores individual de cada puntuación y la total del TORI (es la suma de ambas puntuaciones máximas). El mínimo siempre va a ser 0.
* **`max_score_rating`**: Puntuación máxima asignable o factor de ponderación del peso que tendrá la valoración media de las reseñas de Google Maps. (Ej. Si se pone 5 significa que la escala será de 0 a 5 y si se pone 10 será de 0 a 10).
* **`max_score_sentiment`**: Puntuación máxima asignable o factor de ponderación del peso que tendrá el análisis de sentimiento del texto de las reseñas en el score final. (Ej. Si se pone de valor 5, la ponderación de este campo será sobre 5 y la escala de 0 a 5).
Ambas funcionan de la misma manera y la idea es que se pueda personalizar la escala y la ponderación de cada valor siendo el total del TORI la suma de ambos valores. (Ej. Si se quiere dar más importancia al sentimiento que a la puntuación media de Maps y se quiere que la escala del TORI sea de 0 a 100, se podrían establecer como valores `max_score_rating`: 40 [0,40] y `max_score_sentiment`: 60, dando un total de 100. TORI: [0,100]).

### 3. `scraper_logic`
Define las reglas de negocio esenciales del scraper incremental y los criterios de segmentación demográfica.
* **`margin_days_update_pois`**: Número de días que determina la caducidad de un punto de interés (POI). Si los días transcurridos desde la última actualización del campo correspondiente (municipio, categoría o incluso un POI concreto) superan este margen, el pipeline volverá a invocar al actor de Apify para renovar la tabla de POIs. Si se ejecuta y hay POIs categorías o municipios que tienen guardada la última actualización de POIs con una fecha más cercana a la cifra fijada, los municipios, categorías o POIs se saltarán en el bucle de ejecución y no se actualizarán sus POIs.
* **`margin_days_update_reviews`**: Número de días que determina la necesidad de ampliar las reseñas de un POI. Si los días transcurridos desde la última actualización del campo correspondiente (municipio o POI) superan este margen, el pipeline volverá a invocar al actor de Apify para ampliar la tabla de reseñas. Si se ejecuta y hay POIs o municipios que tienen guardada la última actualización de reseñas con una fecha más cercana a la cifra fijada, los POIs o municipios se saltarán en el bucle de ejecución y no se sacarán reseñas de ellos.
* **`postal_code_prefix`**: Prefijo numérico de la provincia que se quiere ejecutar (ej. `"09"` para Burgos) que sirve de filtro para descartar lugares con códigos postales de otras provincias y que no se guarden en la base de datos.
* **`location_province`**: Cadena de texto que indica la provincia y el país en la que se pretende ejecutar el scraper (ej. `"Burgos, España"`) para evitar ambigüedades con municipios homónimos en otras regiones.
* **`muni_threshold_rural`** y **`muni_threshold_semi_rural`**: Límites numéricos de población (habitantes) utilizados por el clasificador para segmentar los municipios en tres entornos de forma dinámica:
  * **Rural:** Población $\le$ `muni_threshold_rural`.
  * **Semi-rural:** `muni_threshold_rural` $<$ Población $\le$ `muni_threshold_semi_rural`.
  * **Urbano:** Población $>$ `muni_threshold_semi_rural`.

### 4. `execution_filters`
Filtros avanzados orientados al control del flujo incremental, optimización de costes de la API y depuración ágil en local.
* **`target_municipality`** / **`target_category`** / **`target_poi`**: Cadenas de texto que actúan como selectores restrictivos.
  * *Opciones disponibles:*
    * `""` (String vacío): Modo por defecto. El pipeline procesa de forma masiva e incremental toda la provincia.
    * Rellenar alguna o todas las opciones: Ej. `Abajas`,  `Pizzería` o `Cervecería Morito`. Es **imprescindible** que el nombre escrito en cualquiera de los tres campos coincida exactamente con el dato guardado en base de datos para que funcione correctamente la ejecución.
  * Si se indica un POI objetivo lo único que hará el scraper es sacar las reseñas de ese POI (si hay varios en la provincia con ese nombre, ej. `"Burger King"`, sacará las reseñas de todos los POIs de la provincia con ese nombre) ignorando lo que se indique en la categoría ya que solo va a buscar reseñas no POIs. Sin embargo sí que filtra paralelamente por municipio (ej. sacando reseñas únicamente de los `"Burger king"` de `"Burgos"`).
  * Si se deja el `target_poi` en blanco (""), entonces sí realizará búsqueda de POIs (y reseñas) en el municipio y/o de la categoría indicados.
* **`order_municipalities_by`** / **`order_categories_by`** / **`order_pois_by`**: Cláusulas de ordenación nativas en formato SQL que determinan la prioridad de recorrido de los bucles de ejecución del pipeline. 
Escribir nombres de las columnas que coincidan exactamente con uno de los campos de la tabla que se está ordenando (Si es de municipalities, usar una de sus columnas: id_municipality, name, population...)
  * *Opciones típicas:*
    * `"population ASC"` / `"population DESC"` (para priorizar la extracción por municipios según tamaño demográfico).
    * `"name ASC"` / `"id_municipality ASC"` (para un barrido alfabético o numérico secuencial estricto y previsible).

### 5. `apify_params`
Variables de configuración técnica requeridas por la API de Apify para modular el comportamiento de los web scrapers en la nube.
* **`poi_actor`**: Nombre del actor de Apify encargado del rastreo de lugares (ej. `"compass/crawler-google-places"`).
* **`reviews_actor`**: Nombre o ruta del actor encargado de scrapear el feed de reseñas (ej. `"compass/google-maps-reviews-scraper"`).
* **`max_retries`**: Número máximo de reintentos automáticos permitidos ante un fallo técnico momentáneo o un código de estado HTTP erróneo de la API de Apify.
* **`retry_wait_seconds`**: Tiempo de parada o latencia (en segundos) que el script esperará entre reintento y reintento.
* **`language`** y **`country_code`**: Códigos internacionales estandarizados en formato ISO (`"es"`) para forzar a la interfaz de Google Maps a devolver los textos adaptados al lenguaje de destino indicado. En el caso del código del país es para realizar la extracción en el país indicado.
* **`reviews_start_date`**: Tiempo desde el que se quiere extraer reseñas de los POIs almacenados en la base de datos. Se puede establecer en horas, días o meses. Ej. `reviews_start_date`: "1 month". Extraerá todas las reseñas de cada POI que se hayan posteado en el último mes.
* **`reviews_sort`**: Criterio de ordenación de las reseñas en el origen de Google Maps.
  * *Opciones disponibles:*
    * `"newest"`: Trae primero las reseñas más recientes (ideal para actualizaciones incrementales rápidas).
    * `"most_relevant"`: Trae primero las reseñas con más interacciones o interacciones valoradas por los usuarios de Google.
    * `"highest_rating"` / `"lowest_rating"`: Ordena por la polaridad de las estrellas.
* **`reviews_origin`**: Canal de procedencia de las reseñas. Se puede establecer que solo extraiga reseñas de Google o de cualquier otra página como Tripadvisor, etc. (fijado por defecto en `"google"` para asegurar reseñas verificadas).

### 6. `transformer_params`
Reglas de limpieza, preprocesamiento y validación aplicadas por el pipeline de Python sobre las reseñas extraídas antes de enviarlas a BigQuery.
* **`min_review_words`**: Umbral numérico de calidad (longitud de cadena). Si una reseña contiene menos palabras de las especificadas (ej. `8`), se descarta automáticamente. Esto filtra comentarios vacíos o poco informativos (como *"Ok"*, o *"Bien"*) garantizando un set de datos enriquecido para el análisis de sentimiento.
* **`target_lang`**: Código de idioma de destino (`"es"`). Todas las reseñas extraídas se traducirán a este idioma antes de almacenarlas en la base de datos.
* **`default_user_name`**, **`default_user_gender`**, **`default_review_lang`**: Ej. `"Anónimo"` para el nombre del usuario y `"Desconocido"` para género del autor e idioma de la reseña. Palabras que el script inyectará en las columnas correspondientes de la tabla de reseñas en caso de que la API recolecte campos nulos, corruptos o perfiles de usuario privados.

### 7. `logging_params`
Controla el comportamiento del sistema de monitorización visual por consola.
* **`log_level`**: Nivel mínimo de severidad técnica que el logger capturará y pintará en pantalla y guardará en el archivo .log.
  * *Opciones disponibles en orden de restrictividad:*
    * `"DEBUG"`: Muestra trazas hiperdetalladas de variables y flujos internos.
    * `"INFO"`: Muestra el flujo informativo normal de ejecución del pipeline.
    * `"WARNING"`: Filtra todo excepto advertencias de rendimiento o anomalías no críticas.
    * `"ERROR"`: Muestra únicamente excepciones que interrumpen o cuelgan módulos concretos del pipeline.
* **`log_to_file`**: Variable booleana (`true` o `false`) que activa o desactiva la clonación de las trazas de la consola en un archivo de texto físico.
* **`log_file_name`**: Nombre del archivo físico donde se guardará el histórico completo de eventos de la ETL (ej. `"scraper_execution.log"`).
* **`log_format`**: Máscara estructural con marcadores de posición nativos de Python que define el diseño visual exacto de cada línea del log (El formato por defecto contiene marcas de tiempo, etiquetas de severidad, nombre del script de origen, número de línea exacto donde ocurrió el evento y el mensaje descriptivo).