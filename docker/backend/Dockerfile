# Ontology Builder — Backend (FastAPI + Microsoft Agent Framework)
# Build context is the repo root:  docker build -f docker/backend/Dockerfile .
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Build tools for any native wheels, then clean up.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies from pyproject (installs the `app` package + all deps:
# fastapi[standard], agent-framework, agent-framework-ag-ui, openai, aiosqlite, mcp, ...).
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir .

# Application code + the on-disk skill packages (read by /api/skills and prompt injection).
COPY backend/app ./app
COPY backend/skills ./skills

# Writable runtime dirs for the SQLite DB + generated YAML (relative to WORKDIR).
RUN mkdir -p deployment/data deployment/outputs

ENV HOST=0.0.0.0
ENV PORT=8005
EXPOSE 8005

# No embedded server in the app — supply host/port on the CLI.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
