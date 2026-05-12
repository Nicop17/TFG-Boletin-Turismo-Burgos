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
    margin_days_poi = 120 # Número de días para considerar un POI como no actualizado y volver a extraerlo
    margin_days_reviews = 60 # Número de días para considerar las reseñas de un POI como no actualizadas y volver a extraerlas
    print(f"Iniciando scraper - Ejecución del {today_str} - POIs no actualizados desde hace {margin_days_poi} días o más serán procesados.")

    # Obtener municipios y categorías desde BigQuery
    # Filtramos municipios que no han sido procesados hoy ni en extracción general ni en extracción de reseñas
    # query_muni = f"""
    #     SELECT id_municipality, name, population, last_poi_update, last_review_extraction 
    #     FROM `{loader.dataset}.municipalities`
    #     WHERE last_poi_update IS NULL 
    #        OR DATE_DIFF(CURRENT_DATE(), DATE(last_poi_update), DAY) >= {margin_days_poi}
    #        OR last_review_extraction IS NULL
    #        OR DATE_DIFF(CURRENT_DATE(), DATE(last_review_extraction), DAY) >= {margin_days_reviews}
    #     ORDER BY population ASC
    # """
    query_muni = f"""
        SELECT id_municipality, name, population, last_poi_update, last_review_extraction 
        FROM `{loader.dataset}.municipalities`
        WHERE name = 'Burgos'
    """

    try:
        municipalities = list(loader.execute_query(query_muni))
        
        if not municipalities:
            print("No se encontraron municipios pendientes de procesar. Finalizando.")
            return

        print("Cargando taxonomía de categorías desde BigQuery")
        cat_rows = list(loader.execute_query(f"SELECT maps_category, id_category FROM `{loader.dataset}.categories`"))
        
        if not cat_rows: # Si no hay categorías, el mapeo de IDs fallará más tarde
            raise Exception("La tabla de categorías está vacía o no es accesible.")
            
        taxonomy = {c.maps_category: c.id_category for c in cat_rows if c.maps_category}
        print(f"✅ Taxonomía cargada: {len(taxonomy)} categorías detectadas.")

    except Exception as e: # Si falla aquí no se puede continuar porque no tenemos ni municipios para procesar ni taxonomía para categorizar los POIs
        print(f"Error crítico en la configuración inicial: {e}")
        return 

    for muni in municipalities:
        print(f"\n{'-'*30}\n MUNICIPIO: {muni.name}\n{'-'*30}")
       
        # FASE A: Descubrimiento de POIs
        # Solo entramos si no se ha actualizado el catálogo de POIs del municipio en los últimos margin_days_poi días
        muni_can_update_poi = muni.last_poi_update is None or (today_dt.date() - muni.last_poi_update.date()).days >= margin_days_poi
        if muni_can_update_poi:
            # Consultamos qué categorías ya se han buscado en este municipio en los últimos {margin_days_poi} días
            query_log = f"""
                SELECT category FROM `{loader.dataset}.scraper_control`
                WHERE municipality_name = '{muni.name}'
                AND DATE_DIFF(CURRENT_DATE(), DATE(last_update), DAY) < {margin_days_poi}
            """
            done_categories = [r.category for r in loader.execute_query(query_log)]
            
            muni_level = get_muni_level(muni.population)
            categories = list(loader.execute_query(
                f"""
                SELECT * FROM `{loader.dataset}.categories` 
                WHERE search_level <= {muni_level} 
                AND maps_category = 'Piscina'
                ORDER BY level_1_category ASC, level_2_category ASC, level_3_category ASC, level_4_category ASC, maps_category ASC
                """
            ))
            for cat in categories: # Pois por categoría
                # Comprobamos si esta categoría específica ya se buscó en este municipio
                if cat.maps_category in done_categories:
                    continue

                try:
                    search_query = f"{cat.maps_category} en {muni.name}, Burgos, Spain"

                    print(f" Buscando '{cat.maps_category}' en {muni.name}...")
                    pois_items = extractor.fetch_pois_from_apify(search_query, muni.name, muni_level)
                                    
                    pois_to_load = []
                    for poi in pois_items:
                        # Filtra por código postal de Burgos (09xxx) para evitar POIs de otros municipios con nombres similares o errores de geolocalización
                        cp = poi.get('postalCode') or ""
                        if not cp or not cp.startswith('09'): 
                            continue

                        poi_city = poi.get('city') or ""
                        poi_address = poi.get('address') or ""

                        # # Descarta el POI por ser de otro municipio, comprobando que ni en el campo de ciudad ni en el de dirección aparece el nombre del municipio que estamos procesando
                        # if muni.name.lower() not in poi_city.lower() and muni.name.lower() not in poi_address.lower():
                        #     continue

                        google_cat = poi.get('categoryName') or cat.maps_category # Si Google no devuelve categoría, usamos la que tenemos en la tabla de categorías para esta búsqueda
                
                        if google_cat in taxonomy:
                            # Usamos la jerarquía que ya tenemos guardada para esa categoría oficial de Google
                            current_cat_id = taxonomy[google_cat]
                        else:
                            try:
                                # Categoría nueva que se añade a la rama que estamos buscando ahora
                                new_cat_level = muni_level
                                res_max_id = list(loader.execute_query(f"SELECT MAX(id_category) as max_id FROM `{loader.dataset}.categories`"))
                                current_cat_id = (res_max_id[0].max_id or 0) + 1

                                # La añadimos a la tabla de categorías para la próxima vez
                                print(f"Nueva categoría detectada: {google_cat}. Asignando ID: {current_cat_id}")
                                
                                loader.execute_query(f"""
                                    INSERT INTO `{loader.dataset}.categories` 
                                    (id_category, level_1_category, level_2_category, level_3_category, level_4_category, maps_category, search_level)
                                    VALUES ({current_cat_id}, '{cat.level_1_category}', '{cat.level_2_category}', 
                                        '{cat.level_3_category}', '{cat.level_4_category}', '{google_cat}', {new_cat_level})
                                """)
                                # Actualizamos el diccionario en memoria para no insertarla dos veces
                                taxonomy[google_cat] = current_cat_id

                            except Exception as e_cat:
                                print(f"Error insertando nueva categoría {google_cat}: {e_cat}")
                                continue # No podemos cargar el POI sin categoría válida

                        additional_info = poi.get('additionalInfo', {})
                        accesibility_list = additional_info.get('Accessibility', [])
                        wheelchair = any(item.get('Wheelchair accessible entrance') for item in accesibility_list)
                        children_list = additional_info.get('Children', [])
                        children_friendly = any(item.get('Good for kids') for item in children_list)
                        dist = poi.get('reviewsDistribution', {})
                        
                        pois_to_load.append({
                            "poi_id": poi.get('placeId'),
                            "poi_name": poi.get('title'),
                            "id_municipality": muni.id_municipality,
                            "poi_municipality": muni.name,
                            "address": poi.get('address'),         
                            "postal_code": poi.get('postalCode'),
                            "id_category": taxonomy.get(google_cat),
                            "maps_category": google_cat,
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
                        INSERT INTO `{loader.dataset}.scraper_control` (municipality_name, category, last_update)
                        VALUES ('{muni.name}', '{cat.maps_category}', CURRENT_TIMESTAMP())
                    """)

                except Exception as e:# Si falla Apify o el Merge de BigQuery, lo capturamos para no romper el bucle y seguir con las siguientes categorías
                    print(f"Error procesando categoría '{cat.maps_category}' en {muni.name}: {e}")
                    continue # No ejecutamos el INSERT en scraper_control, así que queda pendiente para el futuro
            
            # Marcamos municipio como procesado hoy en extracción de POIs
            loader.execute_query(f"UPDATE `{loader.dataset}.municipalities` SET last_poi_update = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")

        else:
            print(f"Fase A (POIs) ya completada para {muni.name} recientemente. Saltando a reseñas.")

      
        # FASE B: EXTRAER RESEÑAS POI A POI
        # Buscamos POIs pendientes de hoy, ordenados siempre igual por ID
        query_pendientes = f"""
            SELECT poi_id, poi_name, poi_id as url_id FROM `{loader.dataset}.pois`
            WHERE poi_municipality = '{muni.name}'
            AND poi_name = 'Goiko'
            AND (last_review_extraction IS NULL 
                 OR DATE_DIFF(CURRENT_DATE(), DATE(last_review_extraction), DAY) >= {margin_days_reviews})
            ORDER BY poi_id ASC
        """
        pois_pendientes = list(loader.execute_query(query_pendientes))

        for poi in pois_pendientes:
            try:
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
                else:
                    print(f"No se encontraron reseñas nuevas para este POI.")
                # Marcamos el POI como procesado hoy
                loader.execute_query(f"UPDATE `{loader.dataset}.pois` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE poi_id = '{poi.poi_id}'")
                
            except Exception as e:
                print(f"Error procesando reseñas para el POI {poi.poi_name}: {e}")
                continue # Saltamos al siguiente POI
        
        # Marcamos municipio como procesado hoy en extracción de reseñas
        loader.execute_query(f"UPDATE `{loader.dataset}.municipalities` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")
        print(f"Municipio {muni.name} completado.")

if __name__ == "__main__":
    run_scraper()