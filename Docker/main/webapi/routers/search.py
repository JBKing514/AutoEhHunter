import asyncio
import json
import threading
import time
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

import httpx
import psycopg
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile

from ..core.config_values import as_bool as _as_bool
from ..core.schemas import HomeHybridSearchRequest, HomeImageSearchRequest, HomeTextSearchRequest, ReaderReadEventRequest
from ..services.ai_provider import _extract_tags_by_llm
from ..services.config_service import resolve_config
from ..services.db_service import db_dsn, query_rows
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


_thumb_client_lock = threading.Lock()
_thumb_client: httpx.AsyncClient | None = None
_reader_manifest_lock = threading.Lock()
_reader_manifest_cache: dict[str, dict[str, Any]] = {}


def _get_thumb_http_client() -> httpx.AsyncClient:
    global _thumb_client
    with _thumb_client_lock:
        if _thumb_client is None:
            _thumb_client = httpx.AsyncClient(
                verify=False,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=80, max_keepalive_connections=20, keepalive_expiry=30.0),
                timeout=httpx.Timeout(connect=8.0, read=10.0, write=8.0, pool=5.0),
            )
        return _thumb_client


def _normalize_lrr_page_path(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://") or s.startswith("/") or s.startswith("./"):
        if s.startswith("./"):
            s = s[1:]
        u = urlsplit(s)
        q = parse_qs(str(u.query or ""), keep_blank_values=False)
        path_vals = q.get("path") or []
        if path_vals:
            return str(path_vals[0] or "").strip()
        if "&path=" in s and not path_vals:
            tail = s.split("&path=", 1)[1]
            return unquote(tail.split("&", 1)[0]).strip()
    return s


async def _load_reader_manifest(arcid: str, *, force: bool = False) -> list[str]:
    key = str(arcid or "").strip()
    if not key:
        return []
    if not force:
        with _reader_manifest_lock:
            cached = _reader_manifest_cache.get(key)
            if cached and isinstance(cached.get("pages"), list) and cached.get("pages"):
                return list(cached.get("pages") or [])

    cfg, _ = resolve_config()
    base = str(cfg.get("LRR_BASE") or "http://lanraragi:3000").strip().rstrip("/")
    api_key = str(cfg.get("LRR_API_KEY") or "").strip()
    url = f"{base}/api/archives/{key}/files"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    client = _get_thumb_http_client()
    try:
        resp = await client.get(url, headers=headers, timeout=15.0)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"reader manifest load failed: {e}")

    raw_pages = payload.get("pages") if isinstance(payload, dict) else []
    pages: list[str] = []
    seen: set[str] = set()
    for raw in raw_pages or []:
        p = _normalize_lrr_page_path(str(raw or ""))
        if p and p not in seen:
            seen.add(p)
            pages.append(p)
    with _reader_manifest_lock:
        _reader_manifest_cache[key] = {"pages": list(pages)}
    return pages


