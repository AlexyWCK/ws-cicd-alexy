FROM python:3.12-slim

# Relie le package GHCR au dépôt GitHub
LABEL org.opencontainers.image.source="https://github.com/AlexyWCK/ws-cicd-alexy"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Valeur fournie au build (ARG) et conservée à l'exécution (ENV)
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

# L'application ne tourne pas en root
RUN useradd --create-home appuser
USER appuser

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
