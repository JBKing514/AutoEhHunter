from typing import Any

from fastapi import HTTPException

from .chat_memory_service import collect_memory_data, delete_chat_message_row, load_chat_history, update_chat_message
from .chat_service import _chat_message_core
from .db_service import db_dsn, query_rows


def list_chat_sessions(*, user_id: str) -> dict[str, Any]:
    uid = str(user_id or "default_user")
    rows = query_rows(
        """
        SELECT session_id,
               max(created_at) AS last_active,
               (SELECT content FROM chat_history c2
                WHERE c2.session_id = c1.session_id AND c2.user_id = %s
                ORDER BY created_at ASC LIMIT 1) AS title
        FROM chat_history c1
        WHERE user_id = %s
        GROUP BY session_id
        ORDER BY last_active DESC LIMIT 30
        """,
        (uid, uid),
    )
    sessions = []
    for r in rows:
        last_active = r.get("last_active")
        sessions.append({
            "session_id": str(r.get("session_id") or ""),
            "last_active": last_active.isoformat() if hasattr(last_active, "isoformat") else str(last_active or ""),
            "title": str(r.get("title") or "New Chat")[:60],
        })
    return {"ok": True, "sessions": sessions}


def delete_chat_session(*, user_id: str, session_id: str) -> dict[str, Any]:
    import psycopg
    uid = str(user_id or "default_user")
    sid = str(session_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="session_id required")
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="db not available")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_history WHERE user_id=%s AND session_id=%s", (uid, sid))
        conn.commit()
    return {"ok": True}


def edit_chat_message(*, user_id: str, session_id: str, index: int, text: str, regenerate: bool) -> dict[str, Any]:
    uid = str(user_id or "default_user")
    sid = str(session_id or "default")
    try:
        history = update_chat_message(uid, sid, int(index), str(text or ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid message index")

    if not bool(regenerate):
        return {"ok": True, "history": history}

    idx = int(index)
    msgs = list(history or [])
    regen_idx = idx
    if idx < 0 or idx >= len(msgs):
        raise HTTPException(status_code=400, detail="invalid message index")
    if str((msgs[idx] or {}).get("role") or "") == "assistant":
        for i in range(idx - 1, -1, -1):
            if str((msgs[i] or {}).get("role") or "") == "user":
                regen_idx = i
                break
    while len(msgs) > regen_idx:
        try:
            msgs = delete_chat_message_row(uid, sid, regen_idx)
        except ValueError:
            break
    user_text = str((history[regen_idx] or {}).get("text") or "") if regen_idx < len(history) else str(text or "")
    res = _chat_message_core(
        session_id=sid,
        user_id=uid,
        text=user_text,
        mode="chat",
        intent_raw="auto",
        ui_lang="zh",
    )
    return {"ok": True, "history": res.get("history") or []}


def delete_chat_message(*, user_id: str, session_id: str, index: int) -> dict[str, Any]:
    uid = str(user_id or "default_user")
    sid = str(session_id or "default")
    try:
        history = delete_chat_message_row(uid, sid, int(index))
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid message index")
    return {"ok": True, "history": history}


def get_chat_history(*, user_id: str, session_id: str) -> dict[str, Any]:
    uid = str(user_id or "default_user")
    sid = str(session_id or "default")
    history = load_chat_history(uid, sid, limit=120)
    mem = collect_memory_data(uid)
    return {
        "session_id": sid,
        "messages": history,
        "facts": list(mem.get("semantic_facts") or []),
    }
