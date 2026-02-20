#!/usr/bin/env python3
import base64
import json
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import numpy as np
import psycopg
import requests
import requests_unixsocket
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from plotly import figure_factory as ff
from plotly.utils import PlotlyJSONEncoder
from scipy.cluster import hierarchy as sch
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer


RUNTIME_DIR = Path(os.getenv("DATA_UI_RUNTIME_DIR", "/app/runtime/webui"))
SCHEDULE_FILE = RUNTIME_DIR / "schedule.json"
RUN_HISTORY_FILE = RUNTIME_DIR / "run_history.jsonl"
TASK_LOG_DIR = RUNTIME_DIR / "task_logs"
APP_CONFIG_FILE = RUNTIME_DIR / "app_config.json"
APP_CONFIG_KEY_FILE = RUNTIME_DIR / ".app_config.key"
STATIC_DIR = Path(__file__).resolve().parent / "static"

CONFIG_SCOPE = "global"

DEFAULT_SCHEDULE = {
    "eh_fetch": {"enabled": False, "cron": "*/30 * * * *"},
    "lrr_export": {"enabled": False, "cron": "0 * * * *"},
    "text_ingest": {"enabled": False, "cron": "5 * * * *"},
    "compute_daily": {"enabled": False, "cron": "10 * * * *"},
}

CONFIG_SPECS: dict[str, dict[str, Any]] = {
    "POSTGRES_DSN": {"type": "text", "default": "", "secret": True},
    "POSTGRES_HOST": {"type": "text", "default": "pgvector-db"},
    "POSTGRES_PORT": {"type": "int", "default": 5432, "min": 1, "max": 65535},
    "POSTGRES_DB": {"type": "text", "default": "lrr_library"},
    "POSTGRES_USER": {"type": "text", "default": "postgres"},
    "POSTGRES_PASSWORD": {"type": "text", "default": "", "secret": True},
    "POSTGRES_SSLMODE": {"type": "text", "default": "prefer"},
    "LRR_BASE": {"type": "url", "default": "http://lanraragi:3000"},
    "LRR_API_KEY": {"type": "text", "default": "", "secret": True},
    "OPENAI_API_KEY": {"type": "text", "default": "", "secret": True},
    "COMPUTE_HEALTH_URL": {"type": "url", "default": "http://autoeh-compute:18080/health"},
    "OPENAI_HEALTH_URL": {"type": "url", "default": ""},
    "COMPUTE_CONTAINER_NAME": {"type": "text", "default": "autoeh-compute"},
    "DATA_UI_LANG": {"type": "text", "default": "zh"},
    "TEXT_INGEST_PRUNE_NOT_SEEN": {"type": "bool", "default": True},
    "WORKER_ONLY_MISSING": {"type": "bool", "default": True},
    "LRR_READS_HOURS": {"type": "int", "default": 24, "min": 1, "max": 720},
    "EH_BASE_URL": {"type": "text", "default": "https://e-hentai.org"},
    "EH_FETCH_MAX_PAGES": {"type": "int", "default": 8, "min": 1, "max": 64},
    "EH_REQUEST_SLEEP": {"type": "float", "default": 4.0, "min": 0.0, "max": 120.0},
    "EH_SAMPLING_DENSITY": {"type": "float", "default": 1.0, "min": 0.0, "max": 1.0},
    "EH_USER_AGENT": {"type": "text", "default": "AutoEhHunter/1.0"},
    "EH_COOKIE": {"type": "text", "default": "", "secret": True},
    "EH_FILTER_CATEGORY": {"type": "text", "default": ""},
    "EH_MIN_RATING": {"type": "float", "default": 0.0, "min": 0.0, "max": 5.0},
    "EH_FILTER_TAG": {"type": "text", "default": ""},
    "TEXT_INGEST_BATCH_SIZE": {"type": "int", "default": 1000, "min": 100, "max": 5000},
    "EH_QUEUE_LIMIT": {"type": "int", "default": 2000, "min": 100, "max": 5000},
    "LLM_API_BASE": {"type": "url", "default": "http://llm-router:8000/v1"},
    "LLM_API_KEY": {"type": "text", "default": "", "secret": True},
    "LLM_MODEL": {"type": "text", "default": "qwen3-next-80b-instruct"},
    "EMB_API_BASE": {"type": "url", "default": "http://llm-router:8000/v1"},
    "EMB_API_KEY": {"type": "text", "default": "", "secret": True},
    "EMB_MODEL": {"type": "text", "default": "bge-m3"},
    "VL_BASE": {"type": "url", "default": "http://vl-server:8002"},
    "EMB_BASE": {"type": "url", "default": "http://emb-server:8001"},
    "VL_MODEL_ID": {"type": "text", "default": "vl"},
    "EMB_MODEL_ID": {"type": "text", "default": "bge-m3"},
    "SIGLIP_MODEL": {"type": "text", "default": "google/siglip-so400m-patch14-384"},
    "SIGLIP_DEVICE": {"type": "text", "default": "cpu"},
    "WORKER_BATCH": {"type": "int", "default": 32, "min": 1, "max": 512},
    "WORKER_SLEEP": {"type": "float", "default": 0.0, "min": 0.0, "max": 60.0},
}

