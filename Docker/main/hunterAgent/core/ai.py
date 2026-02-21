import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class OpenAICompatClient:
    def __init__(
        self,
        *,
        api_base: str,
        api_key: str = "",
        timeout_s: int = 90,
        max_retries: int = 3,
    ):
        self.api_base = (api_base or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout_s = int(timeout_s)
        self.max_retries = int(max_retries)

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                r = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout_s)
                if r.status_code >= 400:
                    body = r.text
                    if len(body) > 4000:
                        body = body[:4000] + "..."
                    raise RuntimeError(f"HTTP {r.status_code} {url}: {body}")
                return r.json()
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(str(last_err) if last_err else "request failed")

    def chat(
        self,
        *,
        model: str,
        messages: List[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 800,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        if response_format is not None:
            payload["response_format"] = response_format
        obj = self._post("chat/completions", payload)
        choices = obj.get("choices") or []
        if not choices:
            raise RuntimeError("No choices in chat response")
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        # Some servers return list parts.
        if isinstance(content, list):
            parts: List[str] = []
            for p in content:
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    parts.append(p["text"])
            if parts:
                return "\n".join(parts)
        raise RuntimeError("Unexpected chat content")

    def embeddings(self, *, model: str, text: str) -> List[float]:
        payload = {"model": model, "input": text}
        obj = self._post("embeddings", payload)
        data = obj.get("data") or []
        if not data:
            raise RuntimeError("No data in embeddings response")
        emb = data[0].get("embedding")
        if not isinstance(emb, list):
            raise RuntimeError("Embedding is not a list")
        return [float(x) for x in emb]


def extract_json_object(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction.

    Accepts:
    - raw JSON
    - fenced ```json blocks
    - chatty text containing a JSON object
    """

    s = (text or "").strip()
    if not s:
        return {}
    if s.startswith("```"):
        # Strip a single fenced block.
        s2 = s
        if s2.startswith("```json"):
            s2 = s2[len("```json") :]
        elif s2.startswith("```"):
            s2 = s2[len("```") :]
        if s2.endswith("```"):
            s2 = s2[: -len("```")]
        s = s2.strip()
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
        return {}
    except Exception:
        pass

    # Fallback: try to locate first {...} region.
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        chunk = s[start : end + 1]
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return {}
    return {}
