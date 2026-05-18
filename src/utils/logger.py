import logging
import sys
from utils.config_loader import settings

# Extraemos los parámetros del JSON
log_params = settings.get('logging_params', {
    "log_level": "INFO",
    "log_to_file": True,
    "log_file_name": "scraper_execution.log",
    "log_format": "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"
})

# Mapeamos el string del JSON al objeto de configuración real de Python
numeric_level = getattr(logging, log_params['log_level'].upper(), logging.INFO)

# Creamos un logger único para el proyecto
logger = logging.getLogger("scraper_burgos_logger")
logger.setLevel(numeric_level)

# Evitamos duplicar handlers al importar el módulo en cada archivo
if not logger.handlers:
    formatter = logging.Formatter(log_params['log_format'])

    # Handler 1: Consola (Muestra los mensajes en la pantalla de la consola en tiempo real en GitHub Actions)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler 2: Archivo físico (Para guardar históricos y auditoría de errores)
    if log_params.get('log_to_file'):
        # Usamos encoding utf-8 porque las reseñas tienen tildes y emojis que harían explotar el logger por defecto en Windows
        file_handler = logging.FileHandler(log_params['log_file_name'], encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)