COMPUTE_ENV_FORWARD_KEYS = [
    "POSTGRES_DSN",
    "LRR_BASE",
    "LRR_API_KEY",
    "OPENAI_API_KEY",
    "LLM_API_BASE",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMB_API_BASE",
    "EMB_API_KEY",
    "EMB_MODEL",
    "VL_BASE",
    "EMB_BASE",
    "VL_MODEL_ID",
    "EMB_MODEL_ID",
    "SIGLIP_MODEL",
    "SIGLIP_DEVICE",
    "WORKER_BATCH",
    "WORKER_SLEEP",
    "WORKER_ONLY_MISSING",
    "EH_BASE_URL",
    "EH_FETCH_MAX_PAGES",
    "EH_REQUEST_SLEEP",
    "EH_SAMPLING_DENSITY",
    "EH_USER_AGENT",
    "EH_COOKIE",
    "EH_FILTER_CATEGORY",
    "EH_MIN_RATING",
    "EH_FILTER_TAG",
    "EH_QUEUE_LIMIT",
]

TASK_COMMANDS = {
    "eh_fetch": ["/app/ehCrawler/run_eh_fetch.sh"],
    "lrr_export": ["/app/lrrDataFlush/run_daily_lrr_export.sh"],
    "text_ingest": ["/app/textIngest/run_daily_text_ingest.sh"],
    "compute_daily": ["__compute_daily__"],
}

scheduler = BackgroundScheduler(timezone="UTC")
task_state_lock = threading.Lock()
task_state: dict[str, dict[str, Any]] = {}


class ConfigUpdateRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class ScheduleUpdateRequest(BaseModel):
    schedule: dict[str, dict[str, Any]]


class TaskRunRequest(BaseModel):
    task: str
    args: str = ""


def ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    TASK_LOG_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str_bool(v: bool) -> str:
    return "1" if bool(v) else "0"


def _as_bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _normalize_value(key: str, raw: Any) -> str:
    spec = CONFIG_SPECS.get(key, {"type": "text", "default": ""})
    kind = str(spec.get("type", "text"))
    default = spec.get("default", "")
    if kind == "bool":
        return _str_bool(_as_bool(raw, bool(default)))
    if kind == "int":
        try:
            n = int(str(raw).strip())
        except Exception:
            n = int(default)
        n = max(int(spec.get("min", n)), min(int(spec.get("max", n)), n))
        return str(n)
    if kind == "float":
        try:
            n = float(str(raw).strip())
        except Exception:
            n = float(default)
        n = max(float(spec.get("min", n)), min(float(spec.get("max", n)), n))
        return str(n)
    if raw is None:
        return str(default)
    return str(raw).strip()


def get_config_cipher() -> Fernet:
    ensure_dirs()
    key_env = os.getenv("DATA_UI_CONFIG_CRYPT_KEY", "").strip()
    if key_env:
        if len(key_env) == 44 and key_env.endswith("="):
            key = key_env.encode("ascii")
        else:
            key = base64.urlsafe_b64encode(key_env.encode("utf-8")[:32].ljust(32, b"0"))
        return Fernet(key)

    if APP_CONFIG_KEY_FILE.exists():
        return Fernet(APP_CONFIG_KEY_FILE.read_bytes().strip())

    key = Fernet.generate_key()
    APP_CONFIG_KEY_FILE.write_bytes(key + b"\n")
    return Fernet(key)


def _encrypt_secret(value: str) -> str:
    v = str(value or "").strip()
    if not v:
        return ""
    token = get_config_cipher().encrypt(v.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{token}"


def _decrypt_secret(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if not s.startswith("enc:v1:"):
        return s
    token = s[len("enc:v1:") :]
    try:
        return get_config_cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return ""


def _parse_dsn_components(dsn: str) -> dict[str, str]:
    out: dict[str, str] = {}
    s = str(dsn or "").strip()
    if not s:
        return out
    try:
        u = urlparse(s)
    except Exception:
        return out
    out["POSTGRES_HOST"] = (u.hostname or "").strip()
    out["POSTGRES_PORT"] = str(u.port or 5432)
    out["POSTGRES_DB"] = (u.path or "").lstrip("/").strip()
    out["POSTGRES_USER"] = (u.username or "").strip()
    out["POSTGRES_PASSWORD"] = (u.password or "").strip()
    q = (u.query or "").strip()
    if "sslmode=" in q:
        for item in q.split("&"):
            if item.startswith("sslmode="):
                out["POSTGRES_SSLMODE"] = item.split("=", 1)[1].strip()
                break
    return out


def _build_dsn(values: dict[str, str]) -> str:
    manual = str(values.get("POSTGRES_DSN", "")).strip()
    host = str(values.get("POSTGRES_HOST", "")).strip()
    db = str(values.get("POSTGRES_DB", "")).strip()
    user = str(values.get("POSTGRES_USER", "")).strip()
    pwd = str(values.get("POSTGRES_PASSWORD", "")).strip()
    if not host or not db or not user:
        return manual
    port = _normalize_value("POSTGRES_PORT", values.get("POSTGRES_PORT", "5432"))
    sslmode = str(values.get("POSTGRES_SSLMODE", "prefer")).strip() or "prefer"
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/{quote_plus(db)}"
        f"?sslmode={quote_plus(sslmode)}"
    )


def _load_json_config() -> dict[str, str]:
    ensure_dirs()
    if not APP_CONFIG_FILE.exists():
        return {}
    try:
        obj = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    vals = obj.get("values", obj) if isinstance(obj, dict) else {}
    if not isinstance(vals, dict):
        return {}
    out: dict[str, str] = {}
    for key, spec in CONFIG_SPECS.items():
        if key not in vals:
            continue
        raw = vals.get(key)
        out[key] = _decrypt_secret(str(raw or "")) if spec.get("secret", False) else _normalize_value(key, raw)
    return out


def _save_json_config(values: dict[str, str]) -> None:
    ensure_dirs()
    payload: dict[str, Any] = {"version": 1, "updated_at": now_iso(), "values": {}}
    for key, spec in CONFIG_SPECS.items():
        raw = str(values.get(key, _normalize_value(key, spec.get("default", ""))))
        payload["values"][key] = _encrypt_secret(raw) if spec.get("secret", False) else _normalize_value(key, raw)
    APP_CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_db_config(dsn: str) -> tuple[dict[str, str], str]:
    s = str(dsn or "").strip()
    if not s:
        return ({}, "missing dsn")
    sql = "SELECT key, value, is_secret FROM app_config WHERE scope = %s"
    try:
        out: dict[str, str] = {}
        with psycopg.connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (CONFIG_SCOPE,))
                for key, value, is_secret in cur.fetchall():
                    if key not in CONFIG_SPECS:
                        continue
                    out[key] = _decrypt_secret(str(value or "")) if is_secret else _normalize_value(str(key), value)
        return (out, "")
    except Exception as e:
        return ({}, str(e))


