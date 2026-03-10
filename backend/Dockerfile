# ─── Backend Dockerfile ───
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps (pdflatex for LaTeX compilation + Playwright deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-fonts-extra \
    curl build-essential \
    libnss3 libatk-bridge2.0-0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy all source
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -e ".[dev]"

# Install Playwright browsers
RUN playwright install --with-deps chromium

EXPOSE 8000

# ─── Production: Uvicorn ───
FROM base AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ─── Development: auto-reload ───
FROM base AS development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
