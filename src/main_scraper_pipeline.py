from datetime import datetime
import bigquery_loader as loader
import review_transformer as transformer
import apify_extractor as extractor

def get_muni_level(population):
    if not population or population < 400:
        return 1 # Rural
    elif population < 5000:
        return 2 # Semi-urbano
    else:
        return 3 # Urbano
    

def run_scraper():
    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y-%m-%d')
    cp_burgos_capital = ['09001', '09002', '09003', '09004', '09005', '09006', '09007']
    margin_days_poi = 90 # Número de días para considerar un POI como no actualizado y volver a extraerlo
    margin_days_reviews = 30 # Número de días para considerar las reseñas de un POI como no actualizadas y volver a extraerlas
    print(f"Iniciando scraper - Ejecución del {today_str} - POIs no actualizados desde hace {margin_days_poi} días o más serán procesados.")

    # 1. Obtener municipios y categorías desde BigQuery
    # Filtramos municipios que no han sido procesados hoy ni en extracción general ni en extracción de reseñas
    query_muni = f"""
        SELECT id_municipality, name, population, last_poi_update, last_review_extraction 
        FROM `{loader.dataset}.municipalities`
        WHERE last_poi_update IS NULL 
           OR DATE_DIFF(CURRENT_DATE(), DATE(last_poi_update), DAY) >= {margin_days_poi}
           OR last_review_extraction IS NULL
           OR DATE_DIFF(CURRENT_DATE(), DATE(last_review_extraction), DAY) >= {margin_days_reviews}
        ORDER BY id_municipality ASC
    """
    municipalities = list(loader.execute_query(query_muni))

    cat_rows = list(loader.execute_query(f"SELECT * FROM `{loader.dataset}.categories`"))
    taxonomy = {c.maps_category: (c.level_1_category, c.level_2_category, c.level_3_category, c.level_4_category) 
                for c in cat_rows if c.maps_category}

    for muni in municipalities:
        print(f"\n{'-'*30}\n MUNICIPIO: {muni.name}\n{'-'*30}")

        # Si es Burgos, iteramos por CPs. Si no, solo por el nombre del municipio.
        sub_busqueda = cp_burgos_capital if muni.name == "Burgos" else [muni.name]
        
        # FASE A: Descubrimiento de POIs
        # Solo entramos si no se ha actualizado el catálogo de POIs del municipio en los últimos margin_days_poi días
        muni_can_update_poi = muni.last_poi_update is None or (today_dt.date() - muni.last_poi_update.date()).days >= margin_days_poi
        if muni_can_update_poi:
            # Iteramos por cada sub-área (sea código postal o el municipio entero)
            for subsite in sub_busqueda:
                # Consultamos qué categorías ya se han buscado en este municipio en los últimos {margin_days_poi} días
                query_log = f"""
                    SELECT category FROM `{loader.dataset}.scraper_control`
                    WHERE municipality_name = '{muni.name}'
                    AND subsite = '{subsite}'
                    AND DATE_DIFF(CURRENT_DATE(), DATE(last_update), DAY) < {margin_days_poi}
                """
                done_categories = [r.category for r in loader.execute_query(query_log)]
                
                muni_level = get_muni_level(muni.population)
                categories = list(loader.execute_query(f"SELECT * FROM `{loader.dataset}.categories` WHERE search_level <= {muni_level} ORDER BY level_1_category ASC, level_2_category ASC, level_3_category ASC, level_4_category ASC, maps_category ASC"))

                for cat in categories: # Pois por categoría
                    # Comprobamos si esta categoría específica ya se buscó en este municipio
                    if cat.maps_category in done_categories:
                        continue

                    # Si subsite es CP (numérico), formato CP. Si no, formato municipio completo
                    if subsite.isdigit():
                        search_query = f"{cat.maps_category} {subsite}, Burgos, Spain"
                    else:
                        search_query = f"{cat.maps_category} en {subsite}, Burgos, Spain"

                    print(f" Buscando '{cat.maps_category}' en {subsite}...")
                    pois_items = extractor.fetch_pois_from_apify(search_query, muni.name, subsite if subsite.isdigit() else None)
                                   
                    pois_to_load = []
                    for poi in pois_items:
                        # Filtra por código postal de Burgos (09xxx) para evitar POIs de otros municipios con nombres similares o errores de geolocalización
                        cp = poi.get('postalCode', '')
                        if not cp or not cp.startswith('09'): 
                            continue

                        poi_city = poi.get('city', '')
                        poi_address = poi.get('address', '')

                        # Descarta el POI por ser de otro municipio, comprobando que ni en el campo de ciudad ni en el de dirección aparece el nombre del municipio que estamos procesando
                        if muni.name.lower() not in poi_city.lower() and muni.name.lower() not in poi_address.lower():
                            continue

                        google_cat = poi.get('categoryName')
                
                        if google_cat in taxonomy:
                            # Usamos la jerarquía que ya tenemos guardada para esa categoría oficial de Google
                            l1, l2, l3, l4 = taxonomy[google_cat]
                        else:
                            # Categoría nueva que se añade a la rama que estamos buscando ahora
                            new_cat_level = muni_level
                            l1, l2, l3, l4 = (cat.level_1_category, cat.level_2_category, 
                                            cat.level_3_category, cat.level_4_category)
                            
                            # La añadimos a la tabla de categorías para la próxima vez
                            print(f"Nueva categoría detectada: {google_cat}. Asignando a {l4}")
                            loader.execute_query(f"""
                                INSERT INTO `{loader.dataset}.categories` 
                                (level_1_category, level_2_category, level_3_category, level_4_category, maps_category, search_level)
                                VALUES ('{l1}', '{l2}', '{l3}', '{l4}', '{google_cat}', {new_cat_level})
                            """)
                            # Actualizamos el diccionario en memoria para no insertarla dos veces
                            taxonomy[google_cat] = (l1, l2, l3, l4)
                                
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
                            "maps_category": google_cat,
                            "level_1_category": l1,
                            "level_2_category": l2,
                            "level_3_category": l3,
                            "level_4_category": l4,
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
                            "price": str(poi.get('price')) if poi.get('price') is not None else None,
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
                        print(f"No se encontraron nuevos POIs para {cat.maps_category} en {muni.name}.")

                    loader.execute_query(f"""
                        INSERT INTO `{loader.dataset}.scraper_control` (municipality_name, subsite, category, last_update)
                        VALUES ('{muni.name}', '{subsite}', '{cat.maps_category}', CURRENT_TIMESTAMP())
                    """)
                        
            # Marcamos municipio como procesado esta semana
            loader.execute_query(f"UPDATE `{loader.dataset}.municipalities` SET last_poi_update = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")

        else:
            print(f"Fase A (POIs) ya completada para {muni.name} recientemente. Saltando a reseñas.")

      
        # FASE B: EXTRAER RESEÑAS POI A POI
        # Buscamos POIs pendientes de hoy, ordenados siempre igual por ID
        query_pendientes = f"""
            SELECT poi_id, poi_name, poi_id as url_id FROM `{loader.dataset}.pois`
            WHERE poi_municipality = '{muni.name}'
            AND (last_review_extraction IS NULL 
                 OR DATE_DIFF(CURRENT_DATE(), DATE(last_review_extraction), DAY) >= {margin_days_reviews})
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