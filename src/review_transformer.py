from datetime import datetime
from deep_translator import GoogleTranslator
from langdetect import detect
from pysentimiento import create_analyzer
import gender_guesser.detector as gender

sentiment_analyzer = create_analyzer(task="sentiment", lang="es")
gender_detector = gender.Detector()

def clean_translate_review(rev, p_id):
    """Procesa una sola reseña: limpieza, filtro y traducción."""
    text_raw = rev.get('text') or ""

    review_id = rev.get('reviewId') or "ID_NULO"
    reviewer_name = rev.get('name') or "Anónimo" 
    
    fecha_relativa = rev.get('relativeDate') # Ej: "hace 2 horas"
    fecha_exacta = rev.get('publishedAtDate') # Ej: "2024-04-19T..."

    print(f"\n--- [DEBUG REVISIÓN] ---")
    print(f"Autor: {reviewer_name}")
    print(f"ID: {review_id}")
    print(f"Fecha: {fecha_exacta} ({fecha_relativa})")
    print(f"Texto detectado por Apify: '{text_raw}'")
    print(f"Longitud palabras: {len(text_raw.split())}")


    print(f"Analizando reseña {rev.get('reviewId')}: '")
    if not text_raw or len(text_raw.split()) < 8:
        print(f"DESCARTADA: Solo {len(text_raw.split())} palabras (mínimo 8).")
        return None # Filtro de longitud mínima (8 palabras)

    # Limpieza básica de saltos de línea
    text_clean = text_raw.replace('\n', ' ').replace('\r', ' ').strip()
    
    # Limpiar etiquetas de Google si existen
    text_clean = text_clean.replace("(Traducción de Google)", "").replace("(Original)", "").strip()

    # Detección real de idioma
    try:
        # Detectamos el idioma real del texto, ignorando lo que diga la API
        detected_lang = detect(text_clean)
    except:
        detected_lang = 'es'

    # Traducción si no es español
    text_es = text_clean
    if detected_lang != 'es':
        try:
            print(f"IDIOMA: {detected_lang} detectado. Traduciendo al español...")
            text_es = GoogleTranslator(source='auto', target='es').translate(text_clean)
        except:
            print(f"Error traduciendo reseña {rev.get('reviewId')}")
            text_es = text_clean

    # GÉNERO
    first_name = rev.get('name', '').split()[0]
    gender_raw = gender_detector.get_gender(first_name)
    reviewer_gender = "Masculino" if "male" in gender_raw else "Femenino" if "female" in gender_raw else "Desconocido"
    
    # SENTIMIENTO
    sent = sentiment_analyzer.predict(text_es)
    sentiment_label = sent.output # Positivo (POS), Neutral (NEU), Negativo (NEG)
    sentiment_score = float(sent.probas["POS"] - sent.probas["NEG"]) # Puntuación del sentimiento [-1, 1]
    
    return {
        "review_id": rev.get('reviewId'),
        "poi_id": p_id,
        "reviewer_name": rev.get('name', 'Anónimo'),
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