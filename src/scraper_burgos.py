import os
import json
from datetime import datetime
from dotenv import load_dotenv
from apify_client import ApifyClient
from google.cloud import bigquery
from google.oauth2 import service_account

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


def run_scraper():  
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Iniciando scraper - Ejecución del {today}")

    # PASO 1: ACTUALIZAR TODA LA TABLA DE POIS PRIMERO 
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


    # --- PASO 2: EXTRAER RESEÑAS POI A POI (Orden previsible) ---
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
            "maxReviews": 2,
            "language": "es",
            "personalData": True,
            "reviewsSort": "newest"
        }
        rev_run = client_apify.actor("compass/google-maps-reviews-scraper").call(run_input=rev_input)
        reviews_items = list(client_apify.dataset(rev_run["defaultDatasetId"]).iterate_items())

        reviews_to_load = []
        for rev in reviews_items:
            # SI DETECTA UNA RESEÑA QUE YA TENEMOS, SALTA AL SIGUIENTE POI
            if rev.get('reviewId') == last_id_in_db:
                print(f"Coincidencia hallada ({last_id_in_db}). Finalizando este POI.")
                break

            reviews_to_load.append({
                "review_id": rev.get('reviewId'), 
                "poi_id": p_id,
                "reviewer_name": rev.get('name', 'Anónimo'),
                # "reviewer_gender": None, 
                "review_text": rev.get('text'),
                "review_rating": float(rev.get('stars', 0)),
                "review_date": rev.get('publishedAtDate')[:10] if rev.get('publishedAtDate') else None,
                "review_language": rev.get('language', 'es'),
                # "sentiment_label": None, 
                # "sentiment_score": None,
                "extraction_timestamp": datetime.now().isoformat()
            })

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

        
if __name__ == "__main__":
    run_scraper()