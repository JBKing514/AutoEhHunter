import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from .ai_provider import _llm_max_tokens, _llm_timeout_s, _provider_chat_json
from .chat_memory_service import append_chat_message, build_chat_payload, load_chat_history, maybe_store_semantic_fact
from .config_service import now_iso, resolve_config
from .db_service import query_rows
from .rec_service import _build_recommendation_items
from .search_service import _agent_nl_search, _item_from_work, _parse_vector_text, _search_by_visual_vector, _uploaded_image_search

def _chat_bucket(session_id: str, user_id: str = "default_user") -> dict[str, Any]:
    sid = str(session_id or "default").strip() or "default"
    uid = str(user_id or "default_user")
    return {"messages": load_chat_history(uid, sid, limit=120), "facts": []}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "")
    if not raw:
        return None
    m = re.search(r"\{[\s\S]*\}", raw)
    body = m.group(0) if m else raw
    for candidate in [body, body.replace("None", "null").replace("True", "true").replace("False", "false")]:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _extract_intent_from_broken_json(text: str) -> str | None:
    s = str(text or "")
    m = re.search(r'"intent"\s*:\s*"([A-Za-z_]+)"', s)
    if not m:
        return None
    return str(m.group(1) or "").strip().upper()


def _extract_days_fallback(text: str) -> int | None:
    q = str(text or "")
    if not q:
        return None
    if "全部" in q or "all time" in q.lower() or "full" in q.lower():
        return 365
    m = re.search(r"(\d+)\s*天", q)
    if m:
        return max(1, min(365, int(m.group(1))))
    m = re.search(r"(\d+)\s*周", q)
    if m:
        return max(1, min(365, int(m.group(1)) * 7))
    if "一周" in q or "最近周" in q:
        return 7
    m = re.search(r"(\d+)\s*(个月|月)", q)
    if m:
        return max(1, min(365, int(m.group(1)) * 30))
    if "一月" in q or "一个月" in q:
        return 30
    m = re.search(r"(\d+)\s*年", q)
    if m:
        return max(1, min(365, int(m.group(1)) * 365))
    return None


def _extract_hours_fallback(text: str) -> int | None:
    q = str(text or "")
    m = re.search(r"(\d+)\s*小时", q)
    if m:
        return max(1, min(24 * 30, int(m.group(1))))
    d = _extract_days_fallback(q)
    if d is not None:
        return max(1, min(24 * 30, int(d) * 24))
    return None


def _fallback_route(text: str) -> dict[str, Any]:
    q = str(text or "")
    low = q.lower()
    intent = "chat"
    if any(x in low for x in ["推荐", "recommend", "new uploads"]):
        intent = "recommendation"
    elif any(x in low for x in ["报告", "report", "weekly", "monthly", "daily"]):
        intent = "report"
    elif any(x in low for x in ["画像", "profile", "偏好", "口味"]):
        intent = "profile"
    elif any(x in low for x in ["找", "搜索", "search", "类似", "tag"]):
        intent = "search"
    rt = None
    if "日报" in q or "daily" in low:
        rt = "daily"
    elif "月报" in q or "monthly" in low:
        rt = "monthly"
    elif "全量" in q or "全部" in q or "full" in low:
        rt = "full"
    elif "周报" in q or "weekly" in low:
        rt = "weekly"
    return {
        "intent": intent,
        "search_mode": "auto",
        "search_k": None,
        "search_eh_scope": "mixed",
        "search_eh_min_results": None,
        "profile_days": _extract_days_fallback(q),
        "profile_target": "inventory" if ("库存" in q or "inventory" in low) else None,
        "report_type": rt,
        "recommend_k": None,
        "recommend_candidate_hours": _extract_hours_fallback(q),
        "recommend_profile_days": _extract_days_fallback(q),
        "recommend_explore": ("探索" in q or "explore" in low),
    }


