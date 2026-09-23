# ORBINOVASTRO AI backend -- deployable image for Render/Railway/Fly.io/any
# host that runs a Dockerfile. Build context is this folder (ai_app/), so
# both backend/ and frontend/ are visible to it. No external ephemeris data
# files needed: pyswisseph falls back to its built-in Moshier approximation.
#
# Build:  docker build -t orbinovastro-ai .        (run from ai_app/)
# Run:    docker run -p 8000:8000 --env-file backend/.env orbinovastro-ai
FROM python:3.11-slim

WORKDIR /app

# System deps for building pyswisseph's C extension.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY frontend ./frontend

# Render/Railway/Fly all inject $PORT at runtime; default to 8000 for a
# plain `docker run` locally.
ENV PORT=8000
EXPOSE 8000
WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
