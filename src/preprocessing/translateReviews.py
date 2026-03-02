import pandas as pd
import argparse
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, as_completed
from langdetect import detect, DetectorFactory
import os

# Asegurar resultados consistentes de langdetect
DetectorFactory.seed = 0

# Mapa de idiomas personalizados
LANG_MAP = {
    'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'it': 'it',
    'pt': 'pt', 'nl': 'nl', 'ru': 'ru', 'zh': 'zh-CN', 'ja': 'ja',
    'pl': 'pl', 'ca': 'ca', 'gl': 'gl', 'eu': 'eu', 'iw': 'iw',
    'ew': 'iw', 'pt-PT': 'pt', 'zh-Hant': 'zh-TW',
    'he': 'iw',  # hebreo
}

def detectar_idioma(origen):
    origen = str(origen).lower().split("-")[0]
    return LANG_MAP.get(origen, origen)

def detectar_idioma_texto(texto):
    try:
        if texto and len(texto) >= 20:
            return detect(texto)
        else:
            return 'unknown'
    except:
        return 'unknown'

def traducir_texto(texto, origen):
    try:
        lang_code = detectar_idioma(origen)
        if lang_code and lang_code != 'es':
            result = GoogleTranslator(source=lang_code, target='es').translate(texto)
            return result if result is not None else texto
        else:
            return texto
    except Exception as e:
        print(f"Error traduciendo ({origen}): {e}")
        return texto if texto else ""

def traducir_reviews_multihilo(df, max_workers=10):

    def tarea(idx, texto, origen):
        traducido = traducir_texto(texto, origen)
        if origen.lower() != 'es':
            print(f"Traducido ({origen}) → ES: {texto[:40]} → {traducido[:40]}")
        return idx, traducido

    resultados = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = [executor.submit(tarea, idx, row['text'], row['originalLanguage']) for idx, row in df.iterrows()]
        for future in as_completed(futuros):
            idx, traducido = future.result()
            resultados[idx] = traducido

    for idx, texto_traducido in resultados.items():
        texto_original = df.at[idx, 'text']
        df.at[idx, 'text'] = texto_traducido
        if texto_traducido.strip() == texto_original.strip():
            df.at[idx, 'originalLanguage'] = 'es'

    return df

def traducir_reviews(input_csv, max_reviews=5000, workers=10):
    input_path = os.path.join('outputs', input_csv)
    print("Cargando archivo...")
    df = pd.read_csv(input_path)

    columnas_necesarias = {'text', 'categoryName', 'originalLanguage'}
    if not columnas_necesarias.issubset(df.columns):
        raise ValueError(f"El archivo debe contener las columnas: {', '.join(columnas_necesarias)}")

    df = df.dropna(subset=['text', 'categoryName'])
    df['text'] = df['text'].astype(str).str.strip()
    df = df[df['text'] != ""]
    df = df.drop_duplicates(subset=['categoryName', 'text'])

    df['originalLanguage'] = df['originalLanguage'].fillna('').astype(str).str.strip()
    df.loc[df['originalLanguage'] == '', 'originalLanguage'] = df['text'].apply(detectar_idioma_texto)
    df['originalLanguage'] = df['originalLanguage'].apply(lambda x: detectar_idioma(x) if x != 'unknown' else 'unknown')

    print(df['originalLanguage'].value_counts())

    df['text_original'] = df['text']

    no_es_df = df[df['originalLanguage'].str.lower() != 'es']
    print(f"Total textos a traducir: {len(no_es_df)}")

    if not no_es_df.empty:
        traducidos = traducir_reviews_multihilo(no_es_df, max_workers=workers)
        df.update(traducidos)

    print("Filtrando por longitud y categoría...")
    df['text_length'] = df['text'].apply(len)
    dfs_filtrados = []
    for categoria, grupo in df.groupby('categoryName'):
        grupo_ordenado = grupo.sort_values(by='text_length', ascending=False)
        dfs_filtrados.append(grupo_ordenado.head(max_reviews))

    resultado = pd.concat(dfs_filtrados, ignore_index=True)
    resultado = resultado.drop(columns='text_length')

    output_csv = os.path.join('outputs', "translatedReviews.csv")
    resultado.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"Archivo traducido y filtrado guardado en: {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traducir y filtrar hasta N reviews por categoría.")
    parser.add_argument("--input_csv", default="output.csv", help="Archivo CSV de entrada. Default: output.csv")
    parser.add_argument("--max_reviews", type=int, default=5000, help="Máximo de reviews por categoría (default: 5000).")
    parser.add_argument("--workers", type=int, default=10, help="Número de hilos de traducción.")
    args = parser.parse_args()

    traducir_reviews(args.input_csv, args.max_reviews, args.workers)
