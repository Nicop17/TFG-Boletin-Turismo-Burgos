import os
import json
import sys
from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core import exceptions
from dotenv import load_dotenv
from utils.config_loader import settings
from utils.logger import logger

# Configuración de acceso a Google BigQuery
base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.join(base_dir, "..")

load_dotenv(os.path.join(root_dir, ".env"))
g_config = settings['google_cloud']

try:
    with open(os.path.join(root_dir, g_config['credentials_file'])) as f:
        info = json.loads(f.read())
        
    credentials = service_account.Credentials.from_service_account_info(info)
    client_bq = bigquery.Client(credentials=credentials, project=g_config['project_id'])
    dataset_path = f"{g_config['project_id']}.{g_config['dataset_id']}"
    logger.info("Conexión con BigQuery establecida correctamente.")
    
except FileNotFoundError:
    logger.critical(f"No se encontró el archivo de credenciales: {g_config['credentials_file']}.")
    sys.exit(1)
except Exception as e:
    logger.critical(f"No se pudo conectar con BigQuery. Revisa credenciales: {e}")
    sys.exit(1)


def run_merge_query(table_id, staging_table_id, pk_field, update_fields, all_fields):
    """Ejecuta un MERGE en BigQuery para automatizar el Upsert."""
    # Campos que siempre deben ser tratados como STRING 
    string_fields = ["review_id", "poi_id", "reviewer_id", "price", "postal_code"]

    # Generar la parte del UPDATE
    update_clauses = []
    for f in update_fields:
        if f == "location":
            update_clauses.append(f"T.{f} = ST_GEOGFROMTEXT(S.{f})")
        elif f in string_fields:
            update_clauses.append(f"T.{f} = CAST(S.{f} AS STRING)")
        else:
            update_clauses.append(f"T.{f} = S.{f}")
    update_query = ", ".join(update_clauses)
    
    # Generar la parte del INSERT (Columnas y Valores)
    columns = ", ".join(all_fields)
    
    value_clauses = []
    for f in all_fields:
        if f == "location":
            value_clauses.append(f"ST_GEOGFROMTEXT(S.{f})")
        elif f in string_fields:
            value_clauses.append(f"CAST(S.{f} AS STRING)")
        else:
            value_clauses.append(f"S.{f}")
    values = ", ".join(value_clauses)
    
    sql = f"""
    MERGE `{table_id}` T
    USING `{staging_table_id}` S
    ON T.{pk_field} = S.{pk_field}
    WHEN MATCHED THEN
      UPDATE SET {update_query}
    WHEN NOT MATCHED THEN
      INSERT ({columns}) VALUES ({values})
    """
    try:
        client_bq.query(sql).result()
        logger.debug("MERGE ejecutado con éxito.")
    except exceptions.BadRequest as e:
        logger.error(f"Error de formato en el MERGE (400). Revisar tipos: {e}")
        raise e
    except Exception as e:
        logger.exception(f"Error inesperado en la ejecución del MERGE para {table_id}:")
        raise e
    finally:
        # Aseguramos que la tabla de staging se elimine incluso si el MERGE falla, para evitar acumulación de tablas temporales.
        try:
            client_bq.delete_table(staging_table_id)
        except Exception as e:
            logger.warning(f"No se pudo borrar la tabla temporal {staging_table_id}: {e}")


def get_last_stored_review_id(poi_id):
    """Obtiene el ID de la reseña más reciente de un POI en BigQuery para evitar duplicados."""
    table_reviews = g_config['tables']['reviews']
    query = f"""
        SELECT review_id FROM `{dataset_path}.{table_reviews}`
        WHERE poi_id = '{poi_id}'
        ORDER BY review_date DESC, extraction_timestamp DESC
        LIMIT 1
    """
    try:
        results = list(client_bq.query(query).result())
        return results[0].review_id if results else None
    except exceptions.NotFound:
        logger.debug(f"La tabla {table_reviews} no existe o está vacía.")
        return None # Caso normal: tabla vacía
    except Exception as e:
        logger.error(f"No se pudo obtener el último review_id para {poi_id}: {e}")
        return None

def update_poi_tori(p_id):
    """Calcula la media de sentimientos y actualiza el TORI en la tabla pois."""   
    # 1. Busca la nota media de Google (poi_total_rating)
    # 2. Calcula la media de todos los sentiment_score de ese poi
    # 3. Calcula el TORI normalizando ambos valores a una escala de 0 a 5

    t_logic = settings['tori_logic']
    # Escalamiento: Rating (1-5 -> amplitud 4), Sentimiento (-1 a 1 -> amplitud 2)
    krating = t_logic['max_score_rating'] / 4 
    ksentiment = t_logic['max_score_sentiment'] / 2

    query = f"""
    UPDATE `{dataset_path}.{g_config['tables']['pois']}`
    SET tori_score = ({krating} * (poi_total_rating - 1)) + ({ksentiment} * (
        SELECT COALESCE(AVG(sentiment_score), 0) + 1 
        FROM `{dataset_path}.{g_config['tables']['reviews']}` 
        WHERE poi_id = '{p_id}'
    ))
    WHERE poi_id = '{p_id}'
    """
    
    try:
        client_bq.query(query).result()
        logger.info(f"TORI actualizado para el POI: {p_id}")
    except Exception as e:
        logger.error(f"Error actualizando TORI de {p_id}: {e}")


def execute_query(query):
    """Ejecuta una consulta SQL en BigQuery y devuelve los resultados."""
    try:
        return client_bq.query(query).result()
    except exceptions.NotFound:
        logger.error("Error: Tabla o dataset no encontrado en BigQuery.")
        return []
    except Exception as e:
        logger.error(f"Error al ejecutar consulta SQL en BigQuery: {e}")
        return [] # Devolvemos lista vacía para que los bucles for no fallen al iterar sobre resultados inexistentes