def _save_db_config(dsn: str, values: dict[str, str]) -> tuple[bool, str]:
    s = str(dsn or "").strip()
    if not s:
        return (False, "missing dsn")
    create_sql = (
        "CREATE TABLE IF NOT EXISTS app_config ("
        "scope text NOT NULL DEFAULT 'global',"
        "key text NOT NULL,value text NOT NULL,value_type text NOT NULL DEFAULT 'string',"
        "is_secret boolean NOT NULL DEFAULT false,description text,"
        "created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),"
        "PRIMARY KEY (scope, key))"
    )
    upsert_sql = (
        "INSERT INTO app_config(scope, key, value, value_type, is_secret, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, now()) "
        "ON CONFLICT (scope, key) DO UPDATE SET value = EXCLUDED.value, "
        "value_type = EXCLUDED.value_type, is_secret = EXCLUDED.is_secret, updated_at = now()"
    )
    try:
        with psycopg.connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute(create_sql)
                for key, spec in CONFIG_SPECS.items():
                    plain = str(values.get(key, _normalize_value(key, spec.get("default", ""))))
                    stored = _encrypt_secret(plain) if spec.get("secret", False) else _normalize_value(key, plain)
                    cur.execute(
                        upsert_sql,
                        (CONFIG_SCOPE, key, stored, str(spec.get("type", "text")), bool(spec.get("secret", False))),
                    )
            conn.commit()
        return (True, "")
    except Exception as e:
        return (False, str(e))


def resolve_config() -> tuple[dict[str, str], dict[str, Any]]:
    merged: dict[str, str] = {k: _normalize_value(k, spec.get("default", "")) for k, spec in CONFIG_SPECS.items()}

    env_vals: dict[str, str] = {}
    for key in CONFIG_SPECS:
        v = os.getenv(key)
        if v is not None:
            env_vals[key] = _normalize_value(key, v)
    if env_vals.get("POSTGRES_DSN"):
        env_vals.update(_parse_dsn_components(env_vals["POSTGRES_DSN"]))

    json_vals = _load_json_config()
    if json_vals.get("POSTGRES_DSN"):
        json_vals.update(_parse_dsn_components(json_vals["POSTGRES_DSN"]))

    merged.update(env_vals)
    merged.update(json_vals)
    merged["POSTGRES_DSN"] = _build_dsn(merged)

    db_vals, db_error = _load_db_config(merged.get("POSTGRES_DSN", ""))
    if db_vals.get("POSTGRES_DSN"):
        db_vals.update(_parse_dsn_components(db_vals["POSTGRES_DSN"]))
    merged.update(db_vals)
    merged["POSTGRES_DSN"] = _build_dsn(merged)
    meta = {
        "db_connected": bool(merged.get("POSTGRES_DSN", "")) and not db_error,
        "db_error": db_error,
        "sources": "db > json > env",
    }
    return merged, meta


def build_runtime_env() -> dict[str, str]:
    cfg, _ = resolve_config()
    env = dict(os.environ)
    for key in CONFIG_SPECS:
        val = str(cfg.get(key, ""))
        if val:
            env[key] = val
    env["POSTGRES_DSN"] = cfg.get("POSTGRES_DSN", "")
    return env


def db_dsn() -> str:
    cfg, _ = resolve_config()
    return str(cfg.get("POSTGRES_DSN", "")).strip()


def query_rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    dsn = db_dsn()
    if not dsn:
        return []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in (cur.fetchall() or [])]


