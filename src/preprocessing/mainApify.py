from translateReviews import traducir_reviews
from cleanReviews import limpiar_reviews

def main():
    csv_reviews = "apifyReviews.csv"
    max_reviews = 5000 # Máximo de reseñas a procesar por POI (limitado para construir un dataset balanceado)

    # Archivos intermedios y finales
    output_filtrado_csv = "translatedReviews.csv"
    output_limpio_csv = "cleanReviews.csv"

    print("\nPaso 2: Traduciendo y filtrando reviews por categoría...")
    traducir_reviews(input_csv=csv_reviews, max_reviews=max_reviews, workers=10)

    print("\nPaso 3: Limpiando texto y aplicando filtro de longitud...")
    limpiar_reviews(input_csv=output_filtrado_csv, output_csv=output_limpio_csv)

    print("\nPipeline completo. Revisa cleanReviews.csv")

if __name__ == "__main__":
    main()