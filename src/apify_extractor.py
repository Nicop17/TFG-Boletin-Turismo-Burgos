import time
import os
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()
client_apify = ApifyClient(os.getenv("APIFY_TOKEN"))

def fetch_pois_from_apify(search_query, muni_name, muni_level):
    if muni_level == 3:
        poi_input = {
            "searchStringsArray": [search_query],
            "locationQuery": f"{muni_name}, Burgos, Spain", # Para mejorar la precisión de la búsqueda, se añade el municipio al query solo en el caso de municipios de nivel 3 (ciudades)
            "language": "es",
            "countryCode": "es", # Solo se pone aquí porque por sí solo hace una búsqueda exhaustiva por todo el país (como con locationQuery)
        }
    else:
        poi_input = {
            "searchStringsArray": [search_query],
            "language": "es",
        }
    
    attempt = 0
    MAX_RETRIES = 2
    while attempt <= MAX_RETRIES:
        try:
            # Llamada al actor
            run = client_apify.actor("compass/crawler-google-places").call(run_input=poi_input)
            return list(client_apify.dataset(run["defaultDatasetId"]).iterate_items())
        
        except Exception as e:
            attempt += 1
            print(f"Intento {attempt} fallido al extraer POIs ({search_query}): {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(5) # Esperamos 5 segundos antes de reintentar
            else:
                raise Exception(f"Fallo definitivo tras {MAX_RETRIES + 1} intentos en Apify para el municipio {muni_name} con query '{search_query}'")
            
def fetch_reviews_from_apify(p_id):
    rev_input = {
        "startUrls": [{"url": f"https://www.google.com/maps/place/?q=place_id:{p_id}"}],
        "reviewsStartDate": "1 month",
        "language": "es",
        "personalData": True,
        "reviewsSort": "newest",
        "reviewsOrigin": "google",
    }

    attempt = 0
    MAX_RETRIES = 2
    while attempt <= MAX_RETRIES:
        try:
            run = client_apify.actor("compass/google-maps-reviews-scraper").call(run_input=rev_input)
            return list(client_apify.dataset(run["defaultDatasetId"]).iterate_items())
        
        except Exception as e:
            attempt += 1
            print(f"Intento {attempt} fallido al extraer reseñas para POI {p_id}: {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(5)
            else:
                raise Exception(f"Fallo definitivo tras {MAX_RETRIES + 1} intentos en Apify para el POI {p_id}")