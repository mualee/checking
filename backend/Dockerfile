# Prod image for Cloud Run. NOTE: unverified locally — no Docker available in the
# dev environment at build time. Kept minimal/standard to reduce risk.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: pdfplumber relies on pdfminer.six + Pillow (wheels), no apt packages
# are typically required. Add build-essential only if a wheel is unavailable.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Cloud Run injects PORT (defaults to 8080). ENV=prod disables emulator wiring.
ENV ENV=prod
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
