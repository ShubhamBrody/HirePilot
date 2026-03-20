# ─── Backend Dockerfile ───
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps (pdflatex for LaTeX compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-fonts-extra \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy all source
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

# ─── Production: Uvicorn ───
FROM base AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ─── Development: auto-reload ───
FROM base AS development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
