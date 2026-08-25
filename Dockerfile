FROM python:3.11-slim

# Dependências de sistema:
# - tesseract-ocr + idioma português: usado por pytesseract (src/extractor.py)
# - libraries necessárias para PyMuPDF (fitz) e Pillow renderizarem PDFs/imagens
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Diretório para o SQLite (montado como volume no docker-compose, para
# persistir o progresso do processamento entre deploys no Coolify).
RUN mkdir -p /app/data

ENV DB_PATH=/app/data/data.db \
    PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
