from datetime import datetime
from utils.config_loader import settings
from utils.logger import logger
import bigquery_loader as loader
import review_transformer as transformer
import apify_extractor as extractor


s_logic = settings['scraper_logic']
g_tables = settings['google_cloud']['tables']
filters = settings['execution_filters']
params = settings['apify_params']
dataset_path = f"{settings['google_cloud']['project_id']}.{settings['google_cloud']['dataset_id']}"

def get_muni_level(population):
    if not population or population < s_logic['muni_threshold_rural']:
        return 1 # Rural
    elif population < s_logic['muni_threshold_semi_rural']:
        return 2 # Semi-urbano
    else:
        return 3 # Urbano
    

def run_scraper():
    today_dt = datetime.now()
    today_str = today_dt.strftime('%Y-%m-%d')
    margin_days_poi = s_logic['margin_days_update_pois'] # Número de días para considerar un POI como no actualizado y volver a extraerlo
    margin_days_reviews = s_logic['margin_days_update_reviews'] # Número de días para considerar las reseñas de un POI como no actualizadas y volver a extraerlas
    logger.info(f"Iniciando scraper - Ejecución del {today_str}")
    logger.info(f"POIs no actualizados desde hace {margin_days_poi} días o más serán procesados.")


    # Obtener municipios y categorías desde BigQuery
    if filters['target_municipality'] == "": # Si no se especifica un municipio, se procesan todos
    # Filtramos solo municipios que o no se hayan extraído o su última extracción de POIs o de reseñas supere el margen límite establecido en configuración
        query_muni = f"""
            SELECT id_municipality, name, population, last_poi_update, last_review_extraction 
            FROM `{dataset_path}.{g_tables['municipalities']}`
            WHERE last_poi_update IS NULL 
            OR DATE_DIFF(CURRENT_DATE(), DATE(last_poi_update), DAY) >= {margin_days_poi}
            OR last_review_extraction IS NULL
            OR DATE_DIFF(CURRENT_DATE(), DATE(last_review_extraction), DAY) >= {margin_days_reviews}
            ORDER BY {filters['order_municipalities_by']}
        """
    
    else: # Si se especifica un municipio, se filtra solo por ese municipio
        query_muni = f"""
            SELECT id_municipality, name, population, last_poi_update, last_review_extraction 
            FROM `{dataset_path}.{g_tables['municipalities']}`
            WHERE name = '{filters['target_municipality']}'
        """

    try:
        municipalities = list(loader.execute_query(query_muni))
        
        if not municipalities:
            logger.warning("No se encontraron municipios pendientes de procesar. Finalizando extracción de reseñas.")
            return

        logger.info("Cargando taxonomía de categorías desde BigQuery")
        cat_rows = list(loader.execute_query(f"SELECT maps_category, id_category FROM `{dataset_path}.{g_tables['categories']}`"))
        
        if not cat_rows: # Si no hay categorías, el mapeo de IDs fallará más tarde
            raise Exception("La tabla de categorías está vacía o no es accesible.")
            
        taxonomy = {c.maps_category: c.id_category for c in cat_rows if c.maps_category}
        logger.info(f"Taxonomía cargada: {len(taxonomy)} categorías detectadas.")

    except Exception as e: # Si falla aquí no se puede continuar porque no tenemos ni municipios para procesar ni taxonomía para categorizar los POIs
        logger.exception(f"Error crítico en la configuración inicial:")
        return 

    for muni in municipalities:
        logger.info(f"\n{'='*30}\n MUNICIPIO: {muni.name}\n{'='*30}")

        # Obtenemos los códigos postales del municipio para filtrar los POIs por código postal
        cp_muni = loader.get_postal_codes(muni.id_municipality)
        logger.debug(f"Códigos postales permitidos para POIs de {muni.name}: {cp_muni}")

        # FASE A: Descubrimiento de POIs
        # Solo entramos si no se ha actualizado el catálogo de POIs del municipio en los últimos margin_days_poi días
        muni_can_update_poi = (filters['target_poi'] == "") and (muni.last_poi_update is None or (today_dt.date() - muni.last_poi_update.date()).days >= margin_days_poi)
        if muni_can_update_poi:
            logger.info("\n"
                "\t------------------------------------------------------------\n"
                "\t|               [FASE A: EXTRACCIÓN DE POIs]               |\n"
                "\t------------------------------------------------------------")
            # Consultamos qué categorías ya se han buscado en este municipio en los últimos {margin_days_poi} días
            query_cat = f"""
                    SELECT category FROM `{dataset_path}.{g_tables['scraper_control']}`
                    WHERE municipality_name = '{muni.name}'
                    AND DATE_DIFF(CURRENT_DATE(), DATE(last_update), DAY) < {margin_days_poi}
                """
            done_categories = [r.category for r in loader.execute_query(query_cat)]
            muni_level = get_muni_level(muni.population)

            if filters['target_category'] == "": # Si no se especifica una categoría, se procesan todas las categorías del municipio según su nivel de búsqueda
                categories = list(loader.execute_query(
                    f"""
                    SELECT * FROM `{dataset_path}.{g_tables['categories']}` 
                    WHERE search_level <= {muni_level} 
                    ORDER BY {filters['order_categories_by']}
                    """
                ))

            else: # Si se especifica una categoría, se filtra solo por esa categoría y municipio
                categories = list(loader.execute_query(
                    f"""
                    SELECT * FROM `{dataset_path}.{g_tables['categories']}` 
                    WHERE search_level <= {muni_level} 
                    AND maps_category = '{filters['target_category']}'
                    ORDER BY {filters['order_categories_by']}
                    """
                ))

            for cat in categories: # Pois por categoría
                # Comprobamos si esta categoría específica ya se buscó en este municipio
                if cat.maps_category in done_categories:
                    logger.debug(f"Categoría '{cat.maps_category}' ya buscada en {muni.name} recientemente. Saltando categoría.")
                    continue

                try:
                    
                    search_query = f"{cat.maps_category} en {muni.name}, {s_logic['location_province']}"

                    logger.info(f"\n\t{'-'*30}\n\t CATEGORÍA: {cat.maps_category} \n\t{'-'*30}")
                    logger.debug(f"Consulta de búsqueda para Apify: '{search_query}'")
                    pois_items = extractor.fetch_pois_from_apify(search_query, muni.name, muni_level)
                                    
                    pois_to_load = []
                    for poi in pois_items:
                        title = (poi.get('title') or "").strip()
                        title_clean = title.lower().strip()
                        muni_clean = muni.name.lower().strip()
                        cp = (poi.get('postalCode') or "").strip()
                        address = (poi.get('address') or "").strip()

                        # Si el POI se llama igual que el municipio, se descarta directamente (en cada búsqueda trae como POI el nombre del municipio)
                        if title_clean == muni_clean or title_clean == f"{muni_clean}, Burgos":
                            logger.debug(f"Marcador territorial genérico detectado ('{title}'). Evitando elemento fantasma del nombre del propio municipio.")
                            continue
                        
                        # Filtro específico para POIs que no tienen cp pero en el cp de su dirección se ve que sí forman parte del municipio
                        if not cp and address:
                            for cp_autorizado in cp_muni:
                                if cp_autorizado in address:
                                    cp = cp_autorizado
                                    logger.info(f"CP [{cp}] rescatado del texto de la dirección para: '{title}'")
                                    break

                        # Filtra por los códigos postales del municipio para evitar POIs de otros municipios con nombres similares o errores de geolocalización
                        if cp_muni:
                            if cp not in cp_muni:
                                logger.warning(f"Descartado '{poi.get('title')}' porque el código postal [{cp}] no pertenece a {muni.name}.")
                                continue
                        else: # Por si un municipio no tiene códigos postales en base de datos, aplicamos un filtro genérico por prefijo del código postal de la provincia
                            if not cp or not cp.startswith(s_logic['postal_code_prefix']): 
                                continue

                        google_cat = poi.get('categoryName') or cat.maps_category # Si Google no devuelve categoría, usamos la que tenemos en la tabla de categorías para esta búsqueda
                
                        if google_cat in taxonomy:
                            # Usamos la jerarquía que ya tenemos guardada para esa categoría oficial de Google
                            current_cat_id = taxonomy[google_cat]
                        else:
                            try:
                                # Categoría nueva que se añade a la rama que estamos buscando ahora
                                new_cat_level = muni_level
                                res_max_id = list(loader.execute_query(f"SELECT MAX(id_category) as max_id FROM `{dataset_path}.{g_tables['categories']}`"))
                                current_cat_id = (res_max_id[0].max_id or 0) + 1

                                # La añadimos a la tabla de categorías para la próxima vez
                                logger.info(f"Nueva categoría detectada: {google_cat}. Asignando ID: {current_cat_id}")
                                
                                loader.execute_query(f"""
                                    INSERT INTO `{dataset_path}.{g_tables['categories']}` 
                                    (id_category, level_1_category, level_2_category, level_3_category, level_4_category, maps_category, search_level)
                                    VALUES ({current_cat_id}, '{cat.level_1_category}', '{cat.level_2_category}', 
                                        '{cat.level_3_category}', '{cat.level_4_category}', '{google_cat}', {new_cat_level})
                                """)
                                # Actualizamos el diccionario en memoria para no insertarla dos veces
                                taxonomy[google_cat] = current_cat_id

                            except Exception as e_cat:
                                logger.error(f"Error insertando nueva categoría {google_cat}: {e_cat}")
                                continue # No podemos cargar el POI sin categoría válida

                        additional_info = poi.get('additionalInfo', {})
                        
                        wheelchair = None

                        accessibility_list = additional_info.get('Accessibility', []) or additional_info.get('Accesibilidad', [])
                        for item in accessibility_list:
                            for key, value in item.items():
                                key_lower = key.lower()
                                # Si la etiqueta contiene palabras clave de silla de ruedas/accesibilidad
                                if 'wheelchair' in key_lower or 'silla' in key_lower or 'accesible' in key_lower:
                                    wheelchair = bool(value)
                                    break
                            if wheelchair is not None:
                                break
                        
                        if wheelchair is None:
                            wheelchair = False  # Si no indica nada, se asume que no es accesible para sillas de ruedas
                        
                        dist = poi.get('reviewsDistribution', {})
                        
                        pois_to_load.append({
                            "poi_id": poi.get('placeId'),
                            "poi_name": poi.get('title'),
                            "id_municipality": muni.id_municipality,
                            "poi_municipality": muni.name,
                            "address": poi.get('address'),         
                            "postal_code": cp,
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
                            "temporarily_closed": bool(poi.get('temporarilyClosed')),
                            "permanently_closed": bool(poi.get('permanentlyClosed')),
                            "wheelchair_accessible": wheelchair,
                            "claim_business": poi.get('claimThisBusiness'),
                            "last_poi_update": datetime.now().isoformat()
                        })
                        
                    if pois_to_load:
                        stg_poi = f"{dataset_path}.stg_pois_{int(datetime.now().timestamp())}"
                        loader.client_bq.load_table_from_json(pois_to_load, stg_poi).result()
                        poi_updates = ["poi_total_rating", "reviews_count", "reviews_dist_5star", "reviews_dist_4star", 
                                    "reviews_dist_3star", "reviews_dist_2star", "reviews_dist_1star", "images_count", 
                                    "temporarily_closed", "permanently_closed", "wheelchair_accessible", "claim_business","last_poi_update"]
                        loader.run_merge_query(f"{dataset_path}.{g_tables['pois']}", stg_poi, "poi_id", poi_updates, list(pois_to_load[0].keys()))
                        logger.info(f"{len(pois_to_load)} POIs actualizados para la categoría '{cat.maps_category}' en {muni.name}")
                    else:
                        logger.info(f"No se encontraron nuevos POIs para {cat.maps_category} en {muni.name}.")

                    loader.execute_query(f"""
                        INSERT INTO `{dataset_path}.{g_tables['scraper_control']}` (municipality_name, category, last_update)
                        VALUES ('{muni.name}', '{cat.maps_category}', CURRENT_TIMESTAMP())
                    """)

                except Exception as e:# Si falla Apify o el Merge de BigQuery, lo capturamos para no romper el bucle y seguir con las siguientes categorías
                    logger.error(f"Error procesando categoría '{cat.maps_category}' en {muni.name}: {e}")
                    continue # No ejecutamos el INSERT en scraper_control, así que queda pendiente para el futuro
            
            # Si no se ha pedido una única categoría oun único POi marcamos municipio como procesado hoy en extracción de POIs
            if filters['target_category'] == "":
                loader.execute_query(f"UPDATE `{dataset_path}.{g_tables['municipalities']}` SET last_poi_update = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")

            logger.info(f"Fase A (POIs) completada con éxito para {muni.name}.")

        elif (filters['target_poi'] != ""):
            logger.debug(f"Fase A (POIs) no requerida en el flujo actual para {muni.name}. Saltando a reseñas para el poi {filters['target_poi']}.")
        else:
            logger.debug(f"Fase A (POIs) ya completada para {muni.name} recientemente. Saltando a reseñas.")

      
        # # FASE B: EXTRAER RESEÑAS POI A POI
        if filters['target_poi'] == "": # Si no se especifica un POI, se procesan todos los POIs pendientes de extracción de reseñas
            # Buscamos POIs pendientes de hoy
            query_pois = f"""
                SELECT poi_id, poi_name, poi_id as url_id, last_review_extraction FROM `{dataset_path}.{g_tables['pois']}`
                WHERE poi_municipality = '{muni.name}'
                AND (last_review_extraction IS NULL 
                    OR DATE_DIFF(CURRENT_DATE(), DATE(last_review_extraction), DAY) >= {margin_days_reviews})
                ORDER BY {filters['order_pois_by']}
            """
        
        else: # Si se especifica un POI, se filtra solo por ese POI
            query_pois = f"""
                SELECT poi_id, poi_name, poi_id as url_id, last_review_extraction FROM `{dataset_path}.{g_tables['pois']}`
                WHERE poi_municipality = '{muni.name}'
                AND poi_name = '{filters['target_poi']}'
            """
        logger.info("\n"
            "\t------------------------------------------------------------\n"
            "\t|              [FASE B: EXTRACCIÓN DE RESEÑAS]             |\n"
            "\t------------------------------------------------------------")

        pois = list(loader.execute_query(query_pois))

        if not pois:
            logger.info(f"No se encontraron POIs pendientes de procesar. Finalizando extracción de reseñas del municipio {muni.name}.")
            continue
        
        for poi in pois:
            try:
                poi_can_extract_reviews = poi.last_review_extraction is None or (today_dt.date() - poi.last_review_extraction.date()).days >= margin_days_reviews
                if poi_can_extract_reviews:
                    logger.info(f"\n\t{'-'*30}\n\t POI: {poi.poi_name} \n\t{'-'*30}")
                    last_id_in_db = loader.get_last_stored_review_id(poi.poi_id)
                    reviews_items = extractor.fetch_reviews_from_apify(poi.poi_id)

                    reviews_to_load = []
                    for r in reviews_items:
                        res = transformer.clean_translate_review(r, poi.poi_id)
                        if res:
                            # Si la reseña del POI ya la tenemos guardada, paramos este POI porque las reseñas vienen ordenadas de más nuevas a más antiguas, por lo tanto las siguientes también las tendremos guardadas
                            if params['reviews_sort'] == 'newest':
                                if res['review_id'] == last_id_in_db:
                                    logger.info(f"Coincidencia de ID hallada en la base de datos para {poi.poi_name}. Parando extracción de este POI.")
                                    break
                            reviews_to_load.append(res)

                    if reviews_to_load:
                        stg_rev = f"{dataset_path}.stg_reviews_{int(datetime.now().timestamp())}"
                        loader.client_bq.load_table_from_json(reviews_to_load, stg_rev).result()
                        loader.run_merge_query(f"{dataset_path}.{g_tables['reviews']}", stg_rev, "review_id", ["extraction_timestamp"], list(reviews_to_load[0].keys()))
                        loader.update_poi_tori(poi.poi_id) # Actualizamos el TORI de ese POI tras cargar sus reseñas
                        logger.info(f"{len(reviews_to_load)} Nuevas reseñas añadidas.")
                    else:
                        logger.info(f"No se encontraron reseñas nuevas para el POI: {poi.poi_name}.")
                    # Marcamos el POI como procesado hoy
                    loader.execute_query(f"UPDATE `{dataset_path}.{g_tables['pois']}` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE poi_id = '{poi.poi_id}'")
                else:
                    logger.debug(f"Fase B (Reviews) ya completada para {poi.poi_name} recientemente. Saltando al siguiente POI.")

            except Exception as e:
                logger.exception(f"Error procesando reseñas para el POI {poi.poi_name}:")
                continue # Saltamos al siguiente POI
        
        # Marcamos municipio como procesado hoy en extracción de reseñas si no se ha pedido un POI concreto
        if filters['target_poi'] == "":
            loader.execute_query(f"UPDATE `{dataset_path}.{g_tables['municipalities']}` SET last_review_extraction = CURRENT_TIMESTAMP() WHERE name = '{muni.name}'")
            logger.info(f"Municipio {muni.name} completado.")
        elif filters['target_municipality'] == "":
            logger.info(f"Fase B (Reviews) completada para el poi {filters['target_poi']} en {muni.name}. Saltando al siguiente municipio.")
        else:
            logger.info(f"Fase B (Reviews) completada para el poi {filters['target_poi']} en {muni.name}.")
    
    logger.info("\n" + "="*60 + "\n" +
            "      EJECUCIÓN DEL SCRAPER COMPLETADA - BOLETÍN DE TURISMO\n" +
            "="*60)

if __name__ == "__main__":
    run_scraper()