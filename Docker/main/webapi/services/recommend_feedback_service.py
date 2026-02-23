import re
import threading
from typing import Any

import psycopg

from .db_service import db_dsn, query_rows
from .recommend_profile_service import apply_feedback_events, clear_user_interactions, clear_user_profile

_GALLERY_RE = re.compile(r"/g/(\d+)/([A-Za-z0-9]+)/")
_ACTION_TYPES_READY = False
_ACTION_TYPES_LOCK = threading.Lock()


def _ensure_action_types(dsn: str) -> None:
    global _ACTION_TYPES_READY
    if _ACTION_TYPES_READY:
        return
    with _ACTION_TYPES_LOCK:
        if _ACTION_TYPES_READY:
            return
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DO $$ "
                    "BEGIN "
                    "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_interactions_action_type_chk') THEN "
                    "    ALTER TABLE user_interactions DROP CONSTRAINT user_interactions_action_type_chk; "
                    "  END IF; "
                    "  ALTER TABLE user_interactions "
                    "  ADD CONSTRAINT user_interactions_action_type_chk "
                    "  CHECK (action_type IN ('click', 'read', 'dislike', 'impression')); "
                    "EXCEPTION WHEN duplicate_object THEN "
                    "  NULL; "
                    "END $$"
                )
            conn.commit()
        _ACTION_TYPES_READY = True


def recommendation_key(gid: int | str | None, token: str | None) -> str:
    gid_s = str(gid or "").strip()
    tok = str(token or "").strip().lower()
    if not gid_s or not tok:
        return ""
    return f"eh:{gid_s}:{tok}"


def parse_gallery_identity(gid: int | None = None, token: str = "", eh_url: str = "", ex_url: str = "") -> tuple[str, str]:
    gid_s = str(gid or "").strip()
    tok = str(token or "").strip()
    if gid_s and tok:
        return gid_s, tok
    for url in (eh_url, ex_url):
        m = _GALLERY_RE.search(str(url or "").strip())
        if m:
            return str(m.group(1) or "").strip(), str(m.group(2) or "").strip()
    return "", ""


def get_action_counts(user_id: str, keys: list[str], action_type: str) -> dict[str, int]:
    key_list = [str(x or "").strip() for x in (keys or []) if str(x or "").strip()]
    if not key_list:
        return {}
    action = str(action_type or "").strip().lower()
    if action not in {"click", "impression", "read", "dislike"}:
        return {}
    rows = query_rows(
        "SELECT arcid, count(*)::int AS n FROM user_interactions "
        "WHERE user_id = %s AND action_type = %s AND arcid = ANY(%s) "
        "GROUP BY arcid",
        (str(user_id or "default_user"), action, key_list),
    )
    out: dict[str, int] = {}
    for row in rows:
        k = str(row.get("arcid") or "").strip()
        if not k:
            continue
        try:
            out[k] = int(row.get("n") or 0)
        except Exception:
            out[k] = 0
    return out


def get_interaction_revision(user_id: str) -> str:
    rows = query_rows(
        "SELECT action_type, count(*)::int AS n, max(created_at) AS latest "
        "FROM user_interactions "
        "WHERE user_id = %s AND action_type IN ('click', 'impression', 'dislike', 'read') "
        "GROUP BY action_type",
        (str(user_id or "default_user"),),
    )
    click_n = 0
    impr_n = 0
    dislike_n = 0
    read_n = 0
    latest_s = ""
    for row in rows:
        t = str(row.get("action_type") or "").strip().lower()
        n = int(row.get("n") or 0)
        if t == "click":
            click_n = n
        elif t == "impression":
            impr_n = n
        elif t == "dislike":
            dislike_n = n
        elif t == "read":
            read_n = n
        latest = row.get("latest")
        iso = getattr(latest, "isoformat", None)
        cur_s = str(iso() if callable(iso) else (latest or ""))
        if cur_s > latest_s:
            latest_s = cur_s
    return f"c={click_n}|i={impr_n}|d={dislike_n}|r={read_n}|t={latest_s}"


