import math
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .db_service import db_dsn

_KEY_RE = re.compile(r"^eh:(\d+):([a-zA-Z0-9]+)$")


def _parse_vector_text(text: str) -> list[float]:
    s = str(text or "").strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    out: list[float] = []
    for p in s.split(","):
        v = str(p or "").strip()
        if not v:
            continue
        try:
            out.append(float(v))
        except Exception:
            continue
    return out


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"


def _normalize_l2(vec: list[float]) -> list[float]:
    if not vec:
        return []
    s = 0.0
    for x in vec:
        s += float(x) * float(x)
    if s <= 0:
        return vec
    inv = 1.0 / math.sqrt(s)
    return [float(x) * inv for x in vec]


def _project_1024(vec: list[float]) -> list[float]:
    if len(vec) >= 1024:
        return [float(x) for x in vec[:1024]]
    if not vec:
        return []
    return [float(x) for x in vec] + [0.0] * (1024 - len(vec))


def _feedback_alpha(action_type: str) -> float:
    t = str(action_type or "").strip().lower()
    if t == "click":
        return 0.05
    if t == "impression":
        return 0.01
    if t == "dislike":
        return -0.15
    if t == "read":
        return -0.30
    return 0.0


def _parse_key(key: str) -> tuple[int, str]:
    m = _KEY_RE.match(str(key or "").strip())
    if not m:
        return 0, ""
    return int(m.group(1)), str(m.group(2) or "").strip()


def _mix_visual_vectors(cover: list[float], page: list[float]) -> list[float]:
    c = list(cover or [])
    p = list(page or [])
    if c and p and len(c) == len(p):
        return _normalize_l2([(0.6 * float(c[i]) + 0.4 * float(p[i])) for i in range(len(c))])
    if c:
        return _normalize_l2(c)
    if p:
        return _normalize_l2(p)
    return []


def get_user_profile_vector(user_id: str) -> list[float]:
    dsn = db_dsn()
    if not dsn:
        return []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT base_vector::text AS vec FROM user_profiles WHERE user_id = %s LIMIT 1", (str(user_id or "default_user"),))
            row = cur.fetchone() or {}
    vec = _parse_vector_text(str(row.get("vec") or ""))
    return vec if len(vec) == 1024 else []


def apply_feedback_events(user_id: str, events: list[dict[str, Any]]) -> None:
    dsn = db_dsn()
    if not dsn:
        return
    uid = str(user_id or "default_user")
    valid_events = []
    keys: set[str] = set()
    for e in events or []:
        arcid = str((e or {}).get("arcid") or "").strip()
        action = str((e or {}).get("action_type") or "").strip().lower()
        try:
            weight = float((e or {}).get("weight") or 1.0)
        except Exception:
            weight = 1.0
        alpha = _feedback_alpha(action)
        if not arcid or alpha == 0.0:
            continue
        if weight <= 0:
            weight = 1.0
        if weight > 10:
            weight = 10.0
        valid_events.append({"arcid": arcid, "action_type": action, "weight": float(weight)})
        keys.add(arcid)
    if not valid_events:
        return

    gid_tok: list[tuple[int, str]] = []
    work_arcids: list[str] = []
    for key in keys:
        gid, tok = _parse_key(key)
        if gid and tok:
            gid_tok.append((gid, tok))
        else:
            work_arcids.append(str(key).strip())

    vec_map: dict[str, list[float]] = {}
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT base_vector::text AS vec FROM user_profiles WHERE user_id = %s LIMIT 1", (uid,))
            row = cur.fetchone() or {}
            base = _parse_vector_text(str(row.get("vec") or ""))
            if len(base) != 1024:
                base = [0.0] * 1024

            for gid, tok in gid_tok:
                cur.execute(
                    "SELECT cover_embedding::text AS vec FROM eh_works WHERE gid = %s AND token = %s LIMIT 1",
                    (int(gid), str(tok)),
                )
                r = cur.fetchone() or {}
                v = _project_1024(_parse_vector_text(str(r.get("vec") or "")))
                if len(v) == 1024:
                    vec_map[f"eh:{gid}:{tok.lower()}"] = _normalize_l2(v)

            for arcid in work_arcids:
                cur.execute(
                    "SELECT visual_embedding::text AS cover_vec, page_visual_embedding::text AS page_vec "
                    "FROM works WHERE arcid = %s LIMIT 1",
                    (str(arcid),),
                )
                r = cur.fetchone() or {}
                cover_v = _parse_vector_text(str(r.get("cover_vec") or ""))
                page_v = _parse_vector_text(str(r.get("page_vec") or ""))
                mixed = _mix_visual_vectors(cover_v, page_v)
                v = _project_1024(mixed)
                if len(v) == 1024 and any(abs(float(x)) > 1e-12 for x in v):
                    vec_map[str(arcid).lower()] = _normalize_l2(v)

            changed = False
            for e in valid_events:
                key = str(e.get("arcid") or "").strip().lower()
                vec = vec_map.get(key)
                if not vec:
                    continue
                alpha = _feedback_alpha(str(e.get("action_type") or "")) * float(e.get("weight") or 1.0)
                if alpha == 0.0:
                    continue
                for i in range(1024):
                    base[i] = float(base[i]) + alpha * float(vec[i])
                changed = True

            if not changed:
                return
            base = _normalize_l2(base)
            cur.execute(
                "INSERT INTO user_profiles(user_id, base_vector, updated_at) VALUES (%s, %s::vector, now()) "
                "ON CONFLICT (user_id) DO UPDATE SET base_vector = EXCLUDED.base_vector, updated_at = now()",
                (uid, _vector_literal(base)),
            )
        conn.commit()


def clear_user_interactions(user_id: str, action_types: tuple[str, ...] | list[str] = ("click", "impression")) -> int:
    dsn = db_dsn()
    if not dsn:
        return 0
    uid = str(user_id or "default_user")
    acts = [str(x or "").strip().lower() for x in (action_types or []) if str(x or "").strip()]
    if not acts:
        return 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_interactions WHERE user_id = %s AND action_type = ANY(%s)", (uid, acts))
            deleted = int(cur.rowcount or 0)
        conn.commit()
    return deleted


def clear_user_profile(user_id: str) -> int:
    dsn = db_dsn()
    if not dsn:
        return 0
    uid = str(user_id or "default_user")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_profiles WHERE user_id = %s", (uid,))
            deleted = int(cur.rowcount or 0)
        conn.commit()
    return deleted
