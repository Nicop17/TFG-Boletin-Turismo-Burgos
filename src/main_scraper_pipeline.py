from datetime import datetime
import bigquery_loader as loader
import review_transformer as transformer
import apify_extractor as extractor

def run_scraper():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Iniciando scraper - Ejecución del {today}")

    # 1. Obtener municipios y categorías desde BigQuery
    # Filtramos municipios que no han sido procesados hoy ni en extracción general ni en extracción de reseñas
    query_muni = f"""
        SELECT id_municipality, name, last_poi_update, last_review_extraction 
        FROM `{loader.dataset}.municipalities`
        WHERE (DATE(last_poi_update) != '{today}' OR last_poi_update IS NULL)
           OR (DATE(last_review_extraction) != '{today}' OR last_review_extraction IS NULL)
        ORDER BY id_municipality ASC
    """
    municipalities = list(loader.execute_query(query_muni))

    for muni in municipalities:
        muni_pois_date = str(muni.last_poi_update)[:10] if muni.last_poi_update else None
        print(f"\nPROCESANDO MUNICIPIO: {muni.name}")
        
        # FASE A: Descubrimiento de POIs
        # Solo entramos si no se ha actualizado el catálogo de POIs del municipio hoy
        if muni_pois_date != today:
            categories = list(loader.execute_query(f"SELECT * FROM `{loader.dataset}.categories` WHERE level_4_category = 'Parks and gardens'"))
            for cat in categories: # Pois por categoría
                cat_poi_date = str(cat.last_poi_update)[:10] if cat.last_poi_update else None
                
                if cat_poi_date != today:
                    print(f" Buscando {cat.level_4_category} en {muni.name}...")
                    pois_items = extractor.fetch_pois_from_apify(f"{cat.level_4_category} en {muni.name}, Burgos, Spain")
                    
                    pois_to_load = []
                    for poi in pois_items:
                        # Filtra por código postal de Burgos (09xxx)
                        cp = poi.get('postalCode', '')
                        if not cp or not cp.startswith('09'): 
                            continue
                        
                        additional_info = poi.get('additionalInfo', {})
                        accesibility_list = additional_info.get('Accessibility', [])
                        wheelchair = any(item.get('Wheelchair accessible entrance') for item in accesibility_list)
                        children_list = additional_info.get('Children', [])
                        children_friendly = any(item.get('Good for kids') for item in children_list)

                        dist = poi.get('reviewsDistribution', {})
                        pois_to_load.append({
                            "poi_id": poi.get('placeId'),
                            "poi_name": poi.get('title'),
                            "poi_municipality": muni.name,
                            "maps_category": poi.get('categoryName'),
                            "level_1_category": cat.level_1_category,
                            "level_2_category": cat.level_2_category,
                            "level_3_category": cat.level_3_category,
                            "level_4_category": cat.level_4_category,
                            "poi_total_rating": float(poi.get('totalScore') or 0) if poi.get('totalScore') else 0.0,
                            "reviews_count": int(poi.get('reviewsCount') or 0),
                            "reviews_dist_5star": int(dist.get('fiveStar') or 0),
                            "reviews_dist_4star": int(dist.get('fourStar') or 0),
                            "reviews_dist_3star": int(dist.get('threeStar') or 0),
                            "reviews_dist_2star": int(dist.get('twoStar') or 0),
                            "reviews_dist_1star": int(dist.get('oneStar') or 0),
                            "latitude": poi.get('location', {}).get('lat'),
                            "longitude": poi.get('location', {}).get('lng'),
                            "location": f"POINT({poi.get('location', {}).get('lng')} {poi.get('location', {}).get('lat')})",
                            "price": poi.get('price'),
                            "images_count": int(poi.get('imagesCount') or 0),
                            "google_official_tags": ", ".join([t.get('title') for t in poi.get('reviewsTags', [])]),
                            "related_pois": ", ".join([p.get('title') for p in poi.get('peopleAlsoSearch', [])]),
                            "temporarily_closed": bool(poi.get('temporarilyClosed')),
                            "permanently_closed": bool(poi.get('permanentlyClosed')),
                            "wheelchair_accessible": wheelchair,
                            "child_friendly": children_friendly,
                            "claim_business": poi.get('claimThisBusiness'),
                            "last_poi_update": datetime.now().isoformat()
                        })
                    
                    if pois_to_load:
                        stg_poi = f"{loader.dataset}.stg_pois_{int(datetime.now().timestamp())}"
                        loader.client_bq.load_table_from_json(pois_to_load, stg_poi).result()
                        poi_updates = ["poi_total_rating", "reviews_count", "reviews_dist_5star", "reviews_dist_4star", 
                                    "reviews_dist_3star", "reviews_dist_2star", "reviews_dist_1star", "images_count", 
                                    "temporarily_closed", "permanently_closed", "google_official_tags", "related_pois", 
                                    "wheelchair_accessible", "child_friendly", "claim_business","last_poi_update"]
                        loader.run_merge_query(f"{loader.dataset}.pois", stg_poi, "poi_id", poi_updates, list(pois_to_load[0].keys()))
                        print(f"{len(pois_to_load)} POIs actualizados en {muni.name}")
                    else:
                        print(f"No se encontraron nuevos POIs para {cat.level_4_category} en {muni.name}.")

                else:
                    print(f"POIs ya actualizados hoy para {cat.level_4_category}. Saltando a la siguiente categoría.")

            # Marcamos municipio como procesado hoy
            loader.execute_query(f"UPDATE `{loader.dataset}.municipalities` SET last_poi_update = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")

        else:
            print(f"Fase A (POIs) ya completada hoy para {muni.name}. Saltando a reseñas.")

      
        # FASE B: EXTRAER RESEÑAS POI A POI
        # Buscamos POIs pendientes de hoy, ordenados siempre igual por ID
        query_pendientes = f"""
            SELECT poi_id, poi_name, poi_id as url_id FROM `{loader.dataset}.pois`
            WHERE poi_municipality = '{muni.name}'
            AND (DATE(last_review_extraction) != '{today}' OR last_review_extraction IS NULL)
            ORDER BY poi_id ASC
        """
        pois_pendientes = list(loader.execute_query(query_pendientes))

        for poi in pois_pendientes:
            print(f" Sacando reseñas para: {poi.poi_name}...")
            last_id_in_db = loader.get_last_stored_review_id(poi.poi_id)
            reviews_items = extractor.fetch_reviews_from_apify(poi.poi_id)

            reviews_to_load = []
            for r in reviews_items:
                res = transformer.clean_translate_review(r, poi.poi_id)
                if res:
                    # Si la reseña del POI ya la tenemos guardada, paramos este POI porque las reseñas vienen ordenadas de más nuevas a más antiguas, por lo tanto las siguientes también las tendremos guardadas
                    if res['review_id'] == last_id_in_db:
                        print(f"Coincidencia hallada en base de datos. Parando POI.")
                        break
                    reviews_to_load.append(res)

            if reviews_to_load:
                stg_rev = f"{loader.dataset}.stg_reviews_{int(datetime.now().timestamp())}"
                loader.client_bq.load_table_from_json(reviews_to_load, stg_rev).result()
                loader.run_merge_query(f"{loader.dataset}.reviews", stg_rev, "review_id", ["extraction_timestamp"], list(reviews_to_load[0].keys()))
                loader.update_poi_tori(poi.poi_id) # Actualizamos el TORI de ese POI tras cargar sus reseñas
                print(f"{len(reviews_to_load)} Nuevas reseñas añadidas.")
            # Marcamos el POI como procesado hoy
            loader.execute_query(f"UPDATE `{loader.dataset}.pois` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE poi_id = '{poi.poi_id}'")
            
        # Marcamos municipio como procesado hoy en extracción de reseñas
        loader.execute_query(f"UPDATE `{loader.dataset}.municipalities` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")
        print(f"Municipio {muni.name} completado.")

if __name__ == "__main__":
    run_scraper()