def record_recommend_click(*, user_id: str, gid: int | None, token: str, eh_url: str = "", ex_url: str = "", weight: float = 1.0) -> dict[str, Any]:
    gid_s, tok = parse_gallery_identity(gid=gid, token=token, eh_url=eh_url, ex_url=ex_url)
    key = recommendation_key(gid_s, tok)
    if not key:
        return {"ok": False, "recorded": False, "reason": "invalid gallery identity"}

    dsn = db_dsn()
    if not dsn:
        return {"ok": False, "recorded": False, "reason": "missing dsn"}
    _ensure_action_types(dsn)

    w = float(weight)
    if w <= 0:
        w = 1.0
    if w > 10.0:
        w = 10.0

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_interactions(user_id, arcid, action_type, weight) VALUES (%s, %s, 'click', %s)",
                (str(user_id or "default_user"), key, float(w)),
            )
        conn.commit()
    apply_feedback_events(str(user_id or "default_user"), [{"arcid": key, "action_type": "click", "weight": float(w)}])
    return {"ok": True, "recorded": True, "arcid": key}


def record_recommend_impressions(*, user_id: str, items: list[dict[str, Any]], weight: float = 1.0) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        return {"ok": False, "recorded": 0, "reason": "missing dsn"}
    _ensure_action_types(dsn)
    rows: list[tuple[str, str, float]] = []
    w = float(weight)
    if w <= 0:
        w = 1.0
    if w > 10.0:
        w = 10.0
    seen: set[str] = set()
    for it in items or []:
        gid_s, tok = parse_gallery_identity(
            gid=int(it.get("gid") or 0) if str(it.get("gid") or "").strip() else None,
            token=str(it.get("token") or ""),
            eh_url=str(it.get("eh_url") or ""),
            ex_url=str(it.get("ex_url") or ""),
        )
        key = recommendation_key(gid_s, tok)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append((str(user_id or "default_user"), key, float(w)))
    if not rows:
        return {"ok": True, "recorded": 0}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO user_interactions(user_id, arcid, action_type, weight) VALUES (%s, %s, 'impression', %s)",
                rows,
            )
        conn.commit()
    apply_feedback_events(
        str(user_id or "default_user"),
        [{"arcid": arcid, "action_type": "impression", "weight": float(v)} for _, arcid, v in rows],
    )
    return {"ok": True, "recorded": len(rows)}


def record_recommend_dislike(*, user_id: str, gid: int | None, token: str, eh_url: str = "", ex_url: str = "", weight: float = 1.0) -> dict[str, Any]:
    gid_s, tok = parse_gallery_identity(gid=gid, token=token, eh_url=eh_url, ex_url=ex_url)
    key = recommendation_key(gid_s, tok)
    if not key:
        return {"ok": False, "recorded": False, "reason": "invalid gallery identity"}
    dsn = db_dsn()
    if not dsn:
        return {"ok": False, "recorded": False, "reason": "missing dsn"}
    _ensure_action_types(dsn)
    w = float(weight)
    if w <= 0:
        w = 1.0
    if w > 10.0:
        w = 10.0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_interactions(user_id, arcid, action_type, weight) VALUES (%s, %s, 'dislike', %s)",
                (str(user_id or "default_user"), key, float(w)),
            )
        conn.commit()
    apply_feedback_events(str(user_id or "default_user"), [{"arcid": key, "action_type": "dislike", "weight": float(w)}])
    return {"ok": True, "recorded": True, "arcid": key}


def clear_recommend_clicks(user_id: str) -> dict[str, Any]:
    deleted = clear_user_interactions(str(user_id or "default_user"), ("click", "impression"))
    return {"ok": True, "deleted": deleted}


def clear_recommend_profile(user_id: str) -> dict[str, Any]:
    deleted = clear_user_profile(str(user_id or "default_user"))
    return {"ok": True, "deleted": deleted}