def run_docker_exec_via_socket(cmd: list[str], timeout_s: int = 1800) -> tuple[int, str, str]:
    if not Path("/var/run/docker.sock").exists():
        return (127, "", "docker CLI missing and /var/run/docker.sock not mounted")
    if len(cmd) < 4 or cmd[0] != "docker" or cmd[1] != "exec":
        return (2, "", f"unsupported docker command: {' '.join(cmd)}")

    idx = 2
    while idx < len(cmd) and cmd[idx].startswith("-"):
        idx += 1
    if idx >= len(cmd):
        return (2, "", "missing container name in docker exec command")
    container = cmd[idx]
    argv = cmd[idx + 1 :]
    if not argv:
        return (2, "", "missing command in docker exec")

    session = requests_unixsocket.Session()
    base = "http+unix://%2Fvar%2Frun%2Fdocker.sock"
    try:
        create = session.post(
            f"{base}/containers/{container}/exec",
            json={"AttachStdout": True, "AttachStderr": True, "Tty": True, "Cmd": argv},
            timeout=min(timeout_s, 30),
        )
        if create.status_code >= 400:
            return (1, "", f"docker exec create failed: HTTP {create.status_code} {create.text}")
        exec_id = (create.json() or {}).get("Id")
        if not exec_id:
            return (1, "", "docker exec create failed: missing exec id")

        start = session.post(f"{base}/exec/{exec_id}/start", json={"Detach": False, "Tty": True}, timeout=timeout_s)
        combined = start.text if start.text is not None else ""

        inspect = session.get(f"{base}/exec/{exec_id}/json", timeout=min(timeout_s, 30))
        if inspect.status_code >= 400:
            return (1, combined, f"docker exec inspect failed: HTTP {inspect.status_code} {inspect.text}")
        exit_code = int((inspect.json() or {}).get("ExitCode") or 0)
        if exit_code == 0:
            return (0, combined, "")
        return (exit_code, combined, "docker exec returned non-zero exit code")
    except Exception as e:
        return (1, "", f"docker socket exec error: {e}")


def compute_container_name() -> str:
    cfg, _ = resolve_config()
    return str(cfg.get("COMPUTE_CONTAINER_NAME", "autoeh-compute")).strip() or "autoeh-compute"


def compute_exec_cmd(script_path: str, args: list[str] | None = None) -> list[str]:
    runtime_env = build_runtime_env()
    cmd = ["docker", "exec", "-i", compute_container_name(), "env"]
    for key in COMPUTE_ENV_FORWARD_KEYS:
        val = str(runtime_env.get(key, "")).strip()
        if val:
            cmd.append(f"{key}={val}")
    cmd.append(script_path)
    if args:
        cmd.extend(args)
    return cmd


def append_run_history(item: dict[str, Any]) -> None:
    ensure_dirs()
    with RUN_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_run_history(limit: int = 200) -> list[dict[str, Any]]:
    if not RUN_HISTORY_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    with RUN_HISTORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]


def _date_to_epoch(date_txt: str, end_of_day: bool = False) -> int | None:
    s = str(date_txt or "").strip()
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
        if end_of_day:
            dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        else:
            dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def _filter_run_history(
    rows: list[dict[str, Any]],
    task: str = "",
    status: str = "",
    keyword: str = "",
    start_date: str = "",
    end_date: str = "",
) -> list[dict[str, Any]]:
    task_q = str(task or "").strip().lower()
    status_q = str(status or "").strip().lower()
    kw_q = str(keyword or "").strip().lower()
    start_ep = _date_to_epoch(start_date, end_of_day=False)
    end_ep = _date_to_epoch(end_date, end_of_day=True)
    out: list[dict[str, Any]] = []
    for row in rows:
        task_val = str(row.get("task") or "").lower()
        status_val = str(row.get("status") or "").lower()
        line = json.dumps(row, ensure_ascii=False).lower()
        ts = str(row.get("ts") or "")
        try:
            row_ep = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except Exception:
            row_ep = None
        if task_q and task_q not in task_val:
            continue
        if status_q and status_q != status_val:
            continue
        if kw_q and kw_q not in line:
            continue
        if start_ep is not None and (row_ep is None or row_ep < start_ep):
            continue
        if end_ep is not None and (row_ep is None or row_ep > end_ep):
            continue
        out.append(row)
    return out


def _normalize_schedule(data: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_SCHEDULE)
    src = data if isinstance(data, dict) else {}
    for key in merged:
        item = src.get(key, {}) if isinstance(src.get(key, {}), dict) else {}
        enabled = bool(item.get("enabled", merged[key]["enabled"]))
        cron = str(item.get("cron", "")).strip()
        fallback_minutes = 60
        if "interval_minutes" in item:
            try:
                fallback_minutes = max(1, int(item.get("interval_minutes", 60)))
            except Exception:
                fallback_minutes = 60
        cron = _coerce_cron_expr(cron or merged[key]["cron"], fallback_minutes=fallback_minutes)
        merged[key] = {"enabled": enabled, "cron": cron}
    return merged


