FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/Koyeb/Cloud Run all inject $PORT at runtime; config.py already
# reads it via os.environ.get("PORT", 8080).
ENV PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
