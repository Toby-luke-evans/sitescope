# Root Dockerfile for Render deployment
# Build context is repo root
FROM python:3.12-slim

WORKDIR /app

# Install system deps (for shapely, pyproj)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev \
    libproj-dev \
    proj-data \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps for backend
COPY apps/zoning-report/backend/pyproject.toml ./
RUN pip install --no-cache-dir -e "."

# Install shared packages
COPY packages/zoning-core /app/packages/zoning-core
RUN pip install --no-cache-dir -e /app/packages/zoning-core

COPY packages/spatial-engine /app/packages/spatial-engine
RUN pip install --no-cache-dir -e /app/packages/spatial-engine

# Copy app code
COPY apps/zoning-report/backend /app/apps/zoning-report/backend
ENV PYTHONPATH="/app/apps/zoning-report/backend/app:/app/packages/zoning-core/src:/app/packages/spatial-engine/src:${PYTHONPATH}"

WORKDIR /app/apps/zoning-report/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
