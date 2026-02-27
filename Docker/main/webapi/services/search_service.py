import hashlib
import os
import re
import threading
import time
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException

from ..core.config_values import as_bool as _as_bool
from ..core.constants import THUMB_CACHE_DIR
from .ai_provider import _extract_tags_by_llm, _llm_timeout_s, _provider_embedding
from .config_service import ensure_dirs, resolve_config, _runtime_tzinfo
from .db_service import query_rows
from .vision_service import _embed_image_siglip, _embed_text_siglip, _model_status


def _thumb_cache_file(key: str):
    digest = hashlib.sha256(str(key).encode("utf-8", errors="ignore")).hexdigest()
    return THUMB_CACHE_DIR / f"{digest}.bin"


def _cache_read(key: str) -> bytes | None:
    p = _thumb_cache_file(key)
    try:
        if p.exists() and p.is_file() and p.stat().st_size > 0:
            return p.read_bytes()
    except Exception:
        return None
    return None


def _cache_write(key: str, data: bytes) -> None:
    if not data:
        return
    ensure_dirs()
    p = _thumb_cache_file(key)
    tmp = p.with_suffix(f".{time.time_ns()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, p)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return


def _thumb_cache_stats() -> dict[str, Any]:
    ensure_dirs()
    total = 0
    count = 0
    latest = 0.0
    for p in THUMB_CACHE_DIR.glob("*.bin"):
        try:
            st = p.stat()
            total += int(st.st_size)
            count += 1
            latest = max(latest, float(st.st_mtime))
        except Exception:
            continue
    return {
        "files": count,
        "bytes": total,
        "mb": round(total / (1024 * 1024), 2),
        "latest_at": datetime.fromtimestamp(latest, tz=_runtime_tzinfo()).isoformat(timespec="seconds") if latest > 0 else "-",
    }


def _clear_thumb_cache() -> dict[str, Any]:
    ensure_dirs()
    deleted = 0
    freed = 0
    for p in THUMB_CACHE_DIR.glob("*.bin"):
        try:
            st = p.stat()
            freed += int(st.st_size)
            p.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            continue
    return {"deleted": deleted, "freed_bytes": freed, "freed_mb": round(freed / (1024 * 1024), 2)}


def _contains_cjk(s: str) -> bool:
    for ch in str(s or ""):
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            return True
    return False


def _tag_matches_ui_lang(tag: str, ui_lang: str) -> bool:
    zh = str(ui_lang or "zh").lower().startswith("zh")
    has_cjk = _contains_cjk(tag)
    return has_cjk if zh else (not has_cjk)


def _tags_for_ui_lang(tags: list[str], ui_lang: str, fallback_all: bool = False) -> list[str]:
    filtered = [t for t in (tags or []) if _tag_matches_ui_lang(str(t or ""), ui_lang)]
    if filtered:
        return filtered
    return list(tags or []) if fallback_all else []


def _flatten_floats(values: Any) -> list[float]:
    out: list[float] = []
    if isinstance(values, (list, tuple)):
        for v in values:
            out.extend(_flatten_floats(v))
        return out
    try:
        out.append(float(values))
    except Exception:
        return []
    return out


def _vector_literal(vec: list[float]) -> str:
    flat = _flatten_floats(vec)
    return "[" + ",".join(repr(float(x)) for x in flat) + "]"


def _parse_vector_text(text: str) -> list[float]:
    s = str(text or "").strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    if not s.strip():
        return []
    out: list[float] = []
    for part in re.split(r"\s*,\s*", s.strip()):
        if not part:
            continue
        try:
            out.append(float(part))
        except Exception:
            continue
    return out


def _extract_source_urls(tags: list[str]) -> tuple[str, str]:
    eh_url = ""
    ex_url = ""
    for tag in tags or []:
        s = str(tag or "").strip()
        if not s.lower().startswith("source:"):
            continue
        v = s.split(":", 1)[1].strip()
        if not v:
            continue
        if not v.startswith("http://") and not v.startswith("https://"):
            v = f"https://{v}"
        if "exhentai.org" in v:
            ex_url = ex_url or v
        elif "e-hentai.org" in v:
            eh_url = eh_url or v
    return eh_url, ex_url


def _prefer_ex(cfg: dict[str, Any]) -> bool:
    base = str(cfg.get("EH_BASE_URL") or "").strip().lower()
    cookie = str(cfg.get("EH_COOKIE") or "").strip()
    return ("exhentai.org" in base) and bool(cookie)


def _prefer_link(eh_url: str, ex_url: str, cfg: dict[str, Any]) -> str:
    eh_u = str(eh_url or "").strip()
    ex_u = str(ex_url or "").strip()
    if _prefer_ex(cfg):
        if not ex_u and eh_u and "e-hentai.org" in eh_u:
            ex_u = eh_u.replace("https://e-hentai.org/", "https://exhentai.org/")
        return ex_u or eh_u
    return eh_u or ex_u


def _category_from_tags(tags: list[str], fallback: str = "") -> str:
    cat_set = {
        "doujinshi",
        "manga",
        "image set",
        "game cg",
        "artist cg",
        "cosplay",
        "non-h",
        "asian porn",
        "western",
        "misc",
    }
    fb = str(fallback or "").strip().lower()
    if fb in cat_set:
        return fb
    for t in tags or []:
        raw = str(t or "").strip().lower()
        if not raw:
            continue
        if raw in cat_set:
            return raw
        if raw.startswith("category:"):
            c = raw.split(":", 1)[1].strip()
            if c in cat_set:
                return c
    return ""


def _norm_epoch(v: Any) -> int | None:
    try:
        n = int(v)
    except Exception:
        return None
    if n >= 100000000000:
        n = n // 1000
    if n <= 0:
        return None
    return n


def _item_from_work(row: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    tags = [str(x) for x in (row.get("tags") or [])]
    eh_url, ex_url = _extract_source_urls(tags)
    cfg_use = cfg or resolve_config()[0]
    category = _category_from_tags(tags)
    return {
        "id": f"work:{str(row.get('arcid') or '')}",
        "source": "works",
        "arcid": str(row.get("arcid") or ""),
        "title": str(row.get("title") or ""),
        "subtitle": "",
        "tags": tags[:16],
        "tags_translated": [],
        "eh_url": eh_url,
        "ex_url": ex_url,
        "link_url": _prefer_link(eh_url, ex_url, cfg_use),
        "category": category,
        "thumb_url": f"/api/thumb/lrr/{quote(str(row.get('arcid') or ''), safe='')}",
        "reader_url": "",
        "score": float(row.get("score") or 0.0),
        "meta": {
            "read_time": _norm_epoch(row.get("read_time")),
            "eh_posted": _norm_epoch(row.get("eh_posted")),
            "date_added": _norm_epoch(row.get("date_added")),
            "lastreadtime": _norm_epoch(row.get("lastreadtime")),
        },
    }


def _item_from_eh(row: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg_use = cfg or resolve_config()[0]
    gid = int(row.get("gid") or 0)
    token = str(row.get("token") or "")
    eh_url = str(row.get("eh_url") or "")
    ex_url = str(row.get("ex_url") or "")
    category = _category_from_tags([str(x) for x in (row.get("tags") or [])], str(row.get("category") or ""))
    return {
        "id": f"eh:{str(gid or '')}:{token}",
        "source": "eh_works",
        "gid": gid,
        "token": token,
        "title": str(row.get("title") or row.get("title_jpn") or ""),
        "subtitle": str(row.get("title_jpn") or ""),
        "tags": [str(x) for x in (row.get("tags") or [])][:16],
        "tags_translated": [str(x) for x in (row.get("tags_translated") or [])][:16],
        "eh_url": eh_url,
        "ex_url": ex_url,
        "link_url": _prefer_link(eh_url, ex_url, cfg_use),
        "category": category,
        "thumb_url": f"/api/thumb/eh/{gid}/{quote(token, safe='')}",
        "reader_url": "",
        "score": float(row.get("score") or 0.0),
        "meta": {
            "posted": _norm_epoch(row.get("posted")),
            "page_count": int(row.get("filecount") or 0) if int(row.get("filecount") or 0) > 0 else None,
        },
    }


_tag_cache_lock = threading.Lock()
_tag_cache: dict[str, Any] = {"built_at": 0.0, "tags": []}


def _tokenize_query(q: str) -> list[str]:
    s = str(q or "").strip().lower()
    if not s:
        return []
    chunks = [x.strip() for x in re.split(r"[\s,，。；;|/]+", s) if x.strip()]
    return chunks if chunks else [s]


def _tag_candidates(ttl_s: int = 900) -> list[str]:
    now_t = time.time()
    with _tag_cache_lock:
        built = float(_tag_cache.get("built_at") or 0.0)
        if now_t - built <= ttl_s:
            return list(_tag_cache.get("tags") or [])
    rows = query_rows(
        "SELECT tag FROM ("
        "SELECT unnest(tags) AS tag FROM works "
        "UNION ALL "
        "SELECT unnest(tags) AS tag FROM eh_works "
        "UNION ALL "
        "SELECT unnest(tags_translated) AS tag FROM eh_works"
        ") x WHERE tag IS NOT NULL AND length(tag) > 0 GROUP BY tag ORDER BY count(*) DESC LIMIT 5000"
    )
    tags = [str(r.get("tag") or "").strip() for r in rows if str(r.get("tag") or "").strip()]
    with _tag_cache_lock:
        _tag_cache["built_at"] = now_t
        _tag_cache["tags"] = list(tags)
    return tags


def _fuzzy_tags(query: str, threshold: float = 0.62, max_tags: int = 10) -> list[str]:
    tokens = _tokenize_query(query)
    if not tokens:
        return []
    all_tags = _tag_candidates()
    scored: dict[str, float] = {}
    th = max(0.2, min(1.0, float(threshold)))
    for token in tokens:
        if len(token) < 2:
            continue
        for tag in all_tags:
            t = tag.lower()
            if token in t or t in token:
                scored[tag] = max(scored.get(tag, 0.0), 1.0)
                continue
            ratio = SequenceMatcher(None, token, t).ratio()
            if ratio >= th:
                scored[tag] = max(scored.get(tag, 0.0), ratio)
    best = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in best[: max(1, int(max_tags))]]


def _fuzzy_pick_tags(candidates: list[str], valid: list[str], threshold: float) -> list[str]:
    out: list[str] = []
    for c in candidates:
        s = str(c or "").strip().lower()
        if not s:
            continue
        best = ""
        best_score = 0.0
        for v in valid:
            vv = str(v or "").strip().lower()
            if not vv:
                continue
            sc = SequenceMatcher(None, s, vv).ratio()
            if sc > best_score:
                best = v
                best_score = sc
        if best and best_score >= float(threshold):
            out.append(best)
    uniq: list[str] = []
    seen: set[str] = set()
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _expand_tag_aliases(tags: list[str]) -> list[str]:
    aliases = {
        "黑丝": ["female:stockings", "female:thighhighs", "丝袜", "长筒袜"],
        "长筒袜": ["female:thighhighs", "黑丝", "丝袜"],
        "白丝": ["female:thighhighs", "丝袜"],
    }
    out: list[str] = []
    for t in tags:
        s = str(t or "").strip()
        if not s:
            continue
        if s not in out:
            out.append(s)
        key = s.lower()
        for k, vs in aliases.items():
            if k in key:
                for v in vs:
                    if v not in out:
                        out.append(v)
    return out


def _hot_tags(limit: int = 1500, min_freq: int = 5) -> list[str]:
    rows = query_rows(
        "SELECT tag FROM ("
        "SELECT unnest(tags) AS tag FROM works "
        "UNION ALL SELECT unnest(tags) AS tag FROM eh_works "
        "UNION ALL SELECT unnest(tags_translated) AS tag FROM eh_works"
        ") t GROUP BY tag HAVING count(*) >= %s ORDER BY count(*) DESC LIMIT %s",
        (int(min_freq), int(limit)),
    )
    return [str(r.get("tag") or "").strip() for r in rows if str(r.get("tag") or "").strip()]


def _score_text_hit(title: str, query: str, tags: list[str], matched_tags: list[str]) -> float:
    q = str(query or "").strip().lower()
    ttl = str(title or "").strip().lower()
    score = 0.0
    if q and ttl:
        if q == ttl:
            score += 2.0
        elif q in ttl:
            score += 1.2
        else:
            score += SequenceMatcher(None, q, ttl).ratio() * 0.6
    if tags and matched_tags:
        tag_set = {str(x).lower() for x in tags}
        m = sum(1 for x in matched_tags if str(x).lower() in tag_set)
        score += float(m) * 0.35
    return score


def _norm_words(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        s = str(v or "").strip().lower()
        if s:
            out.append(s)
    return out


def _item_passes_filters(item: dict[str, Any], include_categories: list[str], include_tags: list[str]) -> bool:
    cats = _norm_words(include_categories)
    tags_need = _norm_words(include_tags)
    if cats:
        cat = str(item.get("category") or "").strip().lower()
        if cat not in cats:
            return False
    if tags_need:
        tags_all = [str(x).strip().lower() for x in ((item.get("tags") or []) + (item.get("tags_translated") or [])) if str(x).strip()]
        txt = " ".join(tags_all)
        for t in tags_need:
            if t not in txt:
                return False
    return True


def _filter_items(items: list[dict[str, Any]], include_categories: list[str], include_tags: list[str]) -> list[dict[str, Any]]:
    if not include_categories and not include_tags:
        return items
    return [it for it in items if _item_passes_filters(it, include_categories, include_tags)]


def _search_text_non_llm(
    query: str,
    scope: str,
    limit: int,
    cfg: dict[str, Any],
    include_categories: list[str] | None = None,
    include_tags: list[str] | None = None,
) -> dict[str, Any]:
    fuzzy_threshold = float(cfg.get("SEARCH_TAG_FUZZY_THRESHOLD", 0.62))
    matched_tags = _fuzzy_tags(query, threshold=fuzzy_threshold)
    like = f"%{str(query or '').strip()}%"
    items: list[dict[str, Any]] = []

    if scope in ("works", "both"):
        rows = query_rows(
            "SELECT arcid, title, tags, eh_posted, date_added, lastreadtime "
            "FROM works "
            "WHERE (title ILIKE %s OR array_to_string(tags, ' ') ILIKE %s) "
            "OR (tags && %s::text[]) "
            "ORDER BY lastreadtime DESC NULLS LAST LIMIT %s",
            (like, like, matched_tags or [""], int(limit * 3)),
        )
        for r in rows:
            score = _score_text_hit(str(r.get("title") or ""), query, [str(x) for x in (r.get("tags") or [])], matched_tags)
            items.append(_item_from_work({**r, "score": score}, cfg))

    if scope in ("eh", "both"):
        rows = query_rows(
            "SELECT gid, token, eh_url, ex_url, title, title_jpn, category, tags, tags_translated, posted, filecount "
            "FROM eh_works "
            "WHERE (title ILIKE %s OR title_jpn ILIKE %s OR array_to_string(tags, ' ') ILIKE %s OR array_to_string(tags_translated, ' ') ILIKE %s) "
            "OR (tags && %s::text[]) OR (tags_translated && %s::text[]) "
            "ORDER BY posted DESC NULLS LAST LIMIT %s",
            (like, like, like, like, matched_tags or [""], matched_tags or [""], int(limit * 3)),
        )
        for r in rows:
            tags_all = [str(x) for x in (r.get("tags") or [])] + [str(x) for x in (r.get("tags_translated") or [])]
            score = _score_text_hit(str(r.get("title") or r.get("title_jpn") or ""), query, tags_all, matched_tags)
            items.append(_item_from_eh({**r, "score": score}, cfg))

    items.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    dedup: dict[str, dict[str, Any]] = {}
    for it in items:
        dedup[str(it.get("id"))] = it
        if len(dedup) >= int(limit):
            break
    filtered = _filter_items(list(dedup.values()), include_categories or [], include_tags or [])
    return {
        "items": filtered[: int(limit)],
        "next_cursor": "",
        "has_more": False,
        "meta": {
            "mode": "text_search",
            "llm_used": False,
            "fuzzy_tags": matched_tags,
            "scope": scope,
            "filters": {"categories": include_categories or [], "tags": include_tags or []},
        },
    }


def _search_by_visual_vector(
    vec: list[float],
    scope: str,
    limit: int,
    cfg: dict[str, Any],
    include_categories: list[str] | None = None,
    include_tags: list[str] | None = None,
) -> dict[str, Any]:
    vtxt = _vector_literal(vec)
    items: list[dict[str, Any]] = []
    if scope in ("works", "both"):
        works_rows = query_rows(
            "SELECT arcid, title, tags, eh_posted, date_added, lastreadtime, "
            "(visual_embedding <=> (%s)::vector) AS dist "
            "FROM works WHERE visual_embedding IS NOT NULL "
            "ORDER BY visual_embedding <=> (%s)::vector LIMIT %s",
            (vtxt, vtxt, int(limit)),
        )
        for r in works_rows:
            score = 1.0 / (1.0 + float(r.get("dist") or 0.0))
            items.append(_item_from_work({**r, "score": score}, cfg))
    if scope in ("eh", "both"):
        eh_rows = query_rows(
            "SELECT gid, token, eh_url, ex_url, title, title_jpn, category, tags, tags_translated, posted, filecount, "
            "(cover_embedding <=> (%s)::vector) AS dist "
            "FROM eh_works WHERE cover_embedding IS NOT NULL "
            "ORDER BY cover_embedding <=> (%s)::vector LIMIT %s",
            (vtxt, vtxt, int(limit)),
        )
        for r in eh_rows:
            score = 1.0 / (1.0 + float(r.get("dist") or 0.0))
            items.append(_item_from_eh({**r, "score": score}, cfg))
    items.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    items = _filter_items(items, include_categories or [], include_tags or [])
    return {
        "items": items[: int(limit)],
        "next_cursor": "",
        "has_more": False,
        "meta": {"mode": "image_search", "scope": scope, "filters": {"categories": include_categories or [], "tags": include_tags or []}},
    }


def _scenario_weights(cfg: dict[str, Any], scenario: str) -> dict[str, float]:
    sc = str(scenario or "plot").lower()
    if sc == "visual":
        return {
            "visual": float(cfg.get("SEARCH_WEIGHT_VISUAL", 2.0) or 2.0),
            "eh_visual": float(cfg.get("SEARCH_WEIGHT_EH_VISUAL", 1.6) or 1.6),
            "desc": float(cfg.get("SEARCH_WEIGHT_DESC", 0.8) or 0.8),
            "text": float(cfg.get("SEARCH_WEIGHT_TEXT", 0.7) or 0.7),
            "eh_text": float(cfg.get("SEARCH_WEIGHT_EH_TEXT", 0.7) or 0.7),
        }
    if sc == "mixed":
        return {
            "visual": float(cfg.get("SEARCH_WEIGHT_MIXED_VISUAL", 1.2) or 1.2),
            "eh_visual": float(cfg.get("SEARCH_WEIGHT_MIXED_EH_VISUAL", 1.0) or 1.0),
            "desc": float(cfg.get("SEARCH_WEIGHT_MIXED_DESC", 1.4) or 1.4),
            "text": float(cfg.get("SEARCH_WEIGHT_MIXED_TEXT", 0.9) or 0.9),
            "eh_text": float(cfg.get("SEARCH_WEIGHT_MIXED_EH_TEXT", 0.9) or 0.9),
        }
    return {
        "visual": float(cfg.get("SEARCH_WEIGHT_PLOT_VISUAL", 0.6) or 0.6),
        "eh_visual": float(cfg.get("SEARCH_WEIGHT_PLOT_EH_VISUAL", 0.5) or 0.5),
        "desc": float(cfg.get("SEARCH_WEIGHT_PLOT_DESC", 2.0) or 2.0),
        "text": float(cfg.get("SEARCH_WEIGHT_PLOT_TEXT", 0.9) or 0.9),
        "eh_text": float(cfg.get("SEARCH_WEIGHT_PLOT_EH_TEXT", 0.9) or 0.9),
    }


def _rrf_merge_weighted(channels: dict[str, list[str]], weights: dict[str, float], *, k: int, topn: int) -> list[str]:
    scores: dict[str, float] = {}
    for name, ids in channels.items():
        w = max(0.0, float(weights.get(name, 0.0)))
        if w <= 0:
            continue
        for i, _id in enumerate(ids or [], start=1):
            s = str(_id)
            if not s:
                continue
            scores[s] = float(scores.get(s) or 0.0) + w * (1.0 / float(k + i))
    return [x for x, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[: int(topn)]]


def _agent_nl_search(
    query: str,
    scope: str,
    limit: int,
    cfg: dict[str, Any],
    *,
    include_categories: list[str],
    include_tags: list[str],
    ui_lang: str = "zh",
    scenario: str = "plot",
) -> dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"items": [], "next_cursor": "", "has_more": False, "meta": {"mode": "nl_search", "empty": True}}

    hot = _hot_tags(limit=1600, min_freq=5)
    llm_tags: list[str] = []
    final_tags: list[str] = []
    errors: list[str] = []
    try:
        llm_tags = _extract_tags_by_llm(q, cfg, hot)
        final_tags = _fuzzy_pick_tags(llm_tags, hot, float(cfg.get("SEARCH_TAG_FUZZY_THRESHOLD", 0.62) or 0.62))
    except Exception as e:
        errors.append(f"tag_extract:{e}")
        final_tags = []
    final_tags = _expand_tag_aliases(final_tags)
    final_tags = _tags_for_ui_lang(final_tags, ui_lang)

    merged_tags: list[str] = []
    for t in list(include_tags or []) + list(final_tags or []):
        s = str(t or "").strip().lower()
        if s and s not in merged_tags:
            merged_tags.append(s)
    merged_tags = _tags_for_ui_lang(merged_tags, ui_lang)
    hard_filter = _as_bool(cfg.get("SEARCH_TAG_HARD_FILTER"), True)
    filter_tags = merged_tags if hard_filter else []

    n = max(30, int(limit) * 2)
    channels: dict[str, list[str]] = {"text": [], "eh_text": [], "desc": [], "visual": [], "eh_visual": []}
    try:
        if scope in ("works", "both"):
            rows = query_rows(
                "SELECT arcid FROM works "
                "WHERE (title ILIKE %s OR array_to_string(tags, ' ') ILIKE %s) "
                "OR (tags && %s::text[]) "
                "ORDER BY lastreadtime DESC NULLS LAST LIMIT %s",
                (f"%{q}%", f"%{q}%", filter_tags or [""], int(n)),
            )
            channels["text"] = [f"work:{str(r.get('arcid') or '').strip()}" for r in rows if str(r.get("arcid") or "").strip()]
        if scope in ("eh", "both"):
            rows = query_rows(
                "SELECT gid, token FROM eh_works "
                "WHERE (title ILIKE %s OR title_jpn ILIKE %s OR array_to_string(tags, ' ') ILIKE %s OR array_to_string(tags_translated, ' ') ILIKE %s) "
                "OR (tags && %s::text[]) OR (tags_translated && %s::text[]) "
                "ORDER BY posted DESC NULLS LAST LIMIT %s",
                (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", filter_tags or [""], filter_tags or [""], int(n)),
            )
            channels["eh_text"] = [f"eh:{int(r.get('gid') or 0)}:{str(r.get('token') or '').strip()}" for r in rows if int(r.get("gid") or 0) > 0 and str(r.get("token") or "").strip()]
    except Exception as e:
        errors.append(f"text_channel:{e}")

    try:
        emb_model = str(cfg.get("EMB_MODEL_CUSTOM") or cfg.get("EMB_MODEL") or "").strip()
        emb_key = str(cfg.get("LLM_API_KEY") or "").strip()
        vec = _provider_embedding(str(cfg.get("LLM_API_BASE") or ""), emb_key, emb_model, q, timeout_s=_llm_timeout_s(cfg))
        if vec:
            vtxt = _vector_literal(vec)
            if scope in ("works", "both"):
                rows = query_rows(
                    "SELECT w.arcid FROM works w WHERE w.desc_embedding IS NOT NULL "
                    "ORDER BY w.desc_embedding <=> (%s)::vector LIMIT %s",
                    (vtxt, int(max(30, limit * 2))),
                )
                channels["desc"] = [f"work:{str(r.get('arcid') or '').strip()}" for r in rows if str(r.get("arcid") or "").strip()]
    except Exception as e:
        errors.append(f"desc_channel:{e}")

    try:
        model_id = str(cfg.get("SIGLIP_MODEL") or "google/siglip-so400m-patch14-384").strip()
        qv = _embed_text_siglip(q, model_id)
        vtxt2 = _vector_literal(qv)
        if scope in ("works", "both"):
            rows = query_rows(
                "SELECT arcid FROM works WHERE visual_embedding IS NOT NULL "
                "ORDER BY visual_embedding <=> (%s)::vector LIMIT %s",
                (vtxt2, int(n)),
            )
            channels["visual"] = [f"work:{str(r.get('arcid') or '').strip()}" for r in rows if str(r.get("arcid") or "").strip()]
        if scope in ("eh", "both"):
            rows = query_rows(
                "SELECT gid, token FROM eh_works WHERE cover_embedding IS NOT NULL "
                "ORDER BY cover_embedding <=> (%s)::vector LIMIT %s",
                (vtxt2, int(n)),
            )
            channels["eh_visual"] = [f"eh:{int(r.get('gid') or 0)}:{str(r.get('token') or '').strip()}" for r in rows if int(r.get("gid") or 0) > 0 and str(r.get("token") or "").strip()]
    except Exception as e:
        errors.append(f"visual_channel:{e}")

    weights = _scenario_weights(cfg, scenario)
    ranked_ids = _rrf_merge_weighted(channels, weights, k=60, topn=max(int(limit) * 3, 60))
    work_ids = [x.split(":", 1)[1] for x in ranked_ids if x.startswith("work:")]
    eh_parts = [x.split(":", 2) for x in ranked_ids if x.startswith("eh:")]
    eh_pairs = [(int(p[1]), p[2]) for p in eh_parts if len(p) == 3 and p[1].isdigit() and p[2]]
    work_rows = query_rows(
        "SELECT arcid, title, tags, eh_posted, date_added, lastreadtime FROM works WHERE arcid = ANY(%s)",
        (work_ids or [""],),
    ) if work_ids else []
    eh_rows = query_rows(
        "SELECT gid, token, eh_url, ex_url, title, title_jpn, category, tags, tags_translated, posted, filecount "
        "FROM eh_works WHERE (gid, token) IN (SELECT * FROM unnest(%s::int[], %s::text[]))",
        ([x[0] for x in eh_pairs] or [0], [x[1] for x in eh_pairs] or ["_"]),
    ) if eh_pairs else []
    wm = {f"work:{str(r.get('arcid') or '').strip()}": _item_from_work(r, cfg) for r in work_rows}
    em = {f"eh:{int(r.get('gid') or 0)}:{str(r.get('token') or '').strip()}": _item_from_eh(r, cfg) for r in eh_rows}
    ordered: list[dict[str, Any]] = []
    for rid in ranked_ids:
        it = wm.get(rid) or em.get(rid)
        if it:
            ordered.append(it)
    items = _filter_items(ordered, include_categories, filter_tags)[: int(limit)]
    return {
        "items": items,
        "next_cursor": "",
        "has_more": False,
        "meta": {
            "mode": "nl_search",
            "llm_used": True,
            "llm_tags_raw": llm_tags,
            "tags_extracted": final_tags,
            "query": q,
            "ui_lang": ui_lang,
            "scenario": scenario,
            "hard_filter": hard_filter,
            "weights": weights,
            "channels": {k: len(v) for k, v in channels.items()},
            "errors": errors,
        },
    }


def _uploaded_image_search(
    body: bytes,
    *,
    cfg: dict[str, Any],
    scope: str = "both",
    limit: int = 24,
    query: str = "",
    text_weight: float = 0.5,
    visual_weight: float = 0.5,
    include_categories: list[str] | None = None,
    include_tags: list[str] | None = None,
) -> dict[str, Any]:
    if not body:
        raise HTTPException(status_code=400, detail="empty image")
    cats = [x.strip().lower() for x in (include_categories or []) if str(x).strip()]
    tags = [x.strip().lower() for x in (include_tags or []) if str(x).strip()]
    if not _as_bool(cfg.get("SEARCH_TAG_HARD_FILTER"), True):
        tags = []
    scope_use = str(scope or "both").strip().lower()
    if scope_use not in ("works", "eh", "both"):
        scope_use = "both"
    limit_use = max(1, min(500, int(limit or 24)))

    model_id = str(cfg.get("SIGLIP_MODEL") or "google/siglip-so400m-patch14-384").strip()
    status = _model_status()
    if not bool(((status.get("siglip") or {}).get("usable"))):
        raise HTTPException(status_code=400, detail="siglip model not ready, please download first")
    try:
        vec = _embed_image_siglip(body, model_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"siglip embed failed: {e}")
    if not vec:
        raise HTTPException(status_code=500, detail="siglip produced empty vector")

    visual_part = _search_by_visual_vector(vec, scope_use, limit_use * 2, cfg, include_categories=cats, include_tags=tags)
    q = str(query or "").strip()
    if not q:
        visual_part["items"] = (visual_part.get("items") or [])[:limit_use]
        visual_part["meta"] = {**(visual_part.get("meta") or {}), "uploaded": True, "query": ""}
        return visual_part

    tw = max(0.0, float(text_weight or 0.0))
    vw = max(0.0, float(visual_weight or 0.0))
    if tw + vw <= 0:
        tw, vw = 0.5, 0.5
    sw = tw + vw
    tw, vw = tw / sw, vw / sw
    text_part = _search_text_non_llm(q, scope_use, limit_use * 2, cfg, include_categories=cats, include_tags=tags)
    merged: dict[str, dict[str, Any]] = {}
    for idx, it in enumerate(text_part.get("items") or []):
        key = str(it.get("id"))
        score = (float(it.get("score") or 0.0) + 1.0 / (idx + 1)) * tw
        row = dict(it)
        row["score"] = score
        merged[key] = row
    for idx, it in enumerate(visual_part.get("items") or []):
        key = str(it.get("id"))
        score = (float(it.get("score") or 0.0) + 1.0 / (idx + 1)) * vw
        if key in merged:
            merged[key]["score"] = float(merged[key].get("score") or 0.0) + score
        else:
            row = dict(it)
            row["score"] = score
            merged[key] = row
    items = sorted(merged.values(), key=lambda x: float(x.get("score") or 0.0), reverse=True)[:limit_use]
    return {
        "items": items,
        "next_cursor": "",
        "has_more": False,
        "meta": {
            "mode": "hybrid_search",
            "uploaded": True,
            "query": q,
            "weights": {"text": round(tw, 4), "visual": round(vw, 4)},
            "filters": {"categories": cats, "tags": tags},
        },
    }
