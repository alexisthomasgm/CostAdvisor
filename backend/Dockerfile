FROM python:3.12-slim

# Avoid Python writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install curl and Tailscale
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://tailscale.com/install.sh | sh

# Copy app code
COPY . .

# Make entrypoints executable
RUN chmod +x entrypoint.sh entrypoint-worker.sh

# Railway / Render inject PORT at runtime; default to 8000 for local docker runs
ENV PORT=8000
EXPOSE 8000

CMD ["/app/entrypoint.sh"]
