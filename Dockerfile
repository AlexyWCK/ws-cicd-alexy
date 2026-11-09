FROM python:3.12-slim

# TODO : label reliant l'image au dépôt GitHub (org.opencontainers.image.source)

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# TODO : argument de build APP_VERSION transmis à l'application

# TODO : créer un utilisateur non-root et l'utiliser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
