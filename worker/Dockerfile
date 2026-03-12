FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install -e ".[dev]"

FROM deps AS development
COPY . .
RUN addgroup --system app && adduser --system --ingroup app app
USER app
CMD ["python", "-m", "src.main"]

FROM base AS production
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install -e "."
COPY src ./src
RUN addgroup --system app && adduser --system --ingroup app app
USER app
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python -c "import src.anomaly_detector"
CMD ["python", "-m", "src.main"]
