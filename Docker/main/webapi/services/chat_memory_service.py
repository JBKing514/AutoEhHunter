import json
import re
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .db_service import db_dsn, query_rows

_PREF_RE = re.compile(r"(喜欢|不喜欢|讨厌|偏好|口味|别推|不要|不错|再来|黑名单)")


def _get_embedding_for_text(text: str, cfg: dict[str, Any]) -> list[float]:
    """Call the configured embedding provider and return the vector, or [] on failure."""
    try:
        from .ai_provider import _provider_embedding, _llm_timeout_s
        base = str(cfg.get("LLM_API_BASE") or "").strip()
        model = str(cfg.get("EMB_MODEL_CUSTOM") or cfg.get("EMB_MODEL") or "").strip()
        key = str(cfg.get("LLM_API_KEY") or "").strip()
        if not base or not model:
            return []
        return _provider_embedding(base, key, model, text, timeout_s=_llm_timeout_s(cfg, default=30))
    except Exception:
        return []


def build_system_prompt(custom_persona: str, current_task: str, memory_data: dict[str, Any], cfg: dict[str, Any] | None = None) -> str:
    _cfg = cfg or {}
    persona = str(custom_persona or "").strip() or "你是一个智能画廊管理助手，请客观简明地回答问题。"

    def _flag(key: str, default: bool = True) -> bool:
        raw = _cfg.get(key, default)
        return str(raw).strip().lower() not in {"0", "false", ""}

    short_enabled = _flag("MEMORY_SHORT_TERM_ENABLED", True)
    long_enabled = _flag("MEMORY_LONG_TERM_ENABLED", True)
    semantic_enabled = _flag("MEMORY_SEMANTIC_ENABLED", True)

    def _int_cfg(key: str, default: int) -> int:
        try:
            return max(0, int(str(_cfg.get(key, default))))
        except Exception:
            return default

    long_top = _int_cfg("MEMORY_LONG_TERM_TOP_TAGS", 8)
    semantic_top = _int_cfg("MEMORY_SEMANTIC_TOP_FACTS", 8)

    lines: list[str] = []
    if short_enabled:
        high_freq = ", ".join([str(x) for x in (memory_data.get("high_freq_tags") or [])[:12]]) or "暂无"
        dislike = ", ".join([str(x) for x in (memory_data.get("dislike_tags") or [])[:12]]) or "暂无"
        lines.append(f"- 短期交互高频Tag：{high_freq}")
        lines.append(f"- 短期过滤(Dislike)Tag：{dislike}")
    if long_enabled:
        long_tags = (memory_data.get("long_term_tags") or [])[:long_top]
        long_term = ", ".join(str(x) for x in long_tags) if long_tags else str(memory_data.get("long_term_summary") or "暂无")
        lines.append(f"- 长期阅读偏好：{long_term}")
    if semantic_enabled:
        semantic_facts = (memory_data.get("semantic_facts") or [])[:semantic_top]
        facts_txt = "\n".join([f"  - {str(x)}" for x in semantic_facts]) if semantic_facts else "  - 暂无"
        lines.append(f"- 语义记忆事实：\n{facts_txt}")

    memory_str = "\n".join(lines) if lines else "- (记忆注入已关闭)"

    final_prompt = (
        "【系统指令与人设】\n"
        f"{persona}\n\n"
        "---\n"
        "【系统后台数据：记忆与上下文】\n"
        "(以下为系统自动注入的客观事实，请作为背景参考，切勿向用户暴露数据来源)\n"
        f"{memory_str.strip()}\n\n"
        "---\n"
        "【当前任务】\n"
        f"{str(current_task or '').strip() or '与用户对话并完成请求'}"
    )
    return final_prompt


def _parse_tool_calls(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return dict(obj) if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _to_msg_row(row: dict[str, Any]) -> dict[str, Any]:
    extra = _parse_tool_calls(row.get("tool_calls"))
    role = str(row.get("role") or "user")
    content = str(row.get("content") or "")
    ts = row.get("created_at")
    t_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts or "")
    out = {
        "id": str(row.get("id") or ""),
        "role": role,
        "text": content,
        "time": t_iso,
    }
    if isinstance(extra, dict):
        out.update(extra)
    out["role"] = role
    out["text"] = content
    out["time"] = t_iso
    return out


