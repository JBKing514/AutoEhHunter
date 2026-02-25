FROM node:20-bookworm-slim AS webbuild

WORKDIR /webapp
COPY main/webapp/package.json /webapp/package.json
COPY main/webapp/index.html /webapp/index.html
COPY main/webapp/vite.config.js /webapp/vite.config.js
COPY main/webapp/src /webapp/src
RUN npm install --no-audit --no-fund && npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    ca-certificates \
    docker.io \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY main/requirements.txt /app/requirements.txt
COPY main/ehCrawler /app/ehCrawler
COPY main/lrrDataFlush /app/lrrDataFlush
COPY main/textIngest /app/textIngest
COPY main/vectorIngest /app/vectorIngest
COPY main/hunterAgent /app/hunterAgent
COPY main/webapi /app/webapi
COPY --from=webbuild /webapp/dist /app/webapi/static

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements.txt

COPY main/entrypoint.sh /app/entrypoint.sh
RUN chmod +x \
    /app/entrypoint.sh \
    /app/ehCrawler/run_eh_fetch.sh \
    /app/lrrDataFlush/run_daily_lrr_export.sh \
    /app/textIngest/run_daily_text_ingest.sh \
    /app/textIngest/init_schema_once.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["help"]
