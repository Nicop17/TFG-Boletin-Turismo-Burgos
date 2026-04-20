import os
import json
from datetime import datetime
from dotenv import load_dotenv
from apify_client import ApifyClient
from google.cloud import bigquery
from google.oauth2 import service_account
from deep_translator import GoogleTranslator
from langdetect import detect
from pysentimiento import create_analyzer
import gender_guesser.detector as gender

# Configuración de acceso a Google BigQuery y Apify
base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.join(base_dir, "..")

load_dotenv(os.path.join(root_dir, ".env"))

with open(os.path.join(root_dir, "key.json")) as f:
    info = json.loads(f.read())

client_bq = bigquery.Client(credentials=service_account.Credentials.from_service_account_info(info), project=info['project_id'])
client_apify = ApifyClient(os.getenv("APIFY_TOKEN"))
dataset = "tfg-boletin-turismo-burgos.ds_turismo_reviews"


def run_merge_query(table_id, staging_table_id, pk_field, update_fields, all_fields):
    """Ejecuta un MERGE en BigQuery para automatizar el Upsert."""
    # Generar la parte del UPDATE
    update_clauses = []
    for f in update_fields:
        if f == "location":
            update_clauses.append(f"T.{f} = ST_GEOGFROMTEXT(S.{f})")
        else:
            update_clauses.append(f"T.{f} = S.{f}")
    update_query = ", ".join(update_clauses)
    
    # Generar la parte del INSERT (Columnas y Valores)
    columns = ", ".join(all_fields)
    
    value_clauses = []
    for f in all_fields:
        if f == "location":
            value_clauses.append(f"ST_GEOGFROMTEXT(S.{f})")
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
    client_bq.query(sql).result()
    client_bq.delete_table(staging_table_id)


def get_last_stored_review_id(poi_id):
    """Obtiene el ID de la reseña más reciente de un POI en BigQuery para evitar duplicados."""
    query = f"""
        SELECT review_id FROM `{dataset}.reviews`
        WHERE poi_id = '{poi_id}'
        ORDER BY review_date DESC, extraction_timestamp DESC
        LIMIT 1
    """
    results = list(client_bq.query(query).result())
    return results[0].review_id if results else None


sentiment_analyzer = create_analyzer(task="sentiment", lang="es")
gender_detector = gender.Detector()

def clean_translate_review(rev, p_id):
    """Procesa una sola reseña: limpieza, filtro y traducción."""
    text_raw = rev.get('text') or ""

    review_id = rev.get('reviewId') or "ID_NULO"
    reviewer_name = rev.get('name') or "Anónimo" 
    
    fecha_relativa = rev.get('relativeDate') # Ej: "hace 2 horas"
    fecha_exacta = rev.get('publishedAtDate') # Ej: "2024-04-19T..."

    print(f"\n--- [DEBUG REVISIÓN] ---")
    print(f"Autor: {reviewer_name}")
    print(f"ID: {review_id}")
    print(f"Fecha: {fecha_exacta} ({fecha_relativa})")
    print(f"Texto detectado por Apify: '{text_raw}'")
    print(f"Longitud palabras: {len(text_raw.split())}")


    print(f"Analizando reseña {rev.get('reviewId')}: '")
    if not text_raw or len(text_raw.split()) < 8:
        print(f"DESCARTADA: Solo {len(text_raw.split())} palabras (mínimo 8).")
        return None # Filtro de longitud mínima (8 palabras)

    # Limpieza básica de saltos de línea
    text_clean = text_raw.replace('\n', ' ').replace('\r', ' ').strip()
    
    # Limpiar etiquetas de Google si existen
    text_clean = text_clean.replace("(Traducción de Google)", "").replace("(Original)", "").strip()

    # Detección real de idioma
    try:
        # Detectamos el idioma real del texto, ignorando lo que diga la API
        detected_lang = detect(text_clean)
    except:
        detected_lang = 'es'

    # Traducción si no es español
    text_es = text_clean
    if detected_lang != 'es':
        try:
            print(f"IDIOMA: {detected_lang} detectado. Traduciendo al español...")
            text_es = GoogleTranslator(source='auto', target='es').translate(text_clean)
        except:
            print(f"Error traduciendo reseña {rev.get('reviewId')}")
            text_es = text_clean

    # GÉNERO
    first_name = rev.get('name', '').split()[0]
    gender_raw = gender_detector.get_gender(first_name)
    reviewer_gender = "Masculino" if "male" in gender_raw else "Femenino" if "female" in gender_raw else "Desconocido"
    
    # SENTIMIENTO
    sent = sentiment_analyzer.predict(text_es)
    sentiment_label = sent.output # Positivo (POS), Neutral (NEU), Negativo (NEG)
    sentiment_score = float(sent.probas["POS"] - sent.probas["NEG"]) # Puntuación del sentimiento [-1, 1]
    
    return {
        "review_id": rev.get('reviewId'),
        "poi_id": p_id,
        "reviewer_name": rev.get('name', 'Anónimo'),
        "reviewer_gender": reviewer_gender,           
        "review_text": text_es,            # Español
        "review_text_original": text_clean, # Original
        "review_language": detected_lang,
        "review_rating": float(rev.get('stars', 0)),
        "review_date": rev.get('publishedAtDate')[:10] if rev.get('publishedAtDate') else None,
        "sentiment_label": sentiment_label,           
        "sentiment_score": sentiment_score,           
        "extraction_timestamp": datetime.now().isoformat()
    }


