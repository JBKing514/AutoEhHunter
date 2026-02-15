FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    ca-certificates \
    libpq5 \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Keep hunterAgent import path stable.
COPY compute/requirements.txt /app/requirements.txt
COPY compute/hunterAgent /app/hunterAgent
COPY compute/vectorIngest /app/vectorIngest

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements.txt "psycopg[binary]>=3.1"

COPY compute/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 18080
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["agent"]
