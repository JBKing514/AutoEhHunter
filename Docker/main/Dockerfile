FROM node:22-bookworm-slim AS webbuild

WORKDIR /webapp
COPY webapp/package.json /webapp/package.json
COPY webapp/index.html /webapp/index.html
COPY webapp/vite.config.js /webapp/vite.config.js
COPY webapp/src /webapp/src
RUN npm install --no-audit --no-fund && npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    bash \
    curl \
    ca-certificates \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY ehCrawler /app/ehCrawler
COPY lrrDataFlush /app/lrrDataFlush
COPY textIngest /app/textIngest
COPY vectorIngest /app/vectorIngest
COPY hunterAgent /app/hunterAgent
COPY webapi /app/webapi
COPY --from=webbuild /webapp/dist /app/webapi/static

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r /app/requirements.txt

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x \
    /app/entrypoint.sh \
    /app/ehCrawler/run_eh_fetch.sh \
    /app/lrrDataFlush/run_daily_lrr_export.sh \
    /app/textIngest/run_daily_text_ingest.sh \
    /app/textIngest/init_schema_once.sh
EXPOSE 8501
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["help"]
