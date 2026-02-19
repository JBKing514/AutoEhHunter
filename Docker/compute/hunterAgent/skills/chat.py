from typing import Any, Dict, List

from hunterAgent.core.ai import ChatMessage, OpenAICompatClient
from hunterAgent.core.config import Settings


def run_chat(*, settings: Settings, llm: OpenAICompatClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    messages_in = payload.get("messages")
    if not isinstance(messages_in, list) or not messages_in:
        # Minimal fallback: wrap a single 'query'
        q = str(payload.get("query") or "").strip()
        if not q:
            return {"reply": ""}
        messages: List[ChatMessage] = [ChatMessage(role="user", content=q)]
    else:
        messages = []
        for m in messages_in:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role") or "").strip() or "user"
            content = str(m.get("content") or "").strip()
            if content:
                messages.append(ChatMessage(role=role, content=content))
        if not messages:
            return {"reply": ""}

    temperature = float(payload.get("temperature") or 0.2)
    max_tokens = int(payload.get("max_tokens") or 1800)
    reply = llm.chat(
        model=str(payload.get("model") or settings.llm_model),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return {"reply": reply}
