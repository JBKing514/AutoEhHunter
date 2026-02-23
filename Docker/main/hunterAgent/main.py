import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from hunterAgent.core.ai import OpenAICompatClient
from hunterAgent.core.config import get_settings
from hunterAgent.skills import load_all_skills
from hunterAgent.skills.chat import run_chat
from hunterAgent.skills.profile import run_profile
from hunterAgent.skills.recommendation import run_recommendation
from hunterAgent.skills.report import run_report
from hunterAgent.skills.search import run_search


load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


_PLUGIN_DIR = os.getenv("HUNTER_PLUGIN_DIR", "/app/runtime/plugins")
# Activate the skill registry: registers all builtin skills and loads any
# user plugins from the plugin directory.  Must run before request handlers
# are invoked so that list_tools() / run_skill() work correctly.
load_all_skills(_PLUGIN_DIR)


app = FastAPI(title="hunterAgent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clients() -> Dict[str, Any]:
    settings = get_settings()
    llm = OpenAICompatClient(api_base=settings.llm_api_base, api_key=settings.llm_api_key)
    emb = OpenAICompatClient(api_base=settings.emb_api_base, api_key=settings.emb_api_key)
    return {"settings": settings, "llm": llm, "emb": emb}


@app.get("/health")
def health() -> Dict[str, Any]:
    # Keep it minimal: config sanity.
    try:
        s = get_settings()
        return {
            "ok": True,
            "postgres_dsn": "set" if bool(s.postgres_dsn) else "missing",
            "llm_api_base": s.llm_api_base,
            "emb_api_base": s.emb_api_base,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/skill/search")
def skill_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _clients()
    try:
        data = run_search(settings=c["settings"], llm=c["llm"], emb=c["emb"], payload=payload)
        return {"ok": True, "skill": "search", "data": data}
    except Exception as e:
        logger.exception("search failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skill/search/image")
async def skill_search_image(
    image: UploadFile = File(...),
    query: str = Form(""),
    mode: str = Form("auto"),
    k: int = Form(10),
    seed_title: str = Form(""),
    seed_arcid: str = Form(""),
) -> Dict[str, Any]:
    c = _clients()
    try:
        image_bytes = await image.read()
        payload: Dict[str, Any] = {
            "query": query,
            "mode": mode,
            "k": int(k),
            "seed_title": seed_title,
            "seed_arcid": seed_arcid,
            "image_bytes": image_bytes,
        }
        data = run_search(settings=c["settings"], llm=c["llm"], emb=c["emb"], payload=payload)
        return {"ok": True, "skill": "search", "data": data}
    except Exception as e:
        logger.exception("search image failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skill/profile")
def skill_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _clients()
    try:
        data = run_profile(settings=c["settings"], llm=c["llm"], payload=payload)
        return {"ok": True, "skill": "profile", "data": data}
    except Exception as e:
        logger.exception("profile failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skill/report")
def skill_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _clients()
    try:
        data = run_report(settings=c["settings"], llm=c["llm"], payload=payload)
        return {"ok": True, "skill": "report", "data": data}
    except Exception as e:
        logger.exception("report failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skill/recommendation")
def skill_recommendation(payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _clients()
    try:
        data = run_recommendation(settings=c["settings"], llm=c["llm"], payload=payload)
        return {"ok": True, "skill": "recommendation", "data": data}
    except Exception as e:
        logger.exception("recommendation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skill/chat")
def skill_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    c = _clients()
    try:
        data = run_chat(settings=c["settings"], llm=c["llm"], payload=payload)
        return {"ok": True, "skill": "chat", "data": data}
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(e))
