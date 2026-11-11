FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COFFEE_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py pdf_export.py ./
COPY static ./static

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=4)"

CMD ["gunicorn", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:8787", "--timeout", "45", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