def _minutes_to_cron(minutes: int) -> str:
    m = max(1, int(minutes))
    if m <= 59:
        return f"*/{m} * * * *"
    if m < 1440 and m % 60 == 0:
        hours = max(1, min(23, m // 60))
        return f"0 */{hours} * * *"
    if m % 1440 == 0:
        days = m // 1440
        if days <= 1:
            return "0 0 * * *"
        if days <= 31:
            return f"0 0 */{days} * *"
        return "0 0 1 * *"
    return "0 * * * *"


def _coerce_cron_expr(cron_txt: str, fallback_minutes: int = 60) -> str:
    raw = str(cron_txt or "").strip()
    if raw:
        try:
            CronTrigger.from_crontab(raw)
            return raw
        except Exception:
            m = re.match(r"\*/(\d+)\s+\*\s+\*\s+\*\s+\*", raw)
            if m:
                return _minutes_to_cron(int(m.group(1)))
    return _minutes_to_cron(fallback_minutes)


def run_task(task_name: str, cmd: list[str], timeout_s: int = 1800) -> dict[str, Any]:
    ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = TASK_LOG_DIR / f"{task_name}_{ts}.log"
    started = time.time()
    status = "success"
    rc = 0
    out = ""
    err = ""
    try:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False, env=build_runtime_env())
            rc = int(proc.returncode)
            out = proc.stdout or ""
            err = proc.stderr or ""
            if rc != 0:
                status = "failed"
        except FileNotFoundError:
            if cmd and cmd[0] == "docker":
                rc, out, err = run_docker_exec_via_socket(cmd, timeout_s=timeout_s)
                if rc != 0:
                    status = "failed"
            else:
                raise
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        rc = 124
        raw_out = e.stdout or ""
        raw_err = e.stderr or ""
        out = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else str(raw_out)
        err_txt = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)
        err = err_txt + "\nTimeout expired"

    elapsed = round(time.time() - started, 2)
    content = (
        f"[{now_iso()}] task={task_name} status={status} rc={rc} elapsed={elapsed}s\n"
        + "\n--- STDOUT ---\n"
        + out
        + "\n--- STDERR ---\n"
        + err
    )
    log_path.write_text(content, encoding="utf-8")
    event = {
        "task_id": str(uuid.uuid4()),
        "ts": now_iso(),
        "task": task_name,
        "status": status,
        "rc": rc,
        "elapsed_s": elapsed,
        "log_file": str(log_path),
    }
    append_run_history(event)
    return event


def load_schedule() -> dict[str, Any]:
    ensure_dirs()
    if not SCHEDULE_FILE.exists():
        save_schedule(DEFAULT_SCHEDULE)
        return dict(DEFAULT_SCHEDULE)
    try:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return _normalize_schedule(data if isinstance(data, dict) else {})


def save_schedule(data: dict[str, Any]) -> None:
    ensure_dirs()
    normalized = _normalize_schedule(data)
    SCHEDULE_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_task_command(task_name: str, args_line: str = "") -> list[str]:
    args = [a for a in args_line.split(" ") if a.strip()]
    if task_name == "compute_daily":
        return compute_exec_cmd("/app/vectorIngest/run_daily.sh", args)
    if task_name == "compute_worker":
        return compute_exec_cmd("/app/vectorIngest/run_worker.sh", args)
    if task_name == "compute_eh_ingest":
        return compute_exec_cmd("/app/vectorIngest/run_eh_ingest.sh", args)
    if task_name in TASK_COMMANDS:
        base = TASK_COMMANDS[task_name]
        if base and base[0] == "__compute_daily__":
            return compute_exec_cmd("/app/vectorIngest/run_daily.sh", args)
        return base + args
    raise ValueError(f"unsupported task: {task_name}")


def sync_scheduler() -> None:
    cfg = load_schedule()
    desired = {
        "eh_fetch": ["/app/ehCrawler/run_eh_fetch.sh"],
        "lrr_export": ["/app/lrrDataFlush/run_daily_lrr_export.sh"],
        "text_ingest": ["/app/textIngest/run_daily_text_ingest.sh"],
        "compute_daily": compute_exec_cmd("/app/vectorIngest/run_daily.sh"),
    }
    existing = {j.id for j in scheduler.get_jobs()}
    for job_id, cmd in desired.items():
        setting = cfg.get(job_id, {})
        enabled = bool(setting.get("enabled", False))
        cron_expr = _coerce_cron_expr(str(setting.get("cron", "")).strip(), fallback_minutes=60)
        if enabled:
            try:
                trigger = CronTrigger.from_crontab(cron_expr)
            except Exception:
                trigger = CronTrigger.from_crontab("0 * * * *")
            if job_id in existing:
                scheduler.reschedule_job(job_id, trigger=trigger)
            else:
                scheduler.add_job(
                    run_task,
                    trigger=trigger,
                    args=[job_id, cmd],
                    id=job_id,
                    replace_existing=True,
                )
        elif job_id in existing:
            scheduler.remove_job(job_id)


def check_http(url: str, timeout: int = 4) -> tuple[bool, str]:
    if not url:
        return (False, "empty url")
    candidate = str(url).strip()
    parsed = urlparse(candidate)
    if not parsed.scheme:
        candidate = f"http://{candidate}"
    try:
        r = requests.get(candidate, timeout=timeout)
        return (r.ok, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, str(e))


def run_task_async(task_name: str, args_line: str = "") -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    started_at = now_iso()
    item = {
        "task_id": task_id,
        "task": task_name,
        "status": "running",
        "started_at": started_at,
        "updated_at": started_at,
    }
    with task_state_lock:
        task_state[task_id] = item

    def _runner() -> None:
        try:
            cmd = resolve_task_command(task_name, args_line)
            event = run_task(task_name, cmd)
            with task_state_lock:
                task_state[task_id] = {
                    **task_state[task_id],
                    "status": event.get("status", "failed"),
                    "rc": event.get("rc", 1),
                    "elapsed_s": event.get("elapsed_s", 0),
                    "log_file": event.get("log_file", ""),
                    "updated_at": now_iso(),
                }
        except Exception as e:
            with task_state_lock:
                task_state[task_id] = {
                    **task_state[task_id],
                    "status": "failed",
                    "rc": 1,
                    "error": str(e),
                    "updated_at": now_iso(),
                }

    threading.Thread(target=_runner, daemon=True).start()
    return item


