# 1. Imagen base oficial de Python
FROM python:3.13-slim

# 2. Directorio de trabajo
WORKDIR /app

# 3. Copiar e instalar librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar el resto del código
COPY . .

# 5. Comando por defecto (ejecutar el scraper)
CMD ["python", "src/scraper_burgos.py"]