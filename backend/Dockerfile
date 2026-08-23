# AI Assignment Reviewer - backend (FastAPI)
# Build: docker build -t reviewer-backend .
# Run:   docker run -p 8000:8000 --env-file .env reviewer-backend
#
# Render (and most PaaS providers) inject a PORT env var at runtime and
# route external traffic to it - the container must NOT hardcode 8000.

FROM python:3.11-slim

WORKDIR /app

# Install system deps needed by pymupdf (PDF parsing) and python-docx.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Render sets $PORT at runtime; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# Shell form so $PORT is expanded at container start, not build time.
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
