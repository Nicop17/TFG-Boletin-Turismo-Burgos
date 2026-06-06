# Historial de trazas de ejecución (Logs)

Este directorio está destinado exclusivamente al almacenamiento automatizado y la persistencia de los registros de depuración (*logs*) generados por el pipeline ETL en cada ejecución.

El aislamiento de estos registros en ficheros independientes previene que un único archivo de trazas crezca indefinidamente en disco, optimizando el rendimiento de lectura del sistema. Además, simplifica la auditoría del software al permitir al desarrollador o usuario localizar e ir directamente a la ejecución exacta que se desee revisar. De este modo, se optimiza la revisión del histórico de operaciones del scraper y se elimina la necesidad de navegar manualmente entre millones de líneas de texto antiguas para diagnosticar un corte de red, comprobar un fallo puntual de la API o analizar el comportamiento del sistema en un momento específico del tiempo.

---

## Nomenclatura de los Archivos

Para garantizar una indexación temporal previsible y ordenada de forma cronológica por los exploradores de archivos del sistema operativo (o editores como VS Code), se aplica estrictamente el estándar **ISO 8601** adaptado a nombres de ficheros: 
`ejecucion_AAAA-MM-DD_HH-MM-SS.log`
* **`AAAA`**: Año de ejecución con 4 dígitos (ej. `2026`).
* **`MM`**: Mes del año con 2 dígitos (de `01` a `12`).
* **`DD`**: Día del mes con 2 dígitos (de `01` a `31`).
* **`HH-MM-SS`**: Marca de tiempo exacta (Hora, Minuto y Segundo) en la que se instanció el pipeline.