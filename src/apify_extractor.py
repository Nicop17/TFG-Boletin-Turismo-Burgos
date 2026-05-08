import os
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()
client_apify = ApifyClient(os.getenv("APIFY_TOKEN"))

def fetch_pois_from_apify(search_query, muni_name, cp=None):
    poi_input = {
        "searchStringsArray": [search_query],
        "locationQuery": f"{muni_name}, Burgos, Spain",
        "postalCode": str(cp) if cp else None,
        "language": "es",
        "countryCode": "ES",
    }
    run = client_apify.actor("compass/crawler-google-places").call(run_input=poi_input)
    return list(client_apify.dataset(run["defaultDatasetId"]).iterate_items())

def fetch_reviews_from_apify(p_id):
    rev_input = {
        "startUrls": [{"url": f"https://www.google.com/maps/place/?q=place_id:{p_id}"}],
        "reviewsStartDate": "1 day", # Solo para la carga masiva de datos inicial
        "language": "es",
        "personalData": True,
        "reviewsSort": "newest",
        "reviewsOrigin": "google"
    }
    run = client_apify.actor("compass/google-maps-reviews-scraper").call(run_input=rev_input)
    return list(client_apify.dataset(run["defaultDatasetId"]).iterate_items())