def _normalize_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, tuple):
        return [str(x).strip() for x in list(raw) if str(x).strip()]
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    return [s]


def _compute_xp_map(
    mode: str,
    time_basis: str,
    max_points: int,
    days: int,
    k: int,
    topn: int,
    exclude_language_tags: bool,
    exclude_other_tags: bool,
    start_date: str = "",
    end_date: str = "",
    exclude_tags: list[str] | None = None,
    dendro_page: int = 1,
    dendro_page_size: int = 100,
) -> dict[str, Any]:
    horizon_s = int(days * 86400)
    now_ep = int(datetime.now(timezone.utc).timestamp())
    start_ep = _date_to_epoch(start_date, end_of_day=False)
    end_ep = _date_to_epoch(end_date, end_of_day=True)
    if start_ep is None:
        start_ep = now_ep - horizon_s
    if end_ep is None:
        end_ep = now_ep
    if end_ep < start_ep:
        end_ep = start_ep
    exclude_tags_set = {str(x).strip().lower() for x in (exclude_tags or []) if str(x).strip()}
    if mode == "read_history":
        sql = (
            "SELECT DISTINCT w.arcid, w.title, w.tags FROM works w JOIN read_events r ON r.arcid = w.arcid "
            "WHERE r.read_time >= %s AND r.read_time <= %s LIMIT %s"
        )
        rows = query_rows(sql, (int(start_ep), int(end_ep), int(max_points)))
    else:
        basis_col = "eh_posted" if time_basis == "eh_posted" else "date_added"
        sql = (
            f"SELECT w.arcid, w.title, w.tags FROM works w "
            f"WHERE coalesce(w.{basis_col}, 0) >= %s AND coalesce(w.{basis_col}, 0) <= %s LIMIT %s"
        )
        rows = query_rows(sql, (int(start_ep), int(end_ep), int(max_points)))

    if not rows:
        return {"points": [], "clusters": [], "meta": {"reason": "no_data"}}

    lang_prefixes = ("language:", "语言:")
    other_prefixes = ("other:", "misc:", "其他:", "杂项:")
    hard_block_prefixes = ("uploader:", "date_added:", "上传者:", "入库时间:")

    def _keep_tag(tag: str) -> bool:
        low = str(tag).strip().lower()
        if low.startswith(hard_block_prefixes):
            return False
        if exclude_language_tags and low.startswith(lang_prefixes):
            return False
        if exclude_other_tags and low.startswith(other_prefixes):
            return False
        if low in exclude_tags_set:
            return False
        return True

    docs = [" ".join([tg for tg in _normalize_tags(r.get("tags")) if _keep_tag(tg)]) for r in rows]
    if len(docs) < 4 or sum(len(d.strip()) > 0 for d in docs) < 4:
        return {"points": [], "clusters": [], "meta": {"reason": "no_tags"}}

    vec = TfidfVectorizer(max_features=3000, token_pattern=r"[^\s]+")
    X = vec.fit_transform(docs)
    feature_names = vec.get_feature_names_out().tolist()
    n_samples = X.shape[0]
    k_use = min(k, max(2, n_samples // 2))
    km = KMeans(n_clusters=k_use, n_init=10, random_state=42)
    labels = km.fit_predict(X)

    centers = km.cluster_centers_
    cluster_name_map: dict[int, str] = {}
    cluster_top_terms: dict[int, list[str]] = {}
    for cid in range(k_use):
        weights = centers[cid].tolist() if hasattr(centers[cid], "tolist") else list(centers[cid])
        ranked_idx = sorted(range(len(weights)), key=lambda i: weights[i], reverse=True)[:topn]
        top_terms = [feature_names[i] for i in ranked_idx if i < len(feature_names) and weights[i] > 0]
        cluster_top_terms[cid] = top_terms
        cluster_name_map[cid] = " / ".join(top_terms) if top_terms else f"cluster-{cid}"

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X.toarray())

    def _wrap_terms(terms: list[str], line_size: int = 3) -> str:
        if not terms:
            return "-"
        chunks = [terms[i : i + line_size] for i in range(0, len(terms), line_size)]
        return "<br>".join([", ".join(c) for c in chunks])

    def _axis_semantics(comp_idx: int) -> str:
        if comp_idx >= len(pca.components_):
            return "insufficient signal"
        comp = pca.components_[comp_idx]
        ranked_pos = sorted(range(len(comp)), key=lambda i: float(comp[i]), reverse=True)[: min(6, topn * 2)]
        ranked_neg = sorted(range(len(comp)), key=lambda i: float(comp[i]))[: min(6, topn * 2)]
        pos_terms = [feature_names[i] for i in ranked_pos if i < len(feature_names) and float(comp[i]) > 0]
        neg_terms = [feature_names[i] for i in ranked_neg if i < len(feature_names) and float(comp[i]) < 0]
        if not pos_terms and not neg_terms:
            return "insufficient signal"
        return f"+: {_wrap_terms(pos_terms)}<br>-: {_wrap_terms(neg_terms)}"

    x_var = float(pca.explained_variance_ratio_[0]) if len(pca.explained_variance_ratio_) > 0 else 0.0
    y_var = float(pca.explained_variance_ratio_[1]) if len(pca.explained_variance_ratio_) > 1 else 0.0
    x_title = f"PC1 ({round(x_var * 100.0, 1)}% variance) {_axis_semantics(0)}"
    y_title = f"PC2 ({round(y_var * 100.0, 1)}% variance) {_axis_semantics(1)}"

    points: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        cid = int(labels[idx])
        points.append(
            {
                "x": float(coords[idx, 0]),
                "y": float(coords[idx, 1]),
                "cluster_id": cid,
                "cluster": cluster_name_map.get(cid, f"cluster-{cid}"),
                "title": str(row.get("title") or ""),
                "arcid": str(row.get("arcid") or ""),
            }
        )

    clusters = []
    for cid in range(k_use):
        clusters.append(
            {
                "cluster_id": cid,
                "name": cluster_name_map.get(cid, f"cluster-{cid}"),
                "top_terms": cluster_top_terms.get(cid, []),
                "count": int(sum(1 for x in labels if int(x) == cid)),
            }
        )

    dendrogram = {
        "available": False,
        "reason": "need_at_least_4_samples",
        "figure": None,
    }
    try:
        if X.shape[0] >= 4:
            total = X.shape[0]
            page_size = max(20, min(300, int(dendro_page_size)))
            page = max(1, int(dendro_page))
            start = (page - 1) * page_size
            end = min(total, start + page_size)
            dendro_idx = list(range(total))[start:end]
            dense_subset = X[dendro_idx].toarray()
            label_subset: list[str] = []
            for i in dendro_idx:
                title = str(rows[i].get("title") or "").strip()
                label_subset.append((title[:30] + "..") if len(title) > 30 else title)

            linkage_matrix = sch.linkage(dense_subset, method="ward")
            fig = ff.create_dendrogram(
                dense_subset,
                labels=label_subset,
                orientation="left",
                linkagefun=lambda _: linkage_matrix,
            )
            fig.update_layout(
                width=1100,
                height=max(800, len(dendro_idx) * 25),
                margin={"l": 200, "r": 60, "t": 40, "b": 40},
                xaxis_title="Distance",
                yaxis_title="Library Samples",
                showlegend=False,
                hovermode=False,
            )
            dendrogram = {
                "available": True,
                "reason": "",
                "figure": json.loads(json.dumps(fig, cls=PlotlyJSONEncoder)),
                "sample_count": len(dendro_idx),
                "total_count": int(total),
                "page": page,
                "page_size": page_size,
                "pages": max(1, (int(total) + page_size - 1) // page_size),
            }
    except Exception as e:
        dendrogram = {
            "available": False,
            "reason": f"dendrogram_error: {e}",
            "figure": None,
        }

    return {
        "points": points,
        "clusters": clusters,
        "dendrogram": dendrogram,
        "meta": {
            "n_points": len(points),
            "k": k_use,
            "x_variance_ratio": x_var,
            "y_variance_ratio": y_var,
            "x_axis_title": x_title,
            "y_axis_title": y_title,
            "start_epoch": int(start_ep),
            "end_epoch": int(end_ep),
        },
    }


app = FastAPI(title="AutoEhHunter Web API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config/schema")
def get_config_schema() -> dict[str, Any]:
    return {"schema": CONFIG_SPECS}


@app.on_event("startup")
def _on_startup() -> None:
    ensure_dirs()
    if not scheduler.running:
        scheduler.start()
    sync_scheduler()


@app.on_event("shutdown")
def _on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/api/health")
def health() -> dict[str, Any]:
    cfg, _ = resolve_config()
    db_ok = True
    db_error = ""
    total_works = 0
    total_eh = 0
    last_fetch = "-"
    try:
        works = query_rows("SELECT count(*) AS n FROM works")
        eh_works = query_rows("SELECT count(*) AS n FROM eh_works")
        recent = query_rows("SELECT max(last_fetched_at) AS latest FROM eh_works")
        total_works = int((works[0] or {}).get("n") or 0) if works else 0
        total_eh = int((eh_works[0] or {}).get("n") or 0) if eh_works else 0
        last_fetch = str((recent[0] or {}).get("latest") or "-") if recent else "-"
    except Exception as e:
        db_ok = False
        db_error = str(e)

    lrr_base = str(cfg.get("LRR_BASE", "http://lanraragi:3000")).strip().rstrip("/")
    if not urlparse(lrr_base).scheme:
        lrr_base = f"http://{lrr_base}"
    compute_health = str(cfg.get("COMPUTE_HEALTH_URL", "http://autoeh-compute:18080/health"))
    openai_health = str(cfg.get("OPENAI_HEALTH_URL", "")).strip()

    ok_lrr, msg_lrr = check_http(f"{lrr_base}/api/info")
    ok_compute, msg_compute = check_http(compute_health)
    llm = {"ok": None, "message": "n/a"}
    if openai_health:
        ok_llm, msg_llm = check_http(openai_health)
        llm = {"ok": ok_llm, "message": msg_llm}

    return {
        "database": {
            "ok": db_ok,
            "error": db_error,
            "works": total_works,
            "eh_works": total_eh,
            "last_fetch": last_fetch,
        },
        "services": {
            "lrr": {"ok": ok_lrr, "message": msg_lrr},
            "compute": {"ok": ok_compute, "message": msg_compute},
            "llm": llm,
        },
    }


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    cfg, meta = resolve_config()
    values: dict[str, Any] = {}
    secret_state: dict[str, bool] = {}
    for key, spec in CONFIG_SPECS.items():
        if spec.get("secret", False):
            values[key] = ""
            secret_state[key] = bool(str(cfg.get(key, "")).strip())
        else:
            values[key] = cfg.get(key, _normalize_value(key, spec.get("default", "")))
    return {"values": values, "secret_state": secret_state, "meta": meta}


@app.put("/api/config")
def update_config(req: ConfigUpdateRequest) -> dict[str, Any]:
    cfg, _ = resolve_config()
    new_cfg = dict(cfg)
    for key, spec in CONFIG_SPECS.items():
        if key not in req.values:
            continue
        v = req.values[key]
        if spec.get("secret", False) and not str(v or "").strip():
            continue
        new_cfg[key] = _normalize_value(key, v)

    new_cfg["POSTGRES_DSN"] = _build_dsn(new_cfg)
    _save_json_config(new_cfg)
    ok_db, db_err = _save_db_config(new_cfg.get("POSTGRES_DSN", ""), new_cfg)
    return {"ok": True, "saved_json": True, "saved_db": ok_db, "db_error": db_err}


@app.get("/api/schedule")
def get_schedule() -> dict[str, Any]:
    return {"schedule": load_schedule()}


@app.put("/api/schedule")
def update_schedule(req: ScheduleUpdateRequest) -> dict[str, Any]:
    merged = _normalize_schedule(req.schedule)
    save_schedule(merged)
    sync_scheduler()
    return {"ok": True, "schedule": merged}


@app.post("/api/task/run")
def trigger_task(req: TaskRunRequest) -> dict[str, Any]:
    try:
        item = run_task_async(req.task, req.args)
        return {"ok": True, "task": item}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    with task_state_lock:
        items = list(task_state.values())
    items.sort(key=lambda x: str(x.get("started_at", "")), reverse=True)
    return {"tasks": items[:200]}


@app.get("/api/tasks/stream")
def stream_tasks() -> StreamingResponse:
    def event_stream():
        while True:
            with task_state_lock:
                payload = json.dumps({"tasks": list(task_state.values())}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            time.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/audit/history")
def audit_history(
    limit: int = Query(default=300, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    task: str = Query(default=""),
    status: str = Query(default=""),
    keyword: str = Query(default=""),
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
) -> dict[str, Any]:
    rows = load_run_history(limit=max(2000, limit + offset + 200))
    rows = _filter_run_history(
        rows,
        task=task,
        status=status,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    rows.sort(key=lambda x: str(x.get("ts", "")), reverse=True)
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "rows": page,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@app.get("/api/audit/logs")
def audit_logs() -> dict[str, Any]:
    logs = sorted(TASK_LOG_DIR.glob("*.log"), reverse=True)
    return {"logs": [p.name for p in logs]}


@app.get("/api/audit/tasks")
def audit_tasks(limit: int = Query(default=5000, ge=100, le=20000)) -> dict[str, Any]:
    rows = load_run_history(limit=limit)
    names = sorted({str(r.get("task") or "").strip() for r in rows if str(r.get("task") or "").strip()})
    return {"tasks": names}


@app.get("/api/audit/logs/{name}")
def audit_log_content(name: str) -> dict[str, Any]:
    safe_name = Path(name).name
    p = TASK_LOG_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="log not found")
    txt = p.read_text(encoding="utf-8", errors="replace")
    return {"name": safe_name, "content": txt[-12000:]}


@app.get("/api/audit/logs/{name}/tail")
def audit_log_tail(
    name: str,
    offset: int = Query(default=0, ge=0),
    chunk_size: int = Query(default=8000, ge=256, le=100000),
) -> dict[str, Any]:
    safe_name = Path(name).name
    p = TASK_LOG_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="log not found")
    txt = p.read_text(encoding="utf-8", errors="replace")
    total = len(txt)
    start = min(offset, total)
    end = min(start + chunk_size, total)
    return {
        "name": safe_name,
        "offset": start,
        "next_offset": end,
        "total": total,
        "chunk": txt[start:end],
        "eof": end >= total,
    }


@app.get("/api/xp-map")
def xp_map(
    mode: str = Query(default="read_history"),
    time_basis: str = Query(default="eh_posted"),
    max_points: int = Query(default=1800, ge=200, le=5000),
    days: int = Query(default=30, ge=1, le=3650),
    k: int = Query(default=3, ge=2, le=8),
    topn: int = Query(default=3, ge=2, le=6),
    exclude_language_tags: bool = Query(default=True),
    exclude_other_tags: bool = Query(default=False),
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
    exclude_tags: str = Query(default=""),
    dendro_page: int = Query(default=1, ge=1, le=1000),
    dendro_page_size: int = Query(default=100, ge=20, le=300),
) -> dict[str, Any]:
    if mode not in ("read_history", "inventory"):
        raise HTTPException(status_code=400, detail="invalid mode")
    if time_basis not in ("read_time", "eh_posted", "date_added"):
        raise HTTPException(status_code=400, detail="invalid time_basis")
    ex_tags = [x.strip().lower() for x in str(exclude_tags or "").split(",") if x.strip()]
    return _compute_xp_map(
        mode,
        time_basis,
        max_points,
        days,
        k,
        topn,
        exclude_language_tags,
        exclude_other_tags,
        start_date=start_date,
        end_date=end_date,
        exclude_tags=ex_tags,
        dendro_page=dendro_page,
        dendro_page_size=dendro_page_size,
    )


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    raise HTTPException(status_code=404, detail="frontend not built")
