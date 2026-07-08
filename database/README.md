# Inicialización de la Base de Datos en BigQuery

Esta carpeta contiene las plantillas estructurales y los datos maestros necesarios para montar de cero el almacén de datos del Boletín de Turismo en cualquier proyecto de Google Cloud Platform (BigQuery).

## Contenido de la carpeta

* `schema.sql`: Archivo universal con las sentencias `CREATE TABLE` de las 6 tablas del sistema y los `CREATE VIEW` de las 2 vistas de POIs y reseñas.
* `municipalities.csv`: Listado de los municipios de la provincia de Burgos con sus códigos identificadores y población.
* `categories.csv`: Taxonomía y equivalencias de categorías para las búsquedas del scraper.
* `municipality_postal_codes.csv`: Diccionario de los códigos postales autorizados y vinculados a cada municipio.
* `pois.csv` *(Opcional)*: Estado actual de la tabla pois de la base de datos.
* `reviews.csv` *(Opcional)*: Estado actual de la tabla reviews de la base de datos.

---

## Guía de ejecución

### Paso 1: Crear las tablas (`schema.sql`)
1. Entra en la consola web de [Google BigQuery](https://console.cloud.google.com/bigquery).
2. En el panel izquierdo, despliega tu proyecto, haz clic en los tres puntos verticales al lado de tu proyecto y asegúrate de tener creado tu **dataset** (por ejemplo, `ds_turismo_reviews`).
3. Abre una nueva pestaña de consultas pulsando el botón "+" (Consulta en SQL).
4. Copia el contenido completo del archivo `schema.sql` y pégalo en el editor de consultas.
5. Modifica (si es necesario) el id del proyecto y del dataset de las consultas (por defecto están puestos `tfg-boletin-turismo-burgos` como id del proyecto y `ds_turismo_reviews` como nombre del dataset). El formato es: `id_proyecto.nombre_dataset.tabla`
6. Pulsa el botón **Ejecutar**.

### Paso 2: Importar los datos de las tablas (`.csv`)
Para las tablas de configuración (`municipalities`, `categories` y `municipality_postal_codes`) debemos cargar los datos iniciales para el correcto funcionamiento del scraper:

1. En el panel izquierdo, haz clic sobre el nombre de tu **Dataset** para que se abra su pestaña principal.
2. En la barra de herramientas superior, haz clic en el botón **Crear tabla**.
3. Configura las siguientes opciones en el formulario que se despliega:
   * **Crear tabla desde:** Selecciona `Subir`.
   * **Seleccionar archivo:** Elige el archivo correspondiente de esta carpeta (ej. `municipality_postal_codes.csv`).
   * **Formato de archivo:** `CSV`.
   * **Nombre de la tabla:** Escribe exactamente el nombre de la tabla de destino (ej. `municipality_postal_codes`).
   * **Esquema:** Marcar la casilla de **Detección automática** para las tablas `municipalities` y `categories`. Para la tabla `municipality_postal_codes`, marcar la casilla de **Editar como texto** y pegar exactamente lo siguiente: id_municipality:INTEGER,municipality_name:STRING,postal_code:STRING
   * **Preferencias avanzadas:** Despliega esta sección abajo del todo, busca **Preferencia de escritura** y marca la opción **Agrega a la tabla** y unas filas más abajo donde pone **Filas del encabezado que se omitirán**, escribe `1` para que elimine el encabezado de los csv y agregue los datos.
4. Haz clic en el botón azul **Crear tabla** de abajo del todo.

Repite este mismo proceso de subida seleccionando el dataset para los archivos `categories.csv` y `municipalities.csv` en sus respectivas tablas y la base de datos estará 100% operativa para recibir los datos del scraper.

---

### Paso 3 (Opcional): Cargar datos de POIs y reseñas (Evitar base de datos vacía)
Si se desea contar con un conjunto de datos inicial para realizar pruebas o analizar la base de datos completa sin tener que esperar a la ejecución del scraper, se puede poblar la base de datos con el histórico recopilado de POIs y reseñas.

Para hacerlo, repite el mismo procedimiento de importación del **Paso 2** para los archivos `pois.csv` y `reviews.csv`.