def update_poi_tori(p_id):
    """Calcula la media de sentimientos y actualiza el TORI en la tabla pois."""   
    # 1. Busca la nota media de Google (poi_total_rating)
    # 2. Calcula la media de todos los sentiment_score de ese poi
    # 3. Calcula el TORI: TS + 1.25 * Media_Sentimientos
    query = f"""
    UPDATE `{dataset}.pois`
    SET tori_score = poi_total_rating + (1.25 * (
        SELECT COALESCE(AVG(sentiment_score), 0) 
        FROM `{dataset}.reviews` 
        WHERE poi_id = '{p_id}'
    ))
    WHERE poi_id = '{p_id}'
    """
    
    try:
        query_job = client_bq.query(query)
        query_job.result()
        print(f"TORI actualizado para el POI: {p_id}")
    except Exception as e:
        print(f"Error actualizando TORI: {e}")



def run_scraper():  
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Iniciando scraper - Ejecución del {today}")

    # ACTUALIZAR TODA LA TABLA DE POIS PRIMERO 
    # Comprobar si los POIs ya se actualizaron hoy
    check_pois_sql = f"SELECT count(*) as total FROM `{dataset}.pois` WHERE DATE(extraction_timestamp) = '{today}'"
    pois_already_updated = list(client_bq.query(check_pois_sql).result())[0].total > 0

    if not pois_already_updated:
        print("Actualizando tabla de POIs...")
        # Obtener 2 POIs
        poi_input = {
            "searchStringsArray": ["Catedral de Burgos", "Monasterio de las Huelgas"],
            "maxPlacesPerQuery": 1
        }
        poi_run = client_apify.actor("compass/crawler-google-places").call(run_input=poi_input)
        pois_items = list(client_apify.dataset(poi_run["defaultDatasetId"]).iterate_items())

        pois_to_load = []

    # Por cada POI, sacar 2 reseñas
        for poi in pois_items:
            dist = poi.get('reviewsDistribution', {})         

            pois_to_load.append({
                "poi_id": poi.get('placeId'),
                "poi_name": poi.get('title'),
                "poi_category": poi.get('categoryName'),
                "poi_municipality": poi.get('city', 'Burgos'),
                "poi_total_rating": float(poi.get('totalScore', 0)) if poi.get('totalScore') else 0.0,
                "reviews_count": int(poi.get('reviewsCount', 0)),
                "reviews_dist_5star": int(dist.get('fiveStar', 0)),
                "reviews_dist_4star": int(dist.get('fourStar', 0)),
                "reviews_dist_3star": int(dist.get('threeStar', 0)),
                "reviews_dist_2star": int(dist.get('twoStar', 0)),
                "reviews_dist_1star": int(dist.get('oneStar', 0)),
                "latitude": poi.get('location', {}).get('lat'),
                "longitude": poi.get('location', {}).get('lng'),
                "location": f"POINT({poi.get('location', {}).get('lng')} {poi.get('location', {}).get('lat')})",
                "wheelchair_accessible": bool(poi.get('isWheelchairAccessible')),
                "child_friendly": bool(poi.get('canTakeChildren')),
                "claim_business": bool(poi.get('isClaimed')),
                "extraction_timestamp": datetime.now().isoformat()
            })
        
        if pois_to_load:
            stg_poi = f"{dataset}.stg_pois_{int(datetime.now().timestamp())}"
            client_bq.load_table_from_json(pois_to_load, stg_poi).result()
            poi_fields = list(pois_to_load[0].keys())
            poi_updates = ["poi_total_rating", "reviews_count", "reviews_dist_5star", "reviews_dist_4star", 
                           "reviews_dist_3star", "reviews_dist_2star", "reviews_dist_1star", "extraction_timestamp"]
            run_merge_query(f"{dataset}.pois", stg_poi, "poi_id", poi_updates, poi_fields)
            print("Tabla de POIs actualizada.")
    else:
        print("POIs ya actualizados hoy. Saltando al siguiente paso.")


    # EXTRAER RESEÑAS POI A POI
    # Buscamos POIs pendientes de hoy, ordenados siempre igual por ID
    query_pendientes = f"""
        SELECT poi_id, poi_name, poi_id as url_id FROM `{dataset}.pois`
        WHERE DATE(last_review_extraction) != '{today}' OR last_review_extraction IS NULL
        ORDER BY poi_id ASC
    """
    pois_pendientes = list(client_bq.query(query_pendientes).result())

    for poi in pois_pendientes:
        p_id = poi.poi_id
        print(f" Sacando reseñas para: {poi.poi_name}...")

        last_id_in_db = get_last_stored_review_id(p_id)

        rev_input = {
            "startUrls": [{"url": f"https://www.google.com/maps/place/?q=place_id:{p_id}"}],
            "maxReviews": 5,
            # "reviewsStartDate": "1 day", # Solo para la carga masiva de datos inicial
            "language": "es",
            "personalData": True,
            "reviewsSort": "newest",
            "reviewsOrigin": "google" # Para evitar mezclar reseñas de otras fuentes
        }
        rev_run = client_apify.actor("compass/google-maps-reviews-scraper").call(run_input=rev_input)
        reviews_items = list(client_apify.dataset(rev_run["defaultDatasetId"]).iterate_items())

        reviews_to_load = []

        for r in reviews_items:
            res = clean_translate_review(r, p_id)
            if res:
                if res['review_id'] == last_id_in_db:
                    print(f"Coincidencia hallada. Parando POI.")
                    break
                reviews_to_load.append(res)

        # Carga en BigQuery
        # PROCESAR RESEÑAS (Insertar solo si no existe el review_id)
        if reviews_to_load:
            stg_rev = f"{dataset}.stg_reviews_{int(datetime.now().timestamp())}"
            client_bq.load_table_from_json(reviews_to_load, stg_rev).result()
            rev_fields = list(reviews_to_load[0].keys())
            # En reseñas no actualizamos nada (Matched = nada), solo insertamos nuevas
            run_merge_query(f"{dataset}.reviews", stg_rev, "review_id", ["extraction_timestamp"], rev_fields)
            print(f"{len(reviews_to_load)} Nuevas reseñas añadidas sin duplicados.")

        client_bq.query(f"UPDATE `{dataset}.pois` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE poi_id = '{p_id}'").result()
        
        update_poi_tori(p_id) # Actualizamos el TORI de ese POI tras cargar sus reseñas
        
if __name__ == "__main__":
    run_scraper()