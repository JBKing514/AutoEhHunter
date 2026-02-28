from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from ..core.schemas import RecommendImpressionBatchRequest, RecommendTouchRequest
from ..services.config_service import resolve_config
from ..services.recommend_feedback_service import (
    clear_recommend_clicks,
    clear_recommend_profile,
    record_recommend_click,
    record_recommend_dislike,
    record_recommend_impressions,
)
from ..services.rec_service import _compute_xp_map, _get_recommendation_items_cached

router = APIRouter(tags=["recommend"])


@router.get("/api/home/recommend")
def home_recommend(
    request: Request,
    cursor: str = Query(default=""),
    limit: int = Query(default=24, ge=1, le=80),
    mode: str = Query(default=""),
    depth: int = Query(default=1, ge=1, le=8),
    jitter: bool = Query(default=False),
    jitter_nonce: str = Query(default=""),
    visual_scope: str = Query(default="external"),
) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    user_id = str(auth_user.get("uid") or "default_user")
    cfg, _ = resolve_config()
    data = _get_recommendation_items_cached(
        cfg,
        mode=mode,
        user_id=user_id,
        depth=depth,
        jitter=bool(jitter),
        jitter_nonce=str(jitter_nonce or ""),
        visual_scope=str(visual_scope or "external"),
    )
    all_items = list(data.get("items") or [])
    start = 0
    if cursor:
        try:
            start = max(0, int(cursor))
        except Exception:
            start = 0
    end = start + int(limit)
    items = all_items[start:end]
    next_cursor = str(end) if end < len(all_items) else ""
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
        "meta": {
            **(data.get("meta") or {}),
            "mode": "recommend",
            "total": len(all_items),
        },
    }


@router.get("/api/recommend/items")
def recommend_items(
    request: Request,
    cursor: str = Query(default=""),
    limit: int = Query(default=24, ge=1, le=80),
    mode: str = Query(default=""),
    depth: int = Query(default=1, ge=1, le=8),
    jitter: bool = Query(default=False),
    jitter_nonce: str = Query(default=""),
    visual_scope: str = Query(default="external"),
) -> dict[str, Any]:
    return home_recommend(
        request=request,
        cursor=cursor,
        limit=limit,
        mode=mode,
        depth=depth,
        jitter=jitter,
        jitter_nonce=jitter_nonce,
        visual_scope=visual_scope,
    )


@router.post("/api/home/recommend/touch")
def home_recommend_touch(req: RecommendTouchRequest, request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    user_id = str(auth_user.get("uid") or "default_user")
    return record_recommend_click(
        user_id=user_id,
        gid=req.gid,
        token=str(req.token or ""),
        eh_url=str(req.eh_url or ""),
        ex_url=str(req.ex_url or ""),
        weight=float(req.weight or 1.0),
    )


@router.post("/api/home/recommend/dislike")
def home_recommend_dislike(req: RecommendTouchRequest, request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    user_id = str(auth_user.get("uid") or "default_user")
    return record_recommend_dislike(
        user_id=user_id,
        gid=req.gid,
        token=str(req.token or ""),
        eh_url=str(req.eh_url or ""),
        ex_url=str(req.ex_url or ""),
        weight=float(req.weight or 1.0),
    )


@router.delete("/api/home/recommend/touch")
def home_recommend_touch_clear(request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    user_id = str(auth_user.get("uid") or "default_user")
    return clear_recommend_clicks(user_id)


@router.delete("/api/home/recommend/profile")
def home_recommend_profile_clear(request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    user_id = str(auth_user.get("uid") or "default_user")
    return clear_recommend_profile(user_id)


@router.post("/api/home/recommend/impressions")
def home_recommend_impressions(req: RecommendImpressionBatchRequest, request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    user_id = str(auth_user.get("uid") or "default_user")
    items = [
        {
            "gid": it.gid,
            "token": str(it.token or ""),
            "eh_url": str(it.eh_url or ""),
            "ex_url": str(it.ex_url or ""),
        }
        for it in (req.items or [])
    ]
    return record_recommend_impressions(user_id=user_id, items=items, weight=float(req.weight or 1.0))


@router.get("/api/xp-map")
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
