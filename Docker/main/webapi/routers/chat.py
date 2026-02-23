from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from ..core.schemas import ChatMessageDeleteRequest, ChatMessageEditRequest, ChatMessageRequest
from ..services.chat_service import _chat_message_core
from ..services.chat_session_service import delete_chat_message, delete_chat_session, edit_chat_message, get_chat_history, list_chat_sessions
from ..services.chat_stream_service import chat_message_stream_response

router = APIRouter(tags=["chat"])


@router.post("/api/chat/message")
def chat_message(req: ChatMessageRequest, request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return _chat_message_core(
        session_id=str(req.session_id or "default"),
        user_id=str(auth_user.get("uid") or "default_user"),
        text=str(req.text or ""),
        mode=str(req.mode or "chat"),
        intent_raw=str(req.intent or "auto"),
        ui_lang=str(req.ui_lang or "zh"),
        image_arcid=str(req.image_arcid or ""),
    )


@router.post("/api/chat/message/upload")
async def chat_message_upload(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(default="default"),
    text: str = Form(default=""),
    mode: str = Form(default="chat"),
    intent: str = Form(default="auto"),
    ui_lang: str = Form(default="zh"),
) -> dict[str, Any]:
    body = await file.read()
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return _chat_message_core(
        session_id=session_id,
        user_id=str(auth_user.get("uid") or "default_user"),
        text=text,
        mode=mode,
        intent_raw=intent,
        ui_lang=ui_lang,
        uploaded_image=body,
    )


@router.post("/api/chat/stream")
def chat_message_stream(req: ChatMessageRequest, request: Request) -> StreamingResponse:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return chat_message_stream_response(
        session_id=str(req.session_id or "default"),
        text=str(req.text or ""),
        mode=str(req.mode or "chat"),
        intent=str(req.intent or "auto"),
        ui_lang=str(req.ui_lang or "zh"),
        image_arcid=str(req.image_arcid or ""),
        user_id=str(auth_user.get("uid") or "default_user"),
    )


@router.put("/api/chat/message/edit")
def chat_message_edit(req: ChatMessageEditRequest, request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return edit_chat_message(
        user_id=str(auth_user.get("uid") or "default_user"),
        session_id=str(req.session_id or "default"),
        index=int(req.index),
        text=str(req.text or ""),
        regenerate=bool(req.regenerate),
    )


@router.delete("/api/chat/message")
def chat_message_delete(req: ChatMessageDeleteRequest, request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return delete_chat_message(user_id=str(auth_user.get("uid") or "default_user"), session_id=str(req.session_id or "default"), index=int(req.index))


@router.get("/api/chat/history")
def chat_history(request: Request, session_id: str = Query(default="default")) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return get_chat_history(user_id=str(auth_user.get("uid") or "default_user"), session_id=str(session_id or "default"))


@router.get("/api/chat/sessions")
def chat_sessions_list(request: Request) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return list_chat_sessions(user_id=str(auth_user.get("uid") or "default_user"))


@router.delete("/api/chat/session")
def chat_session_delete(request: Request, session_id: str = Query(...)) -> dict[str, Any]:
    auth_user = getattr(request.state, "auth_user", {}) or {}
    return delete_chat_session(user_id=str(auth_user.get("uid") or "default_user"), session_id=str(session_id or ""))
