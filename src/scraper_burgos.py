import os
import json
from datetime import datetime
from dotenv import load_dotenv
from apify_client import ApifyClient
from google.cloud import bigquery
from google.oauth2 import service_account

# 1. Configuración de acceso a Google BigQuery y Apify
base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.join(base_dir, "..")

load_dotenv(os.path.join(root_dir, ".env"))

with open(os.path.join(root_dir, "key.json")) as f:
    info = json.loads(f.read())

client_bq = bigquery.Client(credentials=service_account.Credentials.from_service_account_info(info), project=info['project_id'])
client_apify = ApifyClient(os.getenv("APIFY_TOKEN"))


def run_scraper():
    # 2. Configuración del "Escáner" de área
    
    # PASO 1: Obtener 2 POIs
    print("Buscando 2 POIs en Burgos...")
    poi_input = {
        "searchStringsArray": ["Catedral de Burgos", "Monasterio de las Huelgas"],
        "maxPlacesPerQuery": 1
    }
    poi_run = client_apify.actor("compass/crawler-google-places").call(run_input=poi_input)
    pois = list(client_apify.dataset(poi_run["defaultDatasetId"]).iterate_items())

    rows_to_insert = []

    # Por cada POI, sacar 2 reseñas
    for poi in pois:
        p_id = poi.get('placeId')
        p_name = poi.get('title')
        print(f"  🔍 Sacando reseñas para: {p_name}...")

        rev_input = {
            "startUrls": [{"url": poi.get('url')}],
            "maxReviews": 2,
            "language": "es",
            "personalData": True
        }
        rev_run = client_apify.actor("compass/google-maps-reviews-scraper").call(run_input=rev_input)
        reviews = list(client_apify.dataset(rev_run["defaultDatasetId"]).iterate_items())

        for rev in reviews:
            # Transformación de datos para la tabla
            row = {
                "poi_id": p_id,
                "poi_name": p_name,
                "poi_category": poi.get('categoryName'),
                "poi_municipality": poi.get('city', 'Burgos'),
                "poi_total_rating": float(poi.get('totalScore', 0)),
                "review_text": rev.get('text'),
                "review_rating": float(rev.get('stars', 0)),
                "review_date": rev.get('publishedAtDate')[:10] if rev.get('publishedAtDate') else None,
                "review_language": rev.get('language', 'es'),
                "reviewer_name": rev.get('name', 'Anónimo'),
                "latitude": poi.get('location', {}).get('lat'),
                "longitude": poi.get('location', {}).get('lng'),
                "location": f"POINT({poi.get('location', {}).get('lng')} {poi.get('location', {}).get('lat')})",
                "extraction_timestamp": datetime.now().isoformat()
            }
            rows_to_insert.append(row)

    # Carga en BigQuery
    if rows_to_insert:
        table_id = "tfg-boletin-turismo-burgos.ds_turismo_reviews.poi_reviews"
        errors = client_bq.insert_rows_json(table_id, rows_to_insert)
        if not errors:
            print(f"{len(rows_to_insert)} filas insertadas en BigQuery.")
        else:
            print(f"Errores BQ: {errors}")

if __name__ == "__main__":
    run_scraper()