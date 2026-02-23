from typing import Any

import requests
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile

from ..core.config_values import as_bool as _as_bool
from ..core.schemas import HomeHybridSearchRequest, HomeImageSearchRequest, HomeTextSearchRequest
from ..services.ai_provider import _extract_tags_by_llm
from ..services.config_service import resolve_config
from ..services.db_service import query_rows
from ..services.search_service import (
    _agent_nl_search,
    _cache_read,
    _cache_write,
    _fuzzy_pick_tags,
    _fuzzy_tags,
    _hot_tags,
    _parse_vector_text,
    _prefer_ex,
    _search_by_visual_vector,
    _search_text_non_llm,
    _tag_matches_ui_lang,
    _uploaded_image_search,
)

router = APIRouter(tags=["search"])


@router.get("/api/thumb/lrr/{arcid}")
def thumb_lrr(arcid: str) -> Response:
    cfg, _ = resolve_config()
    base = str(cfg.get("LRR_BASE") or "http://lanraragi:3000").strip().rstrip("/")
    api_key = str(cfg.get("LRR_API_KEY") or "").strip()
    safe_arcid = str(arcid or "").strip()
    if not safe_arcid:
        raise HTTPException(status_code=400, detail="arcid required")
    cache_key = f"lrr:{safe_arcid}"
    cached = _cache_read(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="image/jpeg", headers={"X-Thumb-Cache": "HIT"})
    url = f"{base}/api/archives/{safe_arcid}/thumbnail"
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail="failed to fetch lrr thumbnail")
        ctype = r.headers.get("content-type", "image/jpeg")
        _cache_write(cache_key, r.content)
        return Response(content=r.content, media_type=ctype, headers={"X-Thumb-Cache": "MISS"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"lrr thumbnail error: {e}")


@router.get("/api/thumb/eh/{gid}/{token}")
def thumb_eh(gid: int, token: str) -> Response:
    safe_token = str(token or "").strip()
    if gid <= 0 or not safe_token:
        raise HTTPException(status_code=400, detail="invalid gid/token")
    rows = query_rows(
        "SELECT raw->>'thumb' AS thumb FROM eh_works WHERE gid = %s AND token = %s LIMIT 1",
        (int(gid), safe_token),
    )
    thumb = str((rows[0] or {}).get("thumb") or "").strip() if rows else ""
    if not thumb:
        raise HTTPException(status_code=404, detail="thumb not found")

    cfg, _ = resolve_config()
    cache_key = f"eh:{gid}:{safe_token}:{'ex' if _prefer_ex(cfg) else 'eh'}"
    cached = _cache_read(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="image/jpeg", headers={"X-Thumb-Cache": "HIT"})
    ua = str(cfg.get("EH_USER_AGENT") or "AutoEhHunter/1.0").strip() or "AutoEhHunter/1.0"
    cookie = str(cfg.get("EH_COOKIE") or "").strip()
    headers = {"User-Agent": ua, "Referer": "https://e-hentai.org/"}
    if _prefer_ex(cfg):
        thumb = thumb.replace("https://ehgt.org/", "https://s.exhentai.org/")
        headers["Referer"] = "https://exhentai.org/"
        if cookie:
            headers["Cookie"] = cookie
    try:
        r = requests.get(thumb, headers=headers, timeout=30)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail="failed to fetch eh thumbnail")
        ctype = r.headers.get("content-type", "image/jpeg")
        _cache_write(cache_key, r.content)
        return Response(content=r.content, media_type=ctype, headers={"X-Thumb-Cache": "MISS"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"eh thumbnail error: {e}")


@router.post("/api/home/search/image")
def home_image_search(req: HomeImageSearchRequest) -> dict[str, Any]:
    scope = str(req.scope or "both").strip().lower()
    if scope not in ("works", "eh", "both"):
        scope = "both"
    limit = max(1, min(500, int(req.limit or 24)))
    cfg, _ = resolve_config()
    use_tags = list(req.include_tags or []) if _as_bool(cfg.get("SEARCH_TAG_HARD_FILTER"), True) else []

    vec: list[float] = []
    if str(req.arcid or "").strip():
        rows = query_rows(
            "SELECT visual_embedding::text as vec FROM works WHERE arcid = %s AND visual_embedding IS NOT NULL LIMIT 1",
            (str(req.arcid).strip(),),
        )
        if rows:
            vec = _parse_vector_text(str(rows[0].get("vec") or ""))
    elif req.gid is not None and str(req.token or "").strip():
        rows = query_rows(
            "SELECT cover_embedding::text as vec FROM eh_works "
            "WHERE gid = %s AND token = %s AND cover_embedding IS NOT NULL LIMIT 1",
            (int(req.gid), str(req.token).strip()),
        )
        if rows:
            vec = _parse_vector_text(str(rows[0].get("vec") or ""))

    if not vec:
        raise HTTPException(status_code=400, detail="image search needs a reference arcid or (gid, token) for now")

    return _search_by_visual_vector(
        vec,
        scope,
        limit,
        cfg,
        include_categories=list(req.include_categories or []),
        include_tags=use_tags,
    )


@router.post("/api/home/search/image/upload")
async def home_image_search_upload(
    file: UploadFile = File(...),
    scope: str = Form(default="both"),
    limit: int = Form(default=24),
    query: str = Form(default=""),
    text_weight: float = Form(default=0.5),
    visual_weight: float = Form(default=0.5),
    include_categories: str = Form(default=""),
    include_tags: str = Form(default=""),
) -> dict[str, Any]:
    cfg, _ = resolve_config()
    body = await file.read()
    cats = [x.strip().lower() for x in str(include_categories or "").split(",") if x.strip()]
    tags = [x.strip().lower() for x in str(include_tags or "").split(",") if x.strip()]
    return _uploaded_image_search(
        body,
        cfg=cfg,
        scope=scope,
        limit=limit,
        query=query,
        text_weight=text_weight,
        visual_weight=visual_weight,
        include_categories=cats,
        include_tags=tags,
    )


@router.post("/api/home/search/text")
def home_text_search(req: HomeTextSearchRequest) -> dict[str, Any]:
    cfg, _ = resolve_config()
    query = str(req.query or "").strip()
    if not query:
        return {"items": [], "next_cursor": "", "has_more": False, "meta": {"mode": "text_search", "empty": True}}
    scope = str(req.scope or "both").strip().lower()
    if scope not in ("works", "eh", "both"):
        scope = "both"
    limit = max(1, min(500, int(req.limit or 24)))
    use_nl = bool(req.use_llm) and _as_bool(cfg.get("SEARCH_NL_ENABLED"), False)
    if use_nl:
        return _agent_nl_search(
            query,
            scope,
            limit,
            cfg,
            include_categories=list(req.include_categories or []),
            include_tags=list(req.include_tags or []),
            ui_lang=str(req.ui_lang or "zh"),
            scenario="plot",
        )
    return _search_text_non_llm(
        query,
        scope,
        limit,
        cfg,
        include_categories=list(req.include_categories or []),
        include_tags=list(req.include_tags or []) if _as_bool(cfg.get("SEARCH_TAG_HARD_FILTER"), True) else [],
    )


@router.post("/api/home/search/hybrid")
def home_hybrid_search(req: HomeHybridSearchRequest) -> dict[str, Any]:
    cfg, _ = resolve_config()
    scope = str(req.scope or "both").strip().lower()
    if scope not in ("works", "eh", "both"):
        scope = "both"
    limit = max(1, min(500, int(req.limit or 24)))
    tw = float(req.text_weight if req.text_weight is not None else cfg.get("SEARCH_MIXED_TEXT_WEIGHT", 0.5))
    vw = float(req.visual_weight if req.visual_weight is not None else cfg.get("SEARCH_MIXED_VISUAL_WEIGHT", 0.5))
    tw = max(0.0, tw)
    vw = max(0.0, vw)
    if tw + vw <= 0:
        tw, vw = 0.5, 0.5
    sw = tw + vw
    tw, vw = tw / sw, vw / sw

    q = str(req.query or "").strip()
    use_nl = bool(req.use_llm) and _as_bool(cfg.get("SEARCH_NL_ENABLED"), False)
    text_part = (
        _agent_nl_search(
            q,
            scope,
            limit * 2,
            cfg,
            include_categories=list(req.include_categories or []),
            include_tags=list(req.include_tags or []),
            ui_lang=str(req.ui_lang or "zh"),
            scenario="mixed",
        )
        if (q and use_nl)
        else _search_text_non_llm(
            q,
            scope,
            limit * 2,
            cfg,
            include_categories=list(req.include_categories or []),
            include_tags=list(req.include_tags or []) if _as_bool(cfg.get("SEARCH_TAG_HARD_FILTER"), True) else [],
        )
        if q
        else {"items": []}
    )
    image_part = (
        home_image_search(
            HomeImageSearchRequest(
                arcid=str(req.arcid or ""),
                gid=req.gid,
                token=str(req.token or ""),
                scope=scope,
                limit=limit * 2,
                include_categories=list(req.include_categories or []),
                include_tags=list(req.include_tags or []),
            )
        )
        if (str(req.arcid or "").strip() or (req.gid is not None and str(req.token or "").strip()))
        else {"items": []}
    )

    merged: dict[str, dict[str, Any]] = {}
    for idx, it in enumerate(text_part.get("items") or []):
        key = str(it.get("id"))
        score = (float(it.get("score") or 0.0) + 1.0 / (idx + 1)) * tw
        row = dict(it)
        row["score"] = score
        merged[key] = row
    for idx, it in enumerate(image_part.get("items") or []):
        key = str(it.get("id"))
        score = (float(it.get("score") or 0.0) + 1.0 / (idx + 1)) * vw
        if key in merged:
            merged[key]["score"] = float(merged[key].get("score") or 0.0) + score
        else:
            row = dict(it)
            row["score"] = score
            merged[key] = row
    items = sorted(merged.values(), key=lambda x: float(x.get("score") or 0.0), reverse=True)[:limit]
    return {
        "items": items,
        "next_cursor": "",
        "has_more": False,
        "meta": {
            "mode": "hybrid_search",
            "llm_used": bool(use_nl),
            "weights": {"text": round(tw, 4), "visual": round(vw, 4)},
        },
    }


@router.get("/api/home/filter/tag-suggest")
def home_filter_tag_suggest(
    q: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=30),
    ui_lang: str = Query(default="zh"),
) -> dict[str, Any]:
    kw = str(q or "").strip().lower()
    if not kw:
        return {"items": []}
    cfg, _ = resolve_config()
    fuzzy = _fuzzy_tags(kw, threshold=0.45, max_tags=max(20, limit * 2))
    rows = query_rows(
        "SELECT tag FROM ("
        "SELECT unnest(tags) AS tag FROM works "
        "UNION ALL SELECT unnest(tags) AS tag FROM eh_works "
        "UNION ALL SELECT unnest(tags_translated) AS tag FROM eh_works"
        ") x WHERE tag ILIKE %s GROUP BY tag ORDER BY count(*) DESC LIMIT %s",
        (f"%{kw}%", int(limit * 2)),
    )
    exact = [str(r.get("tag") or "").strip() for r in rows if str(r.get("tag") or "").strip()]
    out: list[str] = []
    for t in exact + fuzzy:
        if not _tag_matches_ui_lang(t, ui_lang):
            continue
        if t not in out:
            out.append(t)
        if len(out) >= int(limit):
            break
    if _as_bool(cfg.get("SEARCH_TAG_SMART_ENABLED"), False):
        try:
            hot = _hot_tags(limit=1500, min_freq=5)
            llm_tags = _extract_tags_by_llm(kw, cfg, hot)
            smart = _fuzzy_pick_tags(llm_tags, hot, float(cfg.get("SEARCH_TAG_FUZZY_THRESHOLD", 0.62) or 0.62))
            for t in smart:
                if not _tag_matches_ui_lang(t, ui_lang):
                    continue
                if t not in out:
                    out.append(t)
                if len(out) >= int(limit):
                    break
        except Exception:
            pass
    return {"items": out}
