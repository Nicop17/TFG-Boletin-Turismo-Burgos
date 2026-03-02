import json, requests, csv, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import Value
from dotenv import load_dotenv

load_dotenv()

# Configura tu API Key de Google Places
API_KEY = os.getenv('GOOGLE_API_KEY')

base_dir = os.path.join(os.path.dirname(__file__), "..", "data", "scripts_data")
os.makedirs(base_dir, exist_ok=True)

json_file = os.path.join(base_dir, "burgos_pois.json")
csv_file = os.path.join(base_dir, "pois_details.csv")

# Cargar coordenadas del archivo burgos_pois.json
def load_coordinates(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    coordinates = []

    # Iteramos sobre los elementos de OSM
    for element in data['elements']:
        # Caso 1: Nodo con coordenadas lat y lon directamente
        if element['type'] == 'node' and 'lat' in element and 'lon' in element:
            coordinates.append({'lat': element['lat'], 'lon': element['lon']})

        # Caso 2: Way o relation con coordenadas en "center"
        elif 'center' in element:
            coords = element['center']
            coordinates.append({'lat': coords['lat'], 'lon': coords['lon']})

    return coordinates

# Obtener detalles del lugar con Nearby Search
def get_place_details(lat, lon):
    url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lon}&rankby=distance&fields=place_id&key={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json().get('results', [])
        place_ids = [result['place_id'] for result in results]
        return place_ids
    return []

# Guardar detalles en el archivo CSV
def append_to_csv(data, csv_file):
    with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(data)

# Procesar cada POI y almacenar en el archivo CSV
def process_poi(poi, existing_place_ids, csv_file, counter):
    lat = poi['lat']
    lon = poi['lon']
    place_ids = get_place_details(lat, lon)

    for place_id in place_ids:
        if place_id and place_id not in existing_place_ids:
            with counter.get_lock():
                print(f"Procesando punto #{counter.value} con coordenadas: ({lat}, {lon})")
                counter.value += 1
            existing_place_ids.add(place_id)
            append_to_csv([place_id, lat, lon], csv_file)
    return counter

# Procesar POIs y guardar en CSV con concurrencia
def process_pois_and_save(csv_file, json_file):
    existing_place_ids = set()
    try:
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                existing_place_ids.add(row[0])
    except FileNotFoundError:
        pass

    pois = load_coordinates(json_file)

    counter = Value('i', 1)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_poi, poi, existing_place_ids, csv_file, counter) for poi in pois]
        for future in as_completed(futures):
            future.result()

    print("Procesamiento completo.")

# Rutas de archivos
csv_file = 'pois_details.csv'
json_file = 'burgos_pois.json'

# Crear el archivo CSV con cabecera si no existe
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Place ID', 'Latitude', 'Longitude'])

process_pois_and_save(csv_file, json_file)