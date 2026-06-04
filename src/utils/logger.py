import logging
import sys
import os
from datetime import datetime
from utils.config_loader import settings

base_dir = os.path.dirname(os.path.abspath(__file__)) 
root_dir = os.path.abspath(os.path.join(base_dir, "..", ".."))
logs_dir = os.path.join(root_dir, "logs")

# Extraemos los parámetros del JSON
log_params = settings.get('logging_params', {
    "log_level": "INFO",
    "log_to_file": True,
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
        # Capturamos la fecha y hora exacta del sistema al arrancar el pipeline para que el archivo sea reconocible
        # Formato: Año-Mes-Día_Hora-Minuto-Segundo 
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"ejecucion_{timestamp}.log"

        # Guardamos el log en la carpeta logs
        complete_path_log = os.path.join(logs_dir, log_filename)

        # Usamos encoding utf-8 porque las reseñas tienen tildes y emojis que harían explotar el logger por defecto en Windows
        file_handler = logging.FileHandler(complete_path_log, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

# Mensaje de inicio del pipeline
current_log_name = log_filename if log_params.get('log_to_file') else "Desactivado"

logger.info("\n" + "="*60 + "\n" +
            "      INICIO DE EJECUCIÓN DEL PIPELINE - BOLETÍN DE TURISMO\n" +
            "="*60)
logger.info(f"Nivel de detalle de logs: [{log_params.get('log_level', 'INFO').upper()}]")
logger.info(f"Historial físico de logs: logs/{current_log_name}")
logger.info("-" * 60)