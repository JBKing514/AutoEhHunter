import math
import threading
import time
from typing import Any

from .db_service import query_rows
from .recommend_profile_service import get_user_profile_vector
from .search_service import _item_from_work


def _parse_vector_text(text: str) -> list[float]:
    s = str(text or "").strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    out: list[float] = []
    for part in [x.strip() for x in s.split(",") if x.strip()]:
        try:
            out.append(float(part))
        except Exception:
            continue
    return out


def _normalize_l2(vec: list[float]) -> list[float]:
    if not vec:
        return []
    s = 0.0
    for x in vec:
        s += float(x) * float(x)
    if s <= 0:
        return []
    inv = 1.0 / math.sqrt(s)
    return [float(x) * inv for x in vec]


def _mix_work_visual(cover_vec: list[float], page_vec: list[float]) -> list[float]:
    c = list(cover_vec or [])
    p = list(page_vec or [])
    if c and p and len(c) == len(p):
        return _normalize_l2([(0.6 * float(c[i]) + 0.4 * float(p[i])) for i in range(len(c))])
    if c:
        return _normalize_l2(c)
    if p:
        return _normalize_l2(p)
    return []


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n <= 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        na += av * av
        nb += bv * bv
    if na <= 0 or nb <= 0:
        return 0.0
    return float(dot / math.sqrt(na * nb))


def _tag_profile_scores() -> dict[str, float]:
    rows = query_rows(
        "SELECT w.tags FROM read_events e JOIN works w ON w.arcid = e.arcid ORDER BY e.read_time DESC LIMIT 2000"
    )
    if not rows:
        rows = query_rows("SELECT tags FROM works ORDER BY COALESCE(lastreadtime, date_added, eh_posted, 0) DESC LIMIT 2000")
    counts: dict[str, int] = {}
    for r in rows:
        for t in (r.get("tags") or []):
            s = str(t or "").strip()
            if not s:
                continue
            counts[s] = counts.get(s, 0) + 1
    if not counts:
        return {}
    mx = max(counts.values())
    if mx <= 0:
        return {}
    return {k: math.log1p(float(v)) / math.log1p(float(mx)) for k, v in counts.items()}


def build_local_recommendation_items(
    cfg: dict[str, Any],
    *,
    user_id: str = "default_user",
    sort_order: str = "desc",
) -> dict[str, Any]:
    tag_scores = _tag_profile_scores()
    profile_vec = list(get_user_profile_vector(str(user_id or "default_user")) or [])
    profile_vec = _normalize_l2(profile_vec)

    tag_weight = max(0.0, float(cfg.get("REC_TAG_WEIGHT", 0.55)))
    visual_weight = max(0.0, float(cfg.get("REC_VISUAL_WEIGHT", 0.45)))
    total_w = tag_weight + visual_weight
    if total_w <= 0:
        tag_weight, visual_weight = 0.55, 0.45
        total_w = 1.0
    tag_weight /= total_w
    visual_weight /= total_w
    floor = max(0.0, min(0.4, float(cfg.get("REC_TAG_FLOOR_SCORE", 0.08))))

    rows = query_rows(
        "SELECT arcid, title, tags, eh_posted, date_added, lastreadtime, "
        "visual_embedding::text as cover_vec, page_visual_embedding::text as page_vec "
        "FROM works "
        "WHERE visual_embedding IS NOT NULL OR page_visual_embedding IS NOT NULL"
    )
    scored: list[dict[str, Any]] = []
    for r in rows:
        tags = [str(x) for x in (r.get("tags") or []) if str(x).strip()]
        tscore = float(sum(float(tag_scores.get(t, floor)) for t in tags) / len(tags)) if tags else float(floor)
        vec = _mix_work_visual(_parse_vector_text(str(r.get("cover_vec") or "")), _parse_vector_text(str(r.get("page_vec") or "")))
        vscore = 0.0
        if profile_vec and vec:
            vscore = max(0.0, min(1.0, (_cosine(profile_vec, vec) + 1.0) * 0.5))
        score = (tag_weight * tscore) + (visual_weight * vscore)
        scored.append({**r, "score": float(score)})

    rev = str(sort_order or "desc").strip().lower() != "asc"
    scored.sort(key=lambda x: float(x.get("score") or 0.0), reverse=rev)
    return {
        "items": [_item_from_work(x, cfg) | {"signals": {"mode": "local_xp", "score": float(x.get("score") or 0.0)}} for x in scored],
        "meta": {
            "mode": "local_xp_sort",
            "sort_order": "desc" if rev else "asc",
            "total": len(scored),
        },
    }


_local_cache_lock = threading.Lock()
_local_cache: dict[str, Any] = {"built_at": 0.0, "key": "", "payload": {"items": [], "meta": {}}}


def get_local_recommendation_items_cached(cfg: dict[str, Any], *, user_id: str = "default_user", sort_order: str = "desc") -> dict[str, Any]:
    ttl = max(60, int(cfg.get("REC_CLUSTER_CACHE_TTL_S", 900)))
    key = "|".join(
        [
            str(user_id or "default_user"),
            str(sort_order or "desc"),
            str(cfg.get("REC_TAG_WEIGHT")),
            str(cfg.get("REC_VISUAL_WEIGHT")),
            str(cfg.get("REC_TAG_FLOOR_SCORE")),
            str(cfg.get("REC_PROFILE_DAYS")),
        ]
    )
    now_t = time.time()
    with _local_cache_lock:
        if _local_cache.get("key") == key and (now_t - float(_local_cache.get("built_at") or 0.0) <= ttl):
            return {
                "items": list((_local_cache.get("payload") or {}).get("items") or []),
                "meta": dict((_local_cache.get("payload") or {}).get("meta") or {}),
            }
    payload = build_local_recommendation_items(cfg, user_id=user_id, sort_order=sort_order)
    with _local_cache_lock:
        _local_cache["built_at"] = now_t
        _local_cache["key"] = key
        _local_cache["payload"] = payload
    return payload
