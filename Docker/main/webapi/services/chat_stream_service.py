import json
import time
import uuid
from typing import Any

from fastapi.responses import StreamingResponse

from .ai_provider import _llm_max_tokens, _llm_timeout_s, _provider_chat_stream_chunks
from .chat_memory_service import append_chat_message, build_chat_payload, load_chat_history, maybe_store_semantic_fact
from .chat_service import _chat_message_core, _chat_profile_payload, _chat_report_payload, _route_chat_intent
from .config_service import now_iso, resolve_config
from .rec_service import _build_recommendation_items
from .search_service import _agent_nl_search


def chat_message_stream_response(
    *,
    session_id: str,
    text: str,
    mode: str,
    intent: str,
    ui_lang: str,
    image_arcid: str,
    user_id: str,
) -> StreamingResponse:
    sid = str(session_id or "default")
    uid = str(user_id or "default_user")
    txt = str(text or "").strip()
    mode_use = str(mode or "chat").strip().lower()
    intent_raw = str(intent or "auto")
    ui_lang_use = str(ui_lang or "zh")
    image_arcid_use = str(image_arcid or "").strip()

    def _emit(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def event_stream():
        if not txt:
            yield _emit({"event": "error", "detail": "empty message"})
            return
        cfg, _ = resolve_config()
        route = _route_chat_intent(txt, intent_raw, cfg)
        route_intent = str(route.get("intent") or "chat")
        base = str(cfg.get("LLM_API_BASE") or "").strip()
        model = str(cfg.get("LLM_MODEL_CUSTOM") or cfg.get("LLM_MODEL") or "").strip()
        key = str(cfg.get("LLM_API_KEY") or "").strip()

        if mode_use != "chat":
            res = _chat_message_core(
                session_id=sid,
                user_id=uid,
                text=txt,
                mode=mode_use,
                intent_raw=intent_raw,
                ui_lang=ui_lang_use,
                image_arcid=image_arcid_use,
            )
            msg = dict((res.get("message") or {}))
            out_text = str(msg.get("text") or "")
            for i in range(0, len(out_text), 8):
                yield _emit({"event": "delta", "delta": out_text[i : i + 8]})
                time.sleep(0.01)
            yield _emit({"event": "done", "message": msg, "history": res.get("history") or [], "stats": msg.get("stats") or {}})
            return

        user_msg = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "text": txt,
            "mode": mode_use,
            "intent": route_intent,
            "route": route,
            "image_arcid": image_arcid_use,
            "has_uploaded_image": False,
            "time": now_iso(),
        }
        append_chat_message(uid, sid, "user", txt, extra={k: v for k, v in user_msg.items() if k not in {"id", "role", "text", "time"}})
        maybe_store_semantic_fact(uid, txt, cfg)

        if route_intent != "chat":
            started = time.time()
            payload: dict[str, Any] | None = None
            parts: list[str] = []
            if route_intent == "search":
                eh_scope = str(route.get("search_eh_scope") or "mixed").strip().lower()
                scope_map = {"mixed": "both", "external_only": "eh", "internal_only": "works"}
                scope_use = scope_map.get(eh_scope, "both")
                try:
                    limit_use = max(1, min(200, int(str(route.get("search_k") or 20))))
                except Exception:
                    limit_use = 20
                payload = _agent_nl_search(
                    txt,
                    scope_use,
                    limit_use,
                    cfg,
                    include_categories=[],
                    include_tags=[],
                    ui_lang=ui_lang_use,
                    scenario="plot",
                )
                payload["type"] = "search"
                payload["title"] = "自然语言检索结果"
                payload["home_tab"] = "search"
                intro = f"### 检索完成\n\n共返回 **{len(payload.get('items') or [])}** 条结果。\n\n"
                parts.append(intro)
                for i in range(0, len(intro), 8):
                    yield _emit({"event": "delta", "delta": intro[i : i + 8]})
                if base and model:
                    try:
                        sample = [
                            {"title": str(x.get("title") or ""), "tags": (x.get("tags") or [])[:6], "source": str(x.get("source") or "")}
                            for x in (payload.get("items") or [])[:8]
                        ]
                        system = str(cfg.get("PROMPT_SEARCH_NARRATIVE_SYSTEM") or "").strip() or "Summarize search results briefly."
                        user = json.dumps({"query": txt, "results": sample}, ensure_ascii=False)
                        for c in _provider_chat_stream_chunks(
                            base,
                            key,
                            model,
                            [{"role": "system", "content": system}, {"role": "user", "content": user}],
                            temperature=0.35,
                            max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_SEARCH_NARRATIVE", 320),
                            timeout_s=max(120, _llm_timeout_s(cfg) * 3),
                        ):
                            parts.append(c)
                            yield _emit({"event": "delta", "delta": c})
                    except Exception:
                        pass
            elif route_intent == "profile":
                try:
                    profile_days = int(str(route.get("profile_days") or cfg.get("REC_PROFILE_DAYS") or 30))
                except Exception:
                    profile_days = 30
                profile_days = max(1, min(365, profile_days))
                payload = _chat_profile_payload(cfg, days=profile_days, limit=20, with_narrative=False)
                intro = f"### 用户画像\n\n{str(payload.get('summary') or '画像已生成。')}\n\n"
                parts.append(intro)
                for i in range(0, len(intro), 8):
                    yield _emit({"event": "delta", "delta": intro[i : i + 8]})
                if base and model:
                    try:
                        system = str(cfg.get("PROMPT_PROFILE_SYSTEM") or "").strip() or "Summarize profile briefly."
                        user = json.dumps(
                            {
                                "days": profile_days,
                                "count": len(payload.get("items") or []),
                                "titles": [str(x.get("title") or "") for x in (payload.get("items") or [])[:6]],
                            },
                            ensure_ascii=False,
                        )
                        for c in _provider_chat_stream_chunks(
                            base,
                            key,
                            model,
                            [{"role": "system", "content": system}, {"role": "user", "content": user}],
                            temperature=0.4,
                            max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_PROFILE", 360),
                            timeout_s=max(120, _llm_timeout_s(cfg) * 3),
                        ):
                            parts.append(c)
                            yield _emit({"event": "delta", "delta": c})
                    except Exception:
                        pass
            elif route_intent == "report":
                report_type = str(route.get("report_type") or "weekly").strip().lower()
                payload = _chat_report_payload(cfg, report_type=report_type, limit=20, with_narrative=False)
                intro = f"### {str(payload.get('title') or '报告')}\n\n{str(payload.get('summary') or '报告已生成。')}\n\n"
                parts.append(intro)
                for i in range(0, len(intro), 8):
                    yield _emit({"event": "delta", "delta": intro[i : i + 8]})
                if base and model:
                    try:
                        system = str(cfg.get("PROMPT_REPORT_SYSTEM") or "").strip() or "Write short report summary."
                        user = json.dumps(
                            {
                                "type": report_type,
                                "total": len(payload.get("items") or []),
                                "titles": [str(x.get("title") or "") for x in (payload.get("items") or [])[:8]],
                            },
                            ensure_ascii=False,
                        )
                        for c in _provider_chat_stream_chunks(
                            base,
                            key,
                            model,
                            [{"role": "system", "content": system}, {"role": "user", "content": user}],
                            temperature=0.4,
                            max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_REPORT", 420),
                            timeout_s=max(120, _llm_timeout_s(cfg) * 3),
                        ):
                            parts.append(c)
                            yield _emit({"event": "delta", "delta": c})
                    except Exception:
                        pass
            else:
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
                    "home_tab": "recommend",
                    "summary": f"候选 {len(list(built.get('items') or [])[:limit_use])} 条",
                }
                intro = f"### 推荐完成\n\n候选 **{len(payload.get('items') or [])}** 条。"
                parts.append(intro)
                for i in range(0, len(intro), 8):
                    yield _emit({"event": "delta", "delta": intro[i : i + 8]})
                if base and model:
                    try:
                        sample = [
                            {"title": str(x.get("title") or ""), "tags": (x.get("tags") or [])[:6], "source": str(x.get("source") or "")}
                            for x in (payload.get("items") or [])[:8]
                        ]
                        system = str(cfg.get("PROMPT_RECOMMEND_SYSTEM") or "").strip() or "Summarize recommendation results briefly."
                        user = json.dumps({"query": txt, "results": sample}, ensure_ascii=False)
                        for c in _provider_chat_stream_chunks(
                            base,
                            key,
                            model,
                            [{"role": "system", "content": system}, {"role": "user", "content": user}],
                            temperature=0.4,
                            max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_REPORT", 420),
                            timeout_s=max(120, _llm_timeout_s(cfg) * 3),
                        ):
                            parts.append(c)
                            yield _emit({"event": "delta", "delta": c})
                    except Exception:
                        pass

            full = "".join(parts).strip()
            elapsed = max(0.001, float(time.time() - started))
            tokens = max(1, int(len(full) / 4))
            stats = {"tokens": tokens, "elapsed_s": round(elapsed, 3), "tps": round(tokens / elapsed, 2)}
            assistant_msg = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "text": full,
                "tool": route_intent,
                "intent": route_intent,
                "payload": payload,
                "stats": stats,
                "time": now_iso(),
            }
            append_chat_message(uid, sid, "assistant", full, extra={k: v for k, v in assistant_msg.items() if k not in {"id", "role", "text", "time"}})
            history = load_chat_history(uid, sid, limit=120)
            yield _emit({"event": "done", "message": assistant_msg, "history": history, "stats": stats})
            return

        msgs = build_chat_payload(
            user_id=uid,
            session_id=sid,
            custom_persona=str(cfg.get("CHAT_CUSTOM_PERSONA") or ""),
            current_task=txt,
            user_text="",
            history_limit=14,
            cfg=cfg,
        )

        started = time.time()
        parts: list[str] = []
        try:
            for chunk in _provider_chat_stream_chunks(
                base,
                key,
                model,
                msgs,
                temperature=0.4,
                max_tokens=_llm_max_tokens(cfg, "LLM_MAX_TOKENS_CHAT", 900),
                timeout_s=max(120, _llm_timeout_s(cfg) * 4),
            ):
                parts.append(chunk)
                yield _emit({"event": "delta", "delta": chunk})
        except Exception as e:
            err_msg = f"聊天调用失败: {e}"
            assistant_msg = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "text": err_msg,
                "tool": "chat",
                "intent": "chat",
                "payload": None,
                "stats": {"tokens": 0, "elapsed_s": 0.0, "tps": 0.0},
                "time": now_iso(),
            }
            append_chat_message(uid, sid, "assistant", err_msg, extra={k: v for k, v in assistant_msg.items() if k not in {"id", "role", "text", "time"}})
            history = load_chat_history(uid, sid, limit=120)
            yield _emit({"event": "error", "detail": str(e), "message": assistant_msg, "history": history})
            return

        full = "".join(parts).strip()
        elapsed = max(0.001, float(time.time() - started))
        tokens = max(1, int(len(full) / 4))
        stats = {"tokens": tokens, "elapsed_s": round(elapsed, 3), "tps": round(tokens / elapsed, 2)}
        assistant_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "text": full or "(empty reply)",
            "tool": "chat",
            "intent": "chat",
            "payload": None,
            "stats": stats,
            "time": now_iso(),
        }
        append_chat_message(uid, sid, "assistant", full or "(empty reply)", extra={k: v for k, v in assistant_msg.items() if k not in {"id", "role", "text", "time"}})
        history = load_chat_history(uid, sid, limit=120)
        yield _emit({"event": "done", "message": assistant_msg, "history": history, "stats": stats})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
