from datetime import datetime
from deep_translator import GoogleTranslator
from langdetect import detect
from pysentimiento import create_analyzer
import gender_guesser.detector as gender
from utils.config_loader import settings
from utils.logger import logger

t_params = settings['transformer_params']
TARGET_LANG = t_params['target_lang']

sentiment_analyzer = create_analyzer(task="sentiment", lang=TARGET_LANG)
gender_detector = gender.Detector()

def clean_translate_review(rev, p_id):
    """Procesa una sola reseña: limpieza, filtro y traducción."""
    text_raw = rev.get('text') or ""
    review_id = rev.get('reviewId') or "ID_NULO"
    reviewer_name = rev.get('name') or t_params['default_user_name']
    
    fecha_relativa = rev.get('relativeDate') # Ej: "hace 2 horas"
    fecha_exacta = rev.get('publishedAtDate') # Ej: "2024-04-19T..."

    word_count = len(text_raw.split())

    logger.debug(f"\n--- [DEBUG REVISIÓN] ---")
    logger.debug(f"Autor: {reviewer_name}")
    logger.debug(f"ID: {review_id}")
    logger.debug(f"Fecha: {fecha_exacta} ({fecha_relativa})")
    logger.debug(f"Texto detectado por Apify: '{text_raw}'")
    logger.debug(f"Longitud palabras: {word_count}")

    logger.info(f"Analizando reseña {review_id}. Fecha: {fecha_relativa}")

    if not text_raw or word_count < t_params['min_review_words']:
        logger.info(f"Reseña {review_id} descartada: Solo {word_count} palabras (mínimo {t_params['min_review_words']}).")
        return None # Filtro de longitud mínima del texto de la reseña para que se guarde

    # Limpieza básica de saltos de línea
    text_clean = text_raw.replace('\n', ' ').replace('\r', ' ').strip()
    
    # Limpiar etiquetas de Google si existen
    text_clean = text_clean.replace("(Traducción de Google)", "").replace("(Original)", "").strip()

    # Detección real de idioma
    try:
        # Detectamos el idioma real del texto, ignorando lo que diga la API
        detected_lang = detect(text_clean)
    except Exception as e:
        logger.error(f"Error detectando idioma en la reseña {review_id}: {e}")
        detected_lang = t_params['default_review_lang'] # Valor por defecto si no se puede detectar

    # Traducción si no es español
    text_es = text_clean
    if detected_lang != TARGET_LANG:
        try:
            logger.info(f"IDIOMA: {detected_lang} detectado en reseña {review_id}. Traduciendo al {TARGET_LANG}")
            text_es = GoogleTranslator(source='auto', target=TARGET_LANG).translate(text_clean)
        except Exception as e:
            logger.error(f"Error traduciendo reseña {review_id} en {detected_lang}: {e}. Usando original")
            text_es = text_clean

    # GÉNERO
    try:
        name_parts = reviewer_name.split()
        first_name = name_parts[0] if name_parts else t_params['default_user_name']
        gender_raw = gender_detector.get_gender(first_name)
        reviewer_gender = "Masculino" if "male" in gender_raw else "Femenino" if "female" in gender_raw else t_params['default_user_gender']
    except Exception as e:
        logger.error(f"Error detectando género de {reviewer_name}: {e}")
        reviewer_gender = t_params['default_user_gender']

    # SENTIMIENTO
    try:
        sent = sentiment_analyzer.predict(text_es)
        sentiment_label = sent.output # Positivo (POS), Neutral (NEU), Negativo (NEG)
        sentiment_score = float(sent.probas["POS"] - sent.probas["NEG"]) # Puntuación del sentimiento [-1, 1]
    except Exception as e:
        logger.error(f"Error en cálculo de sentimiento para reseña {review_id}: {e}")
        sentiment_label = "NEU"
        sentiment_score = 0.0

    return {
        "review_id": rev.get('reviewId'),
        "poi_id": p_id,
        "reviewer_id": rev.get('reviewerId'),
        "reviewer_name": rev.get('name', t_params['default_user_name']),
        "reviewer_gender": reviewer_gender,           
        "review_text": text_es,            # Español
        "review_text_original": text_clean, # Original
        "review_language": detected_lang,
        "review_rating": float(rev.get('stars', 0)),
        "review_date": rev.get('publishedAtDate')[:10] if rev.get('publishedAtDate') else None,
        "sentiment_label": sentiment_label,           
        "sentiment_score": sentiment_score,           
        "extraction_timestamp": datetime.now().isoformat()
    }