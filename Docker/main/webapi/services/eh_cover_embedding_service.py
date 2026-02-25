import json
import sys
import threading
import time
import traceback
from typing import Any

import psycopg
import requests

from .config_service import resolve_config
from .db_service import db_dsn
from .vision_service import _embed_image_siglip


_worker_thread: threading.Thread | None = None
_worker_stop = threading.Event()
_worker_lock = threading.Lock()


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _pick_candidates(conn: psycopg.Connection, include_fail: bool, limit: int) -> list[dict[str, Any]]:
    statuses = ["pending", "processing"]
    if include_fail:
        statuses.append("fail")
    sql = (
        "WITH picked AS ("
        "  SELECT gid, token, eh_url, ex_url, raw "
        "  FROM eh_works "
        "  WHERE cover_embedding IS NULL "
        "    AND cover_embedding_status = ANY(%s) "
        "  ORDER BY posted DESC NULLS LAST, updated_at DESC "
        "  LIMIT %s "
        "  FOR UPDATE SKIP LOCKED"
        ") "
        "UPDATE eh_works w "
        "SET cover_embedding_status = 'processing', updated_at = now() "
        "FROM picked p "
        "WHERE w.gid = p.gid AND w.token = p.token "
        "RETURNING p.gid, p.token, p.eh_url, p.ex_url, p.raw"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (statuses, int(max(1, limit))))
        rows = cur.fetchall() or []
    out: list[dict[str, Any]] = []
    for row in rows:
        gid, token, eh_url, ex_url, raw = row
        payload = raw
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        out.append(
            {
                "gid": int(gid),
                "token": str(token or ""),
                "eh_url": str(eh_url or ""),
                "ex_url": str(ex_url or ""),
                "raw": payload,
            }
        )
    return out


def _fetch_cover_bytes(session: requests.Session, thumb_url: str, referer: str, timeout_s: int) -> bytes:
    headers = {"Referer": str(referer or "")} if referer else {}
    resp = session.get(str(thumb_url), headers=headers, timeout=max(5, int(timeout_s)))
    resp.raise_for_status()
    return resp.content


def _mark_success(conn: psycopg.Connection, gid: int, token: str, vec: list[float]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE eh_works "
            "SET cover_embedding = %s::vector, cover_embedding_status = 'complete', updated_at = now() "
            "WHERE gid = %s AND token = %s",
            (_vector_literal(vec), int(gid), str(token)),
        )


def _mark_fail(conn: psycopg.Connection, gid: int, token: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE eh_works "
            "SET cover_embedding_status = 'fail', updated_at = now() "
            "WHERE gid = %s AND token = %s",
            (int(gid), str(token)),
        )


def run_eh_cover_embedding_once(*, include_fail: bool = False, limit: int = 12) -> dict[str, int]:
    cfg, _ = resolve_config()
    dsn = str(db_dsn() or "").strip()
    if not dsn:
        return {"picked": 0, "completed": 0, "failed": 0}

    sleep_s = max(0.0, float(cfg.get("EH_REQUEST_SLEEP", 4.0)))
    timeout_s = int(float(cfg.get("EH_REQUEST_SLEEP", 4.0)) * 8 + 20)
    model_id = str(cfg.get("SIGLIP_MODEL") or "google/siglip-so400m-patch14-384").strip()
    user_agent = str(cfg.get("EH_USER_AGENT") or "AutoEhHunter/1.0").strip()
    cookie = str(cfg.get("EH_COOKIE") or "").strip()

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent or "AutoEhHunter/1.0"})
    if cookie:
        session.headers.update({"Cookie": cookie})

    picked = 0
    completed = 0
    failed = 0

    with psycopg.connect(dsn) as conn:
        candidates = _pick_candidates(conn, include_fail=include_fail, limit=limit)
        conn.commit()
        picked = len(candidates)
        for item in candidates:
            gid = int(item.get("gid") or 0)
            token = str(item.get("token") or "")
            raw = item.get("raw") or {}
            thumb = str((raw.get("thumb") if isinstance(raw, dict) else "") or "").strip()
            referer = str(item.get("eh_url") or item.get("ex_url") or "").strip()
            try:
                if not thumb:
                    raise RuntimeError("thumb missing")
                if sleep_s > 0:
                    time.sleep(sleep_s)
                img = _fetch_cover_bytes(session, thumb, referer, timeout_s=timeout_s)
                vec = _embed_image_siglip(img, model_id)
                if not vec:
                    raise RuntimeError("embedding empty")
                _mark_success(conn, gid, token, vec)
                conn.commit()
                completed += 1
            except Exception as e:
                print(f"[eh_cover_embedding] gid={gid} token={token} failed: {e}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                _mark_fail(conn, gid, token)
                conn.commit()
                failed += 1

    return {"picked": picked, "completed": completed, "failed": failed}


def _worker_loop() -> None:
    while not _worker_stop.is_set():
        try:
            stats = run_eh_cover_embedding_once(include_fail=False, limit=10)
            if int(stats.get("picked") or 0) > 0:
                continue
        except Exception as e:
            print(f"[eh_cover_embedding] worker loop error: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        _worker_stop.wait(8.0)


def start_eh_cover_embedding_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(target=_worker_loop, name="eh-cover-embed-worker", daemon=True)
        _worker_thread.start()


def stop_eh_cover_embedding_worker() -> None:
    _worker_stop.set()


def reset_failed_eh_cover_embeddings() -> int:
    dsn = str(db_dsn() or "").strip()
    if not dsn:
        return 0
    sql = (
        "UPDATE eh_works "
        "SET cover_embedding_status = 'pending', updated_at = now() "
        "WHERE cover_embedding IS NULL AND cover_embedding_status = 'fail'"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            n = int(cur.rowcount or 0)
        conn.commit()
    return n
