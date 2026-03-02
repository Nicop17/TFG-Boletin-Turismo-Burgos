import pandas as pd
import argparse, os

def clean_and_filter_reviews(df):
    # Quitar NaN en text
    df = df[df['text'].notna()]

    # Limpiar saltos de línea en text
    df['text'] = df['text'].apply(lambda x: str(x).replace('\n', ' ').replace('\r', ' ').strip())

    # Filtro de longitud mínima (mínimo 15 palabras)
    df = df[df['text'].str.split().apply(len) >= 15]

    return df

def limpiar_reviews(input_csv='output_filtrado.csv', output_csv='reviews_limpias.csv'):
    
    if not os.path.exists('outputs'):
        os.makedirs('outputs')

    input_path = os.path.join('outputs', input_csv)
    output_path = os.path.join('outputs', output_csv)

    df = pd.read_csv(input_path, dtype=str)
    df_filtrado = clean_and_filter_reviews(df)

    print(f"Guardando archivo: {output_csv}")
    df_filtrado.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"Limpieza completa. Total reviews finales: {len(df_filtrado)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpiar y filtrar reviews con texto mínimo.")
    parser.add_argument("--input_csv", default="output_filtrado.csv", help="Archivo CSV de entrada (default: output_filtrado.csv)")
    parser.add_argument("--output_csv", default="reviews_limpias.csv", help="Archivo CSV de salida (default: reviews_limpias.csv)")
    args = parser.parse_args()

    limpiar_reviews(args.input_csv, args.output_csv)