async def _fetch_bytes_with_retries(
    client: httpx.AsyncClient,
    urls: list[str],
    headers_factory,
    *,
    retries: int = 3,
    timeout_s: float = 10.0,
) -> tuple[bytes, str]:
    last_err: Exception | None = None
    uniq_urls: list[str] = []
    seen: set[str] = set()
    for u in urls:
        s = str(u or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq_urls.append(s)
    if not uniq_urls:
        raise HTTPException(status_code=404, detail="thumb not found")

    for attempt in range(max(1, int(retries))):
        for url in uniq_urls:
            try:
                headers = headers_factory(url)
                resp = await client.get(
                    url,
                    headers=headers,
                    timeout=max(3.0, float(timeout_s)),
                )
                resp.raise_for_status()
                return resp.content, str(resp.headers.get("content-type") or "image/jpeg")
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_err = e
                continue
        if attempt < max(1, int(retries)) - 1:
            await asyncio.sleep(1.0 * (attempt + 1))

    raise HTTPException(status_code=502, detail=f"thumbnail error after {retries} retries: {last_err}")


def _build_eh_thumb_urls(thumb: str, prefer_ex: bool) -> list[str]:
    base = str(thumb or "").strip()
    if not base:
        return []
    eh_thumb = base.replace("https://s.exhentai.org/", "https://ehgt.org/")
    ex_thumb = base.replace("https://ehgt.org/", "https://s.exhentai.org/")
    candidates = [ex_thumb, eh_thumb] if prefer_ex else [eh_thumb, ex_thumb]
    out: list[str] = []
    seen: set[str] = set()
    for u in candidates:
        s = str(u or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _eh_headers_for(url: str, ua: str, cookie: str) -> dict[str, str]:
    h = {"User-Agent": ua}
    is_ex = "s.exhentai.org" in str(url)
    h["Referer"] = "https://exhentai.org/" if is_ex else "https://e-hentai.org/"
    if is_ex and cookie:
        h["Cookie"] = cookie
    return h


async def _refresh_eh_thumb_from_api(
    *,
    gid: int,
    token: str,
    cfg: dict[str, Any],
    client: httpx.AsyncClient,
) -> dict[str, str]:
    safe_token = str(token or "").strip()
    if gid <= 0 or not safe_token:
        return {}
    api_url = "https://api.e-hentai.org/api.php"
    ua = str(cfg.get("EH_USER_AGENT") or "AutoEhHunter/1.0").strip() or "AutoEhHunter/1.0"
    payload = {"method": "gdata", "gidlist": [[int(gid), safe_token]], "namespace": 1}
    try:
        resp = await client.post(api_url, json=payload, headers={"User-Agent": ua}, timeout=15.0)
        resp.raise_for_status()
        obj = resp.json()
    except Exception:
        return {}

    rows = obj.get("gmetadata") if isinstance(obj, dict) else None
    if not isinstance(rows, list) or not rows:
        return {}
    row = rows[0] if isinstance(rows[0], dict) else None
    if not isinstance(row, dict):
        return {}
    new_thumb = str(row.get("thumb") or "").strip()
    if not new_thumb:
        return {}

    eh_url = f"https://e-hentai.org/g/{int(gid)}/{safe_token}/"
    ex_url = f"https://exhentai.org/g/{int(gid)}/{safe_token}/"
    raw_patch = json.dumps(row, ensure_ascii=False)
    updated = query_rows(
        "UPDATE eh_works "
        "SET raw = COALESCE(raw, '{}'::jsonb) || %s::jsonb, "
        "eh_url = COALESCE(NULLIF(%s, ''), eh_url), "
        "ex_url = COALESCE(NULLIF(%s, ''), ex_url), "
        "last_fetched_at = now(), updated_at = now() "
        "WHERE gid = %s AND token = %s "
        "RETURNING raw->>'thumb' AS thumb, eh_url, ex_url",
        (raw_patch, eh_url, ex_url, int(gid), safe_token),
    )
    if updated:
        return {
            "thumb": str((updated[0] or {}).get("thumb") or new_thumb).strip(),
            "eh_url": str((updated[0] or {}).get("eh_url") or eh_url).strip(),
            "ex_url": str((updated[0] or {}).get("ex_url") or ex_url).strip(),
        }
    return {"thumb": new_thumb, "eh_url": eh_url, "ex_url": ex_url}


@router.get("/api/thumb/lrr/{arcid}")
async def thumb_lrr(arcid: str) -> Response:
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
    client = _get_thumb_http_client()
    data, ctype = await _fetch_bytes_with_retries(
        client,
        [url],
        headers_factory=lambda _u: headers,
        retries=3,
        timeout_s=10.0,
    )
    _cache_write(cache_key, data)
    return Response(content=data, media_type=ctype, headers={"X-Thumb-Cache": "MISS"})


@router.get("/api/thumb/eh/{gid}/{token}")
async def thumb_eh(gid: int, token: str) -> Response:
    safe_token = str(token or "").strip()
    if gid <= 0 or not safe_token:
        raise HTTPException(status_code=400, detail="invalid gid/token")
    rows = query_rows(
        "SELECT raw->>'thumb' AS thumb, eh_url, ex_url FROM eh_works WHERE gid = %s AND token = %s LIMIT 1",
        (int(gid), safe_token),
    )
    db_row = rows[0] if rows else {}
    thumb = str((db_row or {}).get("thumb") or "").strip()

    cfg, _ = resolve_config()
    cache_key = f"eh:{gid}:{safe_token}:{'ex' if _prefer_ex(cfg) else 'eh'}"
    cached = _cache_read(cache_key)
    if cached is not None:
        return Response(content=cached, media_type="image/jpeg", headers={"X-Thumb-Cache": "HIT"})
    ua = str(cfg.get("EH_USER_AGENT") or "AutoEhHunter/1.0").strip() or "AutoEhHunter/1.0"
    cookie = str(cfg.get("EH_COOKIE") or "").strip()
    prefer_ex = _prefer_ex(cfg)
    client = _get_thumb_http_client()

    if not thumb:
        refreshed = await _refresh_eh_thumb_from_api(gid=int(gid), token=safe_token, cfg=cfg, client=client)
        thumb = str((refreshed or {}).get("thumb") or "").strip()
    if not thumb:
        raise HTTPException(status_code=404, detail="thumb not found")

    urls = _build_eh_thumb_urls(thumb, prefer_ex)

    try:
        data, ctype = await _fetch_bytes_with_retries(
            client,
            urls,
            headers_factory=lambda u: _eh_headers_for(u, ua, cookie),
            retries=3,
            timeout_s=10.0,
        )
    except HTTPException:
        refreshed = await _refresh_eh_thumb_from_api(gid=int(gid), token=safe_token, cfg=cfg, client=client)
        refreshed_thumb = str((refreshed or {}).get("thumb") or "").strip()
        if not refreshed_thumb or refreshed_thumb == thumb:
            raise
        retry_urls = _build_eh_thumb_urls(refreshed_thumb, prefer_ex)
        data, ctype = await _fetch_bytes_with_retries(
            client,
            retry_urls,
            headers_factory=lambda u: _eh_headers_for(u, ua, cookie),
            retries=2,
            timeout_s=10.0,
        )

    _cache_write(cache_key, data)
    return Response(content=data, media_type=ctype, headers={"X-Thumb-Cache": "MISS"})


@router.get("/api/reader/{arcid}/manifest")
async def reader_manifest(arcid: str) -> dict[str, Any]:
    safe_arcid = str(arcid or "").strip()
    if not safe_arcid:
        raise HTTPException(status_code=400, detail="arcid required")
    pages = await _load_reader_manifest(safe_arcid)
    row = query_rows("SELECT title FROM works WHERE arcid = %s LIMIT 1", (safe_arcid,))
    title = str((row[0] if row else {}).get("title") or "")
    return {
        "arcid": safe_arcid,
        "title": title,
        "page_count": len(pages),
    }


@router.get("/api/reader/{arcid}/page/{index}")
async def reader_page(arcid: str, index: int) -> Response:
    safe_arcid = str(arcid or "").strip()
    if not safe_arcid:
        raise HTTPException(status_code=400, detail="arcid required")
    if int(index) < 1:
        raise HTTPException(status_code=400, detail="index must be >= 1")
    pages = await _load_reader_manifest(safe_arcid)
    if int(index) > len(pages):
        raise HTTPException(status_code=404, detail="page out of range")

    cfg, _ = resolve_config()
    base = str(cfg.get("LRR_BASE") or "http://lanraragi:3000").strip().rstrip("/")
    api_key = str(cfg.get("LRR_API_KEY") or "").strip()
    page_path = str(pages[int(index) - 1] or "").strip()
    if not page_path:
        raise HTTPException(status_code=404, detail="page path missing")
    url = f"{base}/api/archives/{safe_arcid}/page?path={quote(page_path, safe='')}"
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    client = _get_thumb_http_client()
    try:
        resp = await client.get(url, headers=headers, timeout=20.0)
        resp.raise_for_status()
        ctype = str(resp.headers.get("content-type") or "image/jpeg")
        return Response(content=resp.content, media_type=ctype)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"reader page fetch failed: {e}")


@router.post("/api/reader/read-event")
def reader_read_event(req: ReaderReadEventRequest) -> dict[str, Any]:
    safe_arcid = str(req.arcid or "").strip()
    if not safe_arcid:
        raise HTTPException(status_code=400, detail="arcid required")
    read_time = int(req.read_time or int(time.time()))
    source_file = str(req.source_file or "reader-ui").strip() or "reader-ui"
    ingested_at = str(req.ingested_at or "").strip() or None
    raw = req.raw if isinstance(req.raw, dict) else {}
    dsn = str(db_dsn() or "").strip()
    if not dsn:
        raise HTTPException(status_code=400, detail="POSTGRES_DSN is not configured")

    sql = (
        "INSERT INTO read_events (arcid, read_time, source_file, ingested_at, raw) "
        "VALUES (%s, %s, %s, COALESCE(%s::timestamptz, now()), %s::jsonb) "
        "ON CONFLICT (arcid, read_time) DO NOTHING"
    )
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (safe_arcid, read_time, source_file, ingested_at, json.dumps(raw, ensure_ascii=False)))
                inserted = int(cur.rowcount or 0)
            conn.commit()
        return {"ok": True, "inserted": inserted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"insert read_event failed: {e}")


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
