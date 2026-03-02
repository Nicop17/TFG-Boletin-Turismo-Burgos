import requests, json, os

# Consulta en Overpass QL
# Se eliminan elementos que no son de interés ya que aparecen como nodos en OSM pero no como POIs en Google Maps 
# (bancos, papeleras, máquinas expendedoras, reciclaje, espacios de aparcamiento, puestos de lotería)
query = """
[out:json][timeout:900];
area["name"="Burgos"]["admin_level"="6"]->.searchArea;
(
  node(area.searchArea)["amenity"][amenity!~"bench"][amenity!~"waste_basket"][amenity!~"vending_machine"][amenity!~"recycling"][amenity!~"waste_disposal"][amenity!~"parking_space"];
  way(area.searchArea)["amenity"][amenity!~"bench"][amenity!~"waste_basket"][amenity!~"vending_machine"][amenity!~"recycling"][amenity!~"waste_disposal"][amenity!~"parking_space"];
  relation(area.searchArea)["amenity"][amenity!~"bench"][amenity!~"waste_basket"][amenity!~"vending_machine"][amenity!~"recycling"][amenity!~"waste_disposal"][amenity!~"parking_space"];
  
  node(area.searchArea)["place"="town_square"];
  way(area.searchArea)["place"="town_square"];
  relation(area.searchArea)["place"="town_square"];

  node(area.searchArea)["leisure"="park"];
  way(area.searchArea)["leisure"="park"];
  relation(area.searchArea)["leisure"="park"];
  
  node(area.searchArea)["shop"][shop!~"lottery"];
  way(area.searchArea)["shop"][shop!~"lottery"];
  relation(area.searchArea)["shop"][shop!~"lottery"];
  
  node(area.searchArea)["tourism"];
  way(area.searchArea)["tourism"];
  relation(area.searchArea)["tourism"];
  
  node(area.searchArea)["office"];
  way(area.searchArea)["office"];
  relation(area.searchArea)["office"];
  
  node(area.searchArea)["historic"];
  way(area.searchArea)["historic"];
  relation(area.searchArea)["historic"];
);
out center;
"""

import requests
import json
import os

# Consulta en Overpass QL
query = """
[out:json][timeout:900];
area["name"="Burgos"]["admin_level"="6"]->.searchArea;
(
  node(area.searchArea)["amenity"][amenity!~"bench"][amenity!~"waste_basket"][amenity!~"vending_machine"][amenity!~"recycling"][amenity!~"waste_disposal"][amenity!~"parking_space"];
  way(area.searchArea)["amenity"][amenity!~"bench"][amenity!~"waste_basket"][amenity!~"vending_machine"][amenity!~"recycling"][amenity!~"waste_disposal"][amenity!~"parking_space"];
  relation(area.searchArea)["amenity"][amenity!~"bench"][amenity!~"waste_basket"][amenity!~"vending_machine"][amenity!~"recycling"][amenity!~"waste_disposal"][amenity!~"parking_space"];
  
  node(area.searchArea)["place"="town_square"];
  way(area.searchArea)["place"="town_square"];
  relation(area.searchArea)["place"="town_square"];

  node(area.searchArea)["leisure"="park"];
  way(area.searchArea)["leisure"="park"];
  relation(area.searchArea)["leisure"="park"];
  
  node(area.searchArea)["shop"][shop!~"lottery"];
  way(area.searchArea)["shop"][shop!~"lottery"];
  relation(area.searchArea)["shop"][shop!~"lottery"];
  
  node(area.searchArea)["tourism"];
  way(area.searchArea)["tourism"];
  relation(area.searchArea)["tourism"];
  
  node(area.searchArea)["office"];
  way(area.searchArea)["office"];
  relation(area.searchArea)["office"];
  
  node(area.searchArea)["historic"];
  way(area.searchArea)["historic"];
  relation(area.searchArea)["historic"];
);
out center;
"""

overpassURL = "http://overpass-api.de/api/interpreter"
response = requests.get(overpassURL, params={'data': query})
json_data = response.json()

output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scripts_data")

os.makedirs(output_dir, exist_ok=True)  
output_path = os.path.join(output_dir, "burgos_pois.json")

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(json_data, f, ensure_ascii=False, indent=4)