def load_chat_history(user_id: str, session_id: str, limit: int = 120) -> list[dict[str, Any]]:
    dsn = db_dsn()
    if not dsn:
        return []
    uid = str(user_id or "default_user")
    sid = str(session_id or "default").strip() or "default"
    lim = max(1, min(400, int(limit)))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, content, tool_calls, created_at FROM chat_history "
                "WHERE user_id = %s AND session_id = %s "
                "ORDER BY created_at ASC, id ASC LIMIT %s",
                (uid, sid, lim),
            )
            rows = cur.fetchall() or []
    return [_to_msg_row(dict(r)) for r in rows]


def append_chat_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    extra: dict[str, Any] | None = None,
) -> None:
    dsn = db_dsn()
    if not dsn:
        return
    uid = str(user_id or "default_user")
    sid = str(session_id or "default").strip() or "default"
    r = str(role or "user").strip().lower() or "user"
    if r not in {"user", "assistant", "system", "tool"}:
        r = "user"
    body = json.dumps(extra or {}, ensure_ascii=False)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_history(session_id, user_id, role, content, tool_calls) "
                "VALUES (%s, %s, %s, %s, %s::jsonb)",
                (sid, uid, r, str(content or ""), body),
            )
        conn.commit()


def update_chat_message(user_id: str, session_id: str, index: int, text: str) -> list[dict[str, Any]]:
    dsn = db_dsn()
    if not dsn:
        return []
    uid = str(user_id or "default_user")
    sid = str(session_id or "default").strip() or "default"
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM chat_history WHERE user_id=%s AND session_id=%s "
                "ORDER BY created_at ASC, id ASC",
                (uid, sid),
            )
            rows = cur.fetchall() or []
            ids = [int((r or {}).get("id") or 0) for r in rows]
            idx = int(index)
            if idx < 0 or idx >= len(ids):
                raise ValueError("invalid message index")
            cur.execute("UPDATE chat_history SET content=%s WHERE id=%s", (str(text or ""), ids[idx]))
        conn.commit()
    return load_chat_history(uid, sid)


def delete_chat_message_row(user_id: str, session_id: str, index: int) -> list[dict[str, Any]]:
    dsn = db_dsn()
    if not dsn:
        return []
    uid = str(user_id or "default_user")
    sid = str(session_id or "default").strip() or "default"
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM chat_history WHERE user_id=%s AND session_id=%s "
                "ORDER BY created_at ASC, id ASC",
                (uid, sid),
            )
            rows = cur.fetchall() or []
            ids = [int((r or {}).get("id") or 0) for r in rows]
            idx = int(index)
            if idx < 0 or idx >= len(ids):
                raise ValueError("invalid message index")
            cur.execute("DELETE FROM chat_history WHERE id=%s", (ids[idx],))
        conn.commit()
    return load_chat_history(uid, sid)


