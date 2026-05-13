# 1. Imagen base oficial de Python
FROM python:3.13-slim

# 2. Evitar archivos basura y ver logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Directorio de trabajo
WORKDIR /app

# 4. Instalamos dependencias del sistema necesarias para compilar librerías de texto
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiar e instalar librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código
COPY . .

# 7. Comando por defecto (ejecutar el scraper)
CMD ["python", "src/main_scraper_pipeline.py"]