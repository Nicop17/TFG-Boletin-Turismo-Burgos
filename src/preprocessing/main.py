from processReviews import process_reviews
from translateReviews import traducir_reviews
from cleanReviews import limpiar_reviews

def main():
    csv_reviews = "inputs/all-task-1842-detailed-reviews.csv"
    csv_poi = "inputs/all-task-1842.csv"
    estado = "Burgos"
    max_reviews = 5000 # Máximo de reseñas a procesar por POI (limitado para construir un dataset balanceado)

    # Archivos intermedios y finales
    output_csv = "processedReviews.csv"
    output_filtrado_csv = "translatedReviews.csv"
    output_limpio_csv = "cleanReviews.csv"

    # Paso 1 NO necesario si las reviews son de Apify
    print("\nPaso 1: Generando archivo output.csv desde CSVs de reviews y POIs...")
    process_reviews(csv_reviews, csv_poi, estado)

    print("\nPaso 2: Traduciendo y filtrando reviews por categoría...")
    traducir_reviews(input_csv=output_csv, max_reviews=max_reviews, workers=10)

    print("\nPaso 3: Limpiando texto y aplicando filtro de longitud...")
    limpiar_reviews(input_csv=output_filtrado_csv, output_csv=output_limpio_csv)

    print("\nPipeline completo. Revisa cleanReviews.csv")

if __name__ == "__main__":
    main()
