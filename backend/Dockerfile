FROM python:3.12-slim

# Avoid Python writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Run as non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Railway / Render inject PORT at runtime; default to 8000 for local docker runs
ENV PORT=8000
EXPOSE 8000

# Default command runs the API.
# The worker service in Railway overrides this CMD with:
#   celery -A app.tasks worker --beat --loglevel=info
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
