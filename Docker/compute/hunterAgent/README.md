# hunterAgent (FastAPI skills)

Minimal FastAPI service exposing multiple "skills" over JSON.

## Run

1) Create an env file (example):

```bash
set POSTGRES_DSN=postgresql://user:pass@host:5432/lrr_library
set LLM_API_BASE=http://127.0.0.1:8000/v1
set LLM_API_KEY=
set LLM_MODEL=default
set EMB_API_BASE=http://127.0.0.1:8001/v1
set EMB_MODEL=bge-m3

python -m pip install -r hunterAgent/requirements.txt
python -m uvicorn hunterAgent.main:app --host 0.0.0.0 --port 18080
```

2) Call a skill:

```bash
curl -X POST http://127.0.0.1:18080/skill/search \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"我想找画风像水彩、线条干净的漫画\",\"k\":10}"
```

## Endpoints

- POST `/skill/search`
- POST `/skill/search/image` (multipart image upload for img2img)
- POST `/skill/profile`
- POST `/skill/report`
- POST `/skill/chat`
- POST `/skill/recommendation`

## Img2Img Search

### 1) Search by existing title (JSON)

```bash
curl -X POST http://127.0.0.1:18080/skill/search \
  -H "Content-Type: application/json" \
  -d "{\"seed_title\":\"<已有本子标题>\",\"mode\":\"mixed\",\"k\":10}"
```

### 2) Search by uploading an image (multipart)

```bash
curl -X POST http://127.0.0.1:18080/skill/search/image \
  -F "image=@/path/to/cover.jpg" \
  -F "mode=mixed" \
  -F "k=10"
```

## Recommendation

Recommend newly uploaded EH works from `eh_works` with tag + visual profile scoring:

```bash
curl -X POST http://127.0.0.1:18080/skill/recommendation \
  -H "Content-Type: application/json" \
  -d "{\"k\":10,\"candidate_hours\":24,\"profile_days\":30,\"tag_weight\":0.6,\"visual_weight\":0.4,\"explore\":false}"
```