def collect_memory_data(user_id: str, query_text: str | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    uid = str(user_id or "default_user")
    high_rows = query_rows(
        "SELECT tag, count(*)::int AS n FROM ("
        "SELECT unnest(e.tags) AS tag "
        "FROM user_interactions ui "
        "JOIN eh_works e ON e.gid = split_part(ui.arcid, ':', 2)::bigint AND e.token = split_part(ui.arcid, ':', 3) "
        "WHERE ui.user_id = %s AND ui.action_type IN ('click','impression') "
        "AND ui.created_at >= (now() - interval '30 days')"
        ") x GROUP BY tag ORDER BY n DESC LIMIT 12",
        (uid,),
    )
    dislike_rows = query_rows(
        "SELECT tag, count(*)::int AS n FROM ("
        "SELECT unnest(e.tags) AS tag "
        "FROM user_interactions ui "
        "JOIN eh_works e ON e.gid = split_part(ui.arcid, ':', 2)::bigint AND e.token = split_part(ui.arcid, ':', 3) "
        "WHERE ui.user_id = %s AND ui.action_type = 'dislike' "
        "AND ui.created_at >= (now() - interval '180 days')"
        ") x GROUP BY tag ORDER BY n DESC LIMIT 12",
        (uid,),
    )
    long_rows = query_rows(
        "SELECT t.tag, count(*)::int AS freq FROM ("
        "SELECT unnest(w.tags) AS tag FROM read_events e JOIN works w ON w.arcid=e.arcid "
        "WHERE e.read_time >= %s"
        ") t GROUP BY t.tag ORDER BY freq DESC LIMIT 10",
        (int(datetime.now().timestamp()) - 120 * 86400,),
    )
    # Semantic memory: use vector similarity search when a query embedding is
    # available; fall back to recency order when it is not (no LLM configured,
    # or embedding failed).
    fact_rows: list[dict[str, Any]] = []
    query_vec: list[float] = []
    if query_text and cfg:
        query_vec = _get_embedding_for_text(query_text.strip(), cfg)
    if query_vec:
        emb_str = "[" + ",".join(str(float(x)) for x in query_vec) + "]"
        fact_rows = query_rows(
            "SELECT fact FROM semantic_memory "
            "WHERE user_id=%s AND embedding IS NOT NULL "
            "ORDER BY embedding <=> %s::vector LIMIT 8",
            (uid, emb_str),
        )
    if not fact_rows:
        # Fallback: recency order (embedding unavailable or no embedded facts yet)
        fact_rows = query_rows(
            "SELECT fact FROM semantic_memory WHERE user_id=%s ORDER BY created_at DESC LIMIT 8",
            (uid,),
        )
    high_tags = [str(r.get("tag") or "").strip() for r in high_rows if str(r.get("tag") or "").strip()]
    dislike_tags = [str(r.get("tag") or "").strip() for r in dislike_rows if str(r.get("tag") or "").strip()]
    long_tags = [str(r.get("tag") or "").strip() for r in long_rows if str(r.get("tag") or "").strip()]
    long_summary = ", ".join(long_tags[:8]) if long_tags else "暂无"
    facts = [str(r.get("fact") or "").strip() for r in fact_rows if str(r.get("fact") or "").strip()]
    return {
        "high_freq_tags": high_tags,
        "dislike_tags": dislike_tags,
        "long_term_tags": long_tags,
        "long_term_summary": long_summary,
        "semantic_facts": facts,
    }


def maybe_store_semantic_fact(user_id: str, text: str, cfg: dict[str, Any] | None = None) -> None:
    q = str(text or "").strip()
    if not q or len(q) < 4 or len(q) > 220:
        return
    if not _PREF_RE.search(q):
        return
    dsn = db_dsn()
    if not dsn:
        return
    uid = str(user_id or "default_user")
    # Compute embedding vector (best-effort, may return [] if provider not configured)
    emb_vec: list[float] = _get_embedding_for_text(q, cfg or {}) if cfg else []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM semantic_memory WHERE user_id=%s AND fact=%s ORDER BY created_at DESC LIMIT 1",
                (uid, q),
            )
            if cur.fetchone():
                return
            if emb_vec:
                emb_str = "[" + ",".join(str(float(x)) for x in emb_vec) + "]"
                cur.execute(
                    "INSERT INTO semantic_memory(user_id, fact, embedding) VALUES (%s, %s, %s::vector)",
                    (uid, q, emb_str),
                )
            else:
                cur.execute("INSERT INTO semantic_memory(user_id, fact) VALUES (%s, %s)", (uid, q))
        conn.commit()


def build_chat_payload(
    *,
    user_id: str,
    session_id: str,
    custom_persona: str,
    current_task: str,
    user_text: str,
    history_limit: int = 12,
    cfg: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    _cfg = cfg or {}
    # Respect MEMORY_SHORT_TERM_LIMIT from config (overrides caller's default)
    try:
        history_limit = max(2, min(60, int(str(_cfg.get("MEMORY_SHORT_TERM_LIMIT", history_limit)))))
    except Exception:
        pass
    short_enabled = str(_cfg.get("MEMORY_SHORT_TERM_ENABLED", True)).strip().lower() not in {"0", "false", ""}
    memory_data = collect_memory_data(user_id, query_text=user_text or None, cfg=_cfg)
    system_prompt = build_system_prompt(custom_persona, current_task, memory_data, _cfg)
    history = load_chat_history(user_id, session_id, limit=max(20, history_limit * 2))
    turns: list[dict[str, str]] = []
    if short_enabled:
        for m in history[-max(2, history_limit * 2) :]:
            role = str(m.get("role") or "")
            text = str(m.get("text") or "")
            if role in {"user", "assistant"} and text:
                turns.append({"role": role, "content": text})
        turns = turns[-history_limit:]
    out = [{"role": "system", "content": system_prompt}, *turns]
    final_user = str(user_text or "").strip()
    if final_user:
        out.append({"role": "user", "content": final_user})
    return out
