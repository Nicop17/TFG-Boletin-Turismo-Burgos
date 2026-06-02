-- 1. Tabla de Municipios
CREATE TABLE IF NOT EXISTS `tfg-boletin-turismo-burgos.ds_turismo_reviews.municipalities`
(
  id_municipality INT64 OPTIONS(description="Código oficial del INE para el municipio"),
  name STRING OPTIONS(description="Nombre oficial del municipio de la provincia de Burgos"),
  population INT64 OPTIONS(description="Número de habitantes (INE)"),
  last_poi_update TIMESTAMP OPTIONS(description="Última actualización de POIs"),
  last_review_extraction TIMESTAMP OPTIONS(description="Última extracción de reseñas")
);

-- 2. Tabla de Categorías
CREATE TABLE IF NOT EXISTS `tfg-boletin-turismo-burgos.ds_turismo_reviews.categories`
(
  id_category INT64 OPTIONS(description="ID numérico único y clave primaria de la categoría"),
  level_1_category STRING OPTIONS(description="Categoría raíz de la taxonomía (Anthropomo, Lithomo, Hydromo, Phytomo)"),
  level_2_category STRING OPTIONS(description="Subcategoría de segundo nivel que agrupa sectores económicos o naturales (Commerce, Nature)"),
  level_3_category STRING OPTIONS(description="Clasificación de tercer nivel (Local commerce, Nature water)"),
  level_4_category STRING OPTIONS(description="Nivel más específico de la jerarquía interna"),
  maps_category STRING OPTIONS(description="Nombre exacto de la categoría utilizado para realizar las búsquedas en Google Maps"),
  search_level INT64 OPTIONS(description="Índice de segmentación demográfica para optimización de costes (1: Rural, 2: Semi-urbano, 3: Urbano)")
);

-- 3. Tabla de Puntos de Interés (POIs)
CREATE TABLE IF NOT EXISTS `tfg-boletin-turismo-burgos.ds_turismo_reviews.pois`
(
  poi_id STRING OPTIONS(description="ID único de Google Maps (Place ID)"),
  poi_name STRING OPTIONS(description="Nombre comercial o turístico del sitio"),
  id_municipality INT64 OPTIONS(description="ID numérico único que vincula con la tabla de municipios"),
  poi_municipality STRING OPTIONS(description="Municipio de la provincia de Burgos al que pertenece"),
  address STRING OPTIONS(description="Dirección postal completa del establecimiento"),
  postal_code STRING OPTIONS(description="Código postal"),
  id_category INT64 OPTIONS(description="ID numérico único que vincula con la tabla de categorías"),
  maps_category STRING OPTIONS(description="Categoría original devuelta por la API de Google Maps"),
  poi_total_rating FLOAT64 OPTIONS(description="Puntuación global de Google (1-5)"),
  tori_score FLOAT64 OPTIONS(description="Índice de Reputación Online (TORI) calculado mediante sentimiento"),
  reviews_count INT64 OPTIONS(description="Número total de reseñas en Maps"),
  reviews_dist_5star INT64 OPTIONS(description="Número de reseñas de 5 estrellas"),
  reviews_dist_4star INT64 OPTIONS(description="Número de reseñas de 4 estrellas"),
  reviews_dist_3star INT64 OPTIONS(description="Número de reseñas de 3 estrellas"),
  reviews_dist_2star INT64 OPTIONS(description="Número de reseñas de 2 estrellas"),
  reviews_dist_1star INT64 OPTIONS(description="Número de reseñas de 1 estrella"),
  latitude FLOAT64 OPTIONS(description="Coordenada Latitud"),
  longitude FLOAT64 OPTIONS(description="Coordenada Longitud"),
  location GEOGRAPHY OPTIONS(description="Punto geográfico para visualización cartográfica"),
  price STRING OPTIONS(description="Rango de precios del establecimiento"),
  images_count INT64 OPTIONS(description="Cantidad total de imágenes en la ficha de Google"),
  temporarily_closed BOOL OPTIONS(description="Indica si el sitio está cerrado temporalmente"),
  permanently_closed BOOL OPTIONS(description="Indica si el sitio está cerrado permanentemente"),
  wheelchair_accessible BOOL OPTIONS(description="Indica si el sitio es accesible para sillas de ruedas"),
  child_friendly BOOL OPTIONS(description="Indica si el sitio es adecuado para niños"),
  claim_business BOOL OPTIONS(description="Indica si el negocio ha sido reclamado por su dueño"),
  last_poi_update TIMESTAMP OPTIONS(description="Fecha de la última actualización de los datos generales del POI"),
  last_review_extraction TIMESTAMP OPTIONS(description="Fecha de la última extracción de reseñas para este POI")
);

-- 4. Tabla de Reseñas
CREATE TABLE IF NOT EXISTS `tfg-boletin-turismo-burgos.ds_turismo_reviews.reviews`
(
  review_id STRING OPTIONS(description="ID único de la reseña"),
  poi_id STRING OPTIONS(description="ID del sitio al que pertenece la reseña"),
  reviewer_id STRING OPTIONS(description="ID único del autor de la reseña en Google"),
  reviewer_name STRING OPTIONS(description="Nombre del autor de la reseña"),
  reviewer_gender STRING OPTIONS(description="Género inferido del autor"),
  review_text STRING OPTIONS(description="Texto de la reseña traducido al español"),
  review_text_original STRING OPTIONS(description="Texto original de la reseña"),
  review_language STRING OPTIONS(description="Idioma original detectado"),
  review_rating FLOAT64 OPTIONS(description="Puntuación de la reseña (1-5)"),
  review_date DATE OPTIONS(description="Fecha de publicación de la reseña"),
  sentiment_label STRING OPTIONS(description="Etiqueta de sentimiento (POS, NEG, NEU)"),
  sentiment_score FLOAT64 OPTIONS(description="Puntaje de confianza del análisis de sentimiento"),
  extraction_timestamp TIMESTAMP OPTIONS(description="Fecha y hora de captura del dato")
);

-- 5. Tabla de Control del Scraper
CREATE TABLE IF NOT EXISTS `tfg-boletin-turismo-burgos.ds_turismo_reviews.scraper_control`
(
  municipality_name STRING OPTIONS(description="Nombre del municipio "),
  category STRING OPTIONS(description="Categoría de búsqueda del scraper utilizada para el filtrado"),
  last_update TIMESTAMP OPTIONS(description="Fecha y hora de la última extracción exitosa para este subsite y categoría")
);

-- 6. Tabla de Códigos Postales por Municipio
CREATE TABLE IF NOT EXISTS `tfg-boletin-turismo-burgos.ds_turismo_reviews.municipality_postal_codes`
(
  id_municipality INT64 OPTIONS(description="ID único del municipio"),
  municipality_name STRING OPTIONS(description="Nombre del municipio"),
  postal_code STRING OPTIONS(description="Códigos postalales que puede contener el municipio")
);