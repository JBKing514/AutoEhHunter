#!/usr/bin/env python3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.constants import STATIC_DIR
from .core.middleware import auth_guard
from .routers import auth, chat, recommend, search, settings, system, tasks
from .services.config_service import apply_runtime_timezone, ensure_dirs

app = FastAPI(title="AutoEhHunter Web API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(auth_guard)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(recommend.router)
app.include_router(settings.router)
app.include_router(tasks.router)
app.include_router(chat.router)
app.include_router(system.router)

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

ensure_dirs()
apply_runtime_timezone()
