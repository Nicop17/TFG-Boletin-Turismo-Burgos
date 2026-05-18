import json
import os

class ConfigLoader:
    _config = None

    @classmethod
    def get_config(cls):
        if cls._config is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, "..", "..", "config.json")
            
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cls._config = json.load(f)
            except FileNotFoundError:
                raise Exception(f"CRÍTICO: No se encontró el archivo de configuración en {config_path}")
            except json.JSONDecodeError:
                raise Exception("CRÍTICO: El archivo config.json tiene errores de formato.")
        
        return cls._config

settings = ConfigLoader.get_config()