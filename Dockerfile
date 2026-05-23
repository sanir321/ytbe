FROM python:3.13-slim

WORKDIR /app

# Install system deps: FFmpeg + curl (for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Create required dirs under DATA_DIR (for persistent volume)
RUN mkdir -p /data/videos/raw /data/videos/processed /data/logs

# Railway health check port
ENV PORT=8080
# Persistent data volume (queue.db, logs)
ENV DATA_DIR=/data

CMD ["python", "main.py"]
