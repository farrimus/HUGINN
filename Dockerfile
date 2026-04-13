# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
COPY frontend/patches ./patches/
RUN npm ci

COPY frontend/ .
RUN npm run build

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# System deps for cryptography + fcntl
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY main.py .
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY data/eve_universe.db ./data/eve_universe.db
COPY data/systems.json ./data/systems.json
COPY data/gate_graph.json ./data/gate_graph.json
COPY data/gates.json ./data/gates.json
COPY data/lore_seed.json ./data/lore_seed.json
COPY data/build_tree.json ./data/build_tree.json
COPY data/Allowed_regions.txt ./data/Allowed_regions.txt

# Built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./static/companion/

# Runtime data (sessions, memory, structures) is mounted as a volume
VOLUME ["/app/data/utopia", "/app/data/stillness", "/app/data/structures"]

EXPOSE 8745

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8745"]