def _normalize_route(raw: dict[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
    obj = dict(raw or {})
    out = dict(fallback)
    iv = str(obj.get("intent") or "").strip().upper()
    imap = {
        "SEARCH": "search",
        "PROFILE": "profile",
        "REPORT": "report",
        "RECOMMEND": "recommendation",
        "RECOMMENDATION": "recommendation",
        "CHAT": "chat",
    }
    if iv in imap:
        out["intent"] = imap[iv]
    sm = str(obj.get("search_mode") or "").strip().lower()
    if sm in {"auto", "plot", "visual", "mixed"}:
        out["search_mode"] = sm
    try:
        v = obj.get("search_k")
        if v is not None:
            out["search_k"] = max(1, min(200, int(str(v))))
    except Exception:
        pass
    es = str(obj.get("search_eh_scope") or "").strip().lower()
    if es in {"mixed", "external_only", "internal_only"}:
        out["search_eh_scope"] = es
    for k, lo, hi in [
        ("search_eh_min_results", 1, 200),
        ("profile_days", 1, 365),
        ("recommend_k", 1, 200),
        ("recommend_candidate_hours", 1, 24 * 30),
        ("recommend_profile_days", 1, 365),
    ]:
        try:
            v = obj.get(k)
            if v is not None:
                out[k] = max(lo, min(hi, int(str(v))))
        except Exception:
            pass
    pt = str(obj.get("profile_target") or "").strip().lower()
    if pt in {"reading", "inventory"}:
        out["profile_target"] = pt
    rt = str(obj.get("report_type") or "").strip().lower()
    if rt in {"daily", "weekly", "monthly", "full"}:
        out["report_type"] = rt
    if obj.get("recommend_explore") is not None:
        out["recommend_explore"] = bool(obj.get("recommend_explore"))
    return out


def _route_chat_intent(text: str, req_intent: str, cfg: dict[str, Any]) -> dict[str, Any]:
    explicit = str(req_intent or "auto").strip().lower()
    fallback = _fallback_route(text)
    if explicit in {"chat", "profile", "search", "report", "recommendation"}:
        fallback["intent"] = explicit
        return fallback
    q = str(text or "").strip()
    if not q:
        return fallback
    base = str(cfg.get("LLM_API_BASE") or "").strip()
    model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
    key = str(cfg.get("LLM_API_KEY") or "").strip()
    if not (base and model):
        return fallback
    try:
        system = str(cfg.get("PROMPT_INTENT_ROUTER_SYSTEM") or "").strip() or "You are intent and parameter extractor. Return JSON only."
        user = f"query={q}"
        obj = _provider_chat_json(
            base,
            key,
            model,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_INTENT", 160),
            timeout_s=_llm_timeout_s(cfg),
        )
        txt = str((((obj.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or "")
        parsed = _extract_json_object(txt)
        if parsed is None:
            intent_fallback = _extract_intent_from_broken_json(txt)
            if intent_fallback:
                parsed = {"intent": intent_fallback}
        return _normalize_route(parsed, fallback)
    except Exception:
        return fallback


def _chat_plain_reply(*, user_id: str, session_id: str, text: str, cfg: dict[str, Any]) -> str:
    base = str(cfg.get("LLM_API_BASE") or "").strip()
    model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
    key = str(cfg.get("LLM_API_KEY") or "").strip()
    if not base or not model:
        return "收到。当前未配置LLM模型，可切换为 search/profile/report/recommendation 模式。"
    msgs = build_chat_payload(
        user_id=str(user_id or "default_user"),
        session_id=str(session_id or "default"),
        custom_persona=str(cfg.get("CHAT_CUSTOM_PERSONA") or ""),
        current_task=str(text or "").strip() or "通用对话",
        user_text="",
        history_limit=14,
        cfg=cfg,
    )
    try:
        obj = _provider_chat_json(base, key, model, msgs, temperature=0.4, max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_CHAT", 900), timeout_s=_llm_timeout_s(cfg))
        return str((((obj.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or "").strip() or "(empty reply)"
    except Exception as e:
        return f"聊天调用失败: {e}"


def _chat_profile_payload(cfg: dict[str, Any], days: int = 30, limit: int = 24, with_narrative: bool = True) -> dict[str, Any]:
    now_ep = int(datetime.now(timezone.utc).timestamp())
    start_ep = now_ep - max(1, int(days)) * 86400
    rows = query_rows(
        "SELECT e.arcid, max(e.read_time) as read_time, w.title, w.tags, w.eh_posted, w.date_added, w.lastreadtime "
        "FROM read_events e JOIN works w ON w.arcid = e.arcid "
        "WHERE e.read_time >= %s AND e.read_time <= %s "
        "GROUP BY e.arcid, w.title, w.tags, w.eh_posted, w.date_added, w.lastreadtime "
        "ORDER BY max(e.read_time) DESC LIMIT %s",
        (int(start_ep), int(now_ep), int(max(12, limit))),
    )
    items = [_item_from_work(r, cfg) for r in rows]
    top_tags = query_rows(
        "SELECT t.tag, count(*) as freq FROM ("
        "SELECT unnest(w.tags) as tag FROM read_events e JOIN works w ON w.arcid=e.arcid "
        "WHERE e.read_time >= %s AND e.read_time <= %s"
        ") t GROUP BY t.tag ORDER BY freq DESC LIMIT 8",
        (int(start_ep), int(now_ep)),
    )
    tags_txt = ", ".join([str(r.get("tag") or "") for r in top_tags])
    narrative = ""
    if with_narrative:
        try:
            base = str(cfg.get("LLM_API_BASE") or "").strip()
            model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
            key = str(cfg.get("LLM_API_KEY") or "").strip()
            if base and model:
                system = str(cfg.get("PROMPT_PROFILE_SYSTEM") or "").strip() or "Summarize profile briefly."
                user = json.dumps({"days": days, "count": len(items), "top_tags": [str(r.get("tag") or "") for r in top_tags], "titles": [str(x.get("title") or "") for x in items[:6]]}, ensure_ascii=False)
                obj = _provider_chat_json(base, key, model, [{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0.4, max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_PROFILE", 360), timeout_s=_llm_timeout_s(cfg))
                narrative = str((((obj.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or "").strip()
        except Exception:
            narrative = ""
    return {
        "type": "profile",
        "title": f"最近{days}天阅读画像",
        "summary": f"记录 {len(items)} 条，偏好标签：{tags_txt or '-'}",
        "narrative": narrative,
        "items": items,
        "home_tab": "history",
    }


def _chat_report_payload(cfg: dict[str, Any], report_type: str = "weekly", limit: int = 24, with_narrative: bool = True) -> dict[str, Any]:
    rt = str(report_type or "weekly").strip().lower()
    hours = 24 if rt == "daily" else (30 * 24 if rt == "monthly" else 7 * 24)
    now_ep = int(datetime.now(timezone.utc).timestamp())
    start_ep = now_ep - hours * 3600
    rows = query_rows(
        "SELECT e.arcid, e.read_time, w.title, w.tags, w.eh_posted, w.date_added, w.lastreadtime "
        "FROM read_events e JOIN works w ON w.arcid = e.arcid "
        "WHERE e.read_time >= %s AND e.read_time <= %s ORDER BY e.read_time DESC LIMIT %s",
        (int(start_ep), int(now_ep), int(max(20, limit * 2))),
    )
    items = [_item_from_work(r, cfg) for r in rows]
    total = len(rows)
    unique_titles = len({str(r.get("title") or "") for r in rows if str(r.get("title") or "")})
    narrative = ""
    if with_narrative:
        try:
            base = str(cfg.get("LLM_API_BASE") or "").strip()
            model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
            key = str(cfg.get("LLM_API_KEY") or "").strip()
            if base and model:
                system = str(cfg.get("PROMPT_REPORT_SYSTEM") or "").strip() or "Write short report summary."
                user = json.dumps({"type": rt, "total": total, "unique_titles": unique_titles, "titles": [str(x.get("title") or "") for x in items[:8]]}, ensure_ascii=False)
                obj = _provider_chat_json(base, key, model, [{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0.4, max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_REPORT", 420), timeout_s=_llm_timeout_s(cfg))
                narrative = str((((obj.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or "").strip()
        except Exception:
            narrative = ""
    return {
        "type": "report",
        "title": f"{rt} 阅读报告",
        "summary": f"总阅读 {total}，去重标题 {unique_titles}",
        "narrative": narrative,
        "items": items,
        "home_tab": "history",
    }


def _chat_message_core(
    *,
    session_id: str,
    user_id: str,
    text: str,
    mode: str,
    intent_raw: str,
    ui_lang: str,
    image_arcid: str = "",
    uploaded_image: bytes | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    q = str(text or "").strip()
    mode_use = str(mode or "chat").strip().lower()
    image_arcid_use = str(image_arcid or "").strip()
    if not q and not image_arcid_use and not uploaded_image:
        raise HTTPException(status_code=400, detail="empty message")

    uid = str(user_id or "default_user")
    sid = str(session_id or "default").strip() or "default"
    cfg, _ = resolve_config()
    route = _route_chat_intent(q, str(intent_raw or "auto"), cfg)
    intent = str(route.get("intent") or "chat")
    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "text": q,
        "mode": mode_use,
        "intent": intent,
        "route": route,
        "image_arcid": image_arcid_use,
        "has_uploaded_image": bool(uploaded_image),
        "time": now_iso(),
    }
    append_chat_message(uid, sid, "user", q, extra={k: v for k, v in user_msg.items() if k not in {"id", "role", "text", "time"}})
    maybe_store_semantic_fact(uid, q, cfg)

    reply = ""
    tool = intent
    payload: dict[str, Any] | None = None
    if uploaded_image:
        payload = _uploaded_image_search(uploaded_image, cfg=cfg, scope="both", limit=20, query=q)
        payload["type"] = "search"
        payload["title"] = "图文检索结果" if q else "以图搜图结果"
        payload["home_tab"] = "search"
        reply = "已完成图文联合检索。" if q else "已完成图像检索。"
        tool = "search"
    elif mode_use == "search_image" and image_arcid_use:
        rows = query_rows(
            "SELECT visual_embedding::text as vec FROM works WHERE arcid = %s AND visual_embedding IS NOT NULL LIMIT 1",
            (image_arcid_use,),
        )
        vec = _parse_vector_text(str(rows[0].get("vec") or "")) if rows else []
        if not vec:
            raise HTTPException(status_code=400, detail="reference image embedding not found")
        payload = _search_by_visual_vector(vec, "both", 20, cfg)
        payload["type"] = "search"
        payload["title"] = "以图搜图结果"
        payload["home_tab"] = "search"
        reply = "已完成图像检索。"
        tool = "search"
    elif intent == "search":
        eh_scope = str(route.get("search_eh_scope") or "mixed").strip().lower()
        scope_map = {"mixed": "both", "external_only": "eh", "internal_only": "works"}
        scope_use = scope_map.get(eh_scope, "both")
        try:
            limit_use = max(1, min(200, int(str(route.get("search_k") or 20))))
        except Exception:
            limit_use = 20
        payload = _agent_nl_search(q, scope_use, limit_use, cfg, include_categories=[], include_tags=[], ui_lang=str(ui_lang or "zh"), scenario="plot")
        payload["type"] = "search"
        payload["title"] = "自然语言检索结果"
        payload["home_tab"] = "search"
        reply = f"### 检索完成\n\n共返回 **{len(payload.get('items') or [])}** 条结果。"
    elif intent == "recommendation":
        mode_rec = "explore" if bool(route.get("recommend_explore")) else ""
        cfg_rec = dict(cfg)
        if route.get("recommend_candidate_hours") is not None:
            cfg_rec["REC_CANDIDATE_HOURS"] = str(int(str(route.get("recommend_candidate_hours"))))
        if route.get("recommend_profile_days") is not None:
            cfg_rec["REC_PROFILE_DAYS"] = str(int(str(route.get("recommend_profile_days"))))
        built = _build_recommendation_items(cfg_rec, mode=mode_rec, user_id=uid)
        try:
            limit_use = max(1, min(200, int(str(route.get("recommend_k") or 20))))
        except Exception:
            limit_use = 20
        payload = {
            "items": list(built.get("items") or [])[:limit_use],
            "next_cursor": "",
            "has_more": False,
            "meta": {**(built.get("meta") or {}), "mode": "recommend", "total": len(list(built.get("items") or []))},
            "type": "recommendation",
            "title": "推荐结果",
            "summary": f"候选 {len(list(built.get('items') or [])[:limit_use])} 条",
            "home_tab": "recommend",
        }
        try:
            base = str(cfg.get("LLM_API_BASE") or "").strip()
            model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
            key = str(cfg.get("LLM_API_KEY") or "").strip()
            if base and model:
                sample = [
                    {"title": str(x.get("title") or ""), "tags": (x.get("tags") or [])[:6], "source": str(x.get("source") or "")}
                    for x in (payload.get("items") or [])[:8]
                ]
                system = str(cfg.get("PROMPT_RECOMMEND_SYSTEM") or "").strip() or "Summarize recommendation results briefly."
                user = json.dumps({"query": q, "results": sample}, ensure_ascii=False)
                obj = _provider_chat_json(
                    base,
                    key,
                    model,
                    [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=0.4,
                    max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_REPORT", 420),
                    timeout_s=_llm_timeout_s(cfg),
                )
                payload["narrative"] = str((((obj.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or "").strip()
        except Exception:
            pass
        reply = f"### 推荐完成\n\n候选 **{len(payload.get('items') or [])}** 条。"
        narrative = str(payload.get("narrative") or "").strip()
        payload.pop("narrative", None)
        if narrative:
            reply += f"\n\n{narrative}"
    elif intent == "profile":
        try:
            profile_days = int(str(route.get("profile_days") or cfg.get("REC_PROFILE_DAYS") or 30))
        except Exception:
            profile_days = 30
        payload = _chat_profile_payload(cfg, days=max(1, min(365, profile_days)), limit=20)
        summary = str(payload.get("summary") or "画像已生成。")
        narrative = str(payload.get("narrative") or "").strip()
        payload.pop("narrative", None)
        reply = f"### 用户画像\n\n{summary}"
        if narrative:
            reply += f"\n\n{narrative}"
    elif intent == "report":
        report_type = str(route.get("report_type") or "weekly").strip().lower()
        payload = _chat_report_payload(cfg, report_type=report_type, limit=20)
        summary = str(payload.get("summary") or "报告已生成。")
        narrative = str(payload.get("narrative") or "").strip()
        payload.pop("narrative", None)
        reply = f"### {str(payload.get('title') or '报告')}\n\n{summary}"
        if narrative:
            reply += f"\n\n{narrative}"
    else:
        reply = _chat_plain_reply(user_id=uid, session_id=sid, text=q, cfg=cfg)

    elapsed = max(0.001, float(time.time() - started_at))
    tokens = max(1, int(len(str(reply or "")) / 4))
    assistant_msg = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "text": reply,
        "tool": tool,
        "intent": intent,
        "payload": payload,
        "stats": {"tokens": tokens, "elapsed_s": round(elapsed, 3), "tps": round(tokens / elapsed, 2)},
        "time": now_iso(),
    }
    append_chat_message(uid, sid, "assistant", reply, extra={k: v for k, v in assistant_msg.items() if k not in {"id", "role", "text", "time"}})
    history = load_chat_history(uid, sid, limit=120)
    return {"ok": True, "session_id": sid, "message": assistant_msg, "history": history}